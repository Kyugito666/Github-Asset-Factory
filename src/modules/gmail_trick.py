import os
import logging
import json
import random
from datetime import datetime
from typing import List, Dict, Set

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
GMAIL_FILE_NAME = "gmail.txt"
HISTORY_FILE_NAME = "dot_trick_history.json"
GMAIL_FILE_PATH = os.path.join(ROOT_DIR, 'data', GMAIL_FILE_NAME)
HISTORY_FILE_PATH = os.path.join(ROOT_DIR, 'history', HISTORY_FILE_NAME)
# -------------------------

# ============================================================
# HISTORY MANAGEMENT (Path Diubah)
# ============================================================
def load_history() -> Dict[str, List[str]]:
    """
    Load history: { "email": ["var1", "var2", ...] }
    """
    # Pastikan folder history ada
    history_dir = os.path.dirname(HISTORY_FILE_PATH)
    if not os.path.exists(history_dir):
        logger.info(f"History directory not found, creating: {history_dir}")
        try:
            os.makedirs(history_dir, exist_ok=True)
        except OSError as e:
            logger.error(f"Failed to create history directory {history_dir}: {e}")
            return {} # Gagal buat folder, return empty

    # Baca file history
    if not os.path.exists(HISTORY_FILE_PATH):
        logger.info(f"History file not found: {HISTORY_FILE_PATH}. Starting fresh.")
        return {} # File belum ada, return empty

    try:
        with open(HISTORY_FILE_PATH, 'r', encoding='utf-8') as f:
            data = json.load(f)
            # Validasi format dasar
            if isinstance(data, dict):
                # Pastikan value-nya adalah list string
                valid_data = {}
                for k, v in data.items():
                    if isinstance(v, list) and all(isinstance(item, str) for item in v):
                         valid_data[k] = v
                    else:
                         logger.warning(f"Invalid format for email '{k}' in history file, skipping.")
                return valid_data
            else:
                 logger.warning(f"History file {HISTORY_FILE_PATH} is not a valid JSON object. Resetting history.")
                 return {}
    except (json.JSONDecodeError, IOError) as e:
        logger.error(f"Error loading dot trick history from {HISTORY_FILE_PATH}: {e}")
        return {} # Gagal baca/parse, return empty

def save_history(history: Dict[str, List[str]]):
    """Save history ke file JSON."""
    history_dir = os.path.dirname(HISTORY_FILE_PATH)
    try:
        # Buat folder jika belum ada (safety check)
        os.makedirs(history_dir, exist_ok=True)
        with open(HISTORY_FILE_PATH, 'w', encoding='utf-8') as f:
            json.dump(history, f, indent=2, ensure_ascii=False)
        # Kurangi log spam
        # logger.info(f"Dot trick history saved: {len(history)} emails tracked.")
    except IOError as e:
        logger.error(f"Error saving dot trick history to {HISTORY_FILE_PATH}: {e}")
    except Exception as e: # Tangkap error lain
         logger.error(f"Unexpected error saving dot trick history: {e}", exc_info=True)


def add_variation_to_history(email: str, new_variation: str):
    """Tambah SATU variasi baru ke list history email."""
    if not email or not new_variation:
        logger.warning("Attempted to add variation with empty email or variation.")
        return

    history = load_history() # Load data terbaru

    if email not in history:
        history[email] = []

    # Tambahkan hanya jika belum ada (pakai Set untuk cek cepat)
    if new_variation not in set(history[email]):
        history[email].append(new_variation)
        save_history(history) # Simpan perubahan
        logger.info(f"Added variation '{new_variation}' to history for '{email}'.")
    else:
        logger.debug(f"Variation '{new_variation}' already exists in history for '{email}'.")


def get_generated_variations(email: str) -> Set[str]:
    """Ambil set variasi yang sudah pernah digenerate untuk email ini."""
    history = load_history()
    return set(history.get(email, []))

# ============================================================
# GMAIL LIST LOADING (Path Diubah)
# ============================================================
def load_gmail_list() -> List[str]:
    """Load list email dari data/gmail.txt."""
    if not os.path.exists(GMAIL_FILE_PATH):
        logger.warning(f"{GMAIL_FILE_NAME} not found in 'data/' directory ({GMAIL_FILE_PATH}). Please create the file.")
        return []

    emails = []
    line_count = 0
    added_count = 0
    skipped_count = 0
    try:
        # Buat folder data jika belum ada (safety check)
        os.makedirs(os.path.dirname(GMAIL_FILE_PATH), exist_ok=True)
        with open(GMAIL_FILE_PATH, 'r', encoding='utf-8') as f:
            for line_num, line in enumerate(f, 1):
                line_count += 1
                line = line.strip().strip('~').strip() # Bersihkan spasi dan ~
                if not line or line.startswith('#'):
                    skipped_count += 1
                    continue
                # Validasi format email dasar
                if '@gmail.com' in line.lower() and line.count('@') == 1:
                    emails.append(line.lower())
                    added_count += 1
                else:
                    logger.warning(f"Invalid format or not a Gmail address on line {line_num} (skipped): {line}")
                    skipped_count += 1
    except Exception as e:
        logger.error(f"Error reading Gmail file {GMAIL_FILE_PATH}: {e}")
        return [] # Return empty list on error

    unique_emails = list(dict.fromkeys(emails)) # Hapus duplikat
    logger.info(f"Gmail loading summary: Read {line_count}, Added {added_count} unique, Skipped {skipped_count} from data/{GMAIL_FILE_NAME}")
    return unique_emails

# ============================================================
# DOT TRICK GENERATION (Logika Tidak Berubah)
# ============================================================
def generate_dot_tricks(email: str, existing_variations: Set[str]) -> str | None:
    """
    Generate SATU variasi dot trick acak BARU (jika memungkinkan).
    Mengembalikan None jika gagal atau username terlalu pendek.
    """
    if '@' not in email:
        logger.error(f"Invalid email format passed to generate_dot_tricks: {email}")
        return None

    try:
        username, domain = email.split('@', 1)
        username_clean = username.replace('.', '')
    except ValueError:
        logger.error(f"Could not split email: {email}")
        return None

    if len(username_clean) < 2:
        logger.warning(f"Username '{username_clean}' too short for dot trick: {email}")
        return None # Tidak bisa generate variasi

    possible_positions = list(range(1, len(username_clean)))
    if not possible_positions:
        logger.warning(f"No possible dot positions for username '{username_clean}' in email: {email}")
        return None # Seharusnya tidak terjadi jika len > 1

    MAX_ATTEMPTS = 15 # Tingkatkan sedikit percobaan
    for attempt in range(MAX_ATTEMPTS):
        try:
            # Pilih satu posisi acak
            pos = random.choice(possible_positions)

            # Buat username baru dengan dot
            chars = list(username_clean)
            chars.insert(pos, '.')
            new_username = ''.join(chars)
            new_variation = f"{new_username}@{domain}"

            # Cek apakah variasi ini sudah ada di history + original + clean
            combined_existing = existing_variations.union({email, f"{username_clean}@{domain}"})
            if new_variation not in combined_existing:
                logger.info(f"Generated new unique variation for {email} (attempt {attempt+1}): {new_variation}")
                return new_variation
            # Jika sudah ada, loop akan coba lagi

        except Exception as e:
            logger.error(f"Error during random dot generation for {email}: {e}")
            return None # Gagal generate

    # Jika setelah MAX_ATTEMPTS tetap tidak ketemu yang baru
    logger.warning(f"Could not find a new unique variation for {email} after {MAX_ATTEMPTS} attempts. Returning a random (possibly duplicate) one.")
    # Kembalikan variasi acak (mungkin duplikat) sebagai fallback
    try:
        pos = random.choice(possible_positions)
        chars = list(username_clean)
        chars.insert(pos, '.')
        new_username = ''.join(chars)
        return f"{new_username}@{domain}"
    except Exception as e:
        logger.error(f"Error generating fallback random dot for {email}: {e}")
        return None

# ============================================================
# STATS FUNCTION (Logika Tidak Berubah)
# ============================================================
def get_stats() -> Dict:
    """Hitung statistik berdasarkan history baru."""
    history = load_history()
    all_emails = load_gmail_list()

    total_emails_in_file = len(all_emails)
    emails_with_history = len(history)

    # Hitung total variasi unik yang tersimpan di history
    total_variations_generated = sum(len(variations) for variations in history.values())

    return {
        "total_emails_in_file": total_emails_in_file,
        "emails_with_variations": emails_with_history, # Nama diubah biar lebih jelas
        "total_variations_generated": total_variations_generated
    }

# Contoh penggunaan (jika file dijalankan langsung)
if __name__ == "__main__":
    # Setup basic logging jika dijalankan standalone
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    logger.info("Running gmail_trick.py standalone for testing...")

    # Test loading emails
    test_emails = load_gmail_list()
    if test_emails:
        print(f"\nLoaded {len(test_emails)} emails. First 5: {test_emails[:5]}")

        # Test generating for first email
        test_email = test_emails[0]
        print(f"\nTesting generation for: {test_email}")
        existing = get_generated_variations(test_email)
        print(f"Existing variations: {existing or 'None'}")
        new_var = generate_dot_tricks(test_email, existing)
        if new_var:
            print(f"Generated new variation: {new_var}")
            add_variation_to_history(test_email, new_var)
            existing_after = get_generated_variations(test_email)
            print(f"Variations after adding: {existing_after}")
        else:
            print("Failed to generate new variation.")

        # Test stats
        print("\nTesting stats:")
        stats = get_stats()
        print(json.dumps(stats, indent=2))
    else:
        print("\nNo emails found in gmail.txt for testing.")
