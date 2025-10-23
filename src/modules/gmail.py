import os
import logging
import json
import random
from datetime import datetime
from typing import List, Dict, Set

logger = logging.getLogger(__name__)

# --- PATH DIPERBARUI ---
# Get the directory containing this script (src/modules)
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
# Go up two levels to the root directory
ROOT_DIR = os.path.dirname(os.path.dirname(SCRIPT_DIR))

GMAIL_FILE = os.path.join(ROOT_DIR, "data", "gmail.txt")
HISTORY_FILE = os.path.join(ROOT_DIR, "history", "dot_trick_history.json")
# ---------------------


def load_history() -> Dict[str, List[str]]:
    """
    Load history: { "email": ["var1", "var2", ...] }
    """
    if not os.path.exists(HISTORY_FILE):
        return {}
    
    try:
        with open(HISTORY_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
            # Validasi format dasar
            if isinstance(data, dict):
                # Pastikan value-nya adalah list
                return {k: v for k, v in data.items() if isinstance(v, list)}
            return {}
    except (json.JSONDecodeError, IOError) as e:
        logger.error(f"Error loading dot trick history: {e}")
        return {}

def save_history(history: Dict[str, List[str]]):
    """Save history ke file JSON."""
    try:
        # Pastikan direktori history ada
        os.makedirs(os.path.dirname(HISTORY_FILE), exist_ok=True)
        with open(HISTORY_FILE, 'w', encoding='utf-8') as f:
            json.dump(history, f, indent=2, ensure_ascii=False)
        # Kurangi log spam
        # logger.info(f"Dot trick history saved: {len(history)} emails tracked.")
    except IOError as e:
        logger.error(f"Error saving dot trick history: {e}")

def add_variation_to_history(email: str, new_variation: str):
    """Tambah SATU variasi baru ke list history email."""
    if not email or not new_variation:
        return
        
    history = load_history()
    
    if email not in history:
        history[email] = []
    
    # Tambahkan hanya jika belum ada (meski jarang terjadi duplikat acak)
    if new_variation not in history[email]:
        history[email].append(new_variation)
        save_history(history)
        logger.info(f"Added variation '{new_variation}' to history for '{email}'.")

def get_generated_variations(email: str) -> Set[str]:
    """Ambil set variasi yang sudah pernah digenerate untuk email ini."""
    history = load_history()
    return set(history.get(email, []))

# HAPUS: Fungsi is_generated dan get_history_info dihapus

def load_gmail_list() -> List[str]:
    """Load list email dari gmail.txt (Tidak berubah)."""
    if not os.path.exists(GMAIL_FILE):
        logger.warning(f"{GMAIL_FILE} tidak ditemukan (Expected: data/gmail.txt)")
        return []
    
    emails = []
    with open(GMAIL_FILE, 'r', encoding='utf-8') as f:
        for line_num, line in enumerate(f, 1):
            line = line.strip().strip('~').strip()
            if not line or line.startswith('#'): continue
            if '@gmail.com' not in line.lower(): continue
            if line.count('@') != 1: continue
            emails.append(line.lower())
    
    unique_emails = list(dict.fromkeys(emails))
    logger.info(f"Loaded {len(unique_emails)} unique Gmail addresses dari {GMAIL_FILE}")
    return unique_emails

# HAPUS: Fungsi get_pending_emails dihapus

def generate_dot_tricks(email: str, existing_variations: Set[str]) -> str | None:
    """
    Generate SATU variasi dot trick acak BARU (jika memungkinkan).
    Mengembalikan None jika gagal atau username terlalu pendek.
    """
    if '@' not in email:
        logger.error(f"Invalid email format passed: {email}")
        return None
    
    username, domain = email.split('@', 1)
    username_clean = username.replace('.', '')

    if len(username_clean) < 2:
        logger.warning(f"Username too short for dot trick: {email}")
        return None # Tidak bisa generate variasi
    
    possible_positions = list(range(1, len(username_clean)))
    if not possible_positions:
        return None # Seharusnya tidak terjadi jika len > 1

    MAX_ATTEMPTS = 10 # Coba 10x untuk cari variasi unik
    for _ in range(MAX_ATTEMPTS):
        try:
            pos = random.choice(possible_positions)
            chars = list(username_clean)
            chars.insert(pos, '.')
            new_username = ''.join(chars)
            new_variation = f"{new_username}@{domain}"

            # Cek apakah variasi ini sudah ada di history
            if new_variation not in existing_variations:
                logger.info(f"Generated new variation for {email}: {new_variation}")
                return new_variation
            # Jika sudah ada, loop akan coba lagi
            
        except Exception as e:
            logger.error(f"Error generating random dot for {email}: {e}")
            return None # Gagal generate

    # Jika setelah MAX_ATTEMPTS tetap tidak ketemu yang baru
    logger.warning(f"Could not find a new unique variation for {email} after {MAX_ATTEMPTS} attempts.")
    # Kembalikan variasi acak (mungkin duplikat) sebagai fallback
    pos = random.choice(possible_positions)
    chars = list(username_clean)
    chars.insert(pos, '.')
    new_username = ''.join(chars)
    return f"{new_username}@{domain}"


# HAPUS: Fungsi save_dot_tricks (saving ke file .txt) dihapus total


def get_stats() -> Dict:
    """Hitung statistik berdasarkan history baru."""
    history = load_history()
    all_emails = load_gmail_list()
    
    total_emails_in_file = len(all_emails)
    emails_with_history = len(history)
    
    total_variations_generated = sum(len(variations) for variations in history.values())
    
    return {
        "total_emails_in_file": total_emails_in_file,
        "emails_with_variations": emails_with_history,
        "total_variations_generated": total_variations_generated
    }
