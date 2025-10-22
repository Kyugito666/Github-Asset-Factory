import os
import sys
import logging
from dotenv import load_dotenv # Pastikan dotenv di-load dari root
from itertools import cycle
from typing import List, Optional

# Tentukan ROOT_DIR berdasarkan lokasi file config.py ini
# Naik satu level dari src/
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Load .env dari ROOT_DIR
dotenv_path = os.path.join(ROOT_DIR, '.env')
load_dotenv(dotenv_path=dotenv_path)

# Definisikan logger dulu
logger = logging.getLogger(__name__)

# Fungsi setup_logging (tidak berubah, tapi path LOG_FILE diatur nanti)
def setup_logging(is_controller=False):
    handlers = [logging.StreamHandler(sys.stdout)]
    log_level = logging.INFO
    # --- PATH LOG FILE DIUBAH ---
    log_file_name = os.getenv("LOG_FILE", "app.log")
    log_file_path = os.path.join(ROOT_DIR, 'logs', log_file_name) # Simpan di logs/
    # -----------------------------
    if not is_controller:
        try:
            # Buat folder logs jika belum ada
            os.makedirs(os.path.join(ROOT_DIR, 'logs'), exist_ok=True)
            handlers.append(logging.FileHandler(log_file_path, encoding='utf-8'))
        except Exception as e: print(f"Warning: Could not open log file {log_file_path}: {e}")
    log_format = '%(asctime)s - %(levelname)s - %(message)s'
    logging.basicConfig(level=log_level, format=log_format, handlers=handlers, force=True)
    if sys.platform == 'win32':
        try: sys.stdout.reconfigure(encoding='utf-8')
        except Exception as e: print(f"Warning: Could not reconfigure stdout encoding: {e}")

# Panggil setup_logging (logika IS_CONTROLLER disederhanakan)
# Jika file ini dijalankan langsung (jarang), anggap worker
IS_CONTROLLER_PROCESS = __name__ != "__main__" and "tui.py" in sys.argv[0] # Cek jika dipanggil TUI
setup_logging(is_controller=IS_CONTROLLER_PROCESS)

# API KEY VALIDATION (Tidak berubah)
def validate_api_key(key: str, provider: str) -> bool: /* ... sama ... */
def parse_api_keys(env_var_name: str, provider: str) -> list: /* ... sama ... */

# LOAD RAW API KEYS (Tidak berubah)
GEMINI_API_KEYS = parse_api_keys("GEMINI_API_KEY", "gemini"); GROQ_API_KEYS = parse_api_keys("GROQ_API_KEY", "groq"); COHERE_API_KEYS = parse_api_keys("COHERE_API_KEY", "cohere"); REPLICATE_API_KEYS = parse_api_keys("REPLICATE_API_KEY", "replicate"); HF_API_TOKENS = parse_api_keys("HF_API_TOKEN", "huggingface"); OPENROUTER_API_KEYS = parse_api_keys("OPENROUTER_API_KEY", "openrouter"); MISTRAL_API_KEYS = parse_api_keys("MISTRAL_API_KEY", "mistral"); FIREWORKS_API_KEYS = parse_api_keys("FIREWORKS_API_KEY", "fireworks")

# Telegram config (Tidak berubah)
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN"); TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

# PROXY POOL (Definisi dan load_proxies diubah pathnya)
class ProxyPool: /* ... sama ... */
def load_proxies(file_path: str = "proxy.txt") -> List[str]:
    # --- PATH PROXY FILE DIUBAH ---
    full_path = os.path.join(ROOT_DIR, 'data', file_path)
    # -----------------------------
    if not os.path.exists(full_path): logger.info(f"Proxy file not found: {full_path}."); return []
    proxies = []; line_count = 0; added_count = 0; skipped_count = 0
    try:
        # Buat folder data jika belum ada (opsional)
        os.makedirs(os.path.join(ROOT_DIR, 'data'), exist_ok=True)
        with open(full_path, 'r', encoding='utf-8') as f:
            for line_num, line in enumerate(f, 1):
                line_count += 1; line = line.strip()
                if not line or line.startswith('#'): skipped_count += 1; continue
                if line.startswith("http://") or line.startswith("https://"): proxies.append(line); added_count += 1
                else: logger.warning(f"Invalid proxy format line {line_num} (skipped): {line}"); skipped_count += 1
    except Exception as e: logger.error(f"Error reading proxy file {full_path}: {e}"); return []
    logger.info(f"Proxy summary: Read {line_count}, Added {added_count}, Skipped {skipped_count} from data/{file_path}")
    if added_count == 0 and line_count > 0: logger.warning(f"No valid proxies found in data/{file_path}")
    return proxies
PROXY_LIST = load_proxies(); PROXY_POOL = ProxyPool(PROXY_LIST) if PROXY_LIST else None

# APP SETTINGS (Hapus TEMP_FILES_DIR)
APP_NAME = "GitHub Asset Generator"; APP_VERSION = "v19.4 (Refactored)"; LOG_FILE = os.getenv("LOG_FILE", "app.log") # Nama file log dari env

# VALIDATION (Tidak berubah)
def validate_config(): /* ... sama ... */
