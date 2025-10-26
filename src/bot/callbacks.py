"""
Telegram Bot Callback Query Handlers

Menangani:
- Inline keyboard callbacks
- Persona selection
- Dot trick selection & pagination
- Cancel actions
"""

import logging

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from telegram.constants import ParseMode

from ..modules.gmail import load_gmail_list, generate_dot_tricks, get_generated_variations, add_variation_to_history, get_stats

from .keyboards import get_main_keyboard

logger = logging.getLogger(__name__)


# ============================================================
# DOT TRICK HANDLERS
# ============================================================

async def dot_trick_handler(update: Update, context: ContextTypes.DEFAULT_TYPE, page: int = 0):
    """
    Handler untuk menampilkan daftar email untuk dot trick dengan pagination.
    
    Args:
        update: Update object dari Telegram
        context: Context dari bot
        page: Halaman saat ini (0-indexed)
    """
    is_callback = update.callback_query is not None
    target_message = update.callback_query.message if is_callback else update.message
    if not target_message:
        logger.error("dot_trick_handler: Cannot find message object.")
        return

    try:
        all_emails = load_gmail_list()
        if not all_emails:
            await target_message.reply_text("⚠️ `data/gmail.txt` kosong atau tidak ditemukan!", 
                                           reply_markup=get_main_keyboard())
            return

        # Pagination logic
        items_per_page = 50
        total_pages = (len(all_emails) + items_per_page - 1) // items_per_page
        start_idx = page * items_per_page
        end_idx = min(start_idx + items_per_page, len(all_emails))
        
        current_page_emails = all_emails[start_idx:end_idx]

        # Build keyboard
        keyboard = []
        for i, email in enumerate(current_page_emails):
            actual_index = start_idx + i
            display_email = email if len(email) <= 40 else email[:37] + "..."
            keyboard.append([InlineKeyboardButton(f"📧 {display_email}", 
                                                  callback_data=f"dottrick_{actual_index}")])

        # Navigation buttons
        nav_buttons = []
        if page > 0:
            nav_buttons.append(InlineKeyboardButton("⬅️ Prev", callback_data=f"dottrick_page_{page-1}"))
        if page < total_pages - 1:
            nav_buttons.append(InlineKeyboardButton("➡️ Next", callback_data=f"dottrick_page_{page+1}"))
        
        if nav_buttons:
            keyboard.append(nav_buttons)

        # Stats & Cancel buttons
        keyboard.append([InlineKeyboardButton("📊 Lihat Statistik", callback_data="dottrick_stats")])
        keyboard.append([InlineKeyboardButton("❌ Batal", callback_data="cancel")])
        
        reply_markup = InlineKeyboardMarkup(keyboard)

        message_text = (f"📧 **Gmail Dot Trick**\n"
                       f"Pilih email untuk generate variasi baru:\n\n"
                       f"Halaman {page+1}/{total_pages} (Total: {len(all_emails)} emails)")

        if is_callback:
             await update.callback_query.edit_message_text(message_text, reply_markup=reply_markup, 
                                                          parse_mode=ParseMode.MARKDOWN)
        else:
             await target_message.reply_text(message_text, reply_markup=reply_markup, 
                                            parse_mode=ParseMode.MARKDOWN)

    except Exception as e:
        logger.error(f"Error in dot_trick_handler: {e}", exc_info=True)
        await target_message.reply_text(f"❌ Error menampilkan daftar email: {str(e)}", 
                                       reply_markup=get_main_keyboard())


async def trigger_dot_trick_generation(query, index: int, context: ContextTypes.DEFAULT_TYPE):
    """
    Trigger generation dot trick untuk email tertentu.
    
    Args:
        query: CallbackQuery object
        index: Index email di gmail list
        context: Bot context
    """
    if not query or not query.message:
        logger.error("Cannot trigger dot trick: invalid query/message")
        return
    
    chat_id = str(query.message.chat_id)
    
    try:
        gmail_list = load_gmail_list()
        if index < 0 or index >= len(gmail_list):
            await query.answer("❌ Index email tidak valid.", show_alert=True)
            await query.edit_message_text("❌ Error: Email tidak ditemukan. Silakan coba lagi.", 
                                         reply_markup=None)
            return
        email = gmail_list[index]
    except Exception as e:
        logger.error(f"Error getting email for dot trick index {index}: {e}")
        await query.answer("❌ Gagal memproses pilihan.", show_alert=True)
        await query.edit_message_text(f"❌ Error: {str(e)}", reply_markup=None)
        return

    try:
        await query.edit_message_text(f"⏳ Generating variasi untuk:\n`{email}`...", 
                                     parse_mode=ParseMode.MARKDOWN, reply_markup=None)
    except Exception as e:
        logger.warning(f"Failed edit message for dot trick gen: {e}")
        await context.bot.send_message(chat_id=chat_id, 
                                      text=f"⏳ Generating variasi untuk:\n`{email}`...", 
                                      parse_mode=ParseMode.MARKDOWN)

    context.application.create_task(run_dot_trick_task(email=email, chat_id=chat_id))


async def run_dot_trick_task(email: str, chat_id: str):
    """
    Background task untuk generate dot trick variation.
    
    Args:
        email: Email untuk di-generate
        chat_id: Target chat ID untuk kirim hasil
    """
    import asyncio
    import time
    from ..services.telegram import send_text_message
    
    logger.info(f"Starting dot trick generation task for '{email}' (Chat ID: {chat_id})...")
    start_time = time.time()
    
    try:
        existing = await asyncio.to_thread(get_generated_variations, email)
        new_var = await asyncio.to_thread(generate_dot_tricks, email, existing)
        duration = time.time() - start_time
        logger.info(f"Dot trick generation for '{email}' finished in {duration:.3f}s. "
                   f"Result: {'Found' if new_var else 'Not Found/Failed'}")

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
                           f"❌ Alasan: Username '{username_part}' terlalu pendek "
                           f"(< 2 karakter) untuk dot trick.")
            else:
                message = (f"⚠️ **Tidak Ditemukan Variasi Baru**\n\n"
                           f"📧 Email:\n`{email}`\n\n"
                           f"❌ Mungkin semua kombinasi sudah pernah digenerate atau gagal "
                           f"setelah beberapa percobaan. Cek log server jika perlu.")

        await asyncio.to_thread(send_text_message, message, chat_id)

    except Exception as e:
        duration = time.time() - start_time
        logger.error(f"Error in run_dot_trick_task for '{email}' ({duration:.2f}s): {e}", exc_info=True)
        await asyncio.to_thread(send_text_message, 
            f"❌ Error fatal saat generate dot trick untuk `{email}`: {str(e)[:200]}", chat_id)


async def show_dot_trick_stats(query):
    """Tampilkan statistik dot trick."""
    if not query:
        return
    try:
        await query.answer()
        stats_gmail = get_stats()
        message = (f"📊 **Statistik Gmail Dot Trick**\n\n"
                   f"• Email di `data/gmail.txt`: `{stats_gmail['total_emails_in_file']}`\n"
                   f"• Email dengan History: `{stats_gmail['emails_with_variations']}`\n"
                   f"• Total Variasi Tersimpan: `{stats_gmail['total_variations_generated']}`")

        keyboard = [[InlineKeyboardButton("🔙 Kembali ke Daftar Email", 
                                         callback_data="dottrick_backtolist")]]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await query.edit_message_text(message, parse_mode=ParseMode.MARKDOWN, reply_markup=reply_markup)
    except Exception as e:
        logger.error(f"Error showing dot trick stats: {e}", exc_info=True)
        await query.answer("❌ Gagal menampilkan statistik.", show_alert=True)


async def handle_dottrick_backtolist(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler untuk back to list dari stats."""
    query = update.callback_query
    if not query:
        return
    try:
        await query.answer()
        await query.edit_message_text("🔄 Memuat ulang daftar email...", reply_markup=None)
    except Exception as e:
        logger.warning(f"Minor error editing message on backtolist: {e}")

    await dot_trick_handler(update, context, page=0)


# ============================================================
# MAIN CALLBACK HANDLER
# ============================================================

async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Main callback query handler - router untuk semua callback.
    
    Menangani:
    - cancel: Batalkan operasi
    - persona_*: Pilih persona type
    - random_generate: Generate random persona
    - dottrick_page_*: Pagination dot trick
    - dottrick_*: Generate dot trick untuk email
    - dottrick_stats: Tampilkan stats
    - dottrick_backtolist: Kembali ke list
    """
    query = update.callback_query
    if not query or not query.data:
        return

    try:
        await query.answer()
    except Exception as e:
        logger.warning(f"Failed to answer callback query (might be expired): {e}")

    data = query.data

    # Import trigger_generation dari handlers (avoid circular import)
    from .handlers import trigger_generation, ALL_PERSONAS
    import random

    # CANCEL
    if data == "cancel":
        try:
            await query.edit_message_text("❌ Operasi dibatalkan.", reply_markup=None)
        except Exception:
             if query.message:
                 await query.message.reply_text("❌ Operasi dibatalkan.", reply_markup=get_main_keyboard())
             else:
                 logger.error("Callback 'cancel' failed: No message to reply to/edit.")
    
    # DOT TRICK PAGINATION
    elif data.startswith("dottrick_page_"):
        try:
            page_num = int(data.replace("dottrick_page_", ""))
            await dot_trick_handler(update, context, page=page_num)
        except ValueError:
            logger.error(f"Invalid page number in callback: {data}")
            await query.answer("❌ Halaman tidak valid.", show_alert=True)
    
    # RANDOM GENERATE
    elif data == "random_generate":
        persona_type = random.choice(ALL_PERSONAS)
        await trigger_generation(query, persona_type, context)
    
    # PERSONA SELECTION
    elif data.startswith("persona_"):
        persona_type = data.replace("persona_", "")
        await trigger_generation(query, persona_type, context)
    
    # DOT TRICK STATS
    elif data == "dottrick_stats":
        await show_dot_trick_stats(query)
    
    # DOT TRICK GENERATION
    elif data.startswith("dottrick_"):
        try:
             index_str = data.replace("dottrick_", "")
             if index_str.isdigit():
                 index = int(index_str)
                 await trigger_dot_trick_generation(query, index, context)
             elif index_str == "backtolist":
                  pass  # Handled by separate handler
             else:
                  logger.error(f"Invalid non-numeric index in dottrick callback: {data}")
                  await query.answer("❌ Data callback tidak valid.", show_alert=True)
        except ValueError:
             logger.error(f"Invalid index format in dottrick callback: {data}")
             await query.answer("❌ Format data callback salah.", show_alert=True)
    
    # UNKNOWN CALLBACK
    else:
        logger.warning(f"Unhandled callback data: {data}")
        await query.answer("Aksi tidak dikenali.")
