"""
APScheduler Setup & Background Tasks

Menangani:
- Weekly proxy sync scheduling
- Bot command setup
- Background tasks orchestration
"""

import logging
import time
import asyncio
from datetime import datetime, timedelta

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from telegram import BotCommand
from telegram.ext import Application

from ..config import ENABLE_WEBSHARE_IP_SYNC, reload_proxy_pool
from ..modules.proxy import sync_proxies, run_webshare_ip_sync

logger = logging.getLogger(__name__)

# Global scheduler instance
scheduler = AsyncIOScheduler(timezone="Asia/Jakarta")


async def scheduled_proxy_sync_task():
    """Task untuk scheduled proxy sync (legacy - simple sync tanpa IP auth)."""
    start_time = time.time()
    logger.info("===== Starting SCHEDULED Proxy Sync =====")
    try:
        success = await asyncio.to_thread(sync_proxies)
        duration = time.time() - start_time
        if success:
            logger.info(f"Scheduled sync OK ({duration:.2f}s). Reloading pool...")
            await asyncio.to_thread(reload_proxy_pool)
            logger.info("Scheduled pool reloaded.")
        else:
            logger.error(f"Scheduled sync FAILED ({duration:.2f}s). Pool not reloaded.")
    except Exception as e:
        duration = time.time() - start_time
        logger.error(f"Error scheduled proxy sync ({duration:.2f}s): {e}", exc_info=True)


async def full_webshare_auto_sync():
    """
    Full automation: IP Auth (jika enabled) + Proxy Sync + Reload Pool.
    
    Digunakan untuk:
    - Weekly scheduled job
    - Manual /full_sync command
    """
    start_time = time.time()
    logger.info("===== Starting FULL Webshare Auto Sync =====")
    
    try:
        # Step 1: IP Authorization (jika enabled)
        if ENABLE_WEBSHARE_IP_SYNC:
            logger.info("Step 1: Syncing IP authorization to all Webshare accounts...")
            ip_sync_success = await asyncio.to_thread(run_webshare_ip_sync)
            if ip_sync_success:
                logger.info("✅ IP authorization synced successfully")
            else:
                logger.warning("⚠️ IP authorization had errors, but continuing...")
        else:
            logger.info("Step 1: IP sync disabled, skipping...")
        
        # Step 2-6: Full Proxy Sync
        logger.info("Step 2-6: Running full proxy sync (download, convert, test, save)...")
        proxy_sync_success = await asyncio.to_thread(sync_proxies)
        
        if proxy_sync_success:
            # Step 7: Reload Pool
            logger.info("Step 7: Reloading proxy pool with new working proxies...")
            await asyncio.to_thread(reload_proxy_pool)
            duration = time.time() - start_time
            logger.info(f"===== Full Webshare Auto Sync COMPLETED in {duration:.1f}s =====")
            return True
        else:
            duration = time.time() - start_time
            logger.error(f"===== Full Webshare Auto Sync FAILED in {duration:.1f}s =====")
            return False
            
    except Exception as e:
        duration = time.time() - start_time
        logger.error(f"===== Full Webshare Auto Sync ERROR ({duration:.1f}s): {e} =====", exc_info=True)
        return False


async def setup_bot_commands(app: Application):
    """
    Setup bot commands di Telegram & initialize background scheduler.
    
    Dipanggil via Application.post_init
    """
    # Setup Telegram bot commands
    commands = [
        BotCommand("start", "Mulai bot & tampilkan menu"),
        BotCommand("info", "Informasi tentang bot"),
        BotCommand("stats", "Lihat statistik bot"),
        BotCommand("sync_proxies", "Update daftar proxy (Download, Test, Update)"),
        BotCommand("sync_ip", "Update otorisasi IP di Webshare (jika aktif)"),
        BotCommand("full_sync", "Full Auto Sync (IP Auth + Proxy Download)")
    ]
    
    # Remove /sync_ip command jika feature disabled
    if not ENABLE_WEBSHARE_IP_SYNC:
        commands = [cmd for cmd in commands if cmd.command != "sync_ip"]
        logger.info("Command /sync_ip disabled because ENABLE_WEBSHARE_IP_SYNC is false.")

    try:
        await app.bot.set_my_commands(commands)
        logger.info("Bot commands updated successfully.")
    except Exception as e:
        logger.error(f"Failed to set bot commands: {e}")

    # Initialize background scheduler
    logger.info("Initializing background scheduler with FULL automation...")
    try:
        if not scheduler.running:
            scheduler.add_job(
                full_webshare_auto_sync,
                trigger=IntervalTrigger(weeks=1),
                id="weekly_full_sync",
                name="Weekly Full Webshare Auto Sync",
                next_run_time=datetime.now() + timedelta(seconds=30)  # First run in 30s
            )
            scheduler.start()
            logger.info("✅ Background scheduler started with WEEKLY FULL AUTO SYNC job.")
            logger.info("   → First run in 30 seconds, then weekly")
        else:
            logger.info("Scheduler already running.")
    except Exception as e:
        logger.error(f"❌ Failed to start scheduler: {e}", exc_info=True)
