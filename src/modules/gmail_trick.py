import os
import logging
import json
import random
from datetime import datetime
from typing import List, Dict, Set

# --- IMPORT DARI DALAM 'src' & PATH ---
from ..config import ROOT_DIR # Ambil ROOT_DIR
# -------------------------------------

logger = logging.getLogger(__name__)

# --- PATH FILE DIUBAH ---
GMAIL_FILE_NAME = "gmail.txt"
HISTORY_FILE_NAME = "dot_trick_history.json"
GMAIL_FILE_PATH = os.path.join(ROOT_DIR, 'data', GMAIL_FILE_NAME)
HISTORY_FILE_PATH = os.path.join(ROOT_DIR, 'history', HISTORY_FILE_NAME)
# -------------------------

# HAPUS: OUTPUT_DIR

# --- Fungsi load_history, save_history, add_variation_to_history, get_generated_variations ---
# --- Ubah path file dari HISTORY_FILE jadi HISTORY_FILE_PATH ---
def load_history() -> Dict[str, List[str]]:
    if not os.path.exists(HISTORY_FILE_PATH): return {} # Ubah path
    try:
        with open(HISTORY_FILE_PATH, 'r', encoding='utf-8') as f: # Ubah path
            data = json.load(f); return {k: v for k, v in data.items() if isinstance(v, list)} if isinstance(data, dict) else {}
    except (json.JSONDecodeError, IOError) as e: logger.error(f"Error loading dot trick history: {e}"); return {}
def save_history(history: Dict[str, List[str]]):
    try:
        os.makedirs(os.path.join(ROOT_DIR, 'history'), exist_ok=True) # Buat folder jika belum
        with open(HISTORY_FILE_PATH, 'w', encoding='utf-8') as f: json.dump(history, f, indent=2, ensure_ascii=False) # Ubah path
    except IOError as e: logger.error(f"Error saving dot trick history: {e}")
def add_variation_to_history(email: str, new_variation: str): /* ... (logika sama, panggil save_history) ... */
def get_generated_variations(email: str) -> Set[str]: /* ... (logika sama, panggil load_history) ... */

# --- Fungsi load_gmail_list ---
# --- Ubah path file dari GMAIL_FILE jadi GMAIL_FILE_PATH ---
def load_gmail_list() -> List[str]:
    if not os.path.exists(GMAIL_FILE_PATH): logger.warning(f"{GMAIL_FILE_NAME} not found in data/. Check path."); return [] # Ubah path & pesan
    emails = []
    try:
        os.makedirs(os.path.join(ROOT_DIR, 'data'), exist_ok=True) # Buat folder jika belum
        with open(GMAIL_FILE_PATH, 'r', encoding='utf-8') as f: # Ubah path
            for line_num, line in enumerate(f, 1):
                line = line.strip().strip('~').strip()
                if not line or line.startswith('#'): continue
                if '@gmail.com' not in line.lower(): continue
                if line.count('@') != 1: continue
                emails.append(line.lower())
    except Exception as e: logger.error(f"Error reading gmail file: {e}"); return []
    unique_emails = list(dict.fromkeys(emails))
    logger.info(f"Loaded {len(unique_emails)} unique Gmail addresses from data/{GMAIL_FILE_NAME}")
    return unique_emails

# --- Fungsi generate_dot_tricks ---
# --- TIDAK BERUBAH ---
def generate_dot_tricks(email: str, existing_variations: Set[str]) -> str | None: /* ... sama ... */

# --- Fungsi get_stats ---
# --- TIDAK BERUBAH (tetap panggil load_history & load_gmail_list) ---
def get_stats() -> Dict: /* ... sama ... */
