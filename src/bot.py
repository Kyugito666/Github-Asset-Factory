#!/usr/bin/env python3
# File ini sekarang ada di dalam src/

import sys
import logging
import random
import asyncio
import os
from typing import List

# --- IMPORT DARI DALAM 'src' ---
# Panggil setup_logging DARI config SEBELUM import lain yg log
from .config import TELEGRAM_BOT_TOKEN, validate_config, setup_logging # Pakai titik (.)
setup_logging(is_controller=False) # Worker selalu False
logger = logging.getLogger(__name__)

try:
    from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton, BotCommand
    from telegram.ext import Application, CommandHandler, ContextTypes, CallbackQueryHandler, MessageHandler, filters
except ImportError:
    logger.critical("Failed to import python-telegram-bot. Install: pip install python-telegram-bot"); sys.exit(1)

from .services.llm_service import generate_persona_data # Pakai titik (.)
from .services.telegram_service import send_persona_to_telegram, send_text_message # Pakai titik (.)
from .modules.gmail_trick import ( # Pakai titik (.)
    generate_dot_tricks, load_gmail_list,
    add_variation_to_history, get_generated_variations, get_stats
)
# --------------------------------

# --- LIST INI DIPERBARUI & DIORGANISIR ULANG ---
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
# Total: 40 Persona
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
    # is_persistent=False agar tidak nyangkut
    return ReplyKeyboardMarkup(
        keyboard,
        resize_keyboard=True,
        is_persistent=False, # <-- Keyboard tidak persisten
        one_time_keyboard=False # Bisa dipanggil lagi
    )

async def start_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_name = update.effective_user.first_name
    message = f"👋 Halo, **{user_name}**!\n\n🤖 **GitHub Asset Generator Bot**\n🔥 AI: Multi-Provider (Latency Based)\n\n**Quick Actions:**\n• 🎲 Random - Generate persona acak\n• 📋 List Persona - Pilih persona spesifik\n• 📧 Dot Trick - Generate variasi Gmail acak\n• ℹ️ Info - Tentang bot\n• 📊 Stats - Status AI keys & Dot Trick\n\n_Tap ikon menu keyboard jika perlu._" # Update AI info
    await update.message.reply_text(message, reply_markup=get_main_keyboard(), parse_mode='Markdown')

async def info_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Mention multiple providers
    message = "ℹ️ **GitHub Asset Generator Bot**\n\nBot ini menggunakan AI (Gemini, Cohere, Mistral, dll. via Router) untuk generate:\n• Profile data developer realistis\n• README.md profesional\n• Code snippets & scripts\n• Config files\n• Dotfiles\n• Gmail dot trick variations (1 acak per klik)\n\n**AI Models:**\n• Menggunakan LiteLLM Router untuk memilih model tercepat dari provider yang dikonfigurasi.\n\n**Send Methods:**\n• Text: Code block di chat\n\nMethod dipilih otomatis sesuai persona type."
    await update.message.reply_text(message, parse_mode='Markdown', reply_markup=get_main_keyboard())

async def stats_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Update to show router info? LiteLLM router doesn't easily expose simple stats like KeyPool did.
    # Keep it simple for now, just show Gemini if keys exist & Dot Trick stats.
    from .services.llm_service import GEMINI_API_KEYS # Check if keys exist
    message = "📊 **Bot Statistics**\n\n"
    if GEMINI_API_KEYS: # Check Gemini keys existence as a proxy for AI being configured
         # Could add more checks for other providers if needed
         message += "**AI Providers (via LiteLLM Router):**\n"
         message += "• Status: Router Active (Latency-based)\n"
         # Note: Detailed key status per provider is complex with Router
         # message += f"• Gemini Keys Configured: {len(GEMINI_API_KEYS)}\n\n" # Example
    else:
        message += "**AI Providers:**\n• No valid AI keys detected in config.\n\n"

    stats = get_stats() # Fungsi ini dari modules.gmail_trick
    message += f"**Gmail Dot Trick:**\n• Total Emails (gmail.txt): {stats['total_emails_in_file']}\n• Emails with History: {stats['emails_with_variations']}\n• Total Variations Generated: {stats['total_variations_generated']}\n\n"
    message += "_Router automatically manages API keys & fallback._"
    await update.message.reply_text(message, parse_mode='Markdown', reply_markup=get_main_keyboard())


async def dot_trick_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Tampilkan list email dari gmail.txt tanpa status."""
    try:
        all_emails = load_gmail_list()
        if not all_emails:
            # Pastikan target reply ada
            reply_target = update.message if hasattr(update, 'message') else update
            await reply_target.reply_text("⚠️ **File gmail.txt tidak ditemukan atau kosong!**", reply_markup=get_main_keyboard()); return

        keyboard = []
        for i, email in enumerate(all_emails[:30]): keyboard.append([InlineKeyboardButton(f"{email[:35]}", callback_data=f"dottrick_{i}")])
        if len(all_emails) > 30: keyboard.append([InlineKeyboardButton(f"... +{len(all_emails)-30} more emails", callback_data="dummy")])
        keyboard.append([InlineKeyboardButton("📊 View Stats", callback_data="dottrick_stats")]); keyboard.append([InlineKeyboardButton("❌ Batal", callback_data="cancel")])
        reply_markup = InlineKeyboardMarkup(keyboard)

        # Target edit/reply adalah message asli
        edit_target = update.message if hasattr(update, 'message') else update
        try:
            # Coba edit jika ini dari callback 'backtolist'
            await edit_target.edit_text(f"📧 **Pilih Email untuk Generate Variasi Acak:**\n\n_Setiap klik akan menghasilkan 1 variasi baru._", reply_markup=reply_markup, parse_mode='Markdown')
        except AttributeError: # Jika dipanggil dari command / text, gunakan reply_text
            await edit_target.reply_text(f"📧 **Pilih Email untuk Generate Variasi Acak:**\n\n_Setiap klik akan menghasilkan 1 variasi baru._", reply_markup=reply_markup, parse_mode='Markdown')
        except Exception as e_edit: # Tangkap error edit lain
             logger.warning(f"Failed to edit message in dot_trick_handler: {e_edit}. Replying instead.")
             await edit_target.reply_text(f"📧 **Pilih Email untuk Generate Variasi Acak:**\n\n_Setiap klik akan menghasilkan 1 variasi baru._", reply_markup=reply_markup, parse_mode='Markdown')

    except Exception as e:
        logger.error(f"Error di dot_trick_handler: {e}", exc_info=True)
        reply_target = update.message if hasattr(update, 'message') else update
        await reply_target.reply_text(f"❌ Error memuat list email: {str(e)}", reply_markup=get_main_keyboard())


async def handle_text_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle pesan teks biasa."""
    if not update.message or not update.message.text: return # Abaikan jika tidak ada teks
    text = update.message.text.strip()

    if text == "🎲 Random":
        persona_type = random.choice(ALL_PERSONAS)
        await update.message.reply_text(f"⏳ Generating random persona: **{persona_type.replace('_', ' ').title()}**...", parse_mode='Markdown')
        # Jalankan di background
        context.application.create_task(trigger_generation_task(update.message.chat_id, persona_type))
    elif text == "📋 List Persona":
        # Buat tombol inline
        keyboard = [[InlineKeyboardButton(p.replace('_', ' ').title(), callback_data=f"persona_{p}")] for p in ALL_PERSONAS]
        keyboard.append([InlineKeyboardButton("❌ Batal", callback_data="cancel")])
        await update.message.reply_text("📋 **Pilih Persona:**", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
    elif text == "📧 Dot Trick":
        await dot_trick_handler(update, context) # Panggil handler dot trick
    elif text == "ℹ️ Info":
        await info_handler(update, context) # Panggil handler info
    elif text == "📊 Stats":
        await stats_handler(update, context) # Panggil handler stats
    # Abaikan teks lain yang tidak cocok

async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle tombol inline."""
    query = update.callback_query
    if not query or not query.data: return # Abaikan jika tidak ada data

    try:
        await query.answer() # Jawab callback secepatnya
    except Exception as e:
        logger.warning(f"Failed to answer callback query {query.id}: {e}")

    data = query.data

    if data == "cancel":
        try: await query.edit_message_text("❌ Operasi dibatalkan.", reply_markup=None)
        except Exception: await query.message.reply_text("❌ Operasi dibatalkan.", reply_markup=get_main_keyboard()); return
    elif data == "dummy":
        await query.answer("⚠️ Terlalu banyak item untuk ditampilkan semua.", show_alert=True); return
    elif data == "random_generate":
        persona_type = random.choice(ALL_PERSONAS); await trigger_generation(query, persona_type, context)
    elif data.startswith("persona_"):
        persona_type = data.replace("persona_", ""); await trigger_generation(query, persona_type, context)
    elif data == "dottrick_stats":
        await show_dot_trick_stats(query) # Panggil fungsi stats
    elif data.startswith("dottrick_"):
        try: index = int(data.replace("dottrick_", "")); await trigger_dot_trick_generation(query, index, context)
        except ValueError: logger.warning(f"Invalid dottrick index in callback data: {data}")

async def trigger_generation(query, persona_type: str, context: ContextTypes.DEFAULT_TYPE):
    """Trigger AI persona generation (setelah tombol persona ditekan)."""
    chat_id = query.message.chat_id
    persona_display = persona_type.replace('_', ' ').title()
    try:
        await query.edit_message_text(f"⏳ **Generating: {persona_display}**\n\n_AI Chaining in progress... Please wait._", parse_mode='Markdown', reply_markup=None)
    except Exception as e:
        logger.warning(f"Failed to edit message on trigger_generation: {e}")
        # Kirim pesan baru jika edit gagal (misal: pesan terlalu lama)
        await context.bot.send_message(chat_id=chat_id, text=f"⏳ **Generating: {persona_display}**...", parse_mode='Markdown')
    # Jalankan task utama di background
    context.application.create_task(trigger_generation_task(chat_id, persona_type))

async def trigger_generation_task(chat_id: int, persona_type: str):
    """Run AI persona generation in background."""
    logger.info(f"Starting generation task for persona: {persona_type}, chat_id: {chat_id}")
    try:
        data = await asyncio.to_thread(generate_persona_data, persona_type)
        if not data:
            logger.error(f"AI generation failed for persona: {persona_type}")
            await asyncio.to_thread(send_text_message, "❌ AI generation failed. Check worker logs for details.", str(chat_id))
            return
        logger.info(f"AI generation successful for persona: {persona_type}. Sending to Telegram...")
        await asyncio.to_thread(send_persona_to_telegram, persona_type, data, str(chat_id))
    except Exception as e:
        logger.error(f"Error in trigger_generation_task for {persona_type}: {e}", exc_info=True)
        await asyncio.to_thread(send_text_message, f"❌ An error occurred during generation: {str(e)[:200]}", str(chat_id))

async def trigger_dot_trick_generation(query, index: int, context: ContextTypes.DEFAULT_TYPE):
    """Trigger dot trick generation (setelah tombol email ditekan)."""
    chat_id = str(query.message.chat_id);
    try:
        gmail_list = load_gmail_list()
        if index >= len(gmail_list):
            await query.answer("❌ Email index tidak valid.", show_alert=True); return
        email = gmail_list[index]
    except Exception as e:
        logger.error(f"Error getting email for dot trick index {index}: {e}")
        await query.answer("❌ Gagal memproses pilihan email.", show_alert=True); return

    try:
        await query.edit_message_text(f"⏳ **Generating variasi acak untuk:**\n`{email}`\n\n_Processing..._", parse_mode='Markdown', reply_markup=None)
    except Exception as e:
        logger.warning(f"Failed to edit message on trigger_dot_trick_generation: {e}")
        await context.bot.send_message(chat_id=chat_id, text=f"⏳ Generating variasi acak untuk: `{email}`...", parse_mode='Markdown')
    # Jalankan task utama di background
    context.application.create_task(run_dot_trick_task(email=email, chat_id=chat_id))

async def show_dot_trick_stats(query):
    """Tampilkan statistik dot trick."""
    try:
        stats = get_stats()
        message = f"📊 **Gmail Dot Trick Statistics**\n\n📧 Total Emails (gmail.txt): {stats['total_emails_in_file']}\n📈 Emails with Variations: {stats['emails_with_variations']}\n🔢 Total Variations Generated: {stats['total_variations_generated']}\n\n"
        keyboard = [[InlineKeyboardButton("🔙 Kembali ke List Email", callback_data="dottrick_backtolist")]]; reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(message, parse_mode='Markdown', reply_markup=reply_markup)
    except Exception as e:
        logger.error(f"Error showing dot trick stats: {e}", exc_info=True)
        await query.answer("❌ Gagal memuat statistik.", show_alert=True)
        # Coba kirim pesan error jika edit gagal
        try: await query.message.reply_text("❌ Gagal memuat statistik dot trick.")
        except Exception: pass

async def handle_dottrick_backtolist(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Kembali ke menu pemilihan email dot trick dari stats."""
    query = update.callback_query;
    if not query: return
    await query.answer()
    try:
        # Edit pesan sebelum memanggil handler utama
        await query.edit_message_text("🔄 Memuat ulang list email...", reply_markup=None)
    except Exception as e:
        logger.warning(f"Failed to edit message on backtolist: {e}")
        # Jika edit gagal, coba kirim pesan baru sbg indikator
        await query.message.reply_text("Memuat list email...")

    # Panggil handler utama dot trick, gunakan message object dari query
    await dot_trick_handler(query.message, context)

async def run_dot_trick_task(email: str, chat_id: str):
    """Generate 1 variasi acak, simpan history, kirim ke Telegram."""
    try:
        logger.info(f"Running dot trick task for {email}")
        existing_variations = await asyncio.to_thread(get_generated_variations, email)
        new_variation = await asyncio.to_thread(generate_dot_tricks, email, existing_variations)
        if new_variation:
            await asyncio.to_thread(add_variation_to_history, email, new_variation)
            message = f"✅ **Variasi Gmail Dot Trick Baru**\n\n📧 Original: `{email}`\n🆕 Variasi: `{new_variation}`"
            logger.info(f"Successfully generated dot trick for {email}: {new_variation}")
        else:
            message = f"⚠️ **Gagal Generate Variasi**\n\n📧 Email: `{email}`\n❌ Username mungkin terlalu pendek atau tidak ada variasi baru ditemukan."
            logger.warning(f"Failed to generate new dot trick variation for {email}")
        await asyncio.to_thread(send_text_message, message, chat_id)
    except Exception as e:
        logger.error(f"Error in run_dot_trick_task for {email}: {e}", exc_info=True)
        await asyncio.to_thread(send_text_message, f"❌ Error generating dot trick for `{email}`: {str(e)[:200]}", chat_id)

async def setup_bot_commands(app: Application):
    """Setel command bot."""
    commands = [
        BotCommand("start","Mulai bot & tampilkan menu"),
        BotCommand("info","Info tentang bot"),
        BotCommand("stats","Status AI & Dot Trick")
    ]
    try:
        await app.bot.set_my_commands(commands)
        logger.info("Bot commands updated successfully.")
    except Exception as e:
        logger.error(f"Failed to set bot commands: {e}")

async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    """Handle error global."""
    logger.error(f"Update {update} caused error: {context.error}", exc_info=context.error)
    # Coba kirim pesan error ke user jika memungkinkan
    if isinstance(update, Update) and update.effective_chat:
         try:
             await context.bot.send_message(
                 chat_id=update.effective_chat.id,
                 text=f"❌ Terjadi error internal. Cek log worker untuk detail."
             )
         except Exception as e_send:
              logger.error(f"Failed to send error message to chat {update.effective_chat.id}: {e_send}")


def main():
    """Fungsi utama untuk worker bot."""
    try:
        logger.info("=== Initializing Bot Worker (Subprocess) ===")
        validate_config() # Validasi config dari config.py

        application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

        # Tambahkan handlers
        application.add_handler(CommandHandler("start", start_handler))
        application.add_handler(CommandHandler("info", info_handler))
        application.add_handler(CommandHandler("stats", stats_handler))
        application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text_message))
        # Handler callback spesifik harus SEBELUM handler umum
        application.add_handler(CallbackQueryHandler(handle_dottrick_backtolist, pattern="^dottrick_backtolist$"))
        application.add_handler(CallbackQueryHandler(callback_handler)) # Handler umum terakhir
        application.add_error_handler(error_handler)

        # Setel command setelah init
        application.post_init = setup_bot_commands

        logger.info("🚀 Bot worker ready. Starting polling...")
        application.run_polling(allowed_updates=Update.ALL_TYPES) # Poll semua jenis update

    except ImportError as e:
         logger.critical(f"ImportError during initialization: {e}. Make sure all dependencies are installed.")
         sys.exit(1)
    except Exception as e:
        logger.critical(f"FATAL ERROR during worker initialization or runtime: {e}", exc_info=True)
        sys.exit(1)

if __name__ == "__main__":
    main()
