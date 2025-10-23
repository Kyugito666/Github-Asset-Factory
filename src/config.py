import os
import sys
import logging
from dotenv import load_dotenv
from itertools import cycle
from typing import List, Optional

# --- PATH SETUP ---
# Get the directory containing this script (src)
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
# Go up one level to the root directory
ROOT_DIR = os.path.dirname(SCRIPT_DIR)

# Load environment variables from the root .env file
load_dotenv(os.path.join(ROOT_DIR, ".env"))

# ============================================================
# INITIAL LOGGING SETUP (Dipanggil lebih awal)
# ============================================================
# Definisikan logger dulu
logger = logging.getLogger(__name__)

def setup_logging(is_controller=False):
    """
    Setup logging. Controller (TUI) hanya log ke console.
    Worker (Bot) log ke console dan file.
    """
    handlers = [logging.StreamHandler(sys.stdout)]
    log_level = logging.INFO # Default level
    if not is_controller:
        try:
            # --- PATH DIPERBARUI ---
            log_file = os.getenv("LOG_FILE", os.path.join(ROOT_DIR, "app.log"))
            handlers.append(logging.FileHandler(log_file, encoding='utf-8'))
        except Exception as e:
            print(f"Warning: Could not open log file {log_file}: {e}. Logging to console only.")

    # Tentukan format logging
    log_format = '%(asctime)s - %(levelname)s - %(message)s'

    # Konfigurasi logging
    logging.basicConfig(
        level=log_level,
        format=log_format,
        handlers=handlers,
        force=True # Override konfigurasi sebelumnya jika ada
    )

    # Reconfigure stdout encoding jika di Windows
    if sys.platform == 'win32':
        try:
            sys.stdout.reconfigure(encoding='utf-8')
        except Exception as e:
            print(f"Warning: Could not reconfigure stdout encoding: {e}")

# Panggil setup_logging SEKARANG, tapi tentukan apakah ini controller atau worker
# Kita asumsikan config.py selalu diimport oleh worker atau tui, jadi cek argumen
IS_CONTROLLER_PROCESS = not ("--run-internal" in sys.argv or "bot.py" in sys.argv[0])
# setup_logging(is_controller=IS_CONTROLLER_PROCESS) # Panggil setup_logging di sini agar logger siap

# ============================================================
# API KEY VALIDATION (No change)
# ============================================================
def validate_api_key(key: str, provider: str) -> bool:
    if not key or not isinstance(key, str): return False
    provider = provider.lower()
    if provider == "groq": return key.startswith("gsk_") and len(key) > 20
    elif provider == "gemini": return key.startswith("AIza") and len(key) > 30
    elif provider == "cohere": return len(key) > 20
    elif provider == "replicate": return key.startswith("r8_") or len(key) > 20
    elif provider == "huggingface": return key.startswith("hf_") and len(key) > 20
    elif provider == "openrouter": return key.startswith("sk-or-v1-") and len(key) > 40
    elif provider == "mistral": return len(key) > 20
    elif provider == "fireworks": return key.startswith("fw-") or len(key) > 20
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
    # Gunakan logger yang sudah di-setup
    if invalid_count > 0: logger.warning(f"{invalid_count} invalid {provider.upper()} key(s) filtered out")
    return list(dict.fromkeys(valid_keys))

# ============================================================
# LOAD RAW API KEYS (No change)
# ============================================================
GEMINI_API_KEYS = parse_api_keys("GEMINI_API_KEY", "gemini")
GROQ_API_KEYS = parse_api_keys("GROQ_API_KEY", "groq")
COHERE_API_KEYS = parse_api_keys("COHERE_API_KEY", "cohere")
REPLICATE_API_KEYS = parse_api_keys("REPLICATE_API_KEY", "replicate")
HF_API_TOKENS = parse_api_keys("HF_API_TOKEN", "huggingface")
OPENROUTER_API_KEYS = parse_api_keys("OPENROUTER_API_KEY", "openrouter")
MISTRAL_API_KEYS = parse_api_keys("MISTRAL_API_KEY", "mistral")
FIREWORKS_API_KEYS = parse_api_keys("FIREWORKS_API_KEY", "fireworks")

# Telegram config (No change)
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

# ============================================================
# PROXY POOL (Definisi dipindah setelah logging)
# ============================================================
class ProxyPool:
    # Class ProxyPool tidak berubah
    def __init__(self, proxies: List[str]): self.proxies = list(dict.fromkeys(proxies)); self.pool = cycle(self.proxies); self.failed_proxies = set()
    def get_next_proxy(self) -> Optional[str]:
        if not self.proxies: return None
        for _ in range(len(self.proxies)): proxy = next(self.pool);
        if proxy not in self.failed_proxies: return proxy
        logger.warning("All proxies failed, resetting pool."); self.failed_proxies.clear()
        if not self.proxies: return None; return next(self.pool)
    def mark_failed(self, proxy: str):
        if proxy in self.proxies: self.failed_proxies.add(proxy); logger.warning(f"Proxy failed: {proxy.split('@')[-1]}")

# === PERBAIKAN PROXY PATH DI SINI ===
def load_proxies(file_path: str = os.path.join(ROOT_DIR, "data", "proxy.txt")) -> List[str]: # <-- PATH DIPERBARUI
    """Load proxy dari file proxy.txt dengan logging lebih detail."""
    if not os.path.exists(file_path):
        logger.info(f"Proxy file not found: {file_path}. Running with local IP.") # Use logger
        return []
# === AKHIR PERBAIKAN ===
    proxies = []; line_count = 0; added_count = 0; skipped_count = 0
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            for line_num, line in enumerate(f, 1):
                line_count += 1; line = line.strip()
                if not line or line.startswith('#'): skipped_count += 1; continue
                if line.startswith("http://") or line.startswith("https://"): proxies.append(line); added_count += 1
                else: logger.warning(f"Invalid proxy format on line {line_num} (skipped): {line}"); skipped_count += 1 # Use logger
    except Exception as e: logger.error(f"Error reading proxy file {file_path}: {e}"); return [] # Use logger

    # Gunakan logger yang sudah di-setup
    logger.info(f"Proxy loading summary: Read {line_count} lines, Added {added_count}, Skipped {skipped_count} from {file_path}")
    if added_count == 0 and line_count > 0:
        logger.warning(f"No valid proxies found in {file_path}, check format (e.g., http://user:pass@host:port)")

    return proxies

# Panggil setup_logging SEBELUM load_proxies
setup_logging(is_controller=IS_CONTROLLER_PROCESS)

# Load proxies dan buat pool global SETELAH logging siap
PROXY_LIST = load_proxies()
PROXY_POOL = ProxyPool(PROXY_LIST) if PROXY_LIST else None

# ============================================================
# APP SETTINGS (PATH DIPERBARUI)
# ============================================================
APP_NAME = "GitHub Asset Generator"
APP_VERSION = "v19.3 (Router + More Providers)"
# --- PATH DIPERBARUI ---
TEMP_FILES_DIR = os.path.join(ROOT_DIR, "temp_files")
LOG_FILE = os.getenv("LOG_FILE", os.path.join(ROOT_DIR, "app.log"))
os.makedirs(TEMP_FILES_DIR, exist_ok=True)

# ============================================================
# VALIDATION (Ganti print jadi logger)
# ============================================================
def validate_config():
    """Validasi konfigurasi environment variables."""
    if not all([TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID]):
        logger.critical("CONFIG ERROR: Missing Telegram keys (TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID) in .env") # Use logger
        sys.exit(1)
    any_ai_keys = bool(GEMINI_API_KEYS or GROQ_API_KEYS or COHERE_API_KEYS or REPLICATE_API_KEYS or HF_API_TOKENS or OPENROUTER_API_KEYS or MISTRAL_API_KEYS or FIREWORKS_API_KEYS)
    if not any_ai_keys:
        logger.critical("CONFIG ERROR: No valid AI API keys found in .env for any provider.") # Use logger
        logger.critical("   Please add keys for at least one provider (e.g., GEMINI_API_KEY, COHERE_API_KEY, etc.).") # Use logger
        sys.exit(1)

    logger.info(".env config loaded successfully.") # Use logger
    if GEMINI_API_KEYS: logger.info(f"{len(GEMINI_API_KEYS)} valid Gemini key(s) detected.")
    if GROQ_API_KEYS: logger.info(f"{len(GROQ_API_KEYS)} valid Groq key(s) detected (may be suspended).")
    if COHERE_API_KEYS: logger.info(f"{len(COHERE_API_KEYS)} valid Cohere key(s) detected.")
    if REPLICATE_API_KEYS: logger.info(f"{len(REPLICATE_API_KEYS)} valid Replicate key(s) detected.")
    if HF_API_TOKENS: logger.info(f"{len(HF_API_TOKENS)} valid HuggingFace token(s) detected.")
    if OPENROUTER_API_KEYS: logger.info(f"{len(OPENROUTER_API_KEYS)} valid OpenRouter key(s) detected.")
    if MISTRAL_API_KEYS: logger.info(f"{len(MISTRAL_API_KEYS)} valid Mistral key(s) detected.")
    if FIREWORKS_API_KEYS: logger.info(f"{len(FIREWORKS_API_KEYS)} valid Fireworks key(s) detected.")
    # Pesan proxy sudah dicetak oleh load_proxies
