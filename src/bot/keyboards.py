"""
Keyboard Layouts untuk Telegram Bot

Semua ReplyKeyboardMarkup dan InlineKeyboardMarkup didefinisikan di sini.
"""

from telegram import ReplyKeyboardMarkup, KeyboardButton


def get_main_keyboard():
    """Main menu keyboard dengan fitur utama bot."""
    keyboard = [
        [KeyboardButton("🎲 Random"), KeyboardButton("📋 List Persona")],
        [KeyboardButton("📧 Dot Trick"), KeyboardButton("ℹ️ Info")],
        [KeyboardButton("📊 Stats"), KeyboardButton("🔧 Proxy Menu")]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=False)


def get_proxy_menu_keyboard():
    """Proxy management menu keyboard."""
    keyboard = [
        [KeyboardButton("🌐 IP Auth"), KeyboardButton("⬇️ Download Proxy")],
        [KeyboardButton("🔄 Convert Format"), KeyboardButton("✅ Test Proxy")],
        [KeyboardButton("🚀 Full Auto Sync"), KeyboardButton("🔙 Back to Main")]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=False)
