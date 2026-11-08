package org.derenguhgram;

import android.content.SharedPreferences;
import org.derenguhgram.proxy.DerenguhLocalBridge;
import org.derenguhgram.proxy.DerenguhProxyConfig;
import org.derenguhgram.proxy.DerenguhProto;
import org.telegram.messenger.ApplicationLoader;
import org.telegram.messenger.FileLog;
import org.telegram.messenger.Utilities;
import org.telegram.utils.proxy.ProxySettings;
import android.util.Base64;

/** Process-wide loopback adapter: native tgnet speaks SOCKS5 to 127.0.0.1. */
public final class DerenguhBridgeManager {
    private static DerenguhLocalBridge bridge;
    private static String signature = "";
    private DerenguhBridgeManager() {}

    public static synchronized int start(ProxySettings s) {
        if (s == null || s.getType() != ProxySettings.Type.DERENGUH || !s.isValid()) return 9;
        try {
            byte[] key = Base64.decode(s.getSecret(), Base64.URL_SAFE | Base64.NO_PADDING | Base64.NO_WRAP);
            String sig = s.getAddress() + ":" + s.getPort() + ":" + s.getUser() + ":" + s.getSecret();
            if (bridge != null && bridge.isRunning() && signature.equals(sig)) return bridge.getLocalPort();
            stop();
            DerenguhProxyConfig cfg = new DerenguhProxyConfig(s.getAddress(), s.getPort(), key, s.getUser(), DerenguhProto.CODEC_ZLIB);
            bridge = new DerenguhLocalBridge(cfg);
            bridge.start();
            signature = sig;
            return bridge.getLocalPort();
        } catch (Throwable t) { FileLog.e(t); stop(); return 9; }
    }

    public static synchronized void stop() {
        if (bridge != null) { try { bridge.stop(); } catch (Throwable ignored) {} }
        bridge = null; signature = "";
    }
    public static synchronized boolean isRunning() { return bridge != null && bridge.isRunning(); }

    public static void applyFromPreferences() {
        SharedPreferences p = ApplicationLoader.applicationContext.getSharedPreferences("mainconfig", 0);
        ProxySettings s = ProxySettings.fromSharedPreferences(p);
        if (p.getBoolean("proxy_enabled", false) && s.isValid() && s.getType() == ProxySettings.Type.DERENGUH) start(s);
        else stop();
    }
}
