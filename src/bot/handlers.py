"""
Telegram Bot Command & Message Handlers

FIXED: 
- run_full_auto_sync_task → run_full_sync_task (line 302)
- Import full_webshare_auto_sync dari scheduler
"""

import logging
import random
import asyncio
import time

from telegram import Update
from telegram.ext import ContextTypes
from telegram.constants import ParseMode

from ..config import (
    TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, ENABLE_WEBSHARE_IP_SYNC,
    APP_NAME, APP_VERSION, PROXY_POOL, reload_proxy_pool
)
from ..services.llm import generate_persona_data, llm_call_options
from ..services.telegram import send_persona_to_telegram, send_text_message
from ..modules.gmail import get_stats
from ..modules.proxy import sync_proxies, run_webshare_ip_sync

from .keyboards import get_main_keyboard, get_proxy_menu_keyboard
from .scheduler import full_webshare_auto_sync

logger = logging.getLogger(__name__)

ALL_PERSONAS = [
    "explorer", "project_starter", "professional", "fullstack_dev", "polymath_dev", "student_learner",
    "forker", "socialite", "open_source_advocate", "issue_reporter", "community_helper",
    "readme_pro", "profile_architect", "ui_ux_designer", "technical_writer_dev", "minimalist_dev", 
    "data_viz_enthusiast", "uploader", "backend_dev", "frontend_dev", "mobile_dev_android", 
    "ai_ml_engineer", "data_scientist", "config_master", "dotfiles_enthusiast", "cloud_architect_aws", 
    "database_admin", "network_engineer", "polyglot_tool_builder", "game_developer", 
    "embedded_systems_dev", "framework_maintainer", "performance_optimizer", "api_designer",
    "ghost", "lurker", "securer", "code_collector", "organization_member",
    "security_researcher", "niche_guy",
]


# ============================================================
# COMMAND HANDLERS
# ============================================================
from ..services.llm.caller import _provider_cooldown, _model_cooldown, COOLDOWN_DURATION

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

    current_time = time.time()
    active_provider_cooldowns = sum(1 for timestamp in _provider_cooldown.values() 
                                     if COOLDOWN_DURATION - (current_time - timestamp) > 0)
    active_model_cooldowns = sum(1 for timestamp in _model_cooldown.values() 
                                  if COOLDOWN_DURATION - (current_time - timestamp) > 0)
    
    if active_provider_cooldowns > 0 or active_model_cooldowns > 0:
        message += (f"**AI Cooldowns (1h):**\n"
                    f"• Provider Cooldowns: `{active_provider_cooldowns}`\n"
                    f"• Model Cooldowns: `{active_model_cooldowns}`\n\n")

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


async def sync_proxies_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = str(update.message.chat_id)
    await update.message.reply_text("⏳ Memulai sinkronisasi proxy manual (Download, Test, Update)...", 
                                    parse_mode=ParseMode.MARKDOWN)
    logger.info(f"Manual proxy sync requested by chat_id {chat_id}.")
    context.application.create_task(run_sync_proxies_task(chat_id))


async def sync_webshare_ip_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = str(update.message.chat_id)
    if not ENABLE_WEBSHARE_IP_SYNC:
         await update.message.reply_text("⛔ Fitur Webshare IP Sync tidak diaktifkan di konfigurasi (.env).")
         return
    await update.message.reply_text("⏳ Memulai sinkronisasi IP Webshare manual...", parse_mode=ParseMode.MARKDOWN)
    logger.info(f"Manual Webshare IP sync requested by chat_id {chat_id}.")
    context.application.create_task(run_sync_webshare_ip_task(chat_id))


async def full_sync_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = str(update.message.chat_id)
    await update.message.reply_text(
        "⏳ Memulai **FULL AUTO SYNC**...\n\n"
        "1️⃣ IP Authorization\n"
        "2️⃣ Proxy Download\n"
        "3️⃣ Format Conversion\n"
        "4️⃣ Proxy Testing\n"
        "5️⃣ Save & Reload Pool\n\n"
        "_Proses mungkin memakan waktu 1-3 menit..._",
        parse_mode=ParseMode.MARKDOWN
    )
    logger.info(f"Manual full sync requested by chat_id {chat_id}.")
    context.application.create_task(run_full_sync_task(chat_id))


# ============================================================
# TEXT MESSAGE HANDLER
# ============================================================

async def handle_text_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        return

    text = update.message.text.strip()

    from .callbacks import dot_trick_handler

    if text == "🎲 Random":
        persona_type = random.choice(ALL_PERSONAS)
        await trigger_generation(update, persona_type, context)
    elif text == "📋 List Persona":
        from telegram import InlineKeyboardButton, InlineKeyboardMarkup
        buttons = [InlineKeyboardButton(p.replace('_', ' ').title(), callback_data=f"persona_{p}") 
                   for p in ALL_PERSONAS]
        n_cols = 2
        keyboard = [buttons[i:i + n_cols] for i in range(0, len(buttons), n_cols)]
        keyboard.append([InlineKeyboardButton("❌ Batal", callback_data="cancel")])
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text("📋 **Pilih Tipe Persona:**", reply_markup=reply_markup, 
                                        parse_mode=ParseMode.MARKDOWN)
    elif text == "📧 Dot Trick":
        await dot_trick_handler(update, context)
    elif text == "ℹ️ Info":
        await info_handler(update, context)
    elif text == "📊 Stats":
        await stats_handler(update, context)
    elif text == "🔧 Proxy Menu":
        await show_proxy_menu(update, context)
    elif text == "🔙 Back to Main":
        await update.message.reply_text("🔙 Kembali ke menu utama", reply_markup=get_main_keyboard())
    elif text == "🌐 IP Auth":
        await trigger_ip_auth(update, context)
    elif text == "⬇️ Download Proxy":
        await trigger_download_proxy(update, context)
    elif text == "🔄 Convert Format":
        await trigger_convert_proxy(update, context)
    elif text == "✅ Test Proxy":
        await trigger_test_proxy(update, context)
    elif text == "🚀 Full Auto Sync":
        await trigger_full_auto_sync(update, context)


# ============================================================
# PROXY MENU OPERATIONS
# ============================================================

async def show_proxy_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = (
        "🔧 **Proxy Management Menu**\n\n"
        "Pilih operasi yang ingin dijalankan:\n\n"
        "🌐 **IP Auth** - Sync IP ke Webshare\n"
        "⬇️ **Download** - Download dari API\n"
        "🔄 **Convert** - Format proxy list\n"
        "✅ **Test** - Test proxy validity\n"
        "🚀 **Full Auto** - Semua step otomatis"
    )
    await update.message.reply_text(message, reply_markup=get_proxy_menu_keyboard(), 
                                    parse_mode=ParseMode.MARKDOWN)


async def trigger_ip_auth(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = str(update.message.chat_id)
    if not ENABLE_WEBSHARE_IP_SYNC:
        await update.message.reply_text("⛔ Fitur IP Auth tidak aktif di konfigurasi.")
        return
    await update.message.reply_text("🌐 **Memulai IP Authorization Sync...**", parse_mode=ParseMode.MARKDOWN)
    context.application.create_task(run_ip_auth_task(chat_id))


async def trigger_download_proxy(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = str(update.message.chat_id)
    await update.message.reply_text("⬇️ **Memulai Download Proxy...**", parse_mode=ParseMode.MARKDOWN)
    context.application.create_task(run_download_proxy_task(chat_id))


async def trigger_convert_proxy(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = str(update.message.chat_id)
    await update.message.reply_text("🔄 **Memulai Convert Format...**", parse_mode=ParseMode.MARKDOWN)
    context.application.create_task(run_convert_proxy_task(chat_id))


async def trigger_test_proxy(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = str(update.message.chat_id)
    await update.message.reply_text("✅ **Memulai Test Proxy...**", parse_mode=ParseMode.MARKDOWN)
    context.application.create_task(run_test_proxy_task(chat_id))


async def trigger_full_auto_sync(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """FIXED: Gunakan run_full_sync_task (bukan run_full_auto_sync_task)"""
    chat_id = str(update.message.chat_id)
    await update.message.reply_text(
        "🚀 **Memulai Full Auto Sync...**\n\n"
        "Proses:\n"
        "1️⃣ IP Authorization\n"
        "2️⃣ Download Proxy\n"
        "3️⃣ Convert Format\n"
        "4️⃣ Test Proxy\n"
        "5️⃣ Save & Reload Pool\n\n"
        "_Harap tunggu 1-3 menit..._",
        parse_mode=ParseMode.MARKDOWN
    )
    context.application.create_task(run_full_sync_task(chat_id))


# ============================================================
# GENERATION TRIGGER
# ============================================================

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
                text=f"⏳ **Generating: {persona_type.replace('_', ' ').title()}**...", 
                parse_mode=ParseMode.MARKDOWN)
    else:
        logger.error("Cannot trigger persona generation: invalid input type.")
        return

    if not target_chat_id:
        logger.error("Cannot trigger persona generation: could not determine chat_id.")
        return

    if isinstance(query_or_message, Update):
         await target_message.reply_text(f"⏳ Generating: **{persona_type.replace('_', ' ').title()}**...", 
                                         parse_mode=ParseMode.MARKDOWN)

    context.application.create_task(run_generation_task(target_chat_id, persona_type))


# ============================================================
# BACKGROUND TASK RUNNERS
# ============================================================

async def run_generation_task(chat_id: int, persona_type: str):
    logger.info(f"Starting persona generation task for '{persona_type}' (Chat ID: {chat_id})...")
    start_time = time.time()
    try:
        data = await asyncio.to_thread(generate_persona_data, persona_type)
        duration = time.time() - start_time
        logger.info(f"Persona generation task for '{persona_type}' finished in {duration:.2f}s.")

        if not data:
            logger.error(f"Persona generation failed for '{persona_type}'. No data returned.")
            await asyncio.to_thread(send_text_message, 
                f"❌ Gagal generate persona '{persona_type}'. Cek log server.", str(chat_id))
        else:
            logger.info(f"Sending persona data for '{persona_type}' to chat {chat_id}...")
            await asyncio.to_thread(send_persona_to_telegram, persona_type, data, str(chat_id))
            logger.info(f"Finished sending persona data for '{persona_type}'.")

    except Exception as e:
        duration = time.time() - start_time
        logger.error(f"Error in run_generation_task for '{persona_type}' ({duration:.2f}s): {e}", exc_info=True)
        await asyncio.to_thread(send_text_message, 
            f"❌ Error fatal saat generate '{persona_type}': {str(e)[:200]}", str(chat_id))


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
            await asyncio.to_thread(send_text_message, 
                f"✅ Sync proxy manual OK ({duration:.1f}s) & pool di-reload!", chat_id)
        else:
            logger.error(message_prefix + f"FAILED ({duration:.2f}s). Pool not reloaded.")
            await asyncio.to_thread(send_text_message, 
                f"❌ Sync proxy manual Gagal ({duration:.1f}s). Cek log server.", chat_id)
    except Exception as e:
        duration = time.time() - start_time
        logger.error(message_prefix + f"Error ({duration:.2f}s): {e}", exc_info=True)
        await asyncio.to_thread(send_text_message, 
            f"❌ Error sync proxy ({duration:.1f}s): {str(e)[:100]}. Cek log.", chat_id)


async def run_sync_webshare_ip_task(chat_id: str):
    start_time = time.time()
    message_prefix = f"Manual Webshare IP Sync (Chat ID: {chat_id}): "
    try:
        logger.info(message_prefix + "Running run_webshare_ip_sync...")
        success = await asyncio.to_thread(run_webshare_ip_sync)
        duration = time.time() - start_time
        if success:
            logger.info(message_prefix + f"OK ({duration:.2f}s).")
            await asyncio.to_thread(send_text_message, 
                f"✅ Sync IP Webshare manual OK ({duration:.1f}s)!", chat_id)
        else:
            logger.error(message_prefix + f"FAILED ({duration:.2f}s).")
            await asyncio.to_thread(send_text_message, 
                f"⚠️ Sync IP Webshare manual ada error ({duration:.1f}s). Cek log server.", chat_id)
    except Exception as e:
        duration = time.time() - start_time
        logger.error(message_prefix + f"Error ({duration:.2f}s): {e}", exc_info=True)
        await asyncio.to_thread(send_text_message, 
            f"❌ Error sync IP Webshare ({duration:.1f}s): {str(e)[:100]}. Cek log.", chat_id)


async def run_full_sync_task(chat_id: str):
    """FIXED: Nama fungsi sesuai dengan yang dipanggil"""
    start_time = time.time()
    message_prefix = f"Manual Full Sync (Chat ID: {chat_id}): "
    try:
        logger.info(message_prefix + "Running full_webshare_auto_sync...")
        success = await full_webshare_auto_sync()
        duration = time.time() - start_time
        
        if success:
            logger.info(message_prefix + f"OK ({duration:.2f}s).")
            proxy_count = len(PROXY_POOL.proxies) if PROXY_POOL and PROXY_POOL.proxies else 0
            
            message = (f"✅ **FULL AUTO SYNC Berhasil!**\n\n"
                      f"⏱ Durasi: `{duration:.1f}s`\n"
                      f"📊 Working Proxies: `{proxy_count}`\n"
                      f"🔄 Pool Status: `Active`\n\n"
                      f"_Sistem siap digunakan dengan proxy baru._")
            await asyncio.to_thread(send_text_message, message, chat_id)
        else:
            logger.error(message_prefix + f"FAILED ({duration:.2f}s).")
            message = (f"⚠️ **FULL AUTO SYNC Gagal**\n\n"
                      f"⏱ Durasi: `{duration:.1f}s`\n\n"
                      f"❌ Cek log server untuk detail error.\n"
                      f"_Bot mungkin masih bisa jalan dengan proxy lama (jika ada)._")
            await asyncio.to_thread(send_text_message, message, chat_id)
            
    except Exception as e:
        duration = time.time() - start_time
        logger.error(message_prefix + f"Error ({duration:.2f}s): {e}", exc_info=True)
        await asyncio.to_thread(send_text_message, 
            f"❌ Error fatal saat full sync ({duration:.1f}s): {str(e)[:150]}. Cek log.", chat_id)


async def run_ip_auth_task(chat_id: str):
    start_time = time.time()
    try:
        success = await asyncio.to_thread(run_webshare_ip_sync)
        duration = time.time() - start_time
        if success:
            await asyncio.to_thread(send_text_message, f"✅ IP Auth selesai ({duration:.1f}s)", chat_id)
        else:
            await asyncio.to_thread(send_text_message, 
                f"⚠️ IP Auth ada error ({duration:.1f}s). Cek log.", chat_id)
    except Exception as e:
        duration = time.time() - start_time
        await asyncio.to_thread(send_text_message, 
            f"❌ Error IP Auth ({duration:.1f}s): {str(e)[:100]}", chat_id)


async def run_download_proxy_task(chat_id: str):
    start_time = time.time()
    try:
        from ..modules.proxy import download_proxies_from_apis
        proxies = await asyncio.to_thread(download_proxies_from_apis)
        duration = time.time() - start_time
        if proxies:
            await asyncio.to_thread(send_text_message, 
                f"✅ Download selesai ({duration:.1f}s)\n📦 {len(proxies)} proxy", chat_id)
        else:
            await asyncio.to_thread(send_text_message, 
                f"⚠️ Download gagal/kosong ({duration:.1f}s)", chat_id)
    except Exception as e:
        duration = time.time() - start_time
        await asyncio.to_thread(send_text_message, 
            f"❌ Error Download ({duration:.1f}s): {str(e)[:100]}", chat_id)


async def run_convert_proxy_task(chat_id: str):
    start_time = time.time()
    try:
        from ..modules.proxy import convert_proxylist_to_http, PROXYLIST_SOURCE_FILE, PROXY_SOURCE_FILE
        import os
        if not os.path.exists(PROXYLIST_SOURCE_FILE):
            await asyncio.to_thread(send_text_message, "⚠️ File proxylist.txt tidak ada", chat_id)
            return
        success = await asyncio.to_thread(convert_proxylist_to_http, PROXYLIST_SOURCE_FILE, PROXY_SOURCE_FILE)
        duration = time.time() - start_time
        if success:
            await asyncio.to_thread(send_text_message, f"✅ Convert selesai ({duration:.1f}s)", chat_id)
        else:
            await asyncio.to_thread(send_text_message, f"❌ Convert gagal ({duration:.1f}s)", chat_id)
    except Exception as e:
        duration = time.time() - start_time
        await asyncio.to_thread(send_text_message, 
            f"❌ Error Convert ({duration:.1f}s): {str(e)[:100]}", chat_id)


async def run_test_proxy_task(chat_id: str):
    start_time = time.time()
    try:
        from ..modules.proxy import run_proxy_test, load_and_deduplicate_proxies, PROXY_SOURCE_FILE
        proxies = await asyncio.to_thread(load_and_deduplicate_proxies, PROXY_SOURCE_FILE)
        if not proxies:
            await asyncio.to_thread(send_text_message, "⚠️ Tidak ada proxy untuk di-test", chat_id)
            return
        await asyncio.to_thread(send_text_message, f"🔍 Testing {len(proxies)} proxy...", chat_id)
        good = await asyncio.to_thread(run_proxy_test, proxies)
        duration = time.time() - start_time
        success_rate = (len(good) / len(proxies) * 100) if proxies else 0
        message = (
            f"✅ **Test Selesai** ({duration:.1f}s)\n\n"
            f"📊 Total: `{len(proxies)}`\n"
            f"✔️ Valid: `{len(good)}` ({success_rate:.1f}%)\n"
            f"❌ Gagal: `{len(proxies) - len(good)}`"
        )
        await asyncio.to_thread(send_text_message, message, chat_id)
    except Exception as e:
        duration = time.time() - start_time
        await asyncio.to_thread(send_text_message, 
            f"❌ Error Test ({duration:.1f}s): {str(e)[:100]}", chat_id)
