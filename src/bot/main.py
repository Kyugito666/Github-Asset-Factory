#!/usr/bin/env python3
"""
Main Entry Point - GitHub Asset Factory Bot

Inisialisasi bot, register handlers, dan run polling.
"""

import sys
import logging

from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters

from ..config import (
    TELEGRAM_BOT_TOKEN, 
    validate_config, 
    setup_logging, 
    ENABLE_WEBSHARE_IP_SYNC,
    APP_NAME, 
    APP_VERSION
)

# Setup logging untuk bot worker
setup_logging(is_controller=False)
logger = logging.getLogger(__name__)

# Import handlers
from .handlers import (
    start_handler,
    info_handler,
    stats_handler,
    sync_proxies_handler,
    sync_webshare_ip_handler,
    full_sync_handler,
    handle_text_message
)

from .callbacks import (
    callback_handler,
    handle_dottrick_backtolist
)

from .scheduler import setup_bot_commands, scheduler


async def error_handler(update: object, context):
    """Global error handler untuk menangkap semua error di bot."""
    logger.error(f"Update {update} caused error: {context.error}", exc_info=context.error)


def main():
    """
    Main function - Entry point untuk bot worker.
    
    Dipanggil dari:
    - python -m src.bot (systemd)
    - TUI subprocess
    - Manual execution
    """
    try:
        logger.info(f"=== {APP_NAME} ({APP_VERSION}) Worker Starting ===")
        
        # Validate configuration
        validate_config()

        # Build application
        application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

        # Register command handlers
        application.add_handler(CommandHandler("start", start_handler))
        application.add_handler(CommandHandler("info", info_handler))
        application.add_handler(CommandHandler("stats", stats_handler))
        application.add_handler(CommandHandler("sync_proxies", sync_proxies_handler))
        
        # Conditional: /sync_ip command
        if ENABLE_WEBSHARE_IP_SYNC:
            application.add_handler(CommandHandler("sync_ip", sync_webshare_ip_handler))
        
        application.add_handler(CommandHandler("full_sync", full_sync_handler))

        # Register message handler (untuk keyboard buttons)
        application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text_message))

        # Register callback handlers
        application.add_handler(CallbackQueryHandler(handle_dottrick_backtolist, 
                                                     pattern="^dottrick_backtolist$"))
        application.add_handler(CallbackQueryHandler(callback_handler))

        # Register error handler
        application.add_error_handler(error_handler)

        # Setup bot commands & scheduler (dipanggil setelah bot ready)
        application.post_init = setup_bot_commands

        # Start polling
        logger.info("🚀 Bot worker initialized. Starting polling...")
        application.run_polling(allowed_updates=Update.ALL_TYPES)

        # Cleanup scheduler saat bot stop
        logger.info("Polling stopped. Shutting down scheduler...")
        if scheduler.running:
            scheduler.shutdown()

    except (KeyboardInterrupt, SystemExit):
         logger.info("Bot stopped manually. Shutting down scheduler...")
         if scheduler.running:
             scheduler.shutdown()
         logger.info("Exiting.")

    except Exception as e:
        logger.critical(f"💥 FATAL ERROR in Bot Worker: {e}", exc_info=True)
        if scheduler.running:
            scheduler.shutdown()
        sys.exit(1)


if __name__ == "__main__":
    main()
