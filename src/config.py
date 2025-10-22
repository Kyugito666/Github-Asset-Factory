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

# Definisikan logger dulu (akan dikonfigurasi oleh setup_logging)
logger = logging.getLogger(__name__)

# ============================================================
# LOGGING SETUP (Dipanggil lebih awal)
# ============================================================
def setup_logging(is_controller=False):
    """
    Setup logging. Controller (TUI) hanya log ke console.
    Worker (Bot) log ke console dan file.
    """
    handlers = [logging.StreamHandler(sys.stdout)]
    log_level = logging.INFO # Default level
    # --- PATH LOG FILE DIUBAH ---
    log_file_name = os.getenv("LOG_FILE", "app.log") # Ambil dari env atau default
    log_file_path = os.path.join(ROOT_DIR, 'logs', log_file_name) # Simpan di logs/
    # -----------------------------
    if not is_controller:
        try:
            # Buat folder logs jika belum ada
            os.makedirs(os.path.join(ROOT_DIR, 'logs'), exist_ok=True)
            handlers.append(logging.FileHandler(log_file_path, encoding='utf-8'))
        except Exception as e:
            # Gunakan print karena logger mungkin belum siap sepenuhnya
            print(f"Warning: Could not open log file {log_file_path}: {e}")

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
# Cek jika argumen skrip utama adalah tui.py (controller) atau bot.py (worker)
IS_CONTROLLER_PROCESS = 'tui.py' in sys.argv[0] if sys.argv else False
setup_logging(is_controller=IS_CONTROLLER_PROCESS) # Panggil setup_logging di sini agar logger siap

# ============================================================
# API KEY VALIDATION (Updated for Mistral & Fireworks)
# ============================================================
def validate_api_key(key: str, provider: str) -> bool:
    """Validasi format API key."""
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
    """Parse multiple API keys dari .env dengan validasi."""
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
# LOAD RAW API KEYS (Updated for Mistral & Fireworks)
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
    """Manual proxy rotation."""
    def __init__(self, proxies: List[str]):
        self.proxies = list(dict.fromkeys(proxies)) # Pastikan unik
        self.pool = cycle(self.proxies) if self.proxies else None # Handle empty list
        self.failed_proxies = set()

    def get_next_proxy(self) -> Optional[str]:
        """Ambil proxy berikutnya yang belum ditandai failed."""
        if not self.pool: return None # No proxies loaded

        for _ in range(len(self.proxies)):
            try:
                proxy = next(self.pool)
                if proxy not in self.failed_proxies:
                    return proxy
            except StopIteration: # Should not happen with cycle, but safety first
                 logger.error("ProxyPool StopIteration - should not happen with cycle.")
                 self.pool = cycle(self.proxies) # Re-initialize cycle
                 if not self.proxies: return None
                 proxy = next(self.pool) # Try getting one more time
                 if proxy not in self.failed_proxies: return proxy
                 break # Exit loop if still failing

        # Jika semua proxy gagal, reset dan coba lagi
        logger.warning("All proxies marked as failed, resetting pool.")
        self.failed_proxies.clear()
        if not self.pool: return None
        try:
            # Ambil satu setelah reset
            return next(self.pool)
        except StopIteration:
            logger.error("ProxyPool StopIteration after reset - proxy list might be empty.")
            return None

    def mark_failed(self, proxy: str):
        """Tandai proxy sebagai failed."""
        if proxy in self.proxies:
            self.failed_proxies.add(proxy)
            # Potong URL proxy agar tidak terlalu panjang di log
            proxy_display = proxy.split('@')[-1] if '@' in proxy else proxy
            logger.warning(f"Proxy failed, marking for rotation: {proxy_display}")

def load_proxies(file_path_relative: str = "proxy.txt") -> List[str]:
    """Load proxy dari file (path relatif ke folder data)."""
    # --- PATH PROXY FILE DIUBAH ---
    full_path = os.path.join(ROOT_DIR, 'data', file_path_relative)
    # -----------------------------
    if not os.path.exists(full_path):
        logger.info(f"Proxy file not found: {full_path}. Running with local IP.")
        return []
    proxies = []; line_count = 0; added_count = 0; skipped_count = 0
    try:
        # Buat folder data jika belum ada
        os.makedirs(os.path.join(ROOT_DIR, 'data'), exist_ok=True)
        with open(full_path, 'r', encoding='utf-8') as f:
            for line_num, line in enumerate(f, 1):
                line_count += 1; line = line.strip()
                if not line or line.startswith('#'): skipped_count += 1; continue
                # Validasi format dasar URL proxy
                if (line.startswith("http://") or line.startswith("https://")) and ":" in line and "@" in line:
                    proxies.append(line); added_count += 1
                else:
                    logger.warning(f"Invalid proxy format on line {line_num} (skipped): {line}")
                    skipped_count += 1
    except Exception as e:
        logger.error(f"Error reading proxy file {full_path}: {e}")
        return []

    logger.info(f"Proxy loading summary: Read {line_count}, Added {added_count}, Skipped {skipped_count} from data/{file_path_relative}")
    if added_count == 0 and line_count > 0:
        logger.warning(f"No valid proxies found in data/{file_path_relative}, check format (e.g., http://user:pass@host:port)")
    return proxies

# Load proxies dan buat pool global SETELAH logging siap
PROXY_LIST = load_proxies()
PROXY_POOL = ProxyPool(PROXY_LIST) if PROXY_LIST else None

# ============================================================
# APP SETTINGS (Hapus TEMP_FILES_DIR)
# ============================================================
APP_NAME = "GitHub Asset Generator"; APP_VERSION = "v19.4 (Refactored)"; LOG_FILE = os.getenv("LOG_FILE", "app.log") # Nama file log dari env

# Buat folder logs jika belum ada (dipindah ke setup_logging)
# os.makedirs(os.path.join(ROOT_DIR, 'logs'), exist_ok=True)

# ============================================================
# VALIDATION (Ganti print jadi logger)
# ============================================================
def validate_config():
    """Validasi konfigurasi environment variables."""
    # Panggil setup_logging di awal fungsi ini jika belum dipanggil global
    # setup_logging(is_controller=IS_CONTROLLER_PROCESS) # Pindah ke atas

    if not all([TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID]):
        logger.critical("CONFIG ERROR: Missing Telegram keys (TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID) in .env")
        sys.exit(1)
    any_ai_keys = bool(GEMINI_API_KEYS or GROQ_API_KEYS or COHERE_API_KEYS or REPLICATE_API_KEYS or HF_API_TOKENS or OPENROUTER_API_KEYS or MISTRAL_API_KEYS or FIREWORKS_API_KEYS)
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
    if FIREWORKS_API_KEYS: logger.info(f"{len(FIREWORKS_API_KEYS)} valid Fireworks key(s) detected.")
    # Pesan proxy sudah dicetak oleh load_proxies
