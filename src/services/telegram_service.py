import requests
import os
import time
import logging
from typing import Optional, List

# --- IMPORT DARI DALAM 'src' & PATH ---
# Hapus TEMP_FILES_DIR
from ..config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, PROXY_POOL, ROOT_DIR
# -------------------------------------

logger = logging.getLogger(__name__)

# --- SEMUA FUNGSI (format_profile_message, format_code_message, send_text_message, send_persona_to_telegram) ---
# --- TIDAK BERUBAH SAMA SEKALI DARI VERSI SEBELUMNYA (yang sudah hapus file send) ---
# ... (copy paste SEMUA fungsi dari telegram_service.py lama) ...
