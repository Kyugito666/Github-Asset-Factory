import os
import json
import logging
from typing import Set, List, Dict, Tuple

# --- IMPORT DARI DALAM 'src' & PATH ---
from ..config import ROOT_DIR # Ambil ROOT_DIR
# -------------------------------------

logger = logging.getLogger(__name__)

# --- PATH FILE DIUBAH ---
HISTORY_FILE_NAME = "persona_history.json"
HISTORY_FILE_PATH = os.path.join(ROOT_DIR, 'history', HISTORY_FILE_NAME)
# -------------------------

# --- Semua fungsi (load_history_data, load_used_data, add_to_history) ---
# --- Ubah path file dari HISTORY_FILE jadi HISTORY_FILE_PATH ---
def load_history_data() -> List[Dict]:
    if not os.path.exists(HISTORY_FILE_PATH): return [] # Ubah path
    try:
        with open(HISTORY_FILE_PATH, 'r', encoding='utf-8') as f: # Ubah path
            data = json.load(f); return data if isinstance(data, list) else []
    except (json.JSONDecodeError, IOError) as e: logger.error(f"Error loading persona history: {e}"); return []
def load_used_data() -> Tuple[Set[str], Set[str]]: /* ... (logika sama, panggil load_history_data) ... */
def add_to_history(username: str, name: str):
    if not username or not name: logger.warning(f"Skip add history: missing data (U:{username}, N:{name})"); return
    data = load_history_data(); new_entry = {"username": username, "name": name}; data.append(new_entry)
    try:
        os.makedirs(os.path.join(ROOT_DIR, 'history'), exist_ok=True) # Buat folder jika belum
        with open(HISTORY_FILE_PATH, 'w', encoding='utf-8') as f: json.dump(data, f, indent=2, ensure_ascii=False) # Ubah path
        logger.info(f"Added '{username}' / '{name}' to persona history.")
    except IOError as e: logger.error(f"Error saving persona history: {e}")
