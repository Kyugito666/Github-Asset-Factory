# src/modules/proxy.py

import os
import random
import shutil
import time
import re
import logging
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed

# Import ROOT_DIR dari config
# Ganti ..config jadi .config karena file ini ada di src/modules/
from ..config import ROOT_DIR

logger = logging.getLogger(__name__)

# --- Konfigurasi Path (Relatif ke ROOT_DIR) ---
PROXYLIST_SOURCE_FILE = os.path.join(ROOT_DIR, "data", "proxylist_downloaded.txt") # File sementara hasil download
PROXY_SOURCE_FILE = os.path.join(ROOT_DIR, "data", "proxy.txt") # File proxy utama yang dipakai bot
APILIST_SOURCE_FILE = os.path.join(ROOT_DIR, "data", "apilist.txt") # Daftar URL API download
FAIL_PROXY_FILE = os.path.join(ROOT_DIR, "history", "fail_proxy.txt") # Simpan proxy gagal di history
PROXY_BACKUP_FILE = os.path.join(ROOT_DIR, "history", "proxy_backup.txt") # Simpan backup di history

# --- Konfigurasi Testing (dari ProxySync main.py) ---
PROXY_TIMEOUT = 15 # Timeout tes proxy (detik) - Turunkan dari 20 ke 15
MAX_WORKERS = 10   # Jumlah tes simultan - Turunkan dari 15 ke 10
CHECK_URLS = ["https://api.ipify.org", "http://httpbin.org/ip"] # Target tes koneksi dasar

# --- FUNGSI LOGIKA (Adaptasi dari ProxySync) ---

def load_apis(file_path):
    """Memuat daftar URL API dari file."""
    if not os.path.exists(file_path):
        logger.warning(f"File API list not found: {file_path}. Creating empty file.")
        try:
            os.makedirs(os.path.dirname(file_path), exist_ok=True)
            with open(file_path, "w") as f:
                f.write("# Masukkan URL API download proxy Anda di sini, satu per baris\n")
        except IOError as e:
            logger.error(f"Failed to create API list file: {e}")
        return []
    try:
        with open(file_path, "r", encoding='utf-8') as f: # Tambah encoding utf-8
            return [line.strip() for line in f if line.strip() and not line.strip().startswith("#")]
    except IOError as e:
        logger.error(f"Failed to read API list file {file_path}: {e}")
        return []

def fetch_from_api(url):
    """Mengunduh dari satu URL API dengan retry."""
    max_retries = 2
    headers = {'User-Agent': 'Mozilla/5.0'} # Tambah User-Agent
    for attempt in range(max_retries):
        try:
            response = requests.get(url, timeout=45, headers=headers) # Timeout download 45s
            response.raise_for_status()
            content = response.text.strip()
            if content:
                # Cek jika konten adalah HTML (indikasi halaman error/login)
                if content.lower().startswith("<!doctype html") or "<html" in content.lower():
                     error_message = f"API returned HTML page, possibly error/login page."
                     logger.warning(f"Warning for {url}: {error_message}")
                     return url, [], error_message # Anggap gagal jika HTML
                return url, content.splitlines(), None # Sukses
            error_message = "API returned no content"
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 429: # Rate limit
                wait_time = 5 * (attempt + 1)
                logger.warning(f"Rate limit hit for {url}. Waiting {wait_time}s...")
                time.sleep(wait_time)
                error_message = str(e)
                continue # Coba lagi
            else:
                error_message = f"HTTP Error {e.response.status_code}"
                logger.error(f"Failed download {url}: {error_message}")
                break # Gagal permanen untuk error HTTP lain
        except requests.exceptions.RequestException as e: # Error koneksi/timeout
            error_message = f"Connection Error: {e}"
            logger.warning(f"Failed download attempt {attempt+1}/{max_retries} for {url}: {error_message}")
            time.sleep(2 * (attempt + 1)) # Tunggu sebelum retry
        # Loop akan retry jika continue
    logger.error(f"Final failure downloading from {url} after {max_retries} attempts: {error_message}")
    return url, [], error_message # Return gagal setelah semua retry

def download_proxies_from_apis():
    """Mengunduh proksi dari semua API ke PROXYLIST_SOURCE_FILE."""
    api_urls = load_apis(APILIST_SOURCE_FILE)
    if not api_urls:
        logger.error(f"'{APILIST_SOURCE_FILE}' is empty or not found. Cannot download proxies.")
        return []

    logger.info(f"Downloading proxies from {len(api_urls)} APIs...")
    all_downloaded_proxies = []
    processed_count = 0
    # Download satu per satu untuk keandalan
    for url in api_urls:
        processed_count += 1
        logger.info(f"[{processed_count}/{len(api_urls)}] Downloading from {url[:70]}...")
        _, proxies, error = fetch_from_api(url)
        if error:
            # Tidak perlu log error lagi, sudah di fetch_from_api
            pass
        else:
            logger.info(f"Downloaded {len(proxies)} potential proxies from {url[:70]}.")
            all_downloaded_proxies.extend(proxies)
        time.sleep(0.5) # Jeda singkat antar API

    if not all_downloaded_proxies:
        logger.warning("No proxies were downloaded from any API.")
        return []

    try:
        os.makedirs(os.path.dirname(PROXYLIST_SOURCE_FILE), exist_ok=True)
        with open(PROXYLIST_SOURCE_FILE, "w", encoding='utf-8') as f: # Tambah encoding
            for proxy in all_downloaded_proxies:
                f.write(proxy + "\n")
        logger.info(f"Saved {len(all_downloaded_proxies)} downloaded lines to '{PROXYLIST_SOURCE_FILE}'.")
        return all_downloaded_proxies
    except IOError as e:
        logger.error(f"Failed to write downloaded proxies to '{PROXYLIST_SOURCE_FILE}': {e}")
        return []

def convert_proxylist_to_http(input_file, output_file):
    """Konversi format proxy di input_file ke format http di output_file."""
    if not os.path.exists(input_file):
        logger.error(f"Cannot convert: Input file '{input_file}' not found.")
        return False
    try:
        # Baca dengan ignore error encoding
        with open(input_file, "r", encoding='utf-8', errors='ignore') as f: lines = f.readlines()
    except IOError as e:
        logger.error(f"Failed to read '{input_file}': {e}"); return False

    if not lines:
        logger.info(f"'{input_file}' is empty. Nothing to convert.")
        if os.path.exists(output_file):
            try: os.remove(output_file); logger.info(f"Removed empty output file '{output_file}'.")
            except OSError as e: logger.warning(f"Could not remove existing empty output file '{output_file}': {e}")
        return True # Anggap sukses jika input kosong

    # Tahap 1: Bersihkan prefix http/https jika ada DAN baris kosong/komen
    cleaned_proxies_raw = []
    for line in lines:
        line = line.strip()
        if not line or line.startswith("#"): continue # Skip komen dan baris kosong
        if line.startswith("http://"): line = line[7:]
        elif line.startswith("https://"): line = line[8:]
        cleaned_proxies_raw.append(line)

    if not cleaned_proxies_raw:
        logger.info(f"'{input_file}' contains only comments or empty lines. Nothing to convert.")
        # Hapus file input jika kosong setelah dibersihkan
        try: os.remove(input_file); logger.info(f"Removed empty/commented input file '{input_file}'.")
        except OSError as e: logger.warning(f"Could not remove temporary file '{input_file}': {e}")
        return True

    # Tahap 2: Konversi format
    converted_proxies = []
    malformed_count = 0
    processed_count = 0
    total_raw = len(cleaned_proxies_raw)

    logger.info(f"Starting conversion for {total_raw} raw proxy lines...")

    # Regex untuk host (IP v4 atau domain) dan port
    host_pattern = r"((?:[0-9]{1,3}\.){3}[0-9]{1,3}|(?:[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?\.)+[a-zA-Z]{2,})"
    port_pattern = r"[0-9]{1,5}"

    for p in cleaned_proxies_raw:
        processed_count += 1
        converted = None

        # A. Coba USER:PASS@HOST:PORT (format paling umum)
        match_user_pass_host_port = re.match(rf"^(?P<user_pass>.+)@(?P<host>{host_pattern}):(?P<port>{port_pattern})$", p)
        if match_user_pass_host_port:
            user_pass = match_user_pass_host_port.group("user_pass")
            host = match_user_pass_host_port.group("host")
            port_str = match_user_pass_host_port.group("port")
            if port_str.isdigit() and 1 <= int(port_str) <= 65535:
                converted = f"http://{user_pass}@{host}:{port_str}"
            else:
                malformed_count += 1; logger.debug(f"Skipping invalid port in USER:PASS@HOST:PORT: {p}")

        # B. Coba HOST:PORT:USER:PASS (format alternatif)
        elif not converted and p.count(':') == 3 and '@' not in p:
            parts = p.split(':')
            host, port_str, user, password = parts
            if re.match(rf"^{host_pattern}$", host) and port_str.isdigit() and 1 <= int(port_str) <= 65535:
                 converted = f"http://{user}:{password}@{host}:{port_str}"
            else:
                 malformed_count += 1; logger.debug(f"Skipping invalid host/port in HOST:PORT:USER:PASS: {p}")

        # C. Coba HOST:PORT (tanpa auth)
        elif not converted and p.count(':') == 1 and '@' not in p:
            parts = p.split(':')
            host, port_str = parts
            if re.match(rf"^{host_pattern}$", host) and port_str.isdigit() and 1 <= int(port_str) <= 65535:
                converted = f"http://{host}:{port_str}"
            else:
                 malformed_count += 1; logger.debug(f"Skipping invalid host/port in HOST:PORT: {p}")

        # D. Jika ada '@' tapi tidak cocok format A (mungkin HOST:PORT@USER:PASS?)
        elif not converted and '@' in p and p.count(':') == 2:
             try:
                 host_part, user_part = p.split('@', 1)
                 host, port_str = host_part.split(':', 1)
                 user, password = user_part.split(':', 1) # Asumsi format user:pass
                 if re.match(rf"^{host_pattern}$", host) and port_str.isdigit() and 1 <= int(port_str) <= 65535:
                     converted = f"http://{user}:{password}@{host}:{port_str}"
                 else:
                     malformed_count += 1; logger.debug(f"Skipping invalid host/port in HOST:PORT@USER:PASS: {p}")
             except ValueError:
                 malformed_count += 1; logger.debug(f"Skipping malformed proxy (expected HOST:PORT@USER:PASS): {p}")


        # Jika berhasil dikonversi
        if converted:
            converted_proxies.append(converted)
        elif not match_user_pass_host_port and ':' not in p and '@' not in p: # Handle jika cuma IP/Host tanpa port
             malformed_count += 1
             logger.debug(f"Skipping entry without port: {p}")
        elif converted is None: # Jika sudah dicoba semua tapi gagal
             malformed_count += 1
             # logger.warning(f"Unrecognized proxy format skipped: {p}") # Kurangi noise

        if processed_count % 1000 == 0: logger.info(f"Conversion progress: {processed_count}/{total_raw} lines...")


    if malformed_count > 0:
        logger.warning(f"Skipped {malformed_count} lines due to unrecognized/invalid format during conversion.")

    if not converted_proxies:
        logger.error("No valid proxies could be converted to http format.")
        try: os.remove(input_file); logger.info(f"Removed empty/failed input file '{input_file}'.")
        except OSError as e: logger.warning(f"Could not remove temporary file '{input_file}': {e}")
        return False

    try:
        os.makedirs(os.path.dirname(output_file), exist_ok=True)
        unique_converted = sorted(list(set(converted_proxies)))
        duplicates_removed = len(converted_proxies) - len(unique_converted)
        if duplicates_removed > 0: logger.info(f"Removed {duplicates_removed} duplicates during conversion.")

        with open(output_file, "w", encoding='utf-8') as f:
            for proxy in unique_converted: f.write(proxy + "\n")
        logger.info(f"Successfully converted and saved {len(unique_converted)} unique proxies to '{output_file}'.")
        try: os.remove(input_file); logger.info(f"Removed temporary input file '{input_file}'.")
        except OSError as e: logger.warning(f"Could not remove temporary file '{input_file}': {e}")
        return True
    except IOError as e:
        logger.error(f"Failed to write converted proxies to '{output_file}': {e}")
        return False

def load_and_deduplicate_proxies(file_path):
    """Load, deduplicate, and overwrite file. Returns unique list."""
    if not os.path.exists(file_path):
        logger.warning(f"File not found for deduplication: {file_path}")
        return []
    try:
        # Baca dengan ignore error encoding
        with open(file_path, "r", encoding='utf-8', errors='ignore') as f:
            proxies = [line.strip() for line in f if line.strip() and not line.startswith("#")]
    except IOError as e:
        logger.error(f"Failed to read {file_path} for deduplication: {e}")
        return []

    unique_proxies = sorted(list(set(proxies)))
    removed_count = len(proxies) - len(unique_proxies)
    if removed_count > 0:
        logger.info(f"Removed {removed_count} duplicate proxies from '{os.path.basename(file_path)}'.")
        try:
            with open(file_path, "w", encoding='utf-8') as f:
                for proxy in unique_proxies: f.write(proxy + "\n")
            logger.info(f"Overwrote '{os.path.basename(file_path)}' with {len(unique_proxies)} unique proxies.")
        except IOError as e:
            logger.error(f"Failed to overwrite {file_path} after deduplication: {e}")
            return unique_proxies # Kembalikan list unik jika gagal nulis
    # Jika tidak ada duplikat, tidak perlu overwrite
    elif len(proxies) > 0:
         logger.info(f"No duplicates found in '{os.path.basename(file_path)}' ({len(proxies)} unique).")

    return unique_proxies

def check_proxy_final(proxy):
    """Tes koneksi proxy ke CHECK_URLS (versi sederhana tanpa GitHub token)."""
    proxies_dict = {"http": proxy, "https": proxy}
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
    for url in CHECK_URLS:
        try:
            with requests.Session() as session:
                 session.proxies = proxies_dict
                 session.headers.update(headers)
                 # Timeout per URL check
                 response = session.get(url, timeout=PROXY_TIMEOUT)

            response.raise_for_status() # Cek status 2xx
            content = response.text.strip()
            # Cek kasar apakah isinya IP address
            if re.search(r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}', content):
                # logger.debug(f"Proxy {proxy.split('@')[-1]} OK via {url}")
                return proxy, True, f"OK via {url}" # Berhasil
            else:
                logger.debug(f"Proxy {proxy.split('@')[-1]} returned unexpected content from {url}: {content[:60]}...")
                # Coba URL berikutnya jika ada

        except requests.exceptions.HTTPError as e:
             if e.response.status_code == 407:
                 logger.debug(f"Proxy {proxy.split('@')[-1]} requires auth (407) on {url}")
                 return proxy, False, "Authentication Required (407)" # Gagal permanen
             else:
                 logger.debug(f"HTTP Error for {proxy.split('@')[-1]} on {url}: {e.response.status_code}")
                 # Coba URL berikutnya
        except requests.exceptions.Timeout:
             logger.debug(f"Timeout for {proxy.split('@')[-1]} on {url}")
             # Coba URL berikutnya
        except requests.exceptions.ProxyError as e:
             reason = str(e).split(':')[-1].strip() # Ambil reason error
             logger.debug(f"Proxy Error for {proxy.split('@')[-1]} on {url}: {reason[:40]}")
             # Anggap gagal permanen untuk proxy error
             return proxy, False, f"Proxy Error ({reason[:30]})"
        except requests.exceptions.RequestException as e:
             logger.debug(f"Connection Error for {proxy.split('@')[-1]} on {url}: {e.__class__.__name__}")
             # Coba URL berikutnya

    # Jika loop selesai tanpa return True
    logger.debug(f"Proxy {proxy.split('@')[-1]} failed all check URLs.")
    return proxy, False, "Connection Failed / Bad Response"

def run_proxy_test(proxies_to_test):
    """Tes proxy secara concurrent."""
    if not proxies_to_test:
        logger.info("No proxies to test.")
        return []

    logger.info(f"Testing {len(proxies_to_test)} proxies (Max workers: {MAX_WORKERS}, Timeout: {PROXY_TIMEOUT}s)...")
    good_proxies = []
    failed_proxies_details = []
    tested_count = 0
    total_proxies = len(proxies_to_test)

    executor = ThreadPoolExecutor(max_workers=MAX_WORKERS)
    try:
        future_to_proxy = {executor.submit(check_proxy_final, p): p for p in proxies_to_test}
        log_interval = max(1, total_proxies // 20) # Log progress ~20 kali

        for future in as_completed(future_to_proxy):
            try:
                proxy, is_good, message = future.result()
                tested_count += 1
                if is_good:
                    good_proxies.append(proxy)
                else:
                    failed_proxies_details.append((proxy, message))

                if tested_count % log_interval == 0 or tested_count == total_proxies:
                     progress_percent = (tested_count / total_proxies) * 100
                     logger.info(f"Proxy Test Progress: {tested_count}/{total_proxies} ({progress_percent:.1f}%) - Found {len(good_proxies)} good.")

            except Exception as exc:
                proxy_key = future_to_proxy[future]
                logger.error(f"Error processing proxy {proxy_key.split('@')[-1]}: {exc}")
                failed_proxies_details.append((proxy_key, f"Task Error: {exc}"))
                tested_count += 1 # Pastikan count tetap naik
    finally:
         executor.shutdown(wait=True)

    # Simpan proxy gagal
    if failed_proxies_details:
        try:
            os.makedirs(os.path.dirname(FAIL_PROXY_FILE), exist_ok=True)
            with open(FAIL_PROXY_FILE, "w", encoding='utf-8') as f:
                for p, reason in failed_proxies_details:
                    f.write(f"{p} # {reason}\n")
            logger.info(f"Saved {len(failed_proxies_details)} failed proxies/errors to '{FAIL_PROXY_FILE}'.")
        except IOError as e:
            logger.error(f"Failed to save failed proxies: {e}")

    logger.info(f"Proxy test complete. Found {len(good_proxies)} working proxies out of {total_proxies} tested.")
    return good_proxies

def sync_proxies():
    """Fungsi utama untuk menjalankan seluruh proses sync. Returns True/False."""
    start_time = time.time()
    logger.info("===== Starting Proxy Sync Process =====")

    # 1. Download dari API -> data/proxylist_downloaded.txt
    logger.info("--- Step 1: Downloading Proxies ---")
    downloaded = download_proxies_from_apis()
    # 'downloaded' is the list of lines, could be empty.

    # 2. Konversi hasil download (jika ada) ke data/proxy.txt
    #    Jika download gagal/kosong, langkah ini akan skip atau gagal,
    #    dan kita akan lanjut menggunakan proxy.txt yang sudah ada.
    if downloaded: # Hanya konversi jika ada hasil download
        logger.info("--- Step 2: Converting Downloaded Proxies ---")
        if not convert_proxylist_to_http(PROXYLIST_SOURCE_FILE, PROXY_SOURCE_FILE):
             logger.error("Failed during proxy format conversion. Aborting sync.")
             return False # Gagal
    else:
        logger.warning("No proxies downloaded from APIs. Will proceed using existing 'proxy.txt' if available.")
        # Lanjut ke langkah 3 (backup & load proxy.txt yang ada)

    # 3. Backup data/proxy.txt yang sekarang -> history/proxy_backup.txt
    logger.info("--- Step 3: Backing Up Current Proxy List ---")
    try:
        if os.path.exists(PROXY_SOURCE_FILE):
            os.makedirs(os.path.dirname(PROXY_BACKUP_FILE), exist_ok=True)
            shutil.copy(PROXY_SOURCE_FILE, PROXY_BACKUP_FILE)
            logger.info(f"Created backup: '{PROXY_BACKUP_FILE}'")
        else:
            logger.info("No 'proxy.txt' found to back up (perhaps first run or download failed?).")
    except Exception as e:
        logger.warning(f"Failed to create proxy backup: {e}")

    # 4. Load data/proxy.txt, Deduplikasi, dan Overwrite file itu sendiri
    logger.info("--- Step 4: Loading and Deduplicating Proxies ---")
    proxies_to_test = load_and_deduplicate_proxies(PROXY_SOURCE_FILE)
    if not proxies_to_test:
        logger.error("No unique proxies found in 'proxy.txt' to test. Aborting sync.")
        return False # Gagal

    # 5. Tes proxy
    logger.info("--- Step 5: Testing Proxies ---")
    good_proxies = run_proxy_test(proxies_to_test)

    # 6. Overwrite data/proxy.txt HANYA dengan proxy yang bagus
    logger.info("--- Step 6: Updating Final Proxy List ---")
    if not good_proxies:
        logger.error("No working proxies found after testing. 'proxy.txt' will NOT be updated to prevent emptying the list.")
        logger.error("Check 'history/fail_proxy.txt' for failure details.")
        result = False # Gagal
    else:
        try:
            random.shuffle(good_proxies) # Acak urutan
            with open(PROXY_SOURCE_FILE, "w", encoding='utf-8') as f:
                for proxy in good_proxies:
                    f.write(proxy + "\n")
            logger.info(f"Successfully overwrote '{PROXY_SOURCE_FILE}' with {len(good_proxies)} tested working proxies.")
            result = True # Sukses
        except IOError as e:
            logger.error(f"Failed to overwrite '{PROXY_SOURCE_FILE}' with good proxies: {e}")
            result = False # Gagal

    end_time = time.time()
    duration = end_time - start_time
    logger.info(f"===== Proxy Sync Process Finished in {duration:.2f} seconds (Success: {result}) =====")
    return result

# Jika file ini dijalankan langsung (untuk testing)
if __name__ == "__main__":
    print("Running proxy sync module directly for testing...")
    # Setup basic logging ke console untuk testing
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    # Pastikan file dummy ada
    if not os.path.exists(APILIST_SOURCE_FILE):
        print(f"Creating dummy {APILIST_SOURCE_FILE}...")
        os.makedirs(os.path.dirname(APILIST_SOURCE_FILE), exist_ok=True)
        with open(APILIST_SOURCE_FILE, "w") as f:
            f.write("https://api.proxyscrape.com/v2/?request=getproxies&protocol=http&timeout=10000&country=all&ssl=all&anonymity=all\n")
            f.write("https://raw.githubusercontent.com/TheSpeedX/PROXY-List/master/http.txt\n")
            f.write("https://raw.githubusercontent.com/zevtyardt/proxy-list/main/http.txt\n")


    success = sync_proxies()
    print(f"Sync process completed. Success: {success}")
    if success:
        print(f"Check '{PROXY_SOURCE_FILE}' for results.")
        print(f"Check '{FAIL_PROXY_FILE}' for failures.")
