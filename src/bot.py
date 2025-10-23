#!/usr/bin/env python3

import sys
import logging
import random
import asyncio
import os
from typing import List

# Import config dan setup_logging (Relative)
from .config import TELEGRAM_BOT_TOKEN, validate_config, setup_logging, reload_proxy_pool # Import fungsi reload

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
# --- IMPORT BARU (Nama sudah diganti) ---
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


# ============================================================
# HANDLER BOT (Tidak berubah kecuali sync_proxies)
# ============================================================

def get_main_keyboard():
    keyboard = [
        [KeyboardButton("🎲 Random"), KeyboardButton("📋 List Persona")],
        [KeyboardButton("📧 Dot Trick"), KeyboardButton("ℹ️ Info")],
        [KeyboardButton("📊 Stats")] # Tombol sync proxy tidak di keyboard utama, tapi command
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True, is_persistent=False, one_time_keyboard=False)

async def start_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_name = update.effective_user.first_name
    message = (f"👋 Halo, **{user_name}**!\n\n🤖 **GitHub Asset Generator Bot**\n"
               f"🔥 Model: Manual Fallback\n\n"
               f"**Quick Actions:**\n"
               f"• 🎲 Random\n• 📋 List Persona\n• 📧 Dot Trick\n• ℹ️ Info\n• 📊 Stats\n"
               f"• `/sync_proxies` - Update proxy list\n\n" # Tambah info command sync
               f"_Tap ikon menu keyboard jika perlu._")
    await update.message.reply_text(message, reply_markup=get_main_keyboard(), parse_mode='Markdown')

async def info_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = ("ℹ️ **GitHub Asset Generator Bot**\n\n"
               "Generate:\n"
               "• Profil developer realistis\n• README.md\n• Code snippets & scripts\n"
               "• Config files & Dotfiles\n• Gmail dot trick variations\n\n"
               "**AI Models:** LiteLLM Manual Fallback\n"
               "**Proxy Sync:** Gunakan `/sync_proxies` untuk download, tes, dan update daftar proxy dari `data/apilist.txt` ke `data/proxy.txt`.")
    await update.message.reply_text(message, parse_mode='Markdown', reply_markup=get_main_keyboard())

async def stats_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = "📊 **Bot Statistics**\n\n"
    num_options = len(llm_call_options)
    if num_options > 0:
        message += f"**LiteLLM (Manual Fallback):**\n• Total Call Options: {num_options}\n(Kombinasi model + API key)\n\n"
    else:
        message += "**LiteLLM (Manual Fallback):**\n• No call options loaded.\n\n"
    stats_gmail = get_stats()
    message += (f"**Gmail Dot Trick:**\n"
                f"• Total Emails (data/gmail.txt): {stats_gmail['total_emails_in_file']}\n"
                f"• Emails with History: {stats_gmail['emails_with_variations']}\n"
                f"• Total Variations Generated: {stats_gmail['total_variations_generated']}")
    await update.message.reply_text(message, parse_mode='Markdown', reply_markup=get_main_keyboard())

async def dot_trick_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        all_emails = load_gmail_list()
        if not all_emails: await update.message.reply_text("⚠️ `data/gmail.txt` kosong!", reply_markup=get_main_keyboard()); return
        keyboard = [[InlineKeyboardButton(f"{email[:35]}", callback_data=f"dottrick_{i}")] for i, email in enumerate(all_emails[:30])]
        if len(all_emails) > 30: keyboard.append([InlineKeyboardButton(f"... +{len(all_emails)-30} more", callback_data="dummy")])
        keyboard.append([InlineKeyboardButton("📊 View Stats", callback_data="dottrick_stats")])
        keyboard.append([InlineKeyboardButton("❌ Batal", callback_data="cancel")])
        reply_markup = InlineKeyboardMarkup(keyboard)
        await (update.message or update.callback_query.message).reply_text( # Handle update/callback
             f"📧 **Pilih Email:**\n\n_1 klik = 1 variasi baru._", reply_markup=reply_markup, parse_mode='Markdown')
    except Exception as e:
        logger.error(f"Error in dot_trick_handler: {e}", exc_info=True)
        await (update.message or update.callback_query.message).reply_text(f"❌ Error: {str(e)}", reply_markup=get_main_keyboard())

async def handle_text_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    if text == "🎲 Random":
        persona_type = random.choice(ALL_PERSONAS)
        await update.message.reply_text(f"⏳ Generating: **{persona_type.replace('_', ' ').title()}**...", parse_mode='Markdown')
        context.application.create_task(trigger_generation_task(update.message.chat_id, persona_type))
    elif text == "📋 List Persona":
        # Buat keyboard dalam beberapa kolom biar nggak terlalu panjang
        buttons = [InlineKeyboardButton(p.replace('_', ' ').title(), callback_data=f"persona_{p}") for p in ALL_PERSONAS]
        n_cols = 2 # Jumlah kolom
        keyboard = [buttons[i:i + n_cols] for i in range(0, len(buttons), n_cols)]
        keyboard.append([InlineKeyboardButton("❌ Batal", callback_data="cancel")])
        await update.message.reply_text("📋 **Pilih Persona:**", reply_markup=InlineKeyboardMarkup(keyboard))
    elif text == "📧 Dot Trick": await dot_trick_handler(update, context)
    elif text == "ℹ️ Info": await info_handler(update, context)
    elif text == "📊 Stats": await stats_handler(update, context)
    # Abaikan teks lain atau beri pesan default?
    # else: await update.message.reply_text("Gunakan tombol atau command yang tersedia.")

async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    try: await query.answer()
    except Exception as e: logger.warning(f"Failed answer callback: {e}")
    data = query.data
    if data == "cancel":
        try: await query.edit_message_text("❌ Dibatalkan.", reply_markup=None)
        except Exception: await query.message.reply_text("❌ Dibatalkan.", reply_markup=get_main_keyboard())
    elif data == "dummy": await query.answer("⚠️ List terlalu panjang.", show_alert=True)
    elif data == "random_generate": await trigger_generation(query, random.choice(ALL_PERSONAS), context)
    elif data.startswith("persona_"): await trigger_generation(query, data.replace("persona_", ""), context)
    elif data == "dottrick_stats": await show_dot_trick_stats(query)
    elif data.startswith("dottrick_"): await trigger_dot_trick_generation(query, int(data.replace("dottrick_", "")), context)
    # Abaikan callback lain yang tidak dikenal

async def trigger_generation(query, persona_type: str, context: ContextTypes.DEFAULT_TYPE):
    chat_id = query.message.chat_id
    try: await query.edit_message_text(f"⏳ **Generating: {persona_type.replace('_', ' ').title()}**\n\n_AI Chaining..._", parse_mode='Markdown', reply_markup=None)
    except Exception as e: logger.warning(f"Failed edit message: {e}"); await context.bot.send_message(chat_id=chat_id, text=f"⏳ **Generating: {persona_type.replace('_', ' ').title()}**...", parse_mode='Markdown')
    context.application.create_task(trigger_generation_task(chat_id, persona_type))

async def trigger_generation_task(chat_id: int, persona_type: str):
    """Jalankan generate_persona_data di thread terpisah."""
    try:
        data = await asyncio.to_thread(generate_persona_data, persona_type)
        if not data: await asyncio.to_thread(send_text_message, "❌ AI generation failed. Check logs.", str(chat_id))
        else: await asyncio.to_thread(send_persona_to_telegram, persona_type, data, str(chat_id))
    except Exception as e:
        logger.error(f"Error in trigger_generation_task: {e}", exc_info=True)
        await asyncio.to_thread(send_text_message, f"❌ Error: {str(e)[:200]}", str(chat_id))

async def trigger_dot_trick_generation(query, index: int, context: ContextTypes.DEFAULT_TYPE):
    chat_id = str(query.message.chat_id); gmail_list = load_gmail_list()
    if index >= len(gmail_list): await query.answer("❌ Index email salah.", show_alert=True); return
    email = gmail_list[index]
    try: await query.edit_message_text(f"⏳ **Generating variasi untuk:**\n`{email}`...", parse_mode='Markdown', reply_markup=None)
    except Exception as e: logger.warning(f"Failed edit message: {e}"); await context.bot.send_message(chat_id=chat_id, text=f"⏳ Generating variasi: `{email}`...", parse_mode='Markdown')
    context.application.create_task(run_dot_trick_task(email=email, chat_id=chat_id))

async def show_dot_trick_stats(query):
    """Tampilkan stats dot trick di pesan inline."""
    stats_gmail = get_stats()
    message = (f"📊 **Gmail Dot Trick Stats**\n\n"
               f"📧 Total Emails: {stats_gmail['total_emails_in_file']}\n"
               f"📈 Emails with History: {stats_gmail['emails_with_variations']}\n"
               f"🔢 Total Variations: {stats_gmail['total_variations_generated']}")
    keyboard = [[InlineKeyboardButton("🔙 Kembali", callback_data="dottrick_backtolist")]]
    try: await query.edit_message_text(message, parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(keyboard))
    except Exception as e: logger.warning(f"Failed edit msg stats: {e}"); await query.message.reply_text(message, parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(keyboard))

async def handle_dottrick_backtolist(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Kembali ke list email dari view stats."""
    query = update.callback_query; await query.answer()
    try: await query.edit_message_text("🔄 Reloading list...", reply_markup=None)
    except Exception: pass
    await dot_trick_handler(query, context) # Kirim query object sekarang

async def run_dot_trick_task(email: str, chat_id: str):
    """Jalankan logika dot trick di thread terpisah."""
    try:
        existing = await asyncio.to_thread(get_generated_variations, email)
        new_var = await asyncio.to_thread(generate_dot_tricks, email, existing)
        if new_var:
            await asyncio.to_thread(add_variation_to_history, email, new_var)
            message = f"✅ **Variasi Gmail Baru**\n\n📧 Original: `{email}`\n🆕 Variasi: `{new_var}`"
        else: message = f"⚠️ **Gagal Generate**\n\n📧 Email: `{email}`\n❌ Mungkin error atau username pendek."
        await asyncio.to_thread(send_text_message, message, chat_id)
    except Exception as e:
        logger.error(f"Error run_dot_trick_task for {email}: {e}", exc_info=True)
        await asyncio.to_thread(send_text_message, f"❌ Error dot trick `{email}`: {str(e)[:200]}", chat_id)

# --- HANDLER BARU UNTUK SYNC PROXY ---
async def sync_proxies_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles the /sync_proxies command."""
    chat_id = str(update.message.chat_id)
    # Kirim pesan awal & log
    await update.message.reply_text("⏳ Memulai sinkronisasi proxy (download, tes, update)... Ini bisa lama.", parse_mode='Markdown')
    logger.info(f"Proxy sync requested by chat_id {chat_id} via Telegram.")

    # Jalankan sync di thread terpisah
    context.application.create_task(run_sync_proxies_task(chat_id))

async def run_sync_proxies_task(chat_id: str):
    """Runs sync_proxies and reloads the pool in a separate thread."""
    start_time = time.time()
    message_prefix = f"Proxy Sync Task (Chat ID: {chat_id}): "
    try:
        logger.info(message_prefix + "Running sync_proxies in thread...")
        success = await asyncio.to_thread(sync_proxies) # Panggil fungsi sync
        duration = time.time() - start_time

        if success:
            logger.info(message_prefix + f"sync_proxies completed successfully in {duration:.2f}s. Reloading pool...")
            # Reload pool setelah sync sukses
            await asyncio.to_thread(reload_proxy_pool)
            logger.info(message_prefix + "Proxy pool reloaded.")
            await asyncio.to_thread(send_text_message, f"✅ Sinkronisasi proxy selesai ({duration:.1f}s) & pool di-reload!", chat_id)
        else:
            logger.error(message_prefix + f"sync_proxies failed after {duration:.2f}s. Pool not reloaded.")
            await asyncio.to_thread(send_text_message, f"❌ Sinkronisasi proxy gagal ({duration:.1f}s). Cek log.", chat_id)
    except Exception as e:
        duration = time.time() - start_time
        logger.error(message_prefix + f"Error during task after {duration:.2f}s: {e}", exc_info=True)
        await asyncio.to_thread(send_text_message, f"❌ Error sync proxy ({duration:.1f}s): {str(e)[:100]}", chat_id)

# --- AKHIR HANDLER BARU ---


async def setup_bot_commands(app: Application):
    """Set custom bot commands."""
    commands = [
        BotCommand("start", "Mulai bot & tampilkan menu"),
        BotCommand("info", "Info tentang bot"),
        BotCommand("stats", "Status AI & Dot Trick"),
        BotCommand("sync_proxies", "Update daftar proxy") # Tambah command baru
    ]
    await app.bot.set_my_commands(commands)

async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    """Log errors."""
    logger.error(f"Update {update} caused error: {context.error}", exc_info=context.error)

def main():
    """Start the bot."""
    try:
        logger.info("=== Inisialisasi Bot Worker ===")
        validate_config()

        application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

        # Add handlers
        application.add_handler(CommandHandler("start", start_handler))
        application.add_handler(CommandHandler("info", info_handler))
        application.add_handler(CommandHandler("stats", stats_handler))
        application.add_handler(CommandHandler("sync_proxies", sync_proxies_handler)) # Tambah handler command
        application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text_message))
        application.add_handler(CallbackQueryHandler(handle_dottrick_backtolist, pattern="^dottrick_backtolist$"))
        application.add_handler(CallbackQueryHandler(callback_handler))

        application.add_error_handler(error_handler)
        application.post_init = setup_bot_commands

        logger.info("🚀 Bot worker siap. Memulai polling...")
        application.run_polling()
    except Exception as e:
        logger.critical(f"FATAL ERROR (Worker): {e}", exc_info=True)
        sys.exit(1)

if __name__ == "__main__":
    main()
