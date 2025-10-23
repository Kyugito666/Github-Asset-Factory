import os
import sys
import logging
from dotenv import load_dotenv
from itertools import cycle
from typing import List, Optional
import time # Tambahkan import time

# --- PATH SETUP ---
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.dirname(SCRIPT_DIR)
load_dotenv(os.path.join(ROOT_DIR, ".env"))

# ============================================================
# INITIAL LOGGING SETUP (Tidak berubah)
# ============================================================
logger = logging.getLogger(__name__)

def setup_logging(is_controller=False):
    handlers = [logging.StreamHandler(sys.stdout)]
    log_level = logging.INFO
    if not is_controller:
        try:
            log_file = os.getenv("LOG_FILE", os.path.join(ROOT_DIR, "app.log"))
            handlers.append(logging.FileHandler(log_file, encoding='utf-8'))
        except Exception as e:
            print(f"Warning: Could not open log file {log_file}: {e}. Logging to console only.")
    log_format = '%(asctime)s - %(levelname)s - %(message)s'
    logging.basicConfig(level=log_level, format=log_format, handlers=handlers, force=True)
    if sys.platform == 'win32':
        try: sys.stdout.reconfigure(encoding='utf-8')
        except Exception as e: print(f"Warning: Could not reconfigure stdout encoding: {e}")

IS_CONTROLLER_PROCESS = not ("--run-internal" in sys.argv or "bot.py" in sys.argv[0])

# ============================================================
# API KEY VALIDATION (Tidak berubah)
# ============================================================
def validate_api_key(key: str, provider: str) -> bool:
    # ... (kode validasi tidak berubah) ...
    if not key or not isinstance(key, str): return False
    provider = provider.lower()
    if provider == "groq": return key.startswith("gsk_") and len(key) > 20
    elif provider == "gemini": return key.startswith("AIza") and len(key) > 30
    elif provider == "cohere": return len(key) > 20
    elif provider == "replicate": return key.startswith("r8_") or len(key) > 20
    elif provider == "huggingface": return key.startswith("hf_") and len(key) > 20
    elif provider == "openrouter": return key.startswith("sk-or-v1-") and len(key) > 40
    elif provider == "mistral": return len(key) > 20
    # elif provider == "fireworks": return key.startswith("fw-") or len(key) > 20 # Dihapus
    return True

def parse_api_keys(env_var_name: str, provider: str) -> list:
    keys = []; main_key = os.getenv(env_var_name)
    if main_key and ',' in main_key: keys.extend([k.strip() for k in main_key.split(',') if k.strip()])
    elif main_key: keys.append(main_key.strip())
    i = 1
    while True:
        key = os.getenv(f"{env_var_name}_{i}")
        if not key: break
        keys.append(key.strip()); i += 1
    valid_keys = [k for k in keys if validate_api_key(k, provider)]
    invalid_count = len(keys) - len(valid_keys)
    if invalid_count > 0: logger.warning(f"{invalid_count} invalid {provider.upper()} key(s) filtered out")
    return list(dict.fromkeys(valid_keys))

# ============================================================
# LOAD RAW API KEYS (Tidak berubah)
# ============================================================
GEMINI_API_KEYS = parse_api_keys("GEMINI_API_KEY", "gemini")
GROQ_API_KEYS = parse_api_keys("GROQ_API_KEY", "groq")
COHERE_API_KEYS = parse_api_keys("COHERE_API_KEY", "cohere")
REPLICATE_API_KEYS = parse_api_keys("REPLICATE_API_KEY", "replicate")
HF_API_TOKENS = parse_api_keys("HF_API_TOKEN", "huggingface")
OPENROUTER_API_KEYS = parse_api_keys("OPENROUTER_API_KEY", "openrouter")
MISTRAL_API_KEYS = parse_api_keys("MISTRAL_API_KEY", "mistral")
# FIREWORKS_API_KEYS = parse_api_keys("FIREWORKS_API_KEY", "fireworks") # Dihapus

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

# ============================================================
# PROXY POOL (DIPERBAIKI)
# ============================================================
class ProxyPool:
    def __init__(self, proxies: List[str]):
        self.proxies = list(dict.fromkeys(proxies)) # Hapus duplikat saat init
        self.pool = cycle(self.proxies)
        # Ganti failed_proxies jadi dict: {proxy_url: failure_timestamp}
        self.failed_proxies: Dict[str, float] = {}
        self.cooldown_period = 300 # Cooldown 5 menit (300 detik)

    def get_next_proxy(self) -> Optional[str]:
        if not self.proxies: return None
        start_marker = object() # Penanda untuk deteksi loop penuh
        current = next(self.pool, start_marker)
        checked_count = 0

        while current is not start_marker and checked_count < len(self.proxies):
            # Cek apakah proxy ada di daftar gagal DAN belum cooldown
            fail_time = self.failed_proxies.get(current)
            if fail_time is None or (time.time() - fail_time > self.cooldown_period):
                # Jika tidak gagal atau sudah cooldown, return proxy ini
                if fail_time is not None: # Hapus dari daftar gagal jika sudah cooldown
                    del self.failed_proxies[current]
                return current
            # Jika masih dalam cooldown, lanjut ke proxy berikutnya
            current = next(self.pool, start_marker)
            checked_count += 1

        # Jika loop selesai (semua proxy gagal & masih cooldown)
        logger.warning(f"All {len(self.proxies)} proxies are in cooldown. Trying oldest failed proxy...")
        # Fallback: Cari proxy yang gagal paling lama
        if self.failed_proxies:
            oldest_failed = min(self.failed_proxies, key=self.failed_proxies.get)
            del self.failed_proxies[oldest_failed] # Hapus dari daftar gagal biar bisa dicoba lagi
            logger.info(f"Retrying proxy: {oldest_failed.split('@')[-1]}")
            return oldest_failed

        # Jika tidak ada proxy sama sekali atau tidak ada yg gagal (aneh)
        if self.proxies:
            return next(self.pool) # Coba lagi aja dari awal pool
        else:
            return None # Tidak ada proxy

    def mark_failed(self, proxy: str):
        if proxy in self.proxies:
            self.failed_proxies[proxy] = time.time() # Catat waktu gagal
            logger.warning(f"Proxy failed & marked for cooldown: {proxy.split('@')[-1]}")

    def reload(self, new_proxies: List[str]):
        """Reload pool dengan daftar proxy baru."""
        logger.info(f"Reloading ProxyPool with {len(new_proxies)} proxies...")
        self.proxies = list(dict.fromkeys(new_proxies)) # Hapus duplikat
        self.pool = cycle(self.proxies)
        self.failed_proxies = {} # Reset daftar proxy gagal
        logger.info("ProxyPool reloaded.")


def load_proxies(file_path: str = os.path.join(ROOT_DIR, "data", "proxy.txt")) -> List[str]:
    # ... (kode load_proxies tidak berubah) ...
    if not os.path.exists(file_path):
        logger.info(f"Proxy file not found: {file_path}. Running with local IP.")
        return []
    proxies = []; line_count = 0; added_count = 0; skipped_count = 0
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            for line_num, line in enumerate(f, 1):
                line_count += 1; line = line.strip()
                if not line or line.startswith('#'): skipped_count += 1; continue
                if line.startswith("http://") or line.startswith("https://"): proxies.append(line); added_count += 1
                else: logger.warning(f"Invalid proxy format on line {line_num} (skipped): {line}"); skipped_count += 1
    except Exception as e: logger.error(f"Error reading proxy file {file_path}: {e}"); return []
    logger.info(f"Proxy loading summary: Read {line_count} lines, Added {added_count}, Skipped {skipped_count} from {file_path}")
    if added_count == 0 and line_count > 0:
        logger.warning(f"No valid proxies found in {file_path}, check format (e.g., http://user:pass@host:port)")
    return proxies

# Panggil setup_logging SEBELUM load_proxies
setup_logging(is_controller=IS_CONTROLLER_PROCESS)

# Load proxies dan buat pool global SETELAH logging siap
PROXY_LIST = load_proxies()
PROXY_POOL = ProxyPool(PROXY_LIST) if PROXY_LIST else None

# Fungsi baru untuk reload proxy
def reload_proxy_pool():
    """Reloads the global PROXY_POOL object."""
    global PROXY_POOL
    new_proxy_list = load_proxies()
    if PROXY_POOL:
        PROXY_POOL.reload(new_proxy_list)
    else: # Jika pool belum ada, buat baru
        PROXY_POOL = ProxyPool(new_proxy_list) if new_proxy_list else None

# ============================================================
# APP SETTINGS (Tidak berubah)
# ============================================================
APP_NAME = "GitHub Asset Generator"
APP_VERSION = "v19.3 (Manual Fallback + ProxySync)" # Update versi
TEMP_FILES_DIR = os.path.join(ROOT_DIR, "temp_files")
LOG_FILE = os.getenv("LOG_FILE", os.path.join(ROOT_DIR, "app.log"))
os.makedirs(TEMP_FILES_DIR, exist_ok=True)

# ============================================================
# VALIDATION (Tidak berubah)
# ============================================================
def validate_config():
    # ... (kode validate_config tidak berubah) ...
    if not all([TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID]):
        logger.critical("CONFIG ERROR: Missing Telegram keys (TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID) in .env")
        sys.exit(1)
    any_ai_keys = bool(GEMINI_API_KEYS or GROQ_API_KEYS or COHERE_API_KEYS or REPLICATE_API_KEYS or HF_API_TOKENS or OPENROUTER_API_KEYS or MISTRAL_API_KEYS)
    if not any_ai_keys:
        logger.critical("CONFIG ERROR: No valid AI API keys found in .env for any provider.")
        logger.critical("   Please add keys for at least one provider (e.g., GEMINI_API_KEY, COHERE_API_KEY, etc.).")
        sys.exit(1)
    logger.info(".env config loaded successfully.")
    if GEMINI_API_KEYS: logger.info(f"{len(GEMINI_API_KEYS)} valid Gemini key(s) detected.")
    if GROQ_API_KEYS: logger.info(f"{len(GROQ_API_KEYS)} valid Groq key(s) detected (may be suspended).")
    if COHERE_API_KEYS: logger.info(f"{len(COHERE_API_KEYS)} valid Cohere key(s) detected.")
    if REPLICATE_API_KEYS: logger.info(f"{len(REPLICATE_API_KEYS)} valid Replicate key(s) detected.")
    if HF_API_TOKENS: logger.info(f"{len(HF_API_TOKENS)} valid HuggingFace token(s) detected.")
    if OPENROUTER_API_KEYS: logger.info(f"{len(OPENROUTER_API_KEYS)} valid OpenRouter key(s) detected.")
    if MISTRAL_API_KEYS: logger.info(f"{len(MISTRAL_API_KEYS)} valid Mistral key(s) detected.")
    # Pesan proxy sudah dicetak oleh load_proxies
