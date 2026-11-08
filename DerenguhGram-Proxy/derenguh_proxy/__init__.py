"""DerenguhGram-Proxy: Fake-TLS, compressing MTProto transport proxy.

Public API:
    from derenguh_proxy import Config, Server, build_link
"""
from .config import Config
from .server import Server
from .link import build_link, parse_link, generate_secret, secret_to_key, key_to_secret

__version__ = "1.0.0"
__all__ = ["Config", "Server", "build_link", "parse_link",
           "generate_secret", "secret_to_key", "key_to_secret", "__version__"]
