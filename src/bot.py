#!/usr/bin/env python3

import sys
import logging
import random
import asyncio
import os
import time
from typing import List, Dict
from datetime import datetime, timedelta

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

from .config import (
    TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID,
    validate_config, setup_logging, reload_proxy_pool, ENABLE_WEBSHARE_IP_SYNC,
    APP_NAME, APP_VERSION
)

setup_logging(is_controller=False)
logger = logging.getLogger(__name__)

try:
    from telegram import Update, BotCommand, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton
    from telegram.ext import Application, CommandHandler, ContextTypes, CallbackQueryHandler, MessageHandler, filters
    from telegram.constants import ParseMode
except ImportError:
    logger.critical("Failed to import python-telegram-bot. Install: pip install python-telegram-bot")
    sys.exit(1)

from .services.llm import generate_persona_data, llm_call_options
from .services.telegram import send_persona_to_telegram, send_text_message
from .modules.gmail import generate_dot_tricks, load_gmail_list, add_variation_to_history, get_generated_variations, get_stats
from .modules.proxy import sync_proxies, run_webshare_ip_sync

ALL_PERSONAS = [
    "explorer", "project_starter", "professional", "fullstack_dev", "polymath_dev", "student_learner",
    "forker", "socialite", "open_source_advocate", "issue_reporter", "community_helper",
    "readme_pro", "profile_architect", "ui_ux_designer", "technical_writer_dev", "minimalist_dev", "data_viz_enthusiast",
    "uploader", "backend_dev", "frontend_dev", "mobile_dev_android", "ai_ml_engineer", "data_scientist",
    "config_master", "dotfiles_enthusiast", "cloud_architect_aws", "database_admin", "network_engineer",
    "polyglot_tool_builder", "game_developer", "embedded_systems_dev", "framework_maintainer", "performance_optimizer", "api_designer",
    "ghost", "lurker", "securer", "code_collector", "organization_member",
    "security_researcher", "niche_guy",
]

scheduler = AsyncIOScheduler(timezone="Asia/Jakarta")

async def scheduled_proxy_sync_task():
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

def get_main_keyboard():
    keyboard = [
        [KeyboardButton("🎲 Random"), KeyboardButton("📋 List Persona")],
        [KeyboardButton("📧 Dot Trick"), KeyboardButton("ℹ️ Info")],
        [KeyboardButton("📊 Stats")]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=False)

async def start_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_name = user.first_name if user else "Engineer"
    message = (f"👋 Halo, **{user_name}**!\n\n"
               f"🤖 **GitHub Asset Factory** siap!\n"
               f"Versi: `{APP_VERSION}`\n"
               f"AI Engine: Manual Fallback System\n\n"
               f"Gunakan tombol di bawah atau command:\n"
               f"`/info` - `/stats` - `/sync_proxies` - `/sync_ip`")
    await update.message.reply_text(message, reply_markup=get_main_keyboard(), parse_mode=ParseMode.MARKDOWN)

async def info_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = (f"ℹ️ **{APP_NAME}** ({APP_VERSION})\n\n"
               "Bot ini menghasilkan:\n"
               "• Persona developer (profil realistis)\n"
               "• Aset pendukung (README, code, config)\n"
               "• Variasi Gmail (Dot Trick)\n\n"
               "**Fitur Utama:**\n"
               "✓ Multi-AI Fallback (Gemini, Cohere, OpenRouter, etc.)\n"
               "✓ Proxy Pool + Auto Cooldown\n"
               "✓ Auto Proxy Sync (Mingguan via `/sync_proxies`)\n"
               "✓ Auto Webshare IP Auth (jika aktif via `/sync_ip`)\n\n"
               "Created by: Kyugito666")
    await update.message.reply_text(message, parse_mode=ParseMode.MARKDOWN, reply_markup=get_main_keyboard())

async def stats_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = "📊 **Bot Statistics**\n\n"
    num_options = len(llm_call_options)
    if num_options > 0:
        message += f"**AI Fallback System:**\n• Total Model Options: `{num_options}`\n\n"
    else:
        message += "**AI Fallback System:**\n• `Error: No models loaded!`\n\n"

    from .config import PROXY_POOL
    if PROXY_POOL and PROXY_POOL.proxies:
        active_proxies = len(PROXY_POOL.proxies)
        failed_now = len(PROXY_POOL.failed_proxies)
        message += (f"**Proxy Pool:**\n"
                    f"• Total Loaded: `{active_proxies}`\n"
                    f"• Currently Cooldown: `{failed_now}`\n\n")
    else:
        message += "**Proxy Pool:** `Inactive (No proxies loaded)`\n\n"

    stats_gmail = get_stats()
    message += (f"**Gmail Dot Trick:**\n"
                f"• Emails in `data/gmail.txt`: `{stats_gmail['total_emails_in_file']}`\n"
                f"• Emails in History: `{stats_gmail['emails_with_variations']}`\n"
                f"• Total Variations Generated: `{stats_gmail['total_variations_generated']}`")

    await update.message.reply_text(message, parse_mode=ParseMode.MARKDOWN, reply_markup=get_main_keyboard())

async def trigger_generation(query_or_message, persona_type: str, context: ContextTypes.DEFAULT_TYPE):
    target_chat_id = None
    if isinstance(query_or_message, Update):
        target_message = query_or_message.message
        target_chat_id = target_message.chat_id
    elif hasattr(query_or_message, 'message'):
        target_message = query_or_message.message
        target_chat_id = target_message.chat_id
        try:
            await query_or_message.edit_message_text(
                f"⏳ **Generating: {persona_type.replace('_', ' ').title()}**...",
                parse_mode=ParseMode.MARKDOWN, reply_markup=None)
        except Exception as e:
            logger.warning(f"Failed edit message for persona gen: {e}. Sending new message.")
            await context.bot.send_message(chat_id=target_chat_id,
                text=f"⏳ **Generating: {persona_type.replace('_', ' ').title()}**...", parse_mode=ParseMode.MARKDOWN)
    else:
        logger.error("Cannot trigger persona generation: invalid input type.")
        return

    if not target_chat_id:
        logger.error("Cannot trigger persona generation: could not determine chat_id.")
        return

    if isinstance(query_or_message, Update):
         await target_message.reply_text(f"⏳ Generating: **{persona_type.replace('_', ' ').title()}**...", parse_mode=ParseMode.MARKDOWN)

    context.application.create_task(run_generation_task(target_chat_id, persona_type))

async def run_generation_task(chat_id: int, persona_type: str):
    logger.info(f"Starting persona generation task for '{persona_type}' (Chat ID: {chat_id})...")
    start_time = time.time()
    try:
        data = await asyncio.to_thread(generate_persona_data, persona_type)
        duration = time.time() - start_time
        logger.info(f"Persona generation task for '{persona_type}' finished in {duration:.2f}s.")

        if not data:
            logger.error(f"Persona generation failed for '{persona_type}'. No data returned.")
            await asyncio.to_thread(send_text_message, f"❌ Gagal generate persona '{persona_type}'. Cek log server.", str(chat_id))
        else:
            logger.info(f"Sending persona data for '{persona_type}' to chat {chat_id}...")
            await asyncio.to_thread(send_persona_to_telegram, persona_type, data, str(chat_id))
            logger.info(f"Finished sending persona data for '{persona_type}'.")

    except Exception as e:
        duration = time.time() - start_time
        logger.error(f"Error in run_generation_task for '{persona_type}' ({duration:.2f}s): {e}", exc_info=True)
        await asyncio.to_thread(send_text_message, f"❌ Error fatal saat generate '{persona_type}': {str(e)[:200]}", str(chat_id))

async def dot_trick_handler(update: Update, context: ContextTypes.DEFAULT_TYPE, page: int = 0):
    is_callback = update.callback_query is not None
    target_message = update.callback_query.message if is_callback else update.message
    if not target_message:
        logger.error("dot_trick_handler: Cannot find message object.")
        return

    try:
        all_emails = load_gmail_list()
        if not all_emails:
            await target_message.reply_text("⚠️ `data/gmail.txt` kosong atau tidak ditemukan!", reply_markup=get_main_keyboard())
            return

        items_per_page = 50
        total_pages = (len(all_emails) + items_per_page - 1) // items_per_page
        start_idx = page * items_per_page
        end_idx = min(start_idx + items_per_page, len(all_emails))
        
        current_page_emails = all_emails[start_idx:end_idx]

        keyboard = []
        for i, email in enumerate(current_page_emails):
            actual_index = start_idx + i
            display_email = email if len(email) <= 40 else email[:37] + "..."
            keyboard.append([InlineKeyboardButton(f"📧 {display_email}", callback_data=f"dottrick_{actual_index}")])

        nav_buttons = []
        if page > 0:
            nav_buttons.append(InlineKeyboardButton("⬅️ Prev", callback_data=f"dottrick_page_{page-1}"))
        if page < total_pages - 1:
            nav_buttons.append(InlineKeyboardButton("➡️ Next", callback_data=f"dottrick_page_{page+1}"))
        
        if nav_buttons:
            keyboard.append(nav_buttons)

        keyboard.append([InlineKeyboardButton("📊 Lihat Statistik", callback_data="dottrick_stats")])
        keyboard.append([InlineKeyboardButton("❌ Batal", callback_data="cancel")])
        
        reply_markup = InlineKeyboardMarkup(keyboard)

        message_text = (f"📧 **Gmail Dot Trick**\n"
                       f"Pilih email untuk generate variasi baru:\n\n"
                       f"Halaman {page+1}/{total_pages} (Total: {len(all_emails)} emails)")

        if is_callback:
             await update.callback_query.edit_message_text(message_text, reply_markup=reply_markup, parse_mode=ParseMode.MARKDOWN)
        else:
             await target_message.reply_text(message_text, reply_markup=reply_markup, parse_mode=ParseMode.MARKDOWN)

    except Exception as e:
        logger.error(f"Error in dot_trick_handler: {e}", exc_info=True)
        await target_message.reply_text(f"❌ Error menampilkan daftar email: {str(e)}", reply_markup=get_main_keyboard())

async def trigger_dot_trick_generation(query, index: int, context: ContextTypes.DEFAULT_TYPE):
    if not query or not query.message:
        logger.error("Cannot trigger dot trick: invalid query/message")
        return
    chat_id = str(query.message.chat_id)
    try:
        gmail_list = load_gmail_list()
        if index < 0 or index >= len(gmail_list):
            await query.answer("❌ Index email tidak valid.", show_alert=True)
            await query.edit_message_text("❌ Error: Email tidak ditemukan. Silakan coba lagi.", reply_markup=None)
            return
        email = gmail_list[index]
    except Exception as e:
        logger.error(f"Error getting email for dot trick index {index}: {e}")
        await query.answer("❌ Gagal memproses pilihan.", show_alert=True)
        await query.edit_message_text(f"❌ Error: {str(e)}", reply_markup=None)
        return

    try:
        await query.edit_message_text(f"⏳ Generating variasi untuk:\n`{email}`...", parse_mode=ParseMode.MARKDOWN, reply_markup=None)
    except Exception as e:
        logger.warning(f"Failed edit message for dot trick gen: {e}")
        await context.bot.send_message(chat_id=chat_id, text=f"⏳ Generating variasi untuk:\n`{email}`...", parse_mode=ParseMode.MARKDOWN)

    context.application.create_task(run_dot_trick_task(email=email, chat_id=chat_id))

async def run_dot_trick_task(email: str, chat_id: str):
    logger.info(f"Starting dot trick generation task for '{email}' (Chat ID: {chat_id})...")
    start_time = time.time()
    try:
        existing = await asyncio.to_thread(get_generated_variations, email)
        new_var = await asyncio.to_thread(generate_dot_tricks, email, existing)
        duration = time.time() - start_time
        logger.info(f"Dot trick generation for '{email}' finished in {duration:.3f}s. Result: {'Found' if new_var else 'Not Found/Failed'}")

        if new_var:
            await asyncio.to_thread(add_variation_to_history, email, new_var)
            message = (f"✅ **Variasi Gmail Baru Ditemukan!**\n\n"
                       f"📧 Email Asli:\n`{email}`\n\n"
                       f"✨ Variasi Baru:\n`{new_var}`\n\n"
                       f"_(Variasi ini sudah disimpan ke history)_")
        else:
            username_part = email.split('@')[0].replace('.', '')
            if len(username_part) < 2:
                message = (f"⚠️ **Gagal Generate Variasi**\n\n"
                           f"📧 Email:\n`{email}`\n\n"
                           f"❌ Alasan: Username '{username_part}' terlalu pendek (< 2 karakter) untuk dot trick.")
            else:
                message = (f"⚠️ **Tidak Ditemukan Variasi Baru**\n\n"
                           f"📧 Email:\n`{email}`\n\n"
                           f"❌ Mungkin semua kombinasi sudah pernah digenerate atau gagal setelah beberapa percobaan. Cek log server jika perlu.")

        await asyncio.to_thread(send_text_message, message, chat_id)

    except Exception as e:
        duration = time.time() - start_time
        logger.error(f"Error in run_dot_trick_task for '{email}' ({duration:.2f}s): {e}", exc_info=True)
        await asyncio.to_thread(send_text_message, f"❌ Error fatal saat generate dot trick untuk `{email}`: {str(e)[:200]}", chat_id)

async def show_dot_trick_stats(query):
    if not query:
        return
    try:
        await query.answer()
        stats_gmail = get_stats()
        message = (f"📊 **Statistik Gmail Dot Trick**\n\n"
                   f"• Email di `data/gmail.txt`: `{stats_gmail['total_emails_in_file']}`\n"
                   f"• Email dengan History: `{stats_gmail['emails_with_variations']}`\n"
                   f"• Total Variasi Tersimpan: `{stats_gmail['total_variations_generated']}`")

        keyboard = [[InlineKeyboardButton("🔙 Kembali ke Daftar Email", callback_data="dottrick_backtolist")]]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await query.edit_message_text(message, parse_mode=ParseMode.MARKDOWN, reply_markup=reply_markup)
    except Exception as e:
        logger.error(f"Error showing dot trick stats: {e}", exc_info=True)
        await query.answer("❌ Gagal menampilkan statistik.", show_alert=True)

async def handle_dottrick_backtolist(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not query:
        return
    try:
        await query.answer()
        await query.edit_message_text("🔄 Memuat ulang daftar email...", reply_markup=None)
    except Exception as e:
        logger.warning(f"Minor error editing message on backtolist: {e}")

    await dot_trick_handler(update, context, page=0)

async def handle_text_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        return

    text = update.message.text.strip()

    if text == "🎲 Random":
        persona_type = random.choice(ALL_PERSONAS)
        await trigger_generation(update, persona_type, context)
    elif text == "📋 List Persona":
        buttons = [InlineKeyboardButton(p.replace('_', ' ').title(), callback_data=f"persona_{p}") for p in ALL_PERSONAS]
        n_cols = 2
        keyboard = [buttons[i:i + n_cols] for i in range(0, len(buttons), n_cols)]
        keyboard.append([InlineKeyboardButton("❌ Batal", callback_data="cancel")])
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text("📋 **Pilih Tipe Persona:**", reply_markup=reply_markup, parse_mode=ParseMode.MARKDOWN)
    elif text == "📧 Dot Trick":
        await dot_trick_handler(update, context)
    elif text == "ℹ️ Info":
        await info_handler(update, context)
    elif text == "📊 Stats":
        await stats_handler(update, context)
    else:
        pass

async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not query or not query.data:
        return

    try:
        await query.answer()
    except Exception as e:
        logger.warning(f"Failed to answer callback query (might be expired): {e}")

    data = query.data

    if data == "cancel":
        try:
            await query.edit_message_text("❌ Operasi dibatalkan.", reply_markup=None)
        except Exception:
             if query.message:
                 await query.message.reply_text("❌ Operasi dibatalkan.", reply_markup=get_main_keyboard())
             else:
                 logger.error("Callback 'cancel' failed: No message to reply to/edit.")
    elif data.startswith("dottrick_page_"):
        try:
            page_num = int(data.replace("dottrick_page_", ""))
            await dot_trick_handler(update, context, page=page_num)
        except ValueError:
            logger.error(f"Invalid page number in callback: {data}")
            await query.answer("❌ Halaman tidak valid.", show_alert=True)
    elif data == "random_generate":
        persona_type = random.choice(ALL_PERSONAS)
        await trigger_generation(query, persona_type, context)
    elif data.startswith("persona_"):
        persona_type = data.replace("persona_", "")
        await trigger_generation(query, persona_type, context)
    elif data == "dottrick_stats":
        await show_dot_trick_stats(query)
    elif data.startswith("dottrick_"):
        try:
             index_str = data.replace("dottrick_", "")
             if index_str.isdigit():
                 index = int(index_str)
                 await trigger_dot_trick_generation(query, index, context)
             elif index_str == "backtolist":
                  pass
             else:
                  logger.error(f"Invalid non-numeric index in dottrick callback: {data}")
                  await query.answer("❌ Data callback tidak valid.", show_alert=True)
        except ValueError:
             logger.error(f"Invalid index format in dottrick callback: {data}")
             await query.answer("❌ Format data callback salah.", show_alert=True)
    else:
        logger.warning(f"Unhandled callback data: {data}")
        await query.answer("Aksi tidak dikenali.")

async def sync_proxies_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = str(update.message.chat_id)
    await update.message.reply_text("⏳ Memulai sinkronisasi proxy manual (Download, Test, Update)...", parse_mode=ParseMode.MARKDOWN)
    logger.info(f"Manual proxy sync requested by chat_id {chat_id}.")
    context.application.create_task(run_sync_proxies_task(chat_id))

async def run_sync_proxies_task(chat_id: str):
    start_time = time.time()
    message_prefix = f"Manual Proxy Sync (Chat ID: {chat_id}): "
    try:
        logger.info(message_prefix + "Running sync_proxies...")
        success = await asyncio.to_thread(sync_proxies)
        duration = time.time() - start_time
        if success:
            logger.info(message_prefix + f"OK ({duration:.2f}s). Reloading pool...")
            await asyncio.to_thread(reload_proxy_pool)
            logger.info(message_prefix + "Pool reloaded.")
            await asyncio.to_thread(send_text_message, f"✅ Sync proxy manual OK ({duration:.1f}s) & pool di-reload!", chat_id)
        else:
            logger.error(message_prefix + f"FAILED ({duration:.2f}s). Pool not reloaded.")
            await asyncio.to_thread(send_text_message, f"❌ Sync proxy manual Gagal ({duration:.1f}s). Cek log server.", chat_id)
    except Exception as e:
        duration = time.time() - start_time
        logger.error(message_prefix + f"Error ({duration:.2f}s): {e}", exc_info=True)
        await asyncio.to_thread(send_text_message, f"❌ Error sync proxy ({duration:.1f}s): {str(e)[:100]}. Cek log.", chat_id)

async def sync_webshare_ip_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = str(update.message.chat_id)
    if not ENABLE_WEBSHARE_IP_SYNC:
         await update.message.reply_text("⛔ Fitur Webshare IP Sync tidak diaktifkan di konfigurasi (.env).")
         return
    await update.message.reply_text("⏳ Memulai sinkronisasi IP Webshare manual...", parse_mode=ParseMode.MARKDOWN)
    logger.info(f"Manual Webshare IP sync requested by chat_id {chat_id}.")
    context.application.create_task(run_sync_webshare_ip_task(chat_id))

async def run_sync_webshare_ip_task(chat_id: str):
    start_time = time.time()
    message_prefix = f"Manual Webshare IP Sync (Chat ID: {chat_id}): "
    try:
        logger.info(message_prefix + "Running run_webshare_ip_sync...")
        success = await asyncio.to_thread(run_webshare_ip_sync)
        duration = time.time() - start_time
        if success:
            logger.info(message_prefix + f"OK ({duration:.2f}s).")
            await asyncio.to_thread(send_text_message, f"✅ Sinkronisasi IP Webshare manual Selesai ({duration:.1f}s).", chat_id)
        else:
            logger.error(message_prefix + f"Finished with ERRORS ({duration:.2f}s).")
            await asyncio.to_thread(send_text_message, f"⚠️ Sinkronisasi IP Webshare manual Selesai dengan Error ({duration:.1f}s). Cek log server.", chat_id)
    except Exception as e:
        duration = time.time() - start_time
        logger.error(message_prefix + f"Error ({duration:.2f}s): {e}", exc_info=True)
        await asyncio.to_thread(send_text_message, f"❌ Error fatal saat sync IP ({duration:.1f}s): {str(e)[:100]}. Cek log.", chat_id)

async def setup_bot_commands(app: Application):
    commands = [
        BotCommand("start", "Mulai bot & tampilkan menu"),
        BotCommand("info", "Informasi tentang bot"),
        BotCommand("stats", "Lihat statistik bot"),
        BotCommand("sync_proxies", "Update daftar proxy (Download, Test, Update)"),
        BotCommand("sync_ip", "Update otorisasi IP di Webshare (jika aktif)")
    ]
    if not ENABLE_WEBSHARE_IP_SYNC:
        commands = [cmd for cmd in commands if cmd.command != "sync_ip"]
        logger.info("Command /sync_ip disabled because ENABLE_WEBSHARE_IP_SYNC is false.")

    try:
        await app.bot.set_my_commands(commands)
        logger.info("Bot commands updated successfully.")
    except Exception as e:
        logger.error(f"Failed to set bot commands: {e}")

    logger.info("Initializing background scheduler via post_init...")
    try:
        if not scheduler.running:
            scheduler.add_job(
                scheduled_proxy_sync_task,
                trigger=IntervalTrigger(weeks=1),
                id="weekly_proxy_sync",
                name="Weekly Proxy Sync",
                next_run_time=datetime.now() + timedelta(minutes=1)
            )
            scheduler.start()
            logger.info("✅ Background scheduler started with weekly proxy sync job.")
        else:
            logger.info("Scheduler already running.")
    except Exception as e:
        logger.error(f"❌ Failed to start scheduler: {e}", exc_info=True)

async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    logger.error(f"Update {update} caused error: {context.error}", exc_info=context.error)

def main():
    try:
        logger.info(f"=== {APP_NAME} ({APP_VERSION}) Worker Starting ===")
        validate_config()

        application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

        application.add_handler(CommandHandler("start", start_handler))
        application.add_handler(CommandHandler("info", info_handler))
        application.add_handler(CommandHandler("stats", stats_handler))
        application.add_handler(CommandHandler("sync_proxies", sync_proxies_handler))
        if ENABLE_WEBSHARE_IP_SYNC:
            application.add_handler(CommandHandler("sync_ip", sync_webshare_ip_handler))
        application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text_message))
        application.add_handler(CallbackQueryHandler(handle_dottrick_backtolist, pattern="^dottrick_backtolist$"))
        application.add_handler(CallbackQueryHandler(callback_handler))
        application.add_error_handler(error_handler)

        application.post_init = setup_bot_commands

        logger.info("🚀 Bot worker initialized. Starting polling...")
        application.run_polling(allowed_updates=Update.ALL_TYPES)

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
