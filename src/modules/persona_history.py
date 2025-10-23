import os
import json
import logging
import random
from typing import Set, List, Dict, Tuple

try:
    from ..config import ROOT_DIR
except ImportError:
    ROOT_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    print("Warning: Could not import ROOT_DIR from config, using fallback path.")

logger = logging.getLogger(__name__)

HISTORY_FILE_NAME = "persona_history.json"
HISTORY_FILE_PATH = os.path.join(ROOT_DIR, 'history', HISTORY_FILE_NAME)

# ============================================================
# HISTORY MANAGEMENT
# ============================================================

def load_history_data() -> List[Dict]:
    """Load list of persona dicts from history file."""
    history_dir = os.path.dirname(HISTORY_FILE_PATH)
    if not os.path.exists(history_dir):
        logger.info(f"History directory not found, creating: {history_dir}")
        try:
            os.makedirs(history_dir, exist_ok=True)
        except OSError as e:
            logger.error(f"Failed to create history directory {history_dir}: {e}")
            return []
    
    if not os.path.exists(HISTORY_FILE_PATH):
        logger.info(f"Persona history file not found: {HISTORY_FILE_PATH}. Starting fresh.")
        return []
    
    try:
        with open(HISTORY_FILE_PATH, 'r', encoding='utf-8') as f:
            data = json.load(f)
            if isinstance(data, list):
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
        return []

def load_used_data() -> Tuple[Set[str], Set[str]]:
    """Load used data (username AND name) into Sets for O(1) lookup."""
    data = load_history_data()
    
    used_usernames = {entry.get('username') for entry in data if entry.get('username')}
    used_names = {entry.get('name') for entry in data if entry.get('name')}
    
    if used_usernames or used_names:
        logger.info(f"Loaded {len(used_usernames)} used usernames and {len(used_names)} used names from persona history.")
    else:
        logger.info("Persona history is empty or contains no valid entries.")
    
    return used_usernames, used_names

def add_to_history(username: str, name: str):
    """Add new persona to history file."""
    if not username or not name:
        logger.warning(f"Attempted to add persona history entry with missing data. Skipping. (Username: '{username}', Name: '{name}')")
        return
    
    data = load_history_data()
    
    # Check for duplicates (safety net)
    existing_usernames = {entry.get('username') for entry in data}
    existing_names = {entry.get('name') for entry in data}
    
    if username in existing_usernames or name in existing_names:
        logger.warning(f"Attempted to add duplicate persona to history. Skipping. (Username: '{username}', Name: '{name}')")
        return
    
    new_entry = {
        "username": username,
        "name": name
    }
    
    data.append(new_entry)
    
    history_dir = os.path.dirname(HISTORY_FILE_PATH)
    try:
        os.makedirs(history_dir, exist_ok=True)
        with open(HISTORY_FILE_PATH, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        logger.info(f"Added '{username}' / '{name}' to persona history.")
    except IOError as e:
        logger.error(f"Error saving persona history to {HISTORY_FILE_PATH}: {e}")
    except Exception as e:
        logger.error(f"Unexpected error saving persona history: {e}", exc_info=True)

# ============================================================
# STANDALONE TEST
# ============================================================

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    logger.info("Running persona_history.py standalone for testing...")
    
    print("\n--- Testing Load ---")
    users, names = load_used_data()
    print(f"Loaded Usernames: {users}")
    print(f"Loaded Names: {names}")
    
    print("\n--- Testing Add ---")
    test_user = f"testuser_{random.randint(1000, 9999)}"
    test_name = f"Test User {random.randint(1000, 9999)}"
    print(f"Attempting to add: {test_name} / {test_user}")
    add_to_history(test_user, test_name)
    
    print("\n--- Testing Load Again ---")
    users_after, names_after = load_used_data()
    print(f"Loaded Usernames: {users_after}")
    print(f"Loaded Names: {names_after}")
    
    print("\n--- Testing Add Duplicate ---")
    print(f"Attempting to add again: {test_name} / {test_user}")
    add_to_history(test_user, test_name)
    
    print("\n--- Testing Add Missing ---")
    add_to_history("onlyuser", None)
    add_to_history(None, "Only Name")
