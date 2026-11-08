# DerenguhProto v1 — wire specification

This is the authoritative contract between **DerenguhGram-Client** and
**DerenguhGram-Proxy**. The C++ (tdesktop) and Kotlin (Android) transports MUST match
it byte-for-byte. The Python `reference_client.py` is an executable copy.

## 0. Shared secret

- 16 random bytes. Used **only** as the HMAC-SHA256 key for the Fake-TLS handshake.
- In the link: `key = base64url(secret)` without `=` padding.
- In server config: 32-char hex **or** base64url.
- It is independent of the MTProto auth key and of the obfuscated-2 keys. The proxy
  never sees MTProto plaintext.

## 1. Layering

```
TCP
└── Fake-TLS 1.3 records (type 0x17 application_data, legacy_version 0x0303)
    └── flushed compression blocks (zlib stream, Z_SYNC_FLUSH per block)
        └── obfuscated-2 MTProto byte stream for the chosen DC (opaque to proxy)
```

The proxy is a **transport tunnel**: it strips Fake-TLS + compression and forwards the
raw obfuscated-2 bytes to the Telegram DC. Obfuscated-2 encryption stays end-to-end
between client and Telegram.

## 2. Fake-TLS handshake

Byte-compatible with `alexbers/mtprotoproxy` Fake-TLS.

### ClientHello (client → server)
- A TLS record `16 03 01 <len:2>` wrapping a handshake `01 <len:3>` ClientHello.
- `legacy_version = 03 03`, then a 32-byte `random` field at **offset 11** of the record.
- `session_id` (32 bytes), cipher suites, compression `00`, extensions including
  `server_name` (the chosen SNI), `supported_versions` (TLS 1.3), `key_share` (x25519).
- Handshake length SHOULD be ≥ 512 bytes (pad with extension `0x0015` if needed).
- **Digest**: let `msg` = the whole record with the 32 random bytes zeroed.
  `H = HMAC_SHA256(secret, msg)`. Set
  `random[0:28] = H[0:28]`, `random[28:32] = H[28:32] XOR le32(unix_time)`.

### ServerHello (server → client)
- `build_server_hello`: ServerHello record (`16 03 03`) echoing the session_id,
  cipher `13 01`, key_share + supported_versions extensions; then a ChangeCipherSpec
  record (`14 03 03 00 01 01`); then one application_data record of random "certificate"
  bytes (1024–4096). No real certificate.
- **Digest**: with the ServerHello random zeroed,
  `H2 = HMAC_SHA256(secret, client_random || hello_pkt)`, placed at offset 11.
- The client verifies `H2` before proceeding.

### Authentication / anti-replay (server)
- Recompute `H`, XOR with the received random; first 28 bytes must be zero.
- Last 4 bytes = `le32(timestamp)`; accept if `−20min < now − ts < +10min`
  (or `ts < 1000 days` to tolerate uptime-based clocks, or if configured to ignore skew).
- On failure → **TCP Splice** (§6), never a ServerHello.

## 3. Control frame (first application_data payload)

Client sends exactly one 8-byte frame:

| offset | size | field | value |
|---|---|---|---|
| 0 | 2 | magic | `0x44 0x47` ("DG") |
| 2 | 1 | version | `0x01` |
| 3 | 1 | codec | `0`=none, `1`=zlib, `2`=brotli (requested) |
| 4 | 1 | dc_index | `1..5` (Telegram DC) |
| 5 | 1 | flags | reserved, `0` |
| 6 | 2 | reserved | `0x0000` |

Server replies with one 8-byte ack:

| offset | size | field | value |
|---|---|---|---|
| 0 | 2 | magic | "DG" |
| 2 | 1 | version | `0x01` |
| 3 | 1 | codec | negotiated codec (may downgrade brotli→zlib) |
| 4 | 1 | status | `0`=OK, `1`=DC unreachable, `2`=unsupported codec, `3`=proto error, `4`=forbidden DC |
| 5 | 1 | flags | `0` |
| 6 | 2 | reserved | `0x0000` |

The server dials the fixed DC address for `dc_index` (IPv4 unless `PREFER_IPV6`).
On `status != 0` the client must abort. Both directions then use the **negotiated**
codec.

## 4. Data records

Every subsequent application_data record payload is one flushed compression block:

- **zlib**: a single persistent deflate stream per direction.
  `block = compressobj.compress(chunk) + compressobj.flush(Z_SYNC_FLUSH)`.
  The receiver feeds each block to one persistent `decompressobj`.
  - Server compressor uses a 4 KB window (`wbits=12`, `memLevel=5`) to save RAM.
  - Decompressors use `MAX_WBITS=15` and accept any window ≤ 15 from the header, so
    Java `Inflater`/`Deflater` (window 15) and C++ zlib interoperate without changes.
- **brotli**: persistent `Compressor.process()+flush()` / `Decompressor.process()`.
- **none**: payload is the raw chunk.

A block may span multiple TLS records (the decompressor accumulates); a record may
also contain a block that decompresses to zero bytes (skip it). Max record payload
emitted: `16384+24`; max accepted: `16384+512`.

> **Compression caveat:** obfuscated-2 is AES-CTR ciphertext (high entropy), so zlib
> gains on the payload are small. The codec mainly normalises framing and lets low-CPU
> devices select `none`. For large savings, compress MTProto payloads *before*
> obfuscation (a deeper client change, out of scope for v1).

## 5. Relay

Bidirectional, bounded memory: client→DC reads one record, decompresses, writes raw;
DC→client reads ≤ 8192 bytes, compresses, writes one record. `drain()` after each write
for backpressure. Idle timeout closes the connection.

## 6. TCP Splice (unrecognised peers)

If the first record is not an authenticated ClientHello, the proxy opens a TCP
connection to the **real** host: the SNI's resolved IP if it is in the allowlist,
else `MASK_HOST`. It replays the bytes already read and pipes both directions
verbatim. The probe receives a genuine TLS response from the streaming service.
This is a userspace splice (no root, no kernel `splice(2)`).

## 7. Connection link

```
derenguh://proxy?server=<host>&port=<port>&sni=<sni>&key=<base64url_secret>
```

`server` host, `port` int, `sni` ∈ allowlist, `key` = base64url(16-byte secret).
