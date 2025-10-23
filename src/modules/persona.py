import os
import json
import logging
from typing import Set, List, Dict, Tuple

logger = logging.getLogger(__name__)

# --- PATH DIPERBARUI ---
# Get the directory containing this script (src/modules)
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
# Go up two levels to the root directory
ROOT_DIR = os.path.dirname(os.path.dirname(SCRIPT_DIR))

HISTORY_FILE = os.path.join(ROOT_DIR, "history", "persona_history.json")
# ---------------------

def load_history_data() -> List[Dict]:
    """Load list of persona dicts dari file JSON."""
    if not os.path.exists(HISTORY_FILE):
        return []
    
    try:
        with open(HISTORY_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
            if isinstance(data, list):
                return data
            return []
    except (json.JSONDecodeError, IOError) as e:
        logger.error(f"Error loading persona history: {e}")
        return []

def load_used_data() -> Tuple[Set[str], Set[str]]:
    """
    Load data terpakai (username DAN name) ke dalam Set 
    untuk O(1) lookup.
    """
    data = load_history_data()
    
    used_usernames = {entry.get('username') for entry in data if entry.get('username')}
    used_names = {entry.get('name') for entry in data if entry.get('name')}
    
    logger.info(f"Loaded {len(used_usernames)} used usernames and {len(used_names)} used names.")
    return used_usernames, used_names

def add_to_history(username: str, name: str):
    """Tambah persona baru ke file history."""
    if not username or not name:
        logger.warning(f"Attempted to add entry with missing data. Skipping. (U: {username}, N: {name})")
        return
        
    data = load_history_data()
    
    # Buat entri baru
    new_entry = {
        "username": username,
        "name": name
    }
    
    data.append(new_entry)
    
    try:
        # Pastikan direktori history ada
        os.makedirs(os.path.dirname(HISTORY_FILE), exist_ok=True)
        with open(HISTORY_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        logger.info(f"Added '{username}' / '{name}' to persona history.")
    except IOError as e:
        logger.error(f"Error saving persona history: {e}")
