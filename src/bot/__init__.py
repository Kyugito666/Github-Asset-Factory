"""
Bot Package - GitHub Asset Factory Bot

Entry point untuk bot worker dengan backward compatibility.
Mendukung: python -m src.bot
"""

# Re-export main function untuk backward compatibility
from .main import main

# Re-export handlers untuk internal use
from .handlers import (
    start_handler,
    info_handler,
    stats_handler,
    sync_proxies_handler,
    sync_webshare_ip_handler,
    full_sync_handler,
    handle_text_message,
    show_proxy_menu,
    trigger_ip_auth,
    trigger_download_proxy,
    trigger_convert_proxy,
    trigger_test_proxy,
    trigger_full_auto_sync
)

from .callbacks import (
    callback_handler,
    handle_dottrick_backtolist
)

from .scheduler import (
    setup_bot_commands,
    scheduled_proxy_sync_task,
    full_webshare_auto_sync
)

from .keyboards import (
    get_main_keyboard,
    get_proxy_menu_keyboard
)

__all__ = [
    'main',
    'start_handler',
    'info_handler',
    'stats_handler',
    'sync_proxies_handler',
    'sync_webshare_ip_handler',
    'full_sync_handler',
    'handle_text_message',
    'callback_handler',
    'handle_dottrick_backtolist',
    'setup_bot_commands',
    'get_main_keyboard',
    'get_proxy_menu_keyboard'
]
