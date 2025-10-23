import os
import random
import shutil
import time
import re
import logging
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed

# Import ROOT_DIR dari config
from ..config import ROOT_DIR

logger = logging.getLogger(__name__)

# --- Konfigurasi Path (Relatif ke ROOT_DIR) ---
PROXYLIST_SOURCE_FILE = os.path.join(ROOT_DIR, "data", "proxylist_downloaded.txt")
PROXY_SOURCE_FILE = os.path.join(ROOT_DIR, "data", "proxy.txt")
APILIST_SOURCE_FILE = os.path.join(ROOT_DIR, "data", "apilist.txt")
FAIL_PROXY_FILE = os.path.join(ROOT_DIR, "history", "fail_proxy.txt")
PROXY_BACKUP_FILE = os.path.join(ROOT_DIR, "history", "proxy_backup.txt")

# --- Konfigurasi Testing ---
PROXY_TIMEOUT = 15
MAX_WORKERS = 10
CHECK_URLS = ["https://api.ipify.org", "http://httpbin.org/ip"]

# --- FUNGSI LOGIKA (Adaptasi dari ProxySync) ---

def load_apis(file_path):
    # ... (kode load_apis tidak berubah) ...
    if not os.path.exists(file_path):
        logger.warning(f"File API list not found: {file_path}. Creating empty file.")
        try:
            os.makedirs(os.path.dirname(file_path), exist_ok=True)
            with open(file_path, "w") as f: f.write("# Masukkan URL API download proxy Anda di sini, satu per baris\n")
        except IOError as e: logger.error(f"Failed to create API list file: {e}")
        return []
    try:
        with open(file_path, "r") as f: return [line.strip() for line in f if line.strip() and not line.strip().startswith("#")]
    except IOError as e: logger.error(f"Failed to read API list file {file_path}: {e}"); return []


def fetch_from_api(url):
    # ... (kode fetch_from_api tidak berubah) ...
    max_retries = 2
    for attempt in range(max_retries):
        try:
            response = requests.get(url, timeout=45)
            response.raise_for_status()
            content = response.text.strip()
            if content: return url, content.splitlines(), None
            error_message = "API returned no content"
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 429:
                wait_time = 5 * (attempt + 1); logger.warning(f"Rate limit hit for {url}. Waiting {wait_time}s..."); time.sleep(wait_time); error_message = str(e); continue
            else: error_message = str(e); break
        except requests.exceptions.RequestException as e: error_message = str(e); time.sleep(2 * (attempt + 1))
    return url, [], error_message

def download_proxies_from_apis():
    # ... (kode download_proxies_from_apis tidak berubah) ...
    api_urls = load_apis(APILIST_SOURCE_FILE)
    if not api_urls: logger.error(f"'{APILIST_SOURCE_FILE}' is empty or not found."); return []
    logger.info(f"Downloading proxies from {len(api_urls)} APIs...")
    all_downloaded_proxies = []
    processed_count = 0
    for url in api_urls:
        processed_count += 1; logger.info(f"[{processed_count}/{len(api_urls)}] Downloading from {url[:60]}...")
        _, proxies, error = fetch_from_api(url)
        if error: logger.error(f"Failed to download from {url[:60]}: {error}")
        else: logger.info(f"Downloaded {len(proxies)} proxies from {url[:60]}."); all_downloaded_proxies.extend(proxies)
        time.sleep(1)
    if not all_downloaded_proxies: logger.warning("No proxies downloaded."); return []
    try:
        os.makedirs(os.path.dirname(PROXYLIST_SOURCE_FILE), exist_ok=True)
        with open(PROXYLIST_SOURCE_FILE, "w") as f:
            for proxy in all_downloaded_proxies: f.write(proxy + "\n")
        logger.info(f"Saved {len(all_downloaded_proxies)} downloaded proxies to '{PROXYLIST_SOURCE_FILE}'.")
        return all_downloaded_proxies
    except IOError as e: logger.error(f"Failed to write downloaded proxies: {e}"); return []

# === PERBAIKAN DI FUNGSI INI ===
def convert_proxylist_to_http(input_file, output_file):
    """Konversi format proxy di input_file ke format http di output_file."""
    if not os.path.exists(input_file):
        logger.error(f"Cannot convert: Input file '{input_file}' not found.")
        return False
    try:
        with open(input_file, "r") as f: lines = f.readlines()
    except IOError as e:
        logger.error(f"Failed to read '{input_file}': {e}"); return False

    if not lines:
        logger.info(f"'{input_file}' is empty. Nothing to convert.")
        if os.path.exists(output_file):
            try: os.remove(output_file); logger.info(f"Removed empty output file '{output_file}'.")
            except OSError as e: logger.warning(f"Could not remove existing empty output file '{output_file}': {e}")
        return True

    # Tahap 1: Bersihkan prefix http/https jika ada (sama seperti sebelumnya)
    cleaned_proxies = []
    for line in lines:
        line = line.strip()
        if not line: continue
        # Hapus http:// atau https:// di awal jika ada
        if line.startswith("http://"): line = line[7:]
        elif line.startswith("https://"): line = line[8:]
        cleaned_proxies.append(line)

    # Tahap 2: Konversi format
    converted_proxies = []
    malformed_count = 0
    for p in cleaned_proxies:
        # Cek format IP:PORT@USER:PASS (prioritas)
        if '@' in p and p.count(':') == 2: # Harus ada @ dan 2 titik dua
             try:
                 host_part, user_part = p.split('@', 1)
                 ip, port = host_part.split(':', 1)
                 user, password = user_part.split(':', 1)
                 converted_proxies.append(f"http://{user}:{password}@{ip}:{port}")
                 continue # Lanjut ke proxy berikutnya
             except ValueError:
                 # Jika split gagal (format tidak sesuai ekspektasi)
                 malformed_count += 1
                 logger.warning(f"Skipping malformed proxy (expected IP:PORT@USER:PASS): {p}")
                 continue

        # Cek format IP:PORT (tanpa auth)
        elif ':' in p and '@' not in p and p.count(':') == 1:
            try:
                ip, port = p.split(':', 1)
                # Validasi sederhana IP dan Port (opsional)
                # if re.match(r"^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$", ip) and port.isdigit():
                converted_proxies.append(f"http://{ip}:{port}")
                continue
                # else:
                #     malformed_count += 1
                #     logger.warning(f"Skipping invalid IP:PORT format: {p}")
                #     continue
            except ValueError:
                 malformed_count += 1
                 logger.warning(f"Skipping malformed proxy (expected IP:PORT): {p}")
                 continue

        # Cek format USER:PASS@IP:PORT (format standar yg mungkin ada)
        elif '@' in p and p.count(':') == 3: # Format standar user:pass@ip:port
             try:
                 auth_part, host_part = p.split('@', 1)
                 user, password = auth_part.split(':', 1)
                 ip, port = host_part.split(':', 1)
                 converted_proxies.append(f"http://{user}:{password}@{ip}:{port}")
                 continue
             except ValueError:
                 malformed_count += 1
                 logger.warning(f"Skipping malformed proxy (expected USER:PASS@IP:PORT): {p}")
                 continue
        
        # Jika format lain atau sudah http/https (seharusnya tidak terjadi di sini)
        elif p.startswith("http://") or p.startswith("https://"):
             converted_proxies.append(p) # Langsung tambahkan jika sudah benar
             continue

        # Jika tidak cocok semua
        else:
            malformed_count += 1
            logger.warning(f"Unrecognized proxy format skipped: {p}")

    if malformed_count > 0:
        logger.warning(f"Skipped {malformed_count} proxies due to unrecognized format during conversion.")

    if not converted_proxies:
        logger.error("No proxies could be converted to http format.")
        return False

    try:
        os.makedirs(os.path.dirname(output_file), exist_ok=True)
        with open(output_file, "w") as f:
            for proxy in converted_proxies: f.write(proxy + "\n")
        logger.info(f"Successfully converted/processed {len(converted_proxies)} proxies into '{output_file}'.")
        # Hapus file input setelah konversi sukses
        try: os.remove(input_file); logger.info(f"Removed temporary file '{input_file}'.")
        except OSError as e: logger.warning(f"Could not remove temporary file '{input_file}': {e}")
        return True
    except IOError as e:
        logger.error(f"Failed to write converted proxies to '{output_file}': {e}")
        return False
# === AKHIR PERBAIKAN ===


def load_and_deduplicate_proxies(file_path):
    # ... (kode load_and_deduplicate_proxies tidak berubah) ...
    if not os.path.exists(file_path): logger.warning(f"File not found: {file_path}"); return []
    try:
        with open(file_path, "r") as f: proxies = [line.strip() for line in f if line.strip()]
    except IOError as e: logger.error(f"Failed read {file_path}: {e}"); return []
    unique_proxies = sorted(list(set(proxies))); removed = len(proxies) - len(unique_proxies)
    if removed > 0:
        logger.info(f"Removed {removed} duplicates from '{os.path.basename(file_path)}'.")
        try:
            with open(file_path, "w") as f:
                for p in unique_proxies: f.write(p + "\n")
            logger.info(f"Overwrote '{os.path.basename(file_path)}' with {len(unique_proxies)} unique proxies.")
        except IOError as e: logger.error(f"Failed overwrite {file_path}: {e}"); return proxies
    return unique_proxies

def check_proxy_final(proxy):
    # ... (kode check_proxy_final tidak berubah) ...
    proxies_dict = {"http": proxy, "https": proxy}; headers = {'User-Agent': 'Mozilla/5.0'}
    for url in CHECK_URLS:
        try:
            response = requests.get(url, proxies=proxies_dict, timeout=PROXY_TIMEOUT, headers=headers)
            response.raise_for_status()
            if '.' in response.text or ':' in response.text: return proxy, True, f"OK via {url}"
            else: logger.debug(f"Proxy {proxy.split('@')[-1]} unexpected content {url}: {response.text[:50]}..."); continue
        except requests.exceptions.HTTPError as e:
             if e.response.status_code == 407: return proxy, False, "Auth Required (407)"
             else: logger.debug(f"HTTP Error {proxy.split('@')[-1]} on {url}: {e.response.status_code}"); continue
        except requests.exceptions.RequestException as e: logger.debug(f"Conn Error {proxy.split('@')[-1]} on {url}: {e}"); continue
    return proxy, False, "Connection Failed"

def run_proxy_test(proxies_to_test):
    # ... (kode run_proxy_test tidak berubah) ...
    if not proxies_to_test: logger.info("No proxies to test."); return []
    logger.info(f"Testing {len(proxies_to_test)} proxies (Max workers: {MAX_WORKERS}, Timeout: {PROXY_TIMEOUT}s)...")
    good_proxies = []; failed_proxies_details = []; tested_count = 0
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        future_to_proxy = {executor.submit(check_proxy_final, p): p for p in proxies_to_test}
        for future in as_completed(future_to_proxy):
            proxy, is_good, message = future.result(); tested_count += 1
            if is_good: good_proxies.append(proxy)
            else: failed_proxies_details.append((proxy, message))
            if tested_count % 50 == 0 or tested_count == len(proxies_to_test): logger.info(f"Tested {tested_count}/{len(proxies_to_test)}... (Found {len(good_proxies)} good)")
    if failed_proxies_details:
        try:
            os.makedirs(os.path.dirname(FAIL_PROXY_FILE), exist_ok=True)
            with open(FAIL_PROXY_FILE, "w") as f:
                for p, reason in failed_proxies_details: f.write(f"{p} # {reason}\n")
            logger.info(f"Saved {len(failed_proxies_details)} failed proxies to '{FAIL_PROXY_FILE}'.")
        except IOError as e: logger.error(f"Failed save failed proxies: {e}")
    logger.info(f"Test complete. Found {len(good_proxies)} working proxies.")
    return good_proxies

def sync_proxies():
    # ... (kode sync_proxies tidak berubah) ...
    logger.info("Starting Proxy Sync process...")
    downloaded = download_proxies_from_apis()
    if not downloaded: logger.warning("No proxies downloaded. Processing existing proxy.txt...")
    else:
        if not convert_proxylist_to_http(PROXYLIST_SOURCE_FILE, PROXY_SOURCE_FILE):
             logger.error("Failed proxy format conversion. Aborting sync."); return False
    try:
        if os.path.exists(PROXY_SOURCE_FILE):
            os.makedirs(os.path.dirname(PROXY_BACKUP_FILE), exist_ok=True)
            shutil.copy(PROXY_SOURCE_FILE, PROXY_BACKUP_FILE)
            logger.info(f"Created backup: '{PROXY_BACKUP_FILE}'")
    except Exception as e: logger.warning(f"Failed create backup: {e}")
    proxies_to_test = load_and_deduplicate_proxies(PROXY_SOURCE_FILE)
    if not proxies_to_test: logger.error("No unique proxies found. Aborting sync."); return False
    good_proxies = run_proxy_test(proxies_to_test)
    if not good_proxies:
        logger.error("No working proxies found. 'proxy.txt' NOT updated."); return False
    else:
        try:
            random.shuffle(good_proxies)
            with open(PROXY_SOURCE_FILE, "w") as f:
                for proxy in good_proxies: f.write(proxy + "\n")
            logger.info(f"Overwrote '{PROXY_SOURCE_FILE}' with {len(good_proxies)} working proxies.")
            return True
        except IOError as e: logger.error(f"Failed overwrite '{PROXY_SOURCE_FILE}': {e}"); return False
