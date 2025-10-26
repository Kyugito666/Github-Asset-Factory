# src/modules/proxy.py

import os
import random
import shutil
import time
import re
import logging
import requests
import sys # Tambah import sys
from concurrent.futures import ThreadPoolExecutor, as_completed

# Import ROOT_DIR dan config lain
from ..config import ROOT_DIR, ENABLE_WEBSHARE_IP_SYNC

logger = logging.getLogger(__name__)

# --- Konfigurasi Path (Relatif ke ROOT_DIR) ---
PROXYLIST_SOURCE_FILE = os.path.join(ROOT_DIR, "data", "proxylist_downloaded.txt") # File sementara hasil download
PROXY_SOURCE_FILE = os.path.join(ROOT_DIR, "data", "proxy.txt") # File proxy utama yang dipakai bot
APILIST_SOURCE_FILE = os.path.join(ROOT_DIR, "data", "apilist.txt") # Daftar URL API download manual
FAIL_PROXY_FILE = os.path.join(ROOT_DIR, "history", "fail_proxy.txt") # Simpan proxy gagal di history
PROXY_BACKUP_FILE = os.path.join(ROOT_DIR, "history", "proxy_backup.txt") # Simpan backup di history
WEBSHARE_APIKEYS_FILE = os.path.join(ROOT_DIR, "data", "apikeys.txt") # <= BARU: File API key Webshare

# --- Konfigurasi Testing (dari ProxySync main.py) ---
PROXY_TIMEOUT = 15 # Timeout tes proxy (detik)
MAX_WORKERS = 10   # Jumlah tes simultan
CHECK_URLS = ["https://api.ipify.org?format=json", "http://httpbin.org/ip"] # Target tes koneksi dasar (ipify perlu format json)

# --- Konfigurasi Webshare (dari ProxySync main.py) ---
WEBSHARE_AUTH_URL = "https://proxy.webshare.io/api/v2/proxy/ipauthorization/"
WEBSHARE_SUB_URL = "https://proxy.webshare.io/api/v2/subscription/" # Untuk cek plan ID (opsional tapi bagus)
WEBSHARE_CONFIG_URL = "https://proxy.webshare.io/api/v2/proxy/config/" # Untuk dapat download token & username
WEBSHARE_PROFILE_URL = "https://proxy.webshare.io/api/v2/profile/" # Untuk cek email (logging)
WEBSHARE_DOWNLOAD_URL_FORMAT = "https://proxy.webshare.io/api/v2/proxy/list/download/{token}/-/any/{username}/direct/-/?plan_id={plan_id}"
IP_CHECK_SERVICE_URL = "https://api.ipify.org?format=json"
WEBSHARE_API_TIMEOUT = 60 # Timeout untuk API Webshare

# --- FUNGSI LOGIKA WEBSHARE (Adaptasi dari ProxySync main.py) ---

def load_webshare_apikeys(file_path):
    """Memuat daftar API key Webshare dari file."""
    if not os.path.exists(file_path):
        logger.warning(f"Webshare API key file not found: {file_path}. Creating empty file.")
        try:
            os.makedirs(os.path.dirname(file_path), exist_ok=True)
            with open(file_path, "w", encoding='utf-8') as f:
                f.write("# Masukkan API key Webshare Anda di sini, SATU per baris\n")
        except IOError as e:
            logger.error(f"Failed to create Webshare API key file: {e}")
        return []
    try:
        with open(file_path, "r", encoding='utf-8') as f:
            keys = [line.strip() for line in f if line.strip() and not line.strip().startswith("#")]
            logger.info(f"Loaded {len(keys)} Webshare API key(s) from {os.path.basename(file_path)}.")
            return keys
    except IOError as e:
        logger.error(f"Failed to read Webshare API key file {file_path}: {e}")
        return []

def get_current_public_ip():
    """Mengambil IP publik saat ini."""
    logger.info("Webshare IP Sync: 1. Fetching current public IP...")
    try:
        response = requests.get(IP_CHECK_SERVICE_URL, timeout=15) # Timeout 15s cukup
        response.raise_for_status()
        new_ip = response.json().get("ip")
        if new_ip:
            logger.info(f"   -> Public IP found: {new_ip}")
            return new_ip
        else:
            logger.error("   -> ERROR: IP address not found in ipify response.")
            return None
    except requests.RequestException as e:
        logger.error(f"   -> ERROR: Failed to get public IP: {e}")
        return None
    except json.JSONDecodeError as e:
        logger.error(f"   -> ERROR: Failed to parse ipify response: {e}")
        return None

def get_account_email(session: requests.Session) -> str:
    """Helper untuk mendapatkan email akun (untuk logging)."""
    try:
        response = session.get(WEBSHARE_PROFILE_URL, timeout=WEBSHARE_API_TIMEOUT)
        response.raise_for_status()
        data = response.json()
        email = data.get("email")
        return email if email else "[Email N/A]"
    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 401: return "[Invalid API Key]"
        return f"[HTTP Error {e.response.status_code}]"
    except requests.RequestException: return "[Connection Error]"
    except Exception: return "[Parsing Error]"

def get_target_plan_id(session: requests.Session):
    """Mencari plan ID dari /config/ endpoint."""
    logger.info("Webshare IP Sync: 2. Getting target Plan ID via /config/ ...")
    try:
        response = session.get(WEBSHARE_CONFIG_URL, timeout=WEBSHARE_API_TIMEOUT)
        response.raise_for_status()
        data = response.json()
        plan_id = data.get("id") # Endpoint config langsung return ID plan default
        if plan_id:
            plan_id_str = str(plan_id)
            logger.info(f"   -> Found Plan ID: {plan_id_str}")
            return plan_id_str
        else:
            logger.error("   -> ERROR: '/proxy/config/' response did not contain 'id'.")
            return None
    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 401: logger.error("   -> ERROR: Invalid Webshare API Key (401).")
        else: logger.error(f"   -> ERROR: HTTP Error getting config: {e.response.status_code} - {e.response.text[:100]}")
        return None
    except requests.RequestException as e:
        logger.error(f"   -> ERROR: Connection error getting config: {e}")
        return None

def get_authorized_ips(session: requests.Session, plan_id: str):
    """Mengambil daftar IP yang sudah diotorisasi."""
    logger.info("Webshare IP Sync: 3. Getting currently authorized IPs...")
    params = {"plan_id": plan_id}
    ip_to_id_map = {} # { "ip_address": id }
    try:
        response = session.get(WEBSHARE_AUTH_URL, params=params, timeout=WEBSHARE_API_TIMEOUT)
        response.raise_for_status()
        results = response.json().get("results", [])
        for item in results:
            ip = item.get("ip_address")
            auth_id = item.get("id")
            if ip and auth_id:
                ip_to_id_map[ip] = auth_id
        if not ip_to_id_map:
            logger.info("   -> No existing authorized IPs found.")
        else:
            logger.info(f"   -> Found authorized IPs: {', '.join(ip_to_id_map.keys())}")
        return ip_to_id_map
    except requests.RequestException as e:
        logger.error(f"   -> ERROR: Failed to get authorized IPs: {e}")
        return {} # Return empty dict on error

def remove_ip(session: requests.Session, ip: str, authorization_id: int, plan_id: str):
    """Menghapus satu IP dari otorisasi."""
    logger.info(f"Webshare IP Sync:    -> Removing old IP: {ip} (ID: {authorization_id})")
    params = {"plan_id": plan_id}
    delete_url = f"{WEBSHARE_AUTH_URL}{authorization_id}/" # URL spesifik untuk delete by ID
    try:
        response = session.delete(delete_url, params=params, timeout=WEBSHARE_API_TIMEOUT)
        if response.status_code == 204:
            logger.info(f"       -> Successfully removed IP: {ip}")
            return True
        else:
            # Coba log response error jika ada
            try: error_detail = response.json()
            except: error_detail = response.text[:100]
            logger.error(f"       -> ERROR removing {ip}: Status {response.status_code} - {error_detail}")
            # response.raise_for_status() # Jangan throw, log saja
            return False
    except requests.RequestException as e:
        logger.error(f"       -> ERROR: Connection error removing {ip}: {e}")
        return False

def add_ip(session: requests.Session, ip: str, plan_id: str):
    """Menambahkan satu IP ke otorisasi."""
    logger.info(f"Webshare IP Sync:    -> Adding new IP: {ip}")
    params = {"plan_id": plan_id}
    payload = {"ip_address": ip}
    try:
        response = session.post(WEBSHARE_AUTH_URL, json=payload, params=params, timeout=WEBSHARE_API_TIMEOUT)
        if response.status_code == 201:
            logger.info(f"       -> Successfully added IP: {ip}")
            return True
        else:
            try: error_detail = response.json()
            except: error_detail = response.text[:100]
            logger.error(f"       -> ERROR adding {ip}: Status {response.status_code} - {error_detail}")
            # response.raise_for_status()
            return False
    except requests.RequestException as e:
        logger.error(f"       -> ERROR: Connection error adding {ip}: {e}")
        return False

def run_webshare_ip_sync() -> bool:
    """Fungsi orkestrasi untuk sinkronisasi IP Webshare. Returns True/False."""
    logger.info("===== Starting Webshare IP Authorization Sync =====")
    api_keys = load_webshare_apikeys(WEBSHARE_APIKEYS_FILE)
    if not api_keys:
        logger.error(f"Webshare IP Sync Aborted: API key file '{os.path.basename(WEBSHARE_APIKEYS_FILE)}' is empty or not found.")
        return False

    new_ip = get_current_public_ip()
    if not new_ip:
        logger.error("Webshare IP Sync Aborted: Failed to determine current public IP.")
        return False

    logger.info(f"Syncing IP [{new_ip}] to [{len(api_keys)}] Webshare account(s)...")
    overall_success = True # Anggap sukses sampai ada yg gagal

    for api_key in api_keys:
        email_info = "[Fetching Email...]"
        try:
             # Cek email dulu untuk logging
             with requests.Session() as email_session:
                 email_session.headers.update({"Authorization": f"Token {api_key}", "Accept": "application/json"})
                 email_info = get_account_email(email_session)
        except Exception:
             email_info = "[Error Fetching Email]"

        logger.info(f"\n--- Processing Key: [...{api_key[-6:]}] (Account: {email_info}) ---")
        account_success = False # Status sukses per akun

        with requests.Session() as session:
            session.headers.update({
                "Authorization": f"Token {api_key}",
                "Content-Type": "application/json", # Penting untuk POST/DELETE
                "Accept": "application/json"
            })
            try:
                plan_id = get_target_plan_id(session)
                if not plan_id:
                    logger.error("   -> Skipping account: Could not determine Plan ID.")
                    overall_success = False # Gagal jika plan ID tidak ketemu
                    continue # Lanjut ke key berikutnya

                authorized_ips_map = get_authorized_ips(session, plan_id)
                existing_ips = list(authorized_ips_map.keys())

                if new_ip in existing_ips:
                    logger.info(f"   -> New IP ({new_ip}) is already authorized. No changes needed for this account.")
                    account_success = True # Anggap sukses jika IP sudah ada
                    continue # Lanjut ke key berikutnya

                # Proses Hapus IP Lama
                logger.info("\nWebshare IP Sync: 4. Removing old authorized IPs...")
                removed_count = 0
                failed_remove_count = 0
                if not authorized_ips_map:
                    logger.info("   -> No old IPs to remove.")
                else:
                    for ip_to_delete, auth_id_to_delete in authorized_ips_map.items():
                        if ip_to_delete != new_ip: # Pastikan tidak hapus IP baru jika somehow ada
                            if remove_ip(session, ip_to_delete, auth_id_to_delete, plan_id):
                                removed_count += 1
                            else:
                                failed_remove_count += 1
                    logger.info(f"   -> Removal Summary: {removed_count} removed, {failed_remove_count} failed.")
                    if failed_remove_count > 0:
                        overall_success = False # Gagal jika ada yg gagal dihapus

                # Proses Tambah IP Baru
                logger.info("\nWebshare IP Sync: 5. Adding new IP...")
                if add_ip(session, new_ip, plan_id):
                    account_success = (failed_remove_count == 0) # Sukses jika tambah OK DAN hapus OK
                else:
                    account_success = False # Gagal jika add gagal
                    overall_success = False

            except Exception as e:
                logger.error(f"   -> !!! UNEXPECTED ERROR processing this account: {e}", exc_info=True)
                overall_success = False # Gagal jika ada exception

        if account_success:
             logger.info(f"--- Account [...{api_key[-6:]}] finished successfully. ---")
        else:
             logger.error(f"--- Account [...{api_key[-6:]}] finished with errors. ---")


    logger.info(f"===== Webshare IP Authorization Sync Finished (Overall Success: {overall_success}) =====")
    return overall_success

def get_webshare_download_url(session: requests.Session, plan_id: str):
    """Mengambil URL download proxy dari /config/."""
    logger.info("Webshare Download:    -> Getting download URL via /config/ ...")
    params = {"plan_id": plan_id}
    try:
        response = session.get(WEBSHARE_CONFIG_URL, params=params, timeout=WEBSHARE_API_TIMEOUT)
        response.raise_for_status()
        data = response.json()
        username = data.get("username") # Perlu username
        token = data.get("proxy_list_download_token") # Perlu token

        if not username or not token:
            logger.error("   -> ERROR: 'username' or 'proxy_list_download_token' missing in /config/ response.")
            return None

        # Bangun URL download pakai format
        download_url = WEBSHARE_DOWNLOAD_URL_FORMAT.format(
            token=token,
            username=username, # Masukkan username ke format
            plan_id=plan_id
        )
        logger.info(f"       -> Successfully generated download URL.")
        return download_url

    except requests.exceptions.HTTPError as e:
        logger.error(f"   -> ERROR: HTTP Error getting download config: {e.response.status_code} - {e.response.text[:100]}")
        return None
    except requests.RequestException as e:
        logger.error(f"   -> ERROR: Connection error getting download config: {e}")
        return None

# --- FUNGSI LOGIKA PROXY SYNC LAINNYA (Adaptasi dari ProxySync) ---

def load_apis(file_path):
    # ... (Sama seperti versi sebelumnya) ...
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


# === PERUBAHAN DI SINI: Tambah parameter api_key ===
def fetch_from_api(url, api_key: str = None):
    """Mengunduh dari satu URL API dengan retry + optional auth."""
    max_retries = 2
    headers = {'User-Agent': 'Mozilla/5.0'}
    if api_key: # <= Tambahkan header jika API key ada
        headers['Authorization'] = f"Token {api_key}"

    for attempt in range(max_retries):
        try:
            # Gunakan headers yang sudah disiapkan
            response = requests.get(url, timeout=45, headers=headers)
            response.raise_for_status()
            content = response.text.strip()
            if content:
                if content.lower().startswith("<!doctype html") or "<html" in content.lower():
                     error_message = f"API returned HTML page."
                     logger.warning(f"Warning for {url}: {error_message}")
                     return url, [], error_message
                # Periksa apakah ada baris baru ATAU baris pertama mirip format proxy
                # Ini untuk handle API yg return 1 proxy saja
                first_line = content.splitlines()[0] if '\n' in content else content
                if '\n' in content or re.match(r"^\d{1,3}(\.\d{1,3}){3}:\d+", first_line) or '@' in first_line:
                     return url, content.splitlines(), None # Sukses
                else:
                     error_message = "API response format looks invalid (not a proxy list)."
                     logger.warning(f"Warning for {url}: {error_message}. Content: {content[:100]}...")
                     return url, [], error_message # Anggap gagal jika format aneh

            error_message = "API returned no content"
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 401 and api_key: # <= Handle 401 jika pakai key
                error_message = "Unauthorized (401) - Invalid API Key?"
                logger.error(f"Failed download {url}: {error_message}")
                break # Gagal permanen jika key salah
            elif e.response.status_code == 429:
                wait_time = 5 * (attempt + 1)
                logger.warning(f"Rate limit hit for {url}. Waiting {wait_time}s...")
                time.sleep(wait_time)
                error_message = str(e)
                continue
            else:
                error_message = f"HTTP Error {e.response.status_code}"
                logger.error(f"Failed download {url}: {error_message}")
                break
        except requests.exceptions.RequestException as e:
            error_message = f"Connection Error: {e}"
            logger.warning(f"Failed download attempt {attempt+1}/{max_retries} for {url}: {error_message}")
            time.sleep(2 * (attempt + 1))
    logger.error(f"Final failure downloading from {url} after {max_retries} attempts: {error_message}")
    return url, [], error_message


def download_proxies_from_apis():
    """
    Mengunduh proksi dari Webshare (otomatis via apikeys.txt) DAN
    dari URL manual di apilist.txt ke PROXYLIST_SOURCE_FILE.
    """
    all_download_targets = [] # List of tuples: (url, api_key_or_None)

    # 1. Proses Auto-discover dari apikeys.txt (Webshare)
    logger.info("--- Starting Auto-Discovery from Webshare API Keys ---")
    webshare_api_keys = load_webshare_apikeys(WEBSHARE_APIKEYS_FILE)
    if not webshare_api_keys:
        logger.info(f"'{os.path.basename(WEBSHARE_APIKEYS_FILE)}' empty. Skipping Webshare auto-download.")
    else:
        for api_key in webshare_api_keys:
            email_info = "[Fetching Email...]"
            try:
                 with requests.Session() as email_session:
                     email_session.headers.update({"Authorization": f"Token {api_key}", "Accept": "application/json"})
                     email_info = get_account_email(email_session)
            except Exception: email_info = "[Error Fetching Email]"

            logger.info(f"\n--- Processing Webshare Key: [...{api_key[-6:]}] (Account: {email_info}) ---")
            with requests.Session() as session:
                session.headers.update({"Authorization": f"Token {api_key}", "Accept": "application/json"})
                try:
                    # Dapatkan plan ID (masih pakai /config/ karena lebih simpel)
                    plan_id = get_target_plan_id(session)
                    if not plan_id:
                        logger.error("   -> Skipping account: Could not determine Plan ID.")
                        continue

                    # Dapatkan URL download
                    download_url = get_webshare_download_url(session, plan_id)
                    if download_url:
                        # Tambahkan ke target: URL dan API Key-nya
                        all_download_targets.append((download_url, api_key))
                        logger.info("   -> Added Webshare download URL to the list.")
                    else:
                         logger.error("   -> Failed to get download URL for this account.")

                except Exception as e:
                    logger.error(f"   -> !!! UNEXPECTED ERROR processing this Webshare key: {e}", exc_info=False)

    # 2. Proses URL manual dari apilist.txt
    logger.info(f"\n--- Loading Manual URLs from '{os.path.basename(APILIST_SOURCE_FILE)}' ---")
    manual_urls = load_apis(APILIST_SOURCE_FILE)
    if not manual_urls:
        logger.info("No manual API URLs found.")
    else:
        logger.info(f"Found {len(manual_urls)} manual URL(s).")
        # Tambahkan ke target: URL, tapi API Key = None
        all_download_targets.extend([(url, None) for url in manual_urls])

    # 3. Jalankan Proses Download Gabungan
    if not all_download_targets:
        logger.error("No API URLs (neither Webshare nor manual) found to download from.")
        return [] # Kembalikan list kosong jika tidak ada target

    logger.info(f"\n--- Starting Download from {len(all_download_targets)} Total Sources ---")
    all_downloaded_proxies = []
    processed_count = 0
    total_targets_count = len(all_download_targets)

    # Download satu per satu
    for url, key in all_download_targets:
        processed_count += 1
        source_type = "Webshare" if key else "Manual"
        logger.info(f"[{processed_count}/{total_targets_count}] Downloading ({source_type}) from {url[:70]}...")
        # === Panggil fetch_from_api DENGAN key ===
        _, proxies, error = fetch_from_api(url, key)
        # =========================================
        if error:
            pass # Error sudah di-log di fetch_from_api
        else:
            logger.info(f"   -> Downloaded {len(proxies)} lines from {url[:70]}.")
            all_downloaded_proxies.extend(proxies)
        # Jeda antar download (penting untuk rate limit)
        time.sleep(1) # Jeda 1 detik

    if not all_downloaded_proxies:
        logger.warning("No proxies were successfully downloaded from any source.")
        return []

    # 4. Simpan ke file sementara (proxylist_downloaded.txt)
    try:
        os.makedirs(os.path.dirname(PROXYLIST_SOURCE_FILE), exist_ok=True)
        with open(PROXYLIST_SOURCE_FILE, "w", encoding='utf-8') as f:
            for proxy in all_downloaded_proxies:
                f.write(proxy + "\n")
        logger.info(f"Saved {len(all_downloaded_proxies)} downloaded lines to temporary file '{os.path.basename(PROXYLIST_SOURCE_FILE)}'.")
        return all_downloaded_proxies # Kembalikan list hasil download
    except IOError as e:
        logger.error(f"Failed to write downloaded proxies to '{PROXYLIST_SOURCE_FILE}': {e}")
        return [] # Gagal

def convert_proxylist_to_http(input_file, output_file):
    # ... (Sama seperti versi sebelumnya, tapi logging lebih detail) ...
    if not os.path.exists(input_file):
        logger.error(f"Cannot convert: Input file '{input_file}' not found.")
        return False
    try:
        with open(input_file, "r", encoding='utf-8', errors='ignore') as f: lines = f.readlines()
    except IOError as e:
        logger.error(f"Failed to read '{input_file}': {e}"); return False

    if not lines:
        logger.info(f"'{input_file}' is empty. Nothing to convert.")
        # Hapus output file jika input kosong
        if os.path.exists(output_file):
            try: os.remove(output_file); logger.info(f"Removed empty output file '{output_file}'.")
            except OSError as e: logger.warning(f"Could not remove existing empty output file '{output_file}': {e}")
        # Hapus input file juga
        try: os.remove(input_file); logger.info(f"Removed empty input file '{input_file}'.")
        except OSError as e: logger.warning(f"Could not remove empty input file '{input_file}': {e}")
        return True # Anggap sukses

    cleaned_proxies_raw = []
    for line in lines:
        line = line.strip()
        if not line or line.startswith("#"): continue
        if line.startswith("http://"): line = line[7:]
        elif line.startswith("https://"): line = line[8:]
        cleaned_proxies_raw.append(line)

    if not cleaned_proxies_raw:
        logger.info(f"'{input_file}' contains only comments or empty lines. Nothing to convert.")
        try: os.remove(input_file); logger.info(f"Removed empty/commented input file '{input_file}'.")
        except OSError as e: logger.warning(f"Could not remove temporary file '{input_file}': {e}")
        return True

    converted_proxies = []
    malformed_count = 0
    processed_count = 0
    total_raw = len(cleaned_proxies_raw)
    logger.info(f"Starting conversion for {total_raw} raw proxy lines...")
    host_pattern = r"((?:[0-9]{1,3}\.){3}[0-9]{1,3}|(?:[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?\.)+[a-zA-Z]{2,})"
    port_pattern = r"[0-9]{1,5}"

    for p in cleaned_proxies_raw:
        processed_count += 1; converted = None
        match_user_pass_host_port = re.match(rf"^(?P<user_pass>.+)@(?P<host>{host_pattern}):(?P<port>{port_pattern})$", p)
        if match_user_pass_host_port:
            port_str = match_user_pass_host_port.group("port")
            if port_str.isdigit() and 1 <= int(port_str) <= 65535: converted = f"http://{p}" # Sudah format http
            else: malformed_count += 1; logger.debug(f"Skipping invalid port(A): {p}")
        elif not converted and p.count(':') == 3 and '@' not in p:
            parts = p.split(':'); host, port_str, user, password = parts
            if re.match(rf"^{host_pattern}$", host) and port_str.isdigit() and 1 <= int(port_str) <= 65535: converted = f"http://{user}:{password}@{host}:{port_str}"
            else: malformed_count += 1; logger.debug(f"Skipping invalid host/port(B): {p}")
        elif not converted and p.count(':') == 1 and '@' not in p:
            parts = p.split(':'); host, port_str = parts
            if re.match(rf"^{host_pattern}$", host) and port_str.isdigit() and 1 <= int(port_str) <= 65535: converted = f"http://{host}:{port_str}"
            else: malformed_count += 1; logger.debug(f"Skipping invalid host/port(C): {p}")
        elif not converted and '@' in p and p.count(':') == 2:
             try: host_part, user_part = p.split('@', 1); host, port_str = host_part.split(':', 1); user, password = user_part.split(':', 1)
             except ValueError: malformed_count += 1; logger.debug(f"Skipping malformed(D): {p}"); continue
             if re.match(rf"^{host_pattern}$", host) and port_str.isdigit() and 1 <= int(port_str) <= 65535: converted = f"http://{user}:{password}@{host}:{port_str}"
             else: malformed_count += 1; logger.debug(f"Skipping invalid host/port(D): {p}")

        if converted: converted_proxies.append(converted)
        elif converted is None:
             malformed_count += 1
             # logger.debug(f"Unrecognized format skipped: {p}") # Kurangi noise

        if processed_count % 1000 == 0: logger.info(f"Conversion progress: {processed_count}/{total_raw} lines...")

    if malformed_count > 0: logger.warning(f"Skipped {malformed_count} lines due to unrecognized/invalid format during conversion.")
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
    # ... (Sama seperti versi sebelumnya) ...
    if not os.path.exists(file_path):
        logger.warning(f"File not found for deduplication: {file_path}")
        return []
    try:
        with open(file_path, "r", encoding='utf-8', errors='ignore') as f: # Tambah encoding
            proxies = [line.strip() for line in f if line.strip() and not line.startswith("#")]
    except IOError as e:
        logger.error(f"Failed to read {file_path} for deduplication: {e}")
        return []

    unique_proxies = sorted(list(set(proxies)))
    removed_count = len(proxies) - len(unique_proxies)
    if removed_count > 0:
        logger.info(f"Removed {removed_count} duplicate proxies from '{os.path.basename(file_path)}'.")
        try:
            with open(file_path, "w", encoding='utf-8') as f: # Tambah encoding
                for proxy in unique_proxies: f.write(proxy + "\n")
            logger.info(f"Overwrote '{os.path.basename(file_path)}' with {len(unique_proxies)} unique proxies.")
        except IOError as e:
            logger.error(f"Failed to overwrite {file_path} after deduplication: {e}")
            return unique_proxies
    elif len(proxies) > 0:
         logger.info(f"No duplicates found in '{os.path.basename(file_path)}' ({len(proxies)} unique).")

    return unique_proxies

def check_proxy_final(proxy):
    # ... (Sama seperti versi sebelumnya) ...
    proxies_dict = {"http": proxy, "https": proxy}
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
    for url in CHECK_URLS:
        try:
            with requests.Session() as session:
                 session.proxies = proxies_dict; session.headers.update(headers)
                 response = session.get(url, timeout=PROXY_TIMEOUT)
            response.raise_for_status()
            content = response.text.strip()
            # Cek jika response adalah JSON dan punya key 'ip' atau 'origin' ATAU response adalah plain IP
            is_json_ip = False
            try:
                json_resp = response.json()
                if isinstance(json_resp, dict) and ('ip' in json_resp or 'origin' in json_resp):
                    is_json_ip = True
            except json.JSONDecodeError:
                pass # Bukan JSON, cek plain text

            if is_json_ip or re.search(r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}', content):
                return proxy, True, f"OK via {url}"
            else:
                logger.debug(f"Proxy {proxy.split('@')[-1]} unexpected content from {url}: {content[:60]}...")
        except requests.exceptions.HTTPError as e:
             if e.response.status_code == 407: return proxy, False, "Authentication Required (407)"
             else: logger.debug(f"HTTP Error {proxy.split('@')[-1]} on {url}: {e.response.status_code}")
        except requests.exceptions.Timeout: logger.debug(f"Timeout {proxy.split('@')[-1]} on {url}")
        except requests.exceptions.ProxyError as e:
             reason = str(e).split(':')[-1].strip(); logger.debug(f"Proxy Error {proxy.split('@')[-1]} on {url}: {reason[:40]}")
             return proxy, False, f"Proxy Error ({reason[:30]})"
        except requests.exceptions.RequestException as e: logger.debug(f"Connection Error {proxy.split('@')[-1]} on {url}: {e.__class__.__name__}")
    logger.debug(f"Proxy {proxy.split('@')[-1]} failed all checks.")
    return proxy, False, "Connection Failed / Bad Response"


def run_proxy_test(proxies_to_test):
    # ... (Sama seperti versi sebelumnya) ...
    if not proxies_to_test: logger.info("No proxies to test."); return []
    logger.info(f"Testing {len(proxies_to_test)} proxies (Max workers: {MAX_WORKERS}, Timeout: {PROXY_TIMEOUT}s)...")
    good_proxies, failed_details = [], []; tested_count = 0; total = len(proxies_to_test)
    executor = ThreadPoolExecutor(max_workers=MAX_WORKERS)
    try:
        future_map = {executor.submit(check_proxy_final, p): p for p in proxies_to_test}
        log_interval = max(1, total // 20)
        for future in as_completed(future_map):
            try:
                proxy, is_good, message = future.result(); tested_count += 1
                if is_good: good_proxies.append(proxy)
                else: failed_details.append((proxy, message))
                if tested_count % log_interval == 0 or tested_count == total:
                     logger.info(f"Test Progress: {tested_count}/{total} ({(tested_count/total)*100:.1f}%) - Good: {len(good_proxies)}")
            except Exception as exc:
                proxy_key = future_map[future]; logger.error(f"Error processing {proxy_key.split('@')[-1]}: {exc}")
                failed_details.append((proxy_key, f"Task Error: {exc}")); tested_count += 1
    finally: executor.shutdown(wait=True)
    if failed_details:
        try:
            os.makedirs(os.path.dirname(FAIL_PROXY_FILE), exist_ok=True)
            with open(FAIL_PROXY_FILE, "w", encoding='utf-8') as f:
                for p, reason in failed_details: f.write(f"{p} # {reason}\n")
            logger.info(f"Saved {len(failed_details)} failed to '{FAIL_PROXY_FILE}'.")
        except IOError as e: logger.error(f"Failed save failed proxies: {e}")
    logger.info(f"Test complete. Good: {len(good_proxies)}/{total}.")
    return good_proxies

def sync_proxies() -> bool:
    """Fungsi utama: Sync IP (jika aktif) -> Download -> Convert -> Backup -> Test -> Update."""
    start_time = time.time()
    logger.info("===== Starting Proxy Sync Process =====")
    overall_status = True # Track status keseluruhan

    # 0. Jalankan IP Sync Webshare jika diaktifkan di config
    if ENABLE_WEBSHARE_IP_SYNC:
        logger.info("--- Step 0: Webshare IP Authorization Sync ---")
        ip_sync_success = run_webshare_ip_sync()
        if not ip_sync_success:
            logger.warning("Webshare IP Sync finished with errors. Continuing proxy download/test, but Webshare proxies might not work.")
            # Jangan set overall_status = False, karena proxy lain mungkin masih bisa didownload/bekerja
    else:
        logger.info("--- Step 0: Webshare IP Authorization Sync (Skipped by config) ---")

    # 1. Download dari API (Webshare + Manual) -> data/proxylist_downloaded.txt
    logger.info("--- Step 1: Downloading Proxies ---")
    downloaded = download_proxies_from_apis()

    # 2. Konversi hasil download (jika ada) ke data/proxy.txt
    if downloaded:
        logger.info("--- Step 2: Converting Downloaded Proxies ---")
        if not convert_proxylist_to_http(PROXYLIST_SOURCE_FILE, PROXY_SOURCE_FILE):
             logger.error("Failed during proxy format conversion. Aborting sync.")
             return False # Gagal jika konversi error
    else:
        logger.warning("No proxies downloaded. Proceeding with existing 'proxy.txt' (if available).")

    # 3. Backup data/proxy.txt -> history/proxy_backup.txt
    logger.info("--- Step 3: Backing Up Current Proxy List ---")
    try:
        if os.path.exists(PROXY_SOURCE_FILE):
            os.makedirs(os.path.dirname(PROXY_BACKUP_FILE), exist_ok=True)
            shutil.copy(PROXY_SOURCE_FILE, PROXY_BACKUP_FILE)
            logger.info(f"Created backup: '{os.path.basename(PROXY_BACKUP_FILE)}'")
        else:
            logger.info("No 'proxy.txt' found to back up.")
    except Exception as e:
        logger.warning(f"Failed to create proxy backup: {e}")

    # 4. Load data/proxy.txt, Deduplikasi, dan Overwrite
    logger.info("--- Step 4: Loading and Deduplicating Proxies ---")
    proxies_to_test = load_and_deduplicate_proxies(PROXY_SOURCE_FILE)
    if not proxies_to_test:
        logger.error("No unique proxies found in 'proxy.txt' to test. Aborting sync.")
        return False # Gagal jika tidak ada proxy untuk dites

    # 5. Tes proxy
    logger.info("--- Step 5: Testing Proxies ---")
    good_proxies = run_proxy_test(proxies_to_test)

    # 6. Overwrite data/proxy.txt dengan proxy bagus
    logger.info("--- Step 6: Updating Final Proxy List ---")
    if not good_proxies:
        logger.error("No working proxies found after testing. 'proxy.txt' will NOT be updated.")
        logger.error("Check 'history/fail_proxy.txt' for details.")
        overall_status = False # Gagal jika tidak ada proxy bagus
    else:
        try:
            random.shuffle(good_proxies)
            with open(PROXY_SOURCE_FILE, "w", encoding='utf-8') as f:
                for proxy in good_proxies: f.write(proxy + "\n")
            logger.info(f"Successfully overwrote '{os.path.basename(PROXY_SOURCE_FILE)}' with {len(good_proxies)} working proxies.")
            # Status tetap True jika update berhasil
        except IOError as e:
            logger.error(f"Failed to overwrite '{os.path.basename(PROXY_SOURCE_FILE)}' with good proxies: {e}")
            overall_status = False # Gagal jika tidak bisa nulis hasil

    end_time = time.time(); duration = end_time - start_time
    logger.info(f"===== Proxy Sync Finished in {duration:.2f}s (Overall Success: {overall_status}) =====")
    return overall_status

# Testing entry point
if __name__ == "__main__":
    print("Running proxy module directly for testing (incl. Webshare IP Sync)...")
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

    # Dummy files for testing
    if not os.path.exists(APILIST_SOURCE_FILE):
        print(f"Creating dummy {os.path.basename(APILIST_SOURCE_FILE)}...")
        os.makedirs(os.path.dirname(APILIST_SOURCE_FILE), exist_ok=True)
        with open(APILIST_SOURCE_FILE, "w") as f: f.write("# Dummy API List\n") # Buat kosong aja
    if not os.path.exists(WEBSHARE_APIKEYS_FILE):
         print(f"Creating dummy {os.path.basename(WEBSHARE_APIKEYS_FILE)}...")
         os.makedirs(os.path.dirname(WEBSHARE_APIKEYS_FILE), exist_ok=True)
         with open(WEBSHARE_APIKEYS_FILE, "w") as f: f.write("# Add Webshare keys here for testing\n")

    # Jalankan sync_proxies (asumsi ENABLE_WEBSHARE_IP_SYNC = True by default for test)
    # Anda mungkin perlu set env var ENABLE_WEBSHARE_IP_SYNC=true jika tidak
    os.environ['ENABLE_WEBSHARE_IP_SYNC'] = 'true' # Force enable for testing
    from ..config import ENABLE_WEBSHARE_IP_SYNC # Re-import after setting env
    print(f"Webshare IP Sync Enabled for test: {ENABLE_WEBSHARE_IP_SYNC}")

    success = sync_proxies()
    print(f"\nSync process completed. Success: {success}")
    if success: print(f"Check '{PROXY_SOURCE_FILE}'")
    print(f"Check '{FAIL_PROXY_FILE}' for failures.")
