"""
Proxy Package - Proxy Management System

Menyediakan:
- Proxy download dari API & Webshare
- Format conversion
- Proxy testing
- Webshare IP authorization
- Main sync orchestration

Entry point: sync_proxies() di core.py
"""

# Re-export main functions untuk backward compatibility
from .core import sync_proxies
from .downloader import download_proxies_from_apis
from .converter import convert_proxylist_to_http, load_and_deduplicate_proxies
from .tester import run_proxy_test
from .webshare import run_webshare_ip_sync

# Re-export constants yang sering dipakai
from .core import (
    PROXYLIST_SOURCE_FILE,
    PROXY_SOURCE_FILE,
    APILIST_SOURCE_FILE,
    FAIL_PROXY_FILE,
    PROXY_BACKUP_FILE,
    WEBSHARE_APIKEYS_FILE
)

__all__ = [
    # Main functions
    'sync_proxies',
    'download_proxies_from_apis',
    'convert_proxylist_to_http',
    'load_and_deduplicate_proxies',
    'run_proxy_test',
    'run_webshare_ip_sync',
    
    # Constants
    'PROXYLIST_SOURCE_FILE',
    'PROXY_SOURCE_FILE',
    'APILIST_SOURCE_FILE',
    'FAIL_PROXY_FILE',
    'PROXY_BACKUP_FILE',
    'WEBSHARE_APIKEYS_FILE'
]
