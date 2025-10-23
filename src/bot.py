#!/usr/bin/env python3

import sys
import logging
import random
import asyncio
import os
import time
from typing import List
from datetime import datetime

# Import scheduler
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

# Import config dan setup_logging (Relative)
from .config import TELEGRAM_BOT_TOKEN, validate_config, setup_logging, reload_proxy_pool

# Setup logging untuk worker (ke file + console)
setup_logging(is_controller=False)

logger = logging.getLogger(__name__)

try:
    from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton, BotCommand
    from telegram.ext import Application, CommandHandler, ContextTypes, CallbackQueryHandler, MessageHandler, filters
except ImportError:
    logger.critical("Failed to import python-telegram-bot. Install: pip install python-telegram-bot"); sys.exit(1)

# Import dari modules dan services
from .services.llm import generate_persona_data, llm_call_options
from .services.telegram import send_persona_to_telegram, send_text_message
from .modules.gmail import generate_dot_tricks, load_gmail_list, add_variation_to_history, get_generated_variations, get_stats
from .modules.proxy import sync_proxies
# -------------------------------------

# --- LIST PERSONA (Tidak berubah) ---
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
# -------------------------

# === PERUBAHAN 1: Definisikan Scheduler di Global Scope ===
# Kita definisikan di sini agar bisa diakses oleh main() (untuk shutdown)
# dan setup_bot_commands() (untuk start)
scheduler = AsyncIOScheduler(timezone="Asia/Jakarta")
# =======================================================


# ============================================================
# SCHEDULER TASK UNTUK AUTO SYNC PROXY (Tidak berubah)
# ============================================================
async def scheduled_proxy_sync_task():
    """Wrapper async untuk menjalankan sync_proxies dan reload pool secara terjadwal."""
    start_time = time.time()
    logger.info("===== Starting SCHEDULED Proxy Sync Process =====")
    try:
        success = await asyncio.to_thread(sync_proxies)
        duration = time.time() - start_time
        if success:
            logger.info(f"Scheduled sync successful ({duration:.2f}s). Reloading pool...")
            await asyncio.to_thread(reload_proxy_pool)
            logger.info("Scheduled proxy pool reloaded.")
            # await asyncio.to_thread(send_text_message, f"✅ Auto Proxy Sync OK ({duration:.1f}s)", TELEGRAM_CHAT_ID)
        else:
            logger.error(f"Scheduled sync failed ({duration:.2f}s). Pool not reloaded.")
            # await asyncio.to_thread(send_text_message, f"❌ Auto Proxy Sync Gagal ({duration:.1f}s)", TELEGRAM_CHAT_ID)
    except Exception as e:
        duration = time.time() - start_time
        logger.error(f"Error scheduled proxy sync ({duration:.2f}s): {e}", exc_info=True)
        # await asyncio.to_thread(send_text_message, f"❌ Error Auto Sync Proxy ({duration:.1f}s): {str(e)[:100]}", TELEGRAM_CHAT_ID)

# ============================================================
# HANDLER BOT (Tidak berubah)
# ============================================================

def get_main_keyboard():
    # ... (kode get_main_keyboard tidak berubah) ...
    keyboard = [
        [KeyboardButton("🎲 Random"), KeyboardButton("📋 List Persona")],
        [KeyboardButton("📧 Dot Trick"), KeyboardButton("ℹ️ Info")],
        [KeyboardButton("📊 Stats")]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True, is_persistent=False, one_time_keyboard=False)

async def start_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # ... (kode start_handler tidak berubah) ...
    user_name = update.effective_user.first_name
    message = (f"👋 Halo, **{user_name}**!\n\n🤖 **GitHub Asset Generator Bot**\n"
               f"🔥 Model: Manual Fallback\n\n"
               f"**Quick Actions:**\n"
               f"• 🎲 Random\n• 📋 List Persona\n• 📧 Dot Trick\n• ℹ️ Info\n• 📊 Stats\n"
               f"• `/sync_proxies` - Update proxy list NOW\n\n"
               f"_(Proxy list diupdate otomatis setiap minggu)_")
    await update.message.reply_text(message, reply_markup=get_main_keyboard(), parse_mode='Markdown')


async def info_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # ... (kode info_handler tidak berubah) ...
    message = ("ℹ️ **GitHub Asset Generator Bot**\n\n"
               "Generate:\n"
               "• Profil developer\n• README.md\n• Code snippets\n"
               "• Config/Dotfiles\n• Gmail dot trick\n\n"
               "**AI Models:** LiteLLM Manual Fallback\n"
               "**Proxy Sync:** `/sync_proxies` (Manual), Auto weekly.")
    await update.message.reply_text(message, parse_mode='Markdown', reply_markup=get_main_keyboard())


async def stats_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # ... (kode stats_handler tidak berubah) ...
    message = "📊 **Bot Statistics**\n\n"
    num_options = len(llm_call_options)
    if num_options > 0: message += f"**LiteLLM (Manual Fallback):**\n• Total Call Options: {num_options}\n\n"
    else: message += "**LiteLLM (Manual Fallback):**\n• No call options loaded.\n\n"
    stats_gmail = get_stats()
    message += (f"**Gmail Dot Trick:**\n"
                f"• Total Emails: {stats_gmail['total_emails_in_file']}\n"
                f"• History Emails: {stats_gmail['emails_with_variations']}\n"
                f"• Total Variations: {stats_gmail['total_variations_generated']}")
    await update.message.reply_text(message, parse_mode='Markdown', reply_markup=get_main_keyboard())


async def dot_trick_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # ... (kode dot_trick_handler tidak berubah) ...
    try:
        all_emails = load_gmail_list()
        if not all_emails: await update.message.reply_text("⚠️ `data/gmail.txt` kosong!", reply_markup=get_main_keyboard()); return
        keyboard = [[InlineKeyboardButton(f"{email[:35]}", callback_data=f"dottrick_{i}")] for i, email in enumerate(all_emails[:30])]
        if len(all_emails) > 30: keyboard.append([InlineKeyboardButton(f"... +{len(all_emails)-30} more", callback_data="dummy")])
        keyboard.append([InlineKeyboardButton("📊 View Stats", callback_data="dottrick_stats")])
        keyboard.append([InlineKeyboardButton("❌ Batal", callback_data="cancel")])
        reply_markup = InlineKeyboardMarkup(keyboard)
        target_message = update.message or getattr(update.callback_query, 'message', None) # Handle update/callback
        if target_message: await target_message.reply_text(f"📧 **Pilih Email:**", reply_markup=reply_markup)
        else: logger.error("Cannot determine message to reply to in dot_trick_handler")
    except Exception as e: logger.error(f"Error dot_trick_handler: {e}", exc_info=True); await (update.message or getattr(update.callback_query, 'message', None)).reply_text(f"❌ Error: {str(e)}", reply_markup=get_main_keyboard())

async def handle_text_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # ... (kode handle_text_message tidak berubah) ...
    text = update.message.text.strip()
    if text == "🎲 Random":
        persona_type = random.choice(ALL_PERSONAS)
        await update.message.reply_text(f"⏳ Generating: **{persona_type.replace('_', ' ').title()}**...", parse_mode='Markdown')
        context.application.create_task(trigger_generation_task(update.message.chat_id, persona_type))
    elif text == "📋 List Persona":
        buttons = [InlineKeyboardButton(p.replace('_', ' ').title(), callback_data=f"persona_{p}") for p in ALL_PERSONAS]
        n_cols = 2; keyboard = [buttons[i:i + n_cols] for i in range(0, len(buttons), n_cols)]
        keyboard.append([InlineKeyboardButton("❌ Batal", callback_data="cancel")])
        await update.message.reply_text("📋 **Pilih Persona:**", reply_markup=InlineKeyboardMarkup(keyboard))
    elif text == "📧 Dot Trick": await dot_trick_handler(update, context)
    elif text == "ℹ️ Info": await info_handler(update, context)
    elif text == "📊 Stats": await stats_handler(update, context)


async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # ... (kode callback_handler tidak berubah, perbaikan indentasi sudah ada) ...
    query = update.callback_query
    if not query: return # Safety check
    try: await query.answer()
    except Exception as e: logger.warning(f"Failed answer callback: {e}")

    data = query.data
    if data == "cancel":
        try:
            await query.edit_message_text("❌ Dibatalkan.", reply_markup=None)
        except Exception:
            if query.message: 
                 await query.message.reply_text("❌ Dibatalkan.", reply_markup=get_main_keyboard())
            else:
                 logger.error("Callback 'cancel' failed: No message to reply to.")
    elif data == "dummy":
        await query.answer("⚠️ List terlalu panjang.", show_alert=True)
    elif data == "random_generate":
        await trigger_generation(query, random.choice(ALL_PERSONAS), context)
    elif data.startswith("persona_"):
        await trigger_generation(query, data.replace("persona_", ""), context)
    elif data == "dottrick_stats":
        await show_dot_trick_stats(query)
    elif data.startswith("dottrick_"):
        try: 
             index = int(data.replace("dottrick_", ""))
             await trigger_dot_trick_generation(query, index, context)
        except ValueError:
             logger.error(f"Invalid index in dottrick callback data: {data}")
             await query.answer("❌ Data callback tidak valid.", show_alert=True)


async def trigger_generation(query, persona_type: str, context: ContextTypes.DEFAULT_TYPE):
    # ... (kode trigger_generation tidak berubah) ...
    if not query or not query.message: logger.error("Cannot trigger generation: invalid query/message"); return
    chat_id = query.message.chat_id
    try: await query.edit_message_text(f"⏳ **Generating: {persona_type.replace('_', ' ').title()}**...", parse_mode='Markdown', reply_markup=None)
    except Exception as e: logger.warning(f"Failed edit message: {e}"); await context.bot.send_message(chat_id=chat_id, text=f"⏳ **Generating: {persona_type.replace('_', ' ').title()}**...", parse_mode='Markdown')
    context.application.create_task(trigger_generation_task(chat_id, persona_type))

async def trigger_generation_task(chat_id: int, persona_type: str):
    # ... (kode trigger_generation_task tidak berubah) ...
    try:
        data = await asyncio.to_thread(generate_persona_data, persona_type)
        if not data: await asyncio.to_thread(send_text_message, "❌ AI generation failed. Check logs.", str(chat_id))
        else: await asyncio.to_thread(send_persona_to_telegram, persona_type, data, str(chat_id))
    except Exception as e: logger.error(f"Error trigger_generation_task: {e}", exc_info=True); await asyncio.to_thread(send_text_message, f"❌ Error: {str(e)[:200]}", str(chat_id))

async def trigger_dot_trick_generation(query, index: int, context: ContextTypes.DEFAULT_TYPE):
    # ... (kode trigger_dot_trick_generation tidak berubah) ...
    if not query or not query.message: logger.error("Cannot trigger dot trick: invalid query/message"); return
    chat_id = str(query.message.chat_id); gmail_list = load_gmail_list()
    if index >= len(gmail_list): await query.answer("❌ Index email salah.", show_alert=True); return
    email = gmail_list[index]
    try: await query.edit_message_text(f"⏳ Generating: `{email}`...", parse_mode='Markdown', reply_markup=None)
    except Exception as e: logger.warning(f"Failed edit message: {e}"); await context.bot.send_message(chat_id=chat_id, text=f"⏳ Generating: `{email}`...", parse_mode='Markdown')
    context.application.create_task(run_dot_trick_task(email=email, chat_id=chat_id))

async def show_dot_trick_stats(query):
    # ... (kode show_dot_trick_stats tidak berubah) ...
    if not query: return
    stats_gmail = get_stats()
    message = (f"📊 **Gmail Dot Trick Stats**\n\n📧 Total: {stats_gmail['total_emails_in_file']}\n📈 History: {stats_gmail['emails_with_variations']}\n🔢 Generated: {stats_gmail['total_variations_generated']}")
    keyboard = [[InlineKeyboardButton("🔙 Kembali", callback_data="dottrick_backtolist")]]
    try: await query.edit_message_text(message, parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(keyboard))
    except Exception as e: logger.warning(f"Failed edit stats: {e}"); await query.message.reply_text(message, parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(keyboard))

async def handle_dottrick_backtolist(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # ... (kode handle_dottrick_backtolist tidak berubah) ...
    query = update.callback_query; await query.answer()
    try: await query.edit_message_text("🔄 Reloading list...", reply_markup=None)
    except Exception: pass
    if query.message:
        await dot_trick_handler(query.message, context) 
    else:
        logger.error("Cannot go back to dot trick list: query.message is None")


async def run_dot_trick_task(email: str, chat_id: str):
    # ... (kode run_dot_trick_task tidak berubah) ...
    try:
        existing = await asyncio.to_thread(get_generated_variations, email)
        new_var = await asyncio.to_thread(generate_dot_tricks, email, existing)
        if new_var: await asyncio.to_thread(add_variation_to_history, email, new_var); message = f"✅ **Variasi Gmail Baru**\n\n📧 `{email}`\n🆕 `{new_var}`"
        else: message = f"⚠️ **Gagal Generate**\n\n📧 `{email}`\n❌ Error/Pendek."
        await asyncio.to_thread(send_text_message, message, chat_id)
    except Exception as e: logger.error(f"Error dot_trick_task {email}: {e}", exc_info=True); await asyncio.to_thread(send_text_message, f"❌ Error dot trick `{email}`: {str(e)[:200]}", chat_id)

# --- HANDLER SYNC PROXY MANUAL (Tidak berubah) ---
async def sync_proxies_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # ... (kode sync_proxies_handler tidak berubah) ...
    chat_id = str(update.message.chat_id)
    await update.message.reply_text("⏳ Memulai sinkronisasi proxy manual...", parse_mode='Markdown')
    logger.info(f"Manual proxy sync requested by chat_id {chat_id}.")
    context.application.create_task(run_sync_proxies_task(chat_id))

async def run_sync_proxies_task(chat_id: str):
    # ... (kode run_sync_proxies_task tidak berubah) ...
    start_time = time.time(); message_prefix = f"Proxy Sync Task (Chat ID: {chat_id}): "
    try:
        logger.info(message_prefix + "Running sync_proxies...")
        success = await asyncio.to_thread(sync_proxies)
        duration = time.time() - start_time
        if success:
            logger.info(message_prefix + f"sync successful ({duration:.2f}s). Reloading pool...")
            await asyncio.to_thread(reload_proxy_pool)
            logger.info(message_prefix + "Pool reloaded.")
            await asyncio.to_thread(send_text_message, f"✅ Sync proxy manual OK ({duration:.1f}s) & pool di-reload!", chat_id)
        else:
            logger.error(message_prefix + f"sync failed ({duration:.2f}s). Pool not reloaded.")
            await asyncio.to_thread(send_text_message, f"❌ Sync proxy manual Gagal ({duration:.1f}s). Cek log.", chat_id)
    except Exception as e:
        duration = time.time() - start_time
        logger.error(message_prefix + f"Error ({duration:.2f}s): {e}", exc_info=True)
        await asyncio.to_thread(send_text_message, f"❌ Error sync proxy ({duration:.1f}s): {str(e)[:100]}", chat_id)

# --- AKHIR HANDLER SYNC PROXY ---


# === PERUBAHAN 2: Modifikasi setup_bot_commands ===
async def setup_bot_commands(app: Application):
    """Set bot commands AND start the scheduler."""
    # (Kode setup command tidak berubah)
    commands = [ 
        BotCommand("start", "Mulai bot"), 
        BotCommand("info", "Info bot"), 
        BotCommand("stats", "Status"), 
        BotCommand("sync_proxies", "Update proxy list") 
    ]
    await app.bot.set_my_commands(commands)
    
    # === PINDAHKAN LOGIC START SCHEDULER KE SINI ===
    logger.info("Initializing background scheduler via post_init...")
    try:
        if not scheduler.running:
            # Tambahkan job di sini
            scheduler.add_job( 
                scheduled_proxy_sync_task, 
                trigger=IntervalTrigger(weeks=1), 
                id="weekly_proxy_sync", 
                name="Weekly Proxy Sync", 
                next_run_time=datetime.now() 
            )
            # Mulai scheduler
            scheduler.start()
            logger.info("✅ Background scheduler started.")
        else:
            logger.info("Scheduler already running (skipped start).")
    except Exception as e:
        logger.error(f"❌ Failed to start scheduler in post_init: {e}", exc_info=True)
    # === AKHIR PERUBAHAN ===

async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    # ... (kode error_handler tidak berubah) ...
    logger.error(f"Update {update} caused error: {context.error}", exc_info=context.error)

# === PERUBAHAN 3: Modifikasi main() ===
def main():
    """Start the bot and the scheduler."""
    try:
        logger.info("=== Inisialisasi Bot Worker ===")
        validate_config()
        application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
        
        # (Handler tidak berubah)
        application.add_handler(CommandHandler("start", start_handler))
        application.add_handler(CommandHandler("info", info_handler))
        application.add_handler(CommandHandler("stats", stats_handler))
        application.add_handler(CommandHandler("sync_proxies", sync_proxies_handler))
        application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text_message))
        application.add_handler(CallbackQueryHandler(handle_dottrick_backtolist, pattern="^dottrick_backtolist$"))
        application.add_handler(CallbackQueryHandler(callback_handler))
        application.add_error_handler(error_handler)
        
        # --- PERUBAHAN KUNCI ---
        # Tetapkan post_init ke fungsi yg akan start scheduler
        application.post_init = setup_bot_commands
        # ---------------------

        # --- HAPUS BLOK INI DARI main() ---
        # logger.info("Initializing background scheduler...")
        # scheduler = AsyncIOScheduler(timezone="Asia/Jakarta")
        # scheduler.add_job( scheduled_proxy_sync_task, trigger=IntervalTrigger(weeks=1), id="weekly_proxy_sync", name="Weekly Proxy Sync", next_run_time=datetime.now() )
        # scheduler.start() # <-- INI YANG MENYEBABKAN ERROR
        # logger.info("✅ Background scheduler started.")
        # ---------------------------------
        
        logger.info("🚀 Bot worker siap. Memulai polling...")
        application.run_polling()
        
        # Shutdown scheduler (referensi ke scheduler global)
        logger.info("Shutting down scheduler...")
        if scheduler.running:
            scheduler.shutdown()
            
    except (KeyboardInterrupt, SystemExit):
         logger.info("Bot stopped manually. Shutting down scheduler...")
         if scheduler.running: # Referensi ke scheduler global
             scheduler.shutdown()
             
    except Exception as e:
        logger.critical(f"FATAL ERROR (Worker): {e}", exc_info=True)
        if scheduler.running: # Referensi ke scheduler global
             scheduler.shutdown()
        sys.exit(1)

if __name__ == "__main__":
    main()
