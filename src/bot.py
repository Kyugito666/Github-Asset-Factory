#!/usr/bin/env python3

import sys
import logging
import random
import asyncio
import os
from typing import List

# Import config dan setup_logging (Relative)
from .config import TELEGRAM_BOT_TOKEN, validate_config, setup_logging

# Setup logging untuk worker (ke file + console)
setup_logging(is_controller=False)

logger = logging.getLogger(__name__)

try:
    from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton, BotCommand
    from telegram.ext import Application, CommandHandler, ContextTypes, CallbackQueryHandler, MessageHandler, filters
except ImportError:
    logger.critical("Failed to import python-telegram-bot. Install: pip install python-telegram-bot"); sys.exit(1)

# --- DIPERBARUI (Hapus import router) ---
from .services.llm import generate_persona_data, llm_call_options # Import llm_call_options untuk stats
from .services.telegram import send_persona_to_telegram, send_text_message
from .modules.gmail import generate_dot_tricks, load_gmail_list, add_variation_to_history, get_generated_variations, get_stats
# -------------------------------------


# --- LIST PERSONA (Tidak berubah) ---
ALL_PERSONAS = [
    # Kategori Generalist & Foundational
    "explorer",         # Suka coba-coba repo baru
    "project_starter",  # Mulai proyek baru (basic code + readme)
    "professional",     # Profil dev standar, cenderung lengkap (no code asset)
    "fullstack_dev",    # BARU: Generalist Web Full Stack (code + readme)
    "polymath_dev",     # Skillset luas, aset acak (code + readme)
    "student_learner",  # Pasif, fokus belajar (no code asset)

    # Kategori Kontribusi & Interaksi (5)
    "forker",           # Suka fork repo (no code asset)
    "socialite",        # Aktif di aspek sosial GitHub (no code asset)
    "open_source_advocate", # Fokus highlight kontribusi OS di profil (profile readme)
    "issue_reporter",   # BARU: Fokus lapor bug/issue (no code asset, activity focus)
    "community_helper", # BARU: Fokus diskusi/bantu di issue/discussion (no code asset, activity focus)

    # Kategori Spesialis README & Visual (6)
    "readme_pro",       # Spesialis bikin README proyek bagus (project readme)
    "profile_architect",# Spesialis bikin README profil bagus (struktur) (profile readme)
    "ui_ux_designer",   # BARU: Fokus visual README profil (desain) (profile readme)
    "technical_writer_dev", # BARU: Fokus kejelasan tulisan README profil (profile readme)
    "minimalist_dev",   # BARU: Fokus desain README profil simpel & bersih (profile readme)
    "data_viz_enthusiast", # BARU: Fokus data viz di README profil (profile readme)

    # Kategori Spesialis Kode & Script Dasar (6)
    "uploader",         # Upload 1 utility script (script + readme)
    "backend_dev",      # Buat 1 backend API dasar (code + readme)
    "frontend_dev",     # Buat 1 frontend component dasar (code + readme)
    "mobile_dev_android", # Buat 1 snippet Android dasar (code + readme)
    "ai_ml_engineer",   # Buat 1 script AI/ML dasar (script + readme)
    "data_scientist",   # Buat 1 script data science dasar (script + readme)

    # Kategori Spesialis Infrastruktur & DevOps (5)
    "config_master",    # Buat file konfigurasi (Docker, etc) (config + readme)
    "dotfiles_enthusiast", # Buat dotfiles kustom (dotfile + readme)
    "cloud_architect_aws",  # BARU: Fokus AWS/IaC (Terraform/CF snippet + readme)
    "database_admin",   # BARU: Fokus DB script (SQL snippet + readme)
    "network_engineer", # BARU: Fokus config jaringan (config snippet + readme)

    # Kategori Spesialis Kode & Script Lanjutan (6)
    "polyglot_tool_builder", # Buat >1 script beda bahasa (scripts + readme)
    "game_developer",   # BARU: Snippet game dev (C#/C++ snippet + readme)
    "embedded_systems_dev", # BARU: Snippet embedded (C/Rust snippet + readme)
    "framework_maintainer", # BARU: Contoh kontribusi/internal framework (code + readme)
    "performance_optimizer",# BARU: Script benchmarking (script + readme)
    "api_designer",      # BARU: Fokus desain API (misal: OpenAPI spec snippet + readme)

    # Kategori Pasif & Observasi (5)
    "ghost",            # Sangat pasif (profil hampir kosong) (no code asset)
    "lurker",           # Pasif, mungkin sedikit aktivitas (star/follow) (no code asset)
    "securer",          # Fokus ke security profile (tanpa aset kode) (no code asset)
    "code_collector",   # BARU: Banyak star/fork, sedikit kontribusi (no code asset, activity focus)
    "organization_member", # BARU: Member org tapi pasif (no code asset)

    # Kategori Lainnya
    "security_researcher", # Buat 1 script security dasar (script + readme + disclaimer)
    "niche_guy",        # Fokus ke teknologi spesifik/kurang umum (no code asset)
]
# -------------------------


# ============================================================
# HANDLER BOT
# ============================================================

def get_main_keyboard():
    keyboard = [
        [KeyboardButton("🎲 Random"), KeyboardButton("📋 List Persona")],
        [KeyboardButton("📧 Dot Trick"), KeyboardButton("ℹ️ Info")],
        [KeyboardButton("📊 Stats")]
    ]
    return ReplyKeyboardMarkup(
        keyboard,
        resize_keyboard=True,
        is_persistent=False,
        one_time_keyboard=False
    )

async def start_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_name = update.effective_user.first_name
    message = f"👋 Halo, **{user_name}**!\n\n🤖 **GitHub Asset Generator Bot**\n🔥 Model: Manual Fallback\n\n**Quick Actions:**\n• 🎲 Random - Generate persona acak\n• 📋 List Persona - Pilih persona spesifik\n• 📧 Dot Trick - Generate variasi Gmail acak\n• ℹ️ Info - Tentang bot\n• 📊 Stats - Status AI keys & Dot Trick\n\n_Tap ikon menu keyboard jika perlu._"
    await update.message.reply_text(message, reply_markup=get_main_keyboard(), parse_mode='Markdown')

async def info_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = "ℹ️ **GitHub Asset Generator Bot**\n\nBot ini menggunakan AI untuk generate:\n• Profile data developer realistis\n• README.md profesional\n• Code snippets & scripts\n• Config files\n• Dotfiles\n• Gmail dot trick variations (1 acak per klik)\n\n**AI Models:**\n• LiteLLM Manual Fallback (Multiple Providers)\n\n**Send Methods:**\n• Text: Code block di chat\n\nMethod dipilih otomatis sesuai persona type."
    await update.message.reply_text(message, parse_mode='Markdown', reply_markup=get_main_keyboard())

# === HANDLER STATS DIPERBAIKI ===
async def stats_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = "📊 **Bot Statistics**\n\n"
    # Info AI dari jumlah call options yang di-load
    num_options = len(llm_call_options)
    if num_options > 0:
        message += f"**LiteLLM (Manual Fallback):**\n• Total Call Options: {num_options}\n(Kombinasi model + API key)\n\n"
    else:
        message += "**LiteLLM (Manual Fallback):**\n• No call options loaded. Check config/models.\n\n"

    # Info Dot Trick (tidak berubah)
    stats_gmail = get_stats()
    message += f"**Gmail Dot Trick:**\n• Total Emails (data/gmail.txt): {stats_gmail['total_emails_in_file']}\n• Emails with History: {stats_gmail['emails_with_variations']}\n• Total Variations Generated: {stats_gmail['total_variations_generated']}\n\n"
    # message += "_Failed keys akan auto-reset setelah cooldown_" # Info ini tidak relevan lagi
    await update.message.reply_text(message, parse_mode='Markdown', reply_markup=get_main_keyboard())
# === AKHIR PERBAIKAN ===

async def dot_trick_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        all_emails = load_gmail_list()
        if not all_emails: await update.message.reply_text("⚠️ **File data/gmail.txt tidak ditemukan atau kosong!**", reply_markup=get_main_keyboard()); return
        keyboard = []
        for i, email in enumerate(all_emails[:30]): keyboard.append([InlineKeyboardButton(f"{email[:35]}", callback_data=f"dottrick_{i}")])
        if len(all_emails) > 30: keyboard.append([InlineKeyboardButton(f"... +{len(all_emails)-30} more emails", callback_data="dummy")])
        keyboard.append([InlineKeyboardButton("📊 View Stats", callback_data="dottrick_stats")]); keyboard.append([InlineKeyboardButton("❌ Batal", callback_data="cancel")])
        reply_markup = InlineKeyboardMarkup(keyboard)
        edit_target = update.message if hasattr(update, 'message') else update # Handle potential callback query update
        await edit_target.reply_text(f"📧 **Pilih Email untuk Generate Variasi Acak:**\n\n_Setiap klik akan menghasilkan 1 variasi baru._", reply_markup=reply_markup, parse_mode='Markdown')
    except Exception as e:
        logger.error(f"Error di dot_trick_handler: {e}", exc_info=True)
        reply_target = update.message if hasattr(update, 'message') else update
        await reply_target.reply_text(f"❌ Error: {str(e)}", reply_markup=get_main_keyboard())


async def handle_text_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    if text == "🎲 Random":
        persona_type = random.choice(ALL_PERSONAS)
        await update.message.reply_text(f"⏳ Generating random persona: **{persona_type.replace('_', ' ').title()}**...", parse_mode='Markdown')
        # Jalankan task di background thread
        context.application.create_task(trigger_generation_task(update.message.chat_id, persona_type))
    elif text == "📋 List Persona":
        keyboard = [[InlineKeyboardButton(p.replace('_', ' ').title(), callback_data=f"persona_{p}")] for p in ALL_PERSONAS]
        keyboard.append([InlineKeyboardButton("❌ Batal", callback_data="cancel")])
        await update.message.reply_text("📋 **Pilih Persona:**", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
    elif text == "📧 Dot Trick": await dot_trick_handler(update, context)
    elif text == "ℹ️ Info": await info_handler(update, context)
    elif text == "📊 Stats": await stats_handler(update, context)

async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    try: await query.answer() # Jawab callback secepat mungkin
    except Exception as e: logger.warning(f"Failed to answer callback query: {e}")

    data = query.data

    if data == "cancel":
        try: await query.edit_message_text("❌ Dibatalkan.", reply_markup=None)
        except Exception: # Fallback jika edit gagal (misal pesan terlalu lama)
             await query.message.reply_text("❌ Dibatalkan.", reply_markup=get_main_keyboard())
        return # Stop processing
    elif data == "dummy":
        await query.answer("⚠️ Terlalu banyak email, tampilkan hanya 30 pertama", show_alert=True)
        return
    elif data == "random_generate":
        persona_type = random.choice(ALL_PERSONAS)
        await trigger_generation(query, persona_type, context)
    elif data.startswith("persona_"):
        persona_type = data.replace("persona_", "")
        await trigger_generation(query, persona_type, context)
    elif data == "dottrick_stats":
        await show_dot_trick_stats(query) # Handle stats view
    elif data.startswith("dottrick_"):
        index = int(data.replace("dottrick_", ""))
        await trigger_dot_trick_generation(query, index, context) # Handle generation

async def trigger_generation(query, persona_type: str, context: ContextTypes.DEFAULT_TYPE):
    chat_id = query.message.chat_id
    try:
        # Edit pesan inline keyboard jadi teks loading
        await query.edit_message_text(f"⏳ **Generating: {persona_type.replace('_', ' ').title()}**\n\n_AI Chaining in progress..._", parse_mode='Markdown', reply_markup=None)
    except Exception as e:
        # Fallback jika edit gagal
        logger.warning(f"Failed to edit message: {e}")
        await context.bot.send_message(chat_id=chat_id, text=f"⏳ **Generating: {persona_type.replace('_', ' ').title()}**...", parse_mode='Markdown')

    # Jalankan task generate di background thread
    context.application.create_task(trigger_generation_task(chat_id, persona_type))

async def trigger_generation_task(chat_id: int, persona_type: str):
    """Jalankan generate_persona_data di thread terpisah."""
    try:
        # Panggil fungsi blocking (call_llm) via to_thread
        data = await asyncio.to_thread(generate_persona_data, persona_type)
        if not data:
            # Kirim pesan error jika generate gagal
            await asyncio.to_thread(send_text_message, "❌ AI generation failed. Check logs.", str(chat_id))
            return
        # Kirim hasil jika sukses
        await asyncio.to_thread(send_persona_to_telegram, persona_type, data, str(chat_id))
    except Exception as e:
        logger.error(f"Error in trigger_generation_task: {e}", exc_info=True)
        # Kirim pesan error umum
        await asyncio.to_thread(send_text_message, f"❌ Error: {str(e)[:200]}", str(chat_id))

async def trigger_dot_trick_generation(query, index: int, context: ContextTypes.DEFAULT_TYPE):
    chat_id = str(query.message.chat_id)
    gmail_list = load_gmail_list()
    if index >= len(gmail_list):
        await query.answer("❌ Email index tidak valid", show_alert=True)
        return
    email = gmail_list[index]
    try:
        # Edit pesan inline keyboard jadi teks loading
        await query.edit_message_text(f"⏳ **Generating variasi acak untuk:**\n`{email}`\n\n_Processing..._", parse_mode='Markdown', reply_markup=None)
    except Exception as e:
        logger.warning(f"Failed to edit message: {e}")
        await context.bot.send_message(chat_id=chat_id, text=f"⏳ Generating variasi acak untuk: `{email}`...", parse_mode='Markdown')

    # Jalankan task dot trick di background thread
    context.application.create_task(run_dot_trick_task(email=email, chat_id=chat_id))

async def show_dot_trick_stats(query):
    """Tampilkan stats dot trick di pesan inline."""
    stats_gmail = get_stats()
    message = f"📊 **Gmail Dot Trick Statistics**\n\n"
    message += f"📧 Total Emails (data/gmail.txt): {stats_gmail['total_emails_in_file']}\n"
    message += f"📈 Emails with Variations: {stats_gmail['emails_with_variations']}\n"
    message += f"🔢 Total Variations Generated: {stats_gmail['total_variations_generated']}\n\n"
    keyboard = [[InlineKeyboardButton("🔙 Kembali ke List Email", callback_data="dottrick_backtolist")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    try:
        await query.edit_message_text(message, parse_mode='Markdown', reply_markup=reply_markup)
    except Exception as e:
        logger.warning(f"Failed to edit message for stats: {e}")
        # Fallback jika edit gagal
        await query.message.reply_text(message, parse_mode='Markdown', reply_markup=reply_markup)

async def handle_dottrick_backtolist(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Kembali ke list email dari view stats."""
    query = update.callback_query
    await query.answer()
    try:
        # Tampilkan pesan loading sementara
        await query.edit_message_text("🔄 Memuat ulang list email...", reply_markup=None)
    except Exception:
        pass # Abaikan jika edit gagal
    # Panggil handler asli untuk menampilkan list lagi
    # Perlu message object, bukan query object
    await dot_trick_handler(query.message, context)


async def run_dot_trick_task(email: str, chat_id: str):
    """Jalankan logika dot trick di thread terpisah."""
    try:
        # Panggil fungsi blocking via to_thread
        existing_variations = await asyncio.to_thread(get_generated_variations, email)
        new_variation = await asyncio.to_thread(generate_dot_tricks, email, existing_variations)

        if new_variation:
            # Panggil fungsi blocking via to_thread
            await asyncio.to_thread(add_variation_to_history, email, new_variation)
            message = f"✅ **Variasi Gmail Dot Trick Baru**\n\n📧 Original: `{email}`\n🆕 Variasi: `{new_variation}`"
        else:
            message = f"⚠️ **Gagal Generate Variasi**\n\n📧 Email: `{email}`\n❌ Username mungkin terlalu pendek atau error terjadi."

        # Kirim hasil via to_thread
        await asyncio.to_thread(send_text_message, message, chat_id)
    except Exception as e:
        logger.error(f"Error in run_dot_trick_task for {email}: {e}", exc_info=True)
        # Kirim pesan error via to_thread
        await asyncio.to_thread(send_text_message, f"❌ Error generating dot trick for `{email}`: {str(e)[:200]}", chat_id)


async def setup_bot_commands(app: Application):
    """Set custom bot commands."""
    commands = [
        BotCommand("start", "Mulai bot & tampilkan menu"),
        BotCommand("info", "Info tentang bot"),
        BotCommand("stats", "Status AI keys & Dot Trick")
    ]
    await app.bot.set_my_commands(commands)

async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    """Log errors caused by updates."""
    logger.error(f"Update {update} caused error: {context.error}", exc_info=context.error)

def main():
    """Start the bot."""
    try:
        logger.info("=== Inisialisasi Bot Worker (Subprocess) ===")
        validate_config() # Validasi config dulu

        application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

        # Add handlers
        application.add_handler(CommandHandler("start", start_handler))
        application.add_handler(CommandHandler("info", info_handler))
        application.add_handler(CommandHandler("stats", stats_handler))
        application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text_message))
        # Handler callback query harus spesifik pattern-nya ATAU pakai satu handler umum
        application.add_handler(CallbackQueryHandler(handle_dottrick_backtolist, pattern="^dottrick_backtolist$"))
        application.add_handler(CallbackQueryHandler(callback_handler)) # Handler umum untuk callback lain

        # Add error handler
        application.add_error_handler(error_handler)

        # Set bot commands (run async after init)
        application.post_init = setup_bot_commands

        logger.info("🚀 Bot worker siap. Memulai polling...")
        application.run_polling()
    except Exception as e:
        logger.critical(f"FATAL ERROR (Worker): {e}", exc_info=True)
        sys.exit(1)

if __name__ == "__main__":
    main()
