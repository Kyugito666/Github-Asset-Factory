# src/config.py

import os
import sys
import logging
from dotenv import load_dotenv
from itertools import cycle
from typing import List, Optional, Dict # Tambah Dict
import time

# --- PATH SETUP ---
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.dirname(SCRIPT_DIR)
load_dotenv(os.path.join(ROOT_DIR, ".env"))

# ============================================================
# INITIAL LOGGING SETUP
# ============================================================
logger = logging.getLogger(__name__) # Pindah ke atas sebelum dipakai

def setup_logging(is_controller=False):
    """Konfigurasi logging dasar."""
    handlers = [logging.StreamHandler(sys.stdout)]
    log_level = logging.INFO
    log_file = None # Default tidak ke file

    if not is_controller:
        try:
            log_file_env = os.getenv("LOG_FILE", os.path.join(ROOT_DIR, "app.log"))
            log_dir = os.path.dirname(log_file_env)
            os.makedirs(log_dir, exist_ok=True) # Pastikan direktori log ada
            handlers.append(logging.FileHandler(log_file_env, encoding='utf-8'))
            log_file = log_file_env # Simpan path file log jika berhasil dibuka
        except Exception as e:
            print(f"Warning: Could not open log file '{log_file_env}': {e}. Logging to console only.")

    log_format = '%(asctime)s - %(levelname)s - [%(name)s] - %(message)s' # Tambah nama logger
    # 'force=True' penting agar bisa rekonfigurasi logging jika dipanggil ulang
    logging.basicConfig(level=log_level, format=log_format, handlers=handlers, force=True)

    # Reconfigure stdout encoding jika perlu (misal di Windows)
    if sys.platform == 'win32':
        try:
            sys.stdout.reconfigure(encoding='utf-8')
        except Exception as e:
            print(f"Warning: Could not reconfigure stdout encoding: {e}")

    # Log file log yang dipakai (jika ada) setelah setup selesai
    if log_file:
         logging.getLogger(__name__).info(f"Logging configured. Outputting to console and file: {log_file}")
    else:
         logging.getLogger(__name__).info("Logging configured. Outputting to console only.")

# Tentukan apakah ini proses TUI atau worker
IS_CONTROLLER_PROCESS = not ("--run-internal" in sys.argv or "bot.py" in sys.argv[0])

# Panggil setup_logging SEGERA setelah didefinisikan
# Ini penting agar log selanjutnya (load config, etc.) bisa tercatat
setup_logging(is_controller=IS_CONTROLLER_PROCESS)
# ============================================================

# === BARU: Flag untuk Webshare IP Sync ===
ENABLE_WEBSHARE_IP_SYNC = os.getenv("ENABLE_WEBSHARE_IP_SYNC", "false").lower() in ['true', '1', 'yes']
# ======================================

# ============================================================
# API KEY VALIDATION & PARSING
# ============================================================
def validate_api_key(key: str, provider: str) -> bool:
    """Validasi format dasar API key."""
    if not key or not isinstance(key, str): return False
    key = key.strip() # Hapus spasi di awal/akhir
    provider = provider.lower()
    # Logika validasi (bisa diperketat jika perlu)
    if provider == "groq": return key.startswith("gsk_") and len(key) > 20
    elif provider == "gemini": return key.startswith("AIza") and len(key) > 30
    elif provider == "cohere": return len(key) > 20 # Cohere keys tidak punya prefix standar
    elif provider == "replicate": return key.startswith("r8_") or len(key) > 20
    elif provider == "huggingface": return key.startswith("hf_") and len(key) > 20
    elif provider == "openrouter": return key.startswith("sk-or-v1-") and len(key) > 40
    elif provider == "mistral": return len(key) > 20 # Mistral keys tidak punya prefix standar
    return True # Default anggap valid jika tidak ada aturan khusus

def parse_api_keys(env_var_name: str, provider: str) -> list:
    """Parse API keys dari env var (support koma & suffix angka)."""
    keys = []
    # Cek env var utama (bisa berisi satu key atau multiple dipisah koma)
    main_key_str = os.getenv(env_var_name)
    if main_key_str:
        if ',' in main_key_str:
            keys.extend([k.strip() for k in main_key_str.split(',') if k.strip()])
        else:
            keys.append(main_key_str.strip())

    # Cek env var dengan suffix angka (misal: GEMINI_API_KEY_1, GEMINI_API_KEY_2)
    i = 1
    while True:
        key = os.getenv(f"{env_var_name}_{i}")
        if not key:
            break # Stop jika env var berikutnya tidak ditemukan
        keys.append(key.strip())
        i += 1

    # Validasi dan filter key yang valid
    valid_keys = [k for k in keys if validate_api_key(k, provider)]
    invalid_count = len(keys) - len(valid_keys)
    if invalid_count > 0:
        logger.warning(f"{invalid_count} invalid {provider.upper()} key(s) found in .env and ignored.")

    # Hapus duplikat sambil mempertahankan urutan
    unique_valid_keys = list(dict.fromkeys(valid_keys))
    if len(valid_keys) != len(unique_valid_keys):
         logger.info(f"Removed {len(valid_keys) - len(unique_valid_keys)} duplicate {provider.upper()} keys.")

    return unique_valid_keys

# ============================================================
# LOAD RAW API KEYS
# ============================================================
GEMINI_API_KEYS = parse_api_keys("GEMINI_API_KEY", "gemini")
GROQ_API_KEYS = parse_api_keys("GROQ_API_KEY", "groq")
COHERE_API_KEYS = parse_api_keys("COHERE_API_KEY", "cohere")
REPLICATE_API_KEYS = parse_api_keys("REPLICATE_API_KEY", "replicate")
HF_API_TOKENS = parse_api_keys("HF_API_TOKEN", "huggingface") # Nama env var beda
OPENROUTER_API_KEYS = parse_api_keys("OPENROUTER_API_KEY", "openrouter")
MISTRAL_API_KEYS = parse_api_keys("MISTRAL_API_KEY", "mistral")
# FIREWORKS_API_KEYS = parse_api_keys("FIREWORKS_API_KEY", "fireworks") # Dihapus
# ============================================================

# ============================================================
# TELEGRAM CONFIG
# ============================================================
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
# ============================================================

# ============================================================
# PROXY POOL CLASS
# ============================================================
class ProxyPool:
    def __init__(self, proxies: List[str]):
        self.proxies = list(dict.fromkeys(proxies)) # Hapus duplikat saat init
        # Jika ada proxy, buat iterator cycle. Jika tidak, set ke None.
        self.pool = cycle(self.proxies) if self.proxies else None
        self.failed_proxies: Dict[str, float] = {} # {proxy_url: failure_timestamp}
        self.cooldown_period = 300 # Cooldown 5 menit (300 detik)

    def get_next_proxy(self) -> Optional[str]:
        """Dapatkan proxy berikutnya yang valid (tidak cooldown)."""
        if not self.pool: # Jika tidak ada proxy sama sekali
            return None

        # Coba cari proxy yg tidak cooldown
        start_marker = next(self.pool) # Ambil satu proxy awal sebagai penanda
        current = start_marker
        checked_count = 0

        while checked_count < len(self.proxies):
            fail_time = self.failed_proxies.get(current)
            if fail_time is None or (time.time() - fail_time > self.cooldown_period):
                # Ditemukan proxy yg OK (tidak gagal atau sudah cooldown)
                if fail_time is not None: # Hapus dari daftar gagal jika sudah cooldown
                    try: del self.failed_proxies[current]
                    except KeyError: pass # Abaikan jika sudah dihapus
                # logger.debug(f"Using proxy: {current.split('@')[-1]}")
                return current # Kembalikan proxy yg valid

            # Jika masih cooldown, lanjut ke proxy berikutnya
            current = next(self.pool)
            checked_count += 1

            # Hindari infinite loop jika semua proxy cooldown & start_marker juga cooldown
            if current == start_marker and checked_count >= len(self.proxies):
                 break

        # Jika loop selesai (semua proxy gagal & masih cooldown)
        logger.warning(f"All {len(self.proxies)} proxies seem to be in cooldown.")
        # Fallback: Cari proxy yang gagal paling lama
        if self.failed_proxies:
            try:
                oldest_failed = min(self.failed_proxies, key=self.failed_proxies.get)
                del self.failed_proxies[oldest_failed] # Hapus dari daftar gagal
                logger.info(f"Retrying oldest failed proxy: {oldest_failed.split('@')[-1]}")
                # Set iterator pool ke proxy ini agar berikutnya mulai dari sini lagi
                while next(self.pool) != oldest_failed: pass
                return oldest_failed
            except (ValueError, KeyError) as e: # Handle jika dict kosong atau key hilang
                 logger.error(f"Error finding oldest failed proxy: {e}. Returning None.")
                 return None # Gagal total

        # Jika tidak ada proxy yg gagal (tapi loop selesai?), return None
        logger.error("Proxy pool logic error: Could not select a proxy despite having options.")
        return None

    def mark_failed(self, proxy: str):
        """Tandai proxy sebagai gagal dan catat waktunya."""
        if proxy in self.proxies:
            self.failed_proxies[proxy] = time.time()
            logger.warning(f"Proxy failed & marked for cooldown ({self.cooldown_period}s): {proxy.split('@')[-1]}")

    def reload(self, new_proxies: List[str]):
        """Reload pool dengan daftar proxy baru."""
        new_unique_proxies = list(dict.fromkeys(new_proxies)) # Hapus duplikat
        logger.info(f"Reloading ProxyPool: Old count={len(self.proxies)}, New count={len(new_unique_proxies)}")
        self.proxies = new_unique_proxies
        self.pool = cycle(self.proxies) if self.proxies else None
        self.failed_proxies = {} # Reset daftar proxy gagal
        logger.info("ProxyPool reloaded.")

# ============================================================
# PROXY LOADING FUNCTION
# ============================================================
def load_proxies(file_path: str = os.path.join(ROOT_DIR, "data", "proxy.txt")) -> List[str]:
    """Load proxy dari file (format http://user:pass@host:port)."""
    if not os.path.exists(file_path):
        logger.info(f"Proxy file not found: {file_path}. Running without proxies.")
        return []
    proxies = []; line_count = 0; added_count = 0; skipped_count = 0
    try:
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            for line_num, line in enumerate(f, 1):
                line_count += 1; line = line.strip()
                if not line or line.startswith('#'): skipped_count += 1; continue
                # Validasi format http://... atau https://...
                if line.startswith("http://") or line.startswith("https://"):
                    proxies.append(line); added_count += 1
                else:
                    logger.warning(f"Invalid proxy format on line {line_num} (skipped): {line}")
                    skipped_count += 1
    except Exception as e:
        logger.error(f"Error reading proxy file {file_path}: {e}")
        return []

    # Log summary SETELAH selesai baca file
    logger.info(f"Proxy loading summary: Read={line_count}, Added={added_count}, Skipped={skipped_count} from '{os.path.basename(file_path)}'.")
    if added_count == 0 and line_count > skipped_count:
        logger.warning(f"No valid proxies (http:// or https://) found in '{os.path.basename(file_path)}'.")
    elif added_count > 0:
        logger.info(f"Initialized ProxyPool with {added_count} proxies.")

    return proxies

# ============================================================
# INISIALISASI PROXY POOL GLOBAL
# ============================================================
# Load proxies dan buat pool global SETELAH logging siap
PROXY_LIST = load_proxies()
PROXY_POOL = ProxyPool(PROXY_LIST) if PROXY_LIST else None

# ============================================================
# FUNGSI RELOAD PROXY POOL
# ============================================================
def reload_proxy_pool():
    """Reloads the global PROXY_POOL object after sync."""
    global PROXY_POOL, PROXY_LIST # Pastikan bisa modifikasi global
    logger.info("Attempting to reload global proxy pool...")
    new_proxy_list = load_proxies() # Baca lagi proxy.txt yang (mungkin) baru

    if PROXY_POOL:
        PROXY_POOL.reload(new_proxy_list) # Panggil method reload di object pool
        PROXY_LIST = new_proxy_list # Update juga list global mentahnya (opsional)
    else:
        # Jika pool belum ada (misal run pertama kali tanpa proxy), buat baru
        PROXY_POOL = ProxyPool(new_proxy_list) if new_proxy_list else None
        PROXY_LIST = new_proxy_list
        if PROXY_POOL: logger.info("Initialized global proxy pool after reload.")
        else: logger.warning("Proxy pool remains empty after reload attempt.")
    # Log status akhir pool
    if PROXY_POOL and PROXY_POOL.proxies: logger.info(f"Proxy pool active with {len(PROXY_POOL.proxies)} proxies.")
    elif PROXY_POOL: logger.warning("Proxy pool active but has no proxies loaded.")
    else: logger.warning("Proxy pool is inactive (None).")
# ============================================================

# ============================================================
# APP SETTINGS
# ============================================================
APP_NAME = "GitHub Asset Generator"
APP_VERSION = "v19.4 (Webshare Integrated)" # Update versi
TEMP_FILES_DIR = os.path.join(ROOT_DIR, "temp_files")
# Path LOG_FILE sudah dihandle di setup_logging
os.makedirs(TEMP_FILES_DIR, exist_ok=True)
# ============================================================

# ============================================================
# VALIDATION FUNCTION (Panggil di Awal Bot Start)
# ============================================================
def validate_config():
    """Validasi konfigurasi penting dari .env."""
    # Validasi Telegram
    if not all([TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID]):
        logger.critical("❌ CONFIG ERROR: Missing Telegram keys (TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID) in .env")
        sys.exit(1)
    else:
        logger.info("✅ Telegram config OK.")

    # Validasi AI Keys (minimal 1 provider harus ada)
    any_ai_keys = bool(GEMINI_API_KEYS or GROQ_API_KEYS or COHERE_API_KEYS or REPLICATE_API_KEYS or HF_API_TOKENS or OPENROUTER_API_KEYS or MISTRAL_API_KEYS)
    if not any_ai_keys:
        logger.critical("❌ CONFIG ERROR: No valid AI API keys found in .env for ANY provider.")
        logger.critical("   Please add keys for at least one: GEMINI_API_KEY, COHERE_API_KEY, OPENROUTER_API_KEY, etc.")
        sys.exit(1)
    else:
        logger.info("✅ AI provider keys found:")
        if GEMINI_API_KEYS: logger.info(f"   - Gemini: {len(GEMINI_API_KEYS)} key(s)")
        if GROQ_API_KEYS: logger.info(f"   - Groq: {len(GROQ_API_KEYS)} key(s) (Note: May be rate-limited/suspended)")
        if COHERE_API_KEYS: logger.info(f"   - Cohere: {len(COHERE_API_KEYS)} key(s)")
        if REPLICATE_API_KEYS: logger.info(f"   - Replicate: {len(REPLICATE_API_KEYS)} key(s)")
        if HF_API_TOKENS: logger.info(f"   - HuggingFace: {len(HF_API_TOKENS)} token(s)")
        if OPENROUTER_API_KEYS: logger.info(f"   - OpenRouter: {len(OPENROUTER_API_KEYS)} key(s)")
        if MISTRAL_API_KEYS: logger.info(f"   - Mistral: {len(MISTRAL_API_KEYS)} key(s)")

    # Validasi Webshare Config (jika fitur aktif)
    logger.info(f"ℹ️ Webshare IP Sync Feature: {'ENABLED' if ENABLE_WEBSHARE_IP_SYNC else 'DISABLED'}")
    if ENABLE_WEBSHARE_IP_SYNC:
         webshare_keys_path = os.path.join(ROOT_DIR, "data", "apikeys.txt")
         if not os.path.exists(webshare_keys_path):
              logger.warning(f"   ⚠️ Webshare IP Sync is ENABLED, but 'apikeys.txt' not found in 'data/' directory.")
         else:
              # Coba load keys untuk cek isinya
              ws_keys = load_webshare_apikeys(webshare_keys_path) # Gunakan fungsi dari proxy.py
              if not ws_keys:
                  logger.warning(f"   ⚠️ Webshare IP Sync is ENABLED, but 'apikeys.txt' seems empty or invalid.")
              else:
                  logger.info(f"   ✅ Webshare API key file found and contains {len(ws_keys)} key(s).")

    # Status Proxy Pool (sudah dilog oleh load_proxies dan reload_proxy_pool)
    if PROXY_POOL and PROXY_POOL.proxies:
        logger.info(f"✅ Proxy Pool Initialized with {len(PROXY_POOL.proxies)} proxies.")
    elif PROXY_POOL:
         logger.warning("   ⚠️ Proxy Pool Initialized but is empty (check data/proxy.txt).")
    else:
        logger.info("ℹ️ Proxy Pool Not Initialized (no proxies found in data/proxy.txt).")

    logger.info("--- Configuration Validation Complete ---")
# ============================================================
