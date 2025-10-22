import os
import json
import logging
from typing import Set, List, Dict, Tuple

# --- IMPORT DARI DALAM 'src' & PATH ---
# Import ROOT_DIR dari config untuk path file
try:
    from ..config import ROOT_DIR
except ImportError:
    # Fallback jika dijalankan standalone (meski seharusnya tidak)
    ROOT_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    print("Warning: Could not import ROOT_DIR from config, using fallback path.")
# -------------------------------------

logger = logging.getLogger(__name__)

# --- PATH FILE DIUBAH (relatif ke ROOT_DIR) ---
HISTORY_FILE_NAME = "persona_history.json"
HISTORY_FILE_PATH = os.path.join(ROOT_DIR, 'history', HISTORY_FILE_NAME)
# -------------------------

# ============================================================
# HISTORY MANAGEMENT (Path Diubah)
# ============================================================
def load_history_data() -> List[Dict]:
    """Load list of persona dicts ({"username": "...", "name": "..."}) dari history file."""
    # Pastikan folder history ada
    history_dir = os.path.dirname(HISTORY_FILE_PATH)
    if not os.path.exists(history_dir):
        logger.info(f"History directory not found, creating: {history_dir}")
        try:
            os.makedirs(history_dir, exist_ok=True)
        except OSError as e:
            logger.error(f"Failed to create history directory {history_dir}: {e}")
            return [] # Gagal buat folder, return empty

    # Baca file history
    if not os.path.exists(HISTORY_FILE_PATH):
        logger.info(f"Persona history file not found: {HISTORY_FILE_PATH}. Starting fresh.")
        return [] # File belum ada, return empty

    try:
        with open(HISTORY_FILE_PATH, 'r', encoding='utf-8') as f:
            data = json.load(f)
            # Validasi format dasar (harus list)
            if isinstance(data, list):
                 # Validasi isi list (harus dict dengan 'username' dan 'name')
                 valid_data = []
                 for i, entry in enumerate(data):
                     if isinstance(entry, dict) and 'username' in entry and 'name' in entry:
                         valid_data.append(entry)
                     else:
                         logger.warning(f"Invalid entry format at index {i} in persona history, skipping: {entry}")
                 return valid_data
            else:
                 logger.warning(f"Persona history file {HISTORY_FILE_PATH} is not a valid JSON list. Resetting history.")
                 return []
    except (json.JSONDecodeError, IOError) as e:
        logger.error(f"Error loading persona history from {HISTORY_FILE_PATH}: {e}")
        return [] # Gagal baca/parse, return empty

def load_used_data() -> Tuple[Set[str], Set[str]]:
    """
    Load data terpakai (username DAN name) ke dalam Set
    untuk O(1) lookup.
    """
    data = load_history_data() # Load data yang sudah divalidasi

    used_usernames = {entry.get('username') for entry in data if entry.get('username')}
    used_names = {entry.get('name') for entry in data if entry.get('name')}

    # Log hanya jika ada data yang di-load
    if used_usernames or used_names:
        logger.info(f"Loaded {len(used_usernames)} used usernames and {len(used_names)} used names from persona history.")
    else:
        logger.info("Persona history is empty or contains no valid entries.")

    return used_usernames, used_names

def add_to_history(username: str, name: str):
    """Tambah persona baru ke file history."""
    if not username or not name:
        logger.warning(f"Attempted to add persona history entry with missing data. Skipping. (Username: '{username}', Name: '{name}')")
        return

    data = load_history_data() # Load data terbaru

    # Cek duplikat sebelum menambah (safety net, meski llm_service sudah cek)
    existing_usernames = {entry.get('username') for entry in data}
    existing_names = {entry.get('name') for entry in data}
    if username in existing_usernames or name in existing_names:
         logger.warning(f"Attempted to add duplicate persona to history (should have been caught earlier). Skipping. (Username: '{username}', Name: '{name}')")
         return

    # Buat entri baru
    new_entry = {
        "username": username,
        "name": name
        # Bisa tambah timestamp jika perlu: "added_at": datetime.now().isoformat()
    }

    data.append(new_entry) # Tambah ke list

    # Simpan kembali ke file
    history_dir = os.path.dirname(HISTORY_FILE_PATH)
    try:
        # Buat folder jika belum ada (safety check)
        os.makedirs(history_dir, exist_ok=True)
        with open(HISTORY_FILE_PATH, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        logger.info(f"Added '{username}' / '{name}' to persona history.")
    except IOError as e:
        logger.error(f"Error saving persona history to {HISTORY_FILE_PATH}: {e}")
    except Exception as e: # Tangkap error lain
         logger.error(f"Unexpected error saving persona history: {e}", exc_info=True)

# Contoh penggunaan (jika file dijalankan langsung)
if __name__ == "__main__":
    # Setup basic logging jika dijalankan standalone
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    logger.info("Running persona_history.py standalone for testing...")

    # Test loading
    print("\n--- Testing Load ---")
    users, names = load_used_data()
    print(f"Loaded Usernames: {users}")
    print(f"Loaded Names: {names}")

    # Test adding
    print("\n--- Testing Add ---")
    test_user = f"testuser_{random.randint(1000, 9999)}"
    test_name = f"Test User {random.randint(1000, 9999)}"
    print(f"Attempting to add: {test_name} / {test_user}")
    add_to_history(test_user, test_name)

    # Test loading again
    print("\n--- Testing Load Again ---")
    users_after, names_after = load_used_data()
    print(f"Loaded Usernames: {users_after}")
    print(f"Loaded Names: {names_after}")

    # Test adding duplicate (should be skipped)
    print("\n--- Testing Add Duplicate ---")
    print(f"Attempting to add again: {test_name} / {test_user}")
    add_to_history(test_user, test_name)

    # Test adding missing data (should be skipped)
    print("\n--- Testing Add Missing ---")
    add_to_history("onlyuser", None)
    add_to_history(None, "Only Name")
