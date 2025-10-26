# src/modules/proxy.py

import os
import random
import shutil
import time
import re
import logging
import requests
import sys
import json
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
WEBSHARE_APIKEYS_FILE = os.path.join(ROOT_DIR, "data", "apikeys.txt") # File API key Webshare

# --- Konfigurasi Testing ---
PROXY_TIMEOUT = 15
MAX_WORKERS = 10
CHECK_URLS = ["https://api.ipify.org?format=json", "http://httpbin.org/ip"]

# --- Konfigurasi Webshare ---
WEBSHARE_AUTH_URL = "https://proxy.webshare.io/api/v2/proxy/ipauthorization/"
WEBSHARE_SUB_URL = "https://proxy.webshare.io/api/v2/subscription/"
WEBSHARE_CONFIG_URL = "https://proxy.webshare.io/api/v2/proxy/config/"
WEBSHARE_PROFILE_URL = "https://proxy.webshare.io/api/v2/profile/"
WEBSHARE_DOWNLOAD_URL_FORMAT = "https://proxy.webshare.io/api/v2/proxy/list/download/{token}/-/any/{username}/direct/-/?plan_id={plan_id}"
IP_CHECK_SERVICE_URL = "https://api.ipify.org?format=json"
WEBSHARE_API_TIMEOUT = 60

# --- FUNGSI LOGIKA WEBSHARE ---

def load_webshare_apikeys(file_path):
    """Memuat daftar API key Webshare dari file."""
    if not os.path.exists(file_path):
        logger.warning(f"Webshare API key file not found: {file_path}. Creating empty file.")
        try:
            os.makedirs(os.path.dirname(file_path), exist_ok=True)
            with open(file_path, "w", encoding='utf-8') as f: f.write("# Masukkan API key Webshare Anda di sini, SATU per baris\n")
        except IOError as e: logger.error(f"Failed create Webshare API key file: {e}")
        return []
    try:
        with open(file_path, "r", encoding='utf-8') as f:
            keys = [line.strip() for line in f if line.strip() and not line.strip().startswith("#")]
            logger.info(f"Loaded {len(keys)} Webshare API key(s) from {os.path.basename(file_path)}.")
            return keys
    except IOError as e: logger.error(f"Failed read Webshare API key file {file_path}: {e}"); return []

def get_current_public_ip():
    """Mengambil IP publik saat ini."""
    logger.info("Webshare IP Sync: 1. Fetching current public IP...")
    try:
        response = requests.get(IP_CHECK_SERVICE_URL, timeout=15); response.raise_for_status()
        new_ip = response.json().get("ip")
        if new_ip: logger.info(f"   -> Public IP found: {new_ip}"); return new_ip
        else: logger.error("   -> ERROR: IP address not found in ipify response."); return None
    except requests.RequestException as e: logger.error(f"   -> ERROR: Failed get public IP: {e}"); return None
    except json.JSONDecodeError as e: logger.error(f"   -> ERROR: Failed parse ipify response: {e}"); return None

def get_account_email(session: requests.Session) -> str:
    """Helper mendapatkan email akun."""
    try:
        response = session.get(WEBSHARE_PROFILE_URL, timeout=WEBSHARE_API_TIMEOUT); response.raise_for_status()
        email = response.json().get("email"); return email if email else "[Email N/A]"
    except requests.exceptions.HTTPError as e: return "[Invalid API Key]" if e.response.status_code == 401 else f"[HTTP Error {e.response.status_code}]"
    except requests.RequestException: return "[Connection Error]"
    except Exception: return "[Parsing Error]"

def get_target_plan_id(session: requests.Session):
    """Mencari plan ID dari /config/ endpoint."""
    logger.info("Webshare IP Sync: 2. Getting target Plan ID via /config/ ...")
    try:
        response = session.get(WEBSHARE_CONFIG_URL, timeout=WEBSHARE_API_TIMEOUT); response.raise_for_status()
        plan_id = response.json().get("id")
        if plan_id: plan_id_str = str(plan_id); logger.info(f"   -> Found Plan ID: {plan_id_str}"); return plan_id_str
        else: logger.error("   -> ERROR: '/proxy/config/' no 'id'."); return None
    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 401: logger.error("   -> ERROR: Invalid Webshare API Key (401).")
        else: logger.error(f"   -> ERROR: HTTP Error getting config: {e.response.status_code} - {e.response.text[:100]}")
        return None
    except requests.RequestException as e: logger.error(f"   -> ERROR: Connection error getting config: {e}"); return None

def get_authorized_ips(session: requests.Session, plan_id: str):
    """Mengambil daftar IP yang sudah diotorisasi."""
    logger.info("Webshare IP Sync: 3. Getting currently authorized IPs...")
    params = {"plan_id": plan_id}; ip_to_id_map = {}
    try:
        response = session.get(WEBSHARE_AUTH_URL, params=params, timeout=WEBSHARE_API_TIMEOUT); response.raise_for_status()
        results = response.json().get("results", [])
        for item in results:
            ip = item.get("ip_address"); auth_id = item.get("id")
            if ip and auth_id: ip_to_id_map[ip] = auth_id
        if not ip_to_id_map: logger.info("   -> No existing authorized IPs found.")
        else: logger.info(f"   -> Found authorized IPs: {', '.join(ip_to_id_map.keys())}")
        return ip_to_id_map
    except requests.RequestException as e: logger.error(f"   -> ERROR: Failed get authorized IPs: {e}"); return {}

def remove_ip(session: requests.Session, ip: str, authorization_id: int, plan_id: str):
    """Menghapus satu IP dari otorisasi."""
    logger.info(f"Webshare IP Sync:    -> Removing old IP: {ip} (ID: {authorization_id})")
    params = {"plan_id": plan_id}; delete_url = f"{WEBSHARE_AUTH_URL}{authorization_id}/"
    try:
        response = session.delete(delete_url, params=params, timeout=WEBSHARE_API_TIMEOUT)
        if response.status_code == 204: logger.info(f"       -> Successfully removed IP: {ip}"); return True
        else:
            try: error_detail = response.json()
            except: error_detail = response.text[:100]
            logger.error(f"       -> ERROR removing {ip}: Status {response.status_code} - {error_detail}"); return False
    except requests.RequestException as e: logger.error(f"       -> ERROR: Connection error removing {ip}: {e}"); return False

def add_ip(session: requests.Session, ip: str, plan_id: str):
    """Menambahkan satu IP ke otorisasi."""
    logger.info(f"Webshare IP Sync:    -> Adding new IP: {ip}")
    params = {"plan_id": plan_id}; payload = {"ip_address": ip}
    try:
        response = session.post(WEBSHARE_AUTH_URL, json=payload, params=params, timeout=WEBSHARE_API_TIMEOUT)
        if response.status_code == 201: logger.info(f"       -> Successfully added IP: {ip}"); return True
        else:
            try: error_detail = response.json()
            except: error_detail = response.text[:100]
            logger.error(f"       -> ERROR adding {ip}: Status {response.status_code} - {error_detail}"); return False
    except requests.RequestException as e: logger.error(f"       -> ERROR: Connection error adding {ip}: {e}"); return False

def run_webshare_ip_sync() -> bool:
    """Fungsi orkestrasi sinkronisasi IP Webshare."""
    logger.info("===== Starting Webshare IP Authorization Sync =====")
    api_keys = load_webshare_apikeys(WEBSHARE_APIKEYS_FILE)
    if not api_keys: logger.error(f"IP Sync Aborted: '{os.path.basename(WEBSHARE_APIKEYS_FILE)}' empty."); return False
    new_ip = get_current_public_ip()
    if not new_ip: logger.error("IP Sync Aborted: Failed get public IP."); return False
    logger.info(f"Syncing IP [{new_ip}] to [{len(api_keys)}] Webshare account(s)...")
    overall_success = True

    for api_key in api_keys:
        email_info = "[Fetching Email...]"
        try:
             with requests.Session() as es: es.headers.update({"Authorization": f"Token {api_key}", "Accept": "application/json"}); email_info = get_account_email(es)
        except Exception: email_info = "[Error Email]"
        logger.info(f"\n--- Processing Key: [...{api_key[-6:]}] ({email_info}) ---")
        account_success = False
        with requests.Session() as s:
            s.headers.update({"Authorization": f"Token {api_key}", "Content-Type": "application/json", "Accept": "application/json"})
            try:
                plan_id = get_target_plan_id(s)
                if not plan_id: logger.error("   -> Skip: No Plan ID."); overall_success = False; continue
                auth_ips_map = get_authorized_ips(s, plan_id)
                if new_ip in auth_ips_map: logger.info(f"   -> IP ({new_ip}) already authorized."); account_success = True; continue

                logger.info("\nWebshare IP Sync: 4. Removing old IPs...")
                removed, failed_remove = 0, 0
                if not auth_ips_map: logger.info("   -> No old IPs.")
                else:
                    for ip_del, id_del in auth_ips_map.items():
                        if ip_del != new_ip:
                            if remove_ip(s, ip_del, id_del, plan_id): removed += 1
                            else: failed_remove += 1
                    logger.info(f"   -> Removal: {removed} removed, {failed_remove} failed.")
                    if failed_remove > 0: overall_success = False

                logger.info("\nWebshare IP Sync: 5. Adding new IP...")
                if add_ip(s, new_ip, plan_id): account_success = (failed_remove == 0)
                else: account_success = False; overall_success = False
            except Exception as e: logger.error(f"   -> !!! UNEXPECTED ERROR: {e}", exc_info=True); overall_success = False
        if account_success: logger.info(f"--- Account [...{api_key[-6:]}] OK. ---")
        else: logger.error(f"--- Account [...{api_key[-6:]}] FAILED. ---")
    logger.info(f"===== Webshare IP Sync Finished (Overall Success: {overall_success}) =====")
    return overall_success

def get_webshare_download_url(session: requests.Session, plan_id: str):
    """Mengambil URL download proxy dari /config/."""
    logger.info("Webshare Download:    -> Getting download URL via /config/ ...")
    params = {"plan_id": plan_id}
    try:
        response = session.get(WEBSHARE_CONFIG_URL, params=params, timeout=WEBSHARE_API_TIMEOUT); response.raise_for_status()
        data = response.json(); username = data.get("username"); token = data.get("proxy_list_download_token")
        if not username or not token: logger.error("   -> ERROR: 'username' or 'token' missing."); return None
        dl_url = WEBSHARE_DOWNLOAD_URL_FORMAT.format(token=token, username=username, plan_id=plan_id)
        logger.info(f"       -> OK URL generated."); return dl_url
    except requests.exceptions.HTTPError as e: logger.error(f"   -> ERROR HTTP getting DL config: {e.response.status_code} - {e.response.text[:100]}"); return None
    except requests.RequestException as e: logger.error(f"   -> ERROR Connection getting DL config: {e}"); return None

# --- FUNGSI LOGIKA PROXY SYNC LAINNYA ---

def load_apis(file_path):
    """Memuat daftar URL API download manual."""
    if not os.path.exists(file_path):
        logger.warning(f"Manual API list not found: {file_path}. Creating empty.");
        try: os.makedirs(os.path.dirname(file_path), exist_ok=True); open(file_path, 'a', encoding='utf-8').close()
        except IOError as e: logger.error(f"Failed create manual API list: {e}")
        return []
    try:
        with open(file_path, "r", encoding='utf-8') as f:
            urls = [line.strip() for line in f if line.strip() and not line.strip().startswith("#")]
            logger.info(f"Loaded {len(urls)} manual API URL(s) from {os.path.basename(file_path)}.")
            return urls
    except IOError as e: logger.error(f"Failed read manual API list {file_path}: {e}"); return []

def fetch_from_api(url, api_key: str = None):
    """Mengunduh dari satu URL API dengan retry + optional auth."""
    max_retries = 2; headers = {'User-Agent': 'Mozilla/5.0'}
    if api_key: headers['Authorization'] = f"Token {api_key}"
    for attempt in range(max_retries):
        try:
            response = requests.get(url, timeout=45, headers=headers); response.raise_for_status()
            content = response.text.strip()
            if content:
                if content.lower().startswith("<!doctype html") or "<html" in content.lower():
                     error_message = f"API returned HTML page."; logger.warning(f"Warn {url}: {error_message}"); return url, [], error_message
                first_line = content.splitlines()[0] if '\n' in content else content
                if '\n' in content or re.match(r"^\d{1,3}(\.\d{1,3}){3}:\d+", first_line) or ('@' in first_line and ':' in first_line): return url, content.splitlines(), None # Sukses
                else: error_message = "API response format invalid."; logger.warning(f"Warn {url}: {error_message}. Content: {content[:100]}..."); return url, [], error_message
            error_message = "API returned no content"
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 401 and api_key: error_message = "Unauthorized (401)"; logger.error(f"Failed {url}: {error_message}"); break
            elif e.response.status_code == 429: wait_time = 5 * (attempt + 1); logger.warning(f"Rate limit {url}. Wait {wait_time}s..."); time.sleep(wait_time); error_message = str(e); continue
            else: error_message = f"HTTP Error {e.response.status_code}"; logger.error(f"Failed {url}: {error_message}"); break
        except requests.exceptions.RequestException as e: error_message = f"Connection Error: {e}"; logger.warning(f"Attempt {attempt+1}/{max_retries} {url}: {error_message}"); time.sleep(2 * (attempt + 1))
    logger.error(f"Final failure {url} after {max_retries} attempts: {error_message}")
    return url, [], error_message

def download_proxies_from_apis():
    """Download dari Webshare (auto) + Manual API ke file sementara."""
    all_targets = []

    # 1. Webshare Auto-discovery
    logger.info("--- Starting Auto-Discovery from Webshare ---")
    ws_keys = load_webshare_apikeys(WEBSHARE_APIKEYS_FILE)
    if not ws_keys: logger.info(f"'{os.path.basename(WEBSHARE_APIKEYS_FILE)}' empty. Skip Webshare.")
    else:
        for key in ws_keys:
            email = "[Fetching Email...]"; logger.info(f"\n--- Processing Webshare Key: [...{key[-6:]}] ---")
            try:
                 with requests.Session() as es: es.headers.update({"Authorization": f"Token {key}", "Accept": "application/json"}); email = get_account_email(es)
                 logger.info(f"   Account Email: {email}")
            except Exception: logger.warning("   Could not fetch account email.")
            with requests.Session() as s:
                s.headers.update({"Authorization": f"Token {key}", "Accept": "application/json"})
                try:
                    plan_id = get_target_plan_id(s)
                    if not plan_id: logger.error("   -> Skip: No Plan ID."); continue
                    dl_url = get_webshare_download_url(s, plan_id)
                    if dl_url: all_targets.append((dl_url, key)); logger.info("   -> Added Webshare URL.")
                    else: logger.error("   -> Failed get download URL.")
                except Exception as e: logger.error(f"   -> !!! ERROR processing key: {e}", exc_info=False)

    # 2. Manual URLs
    logger.info(f"\n--- Loading Manual URLs ---")
    manuals = load_apis(APILIST_SOURCE_FILE)
    if not manuals: logger.info("No manual URLs.")
    else: logger.info(f"Found {len(manuals)} manual URL(s)."); all_targets.extend([(url, None) for url in manuals])

    # 3. Download Gabungan
    if not all_targets: logger.error("No API URLs found."); return []
    logger.info(f"\n--- Starting Download from {len(all_targets)} Sources ---")
    all_proxies = []; count = 0; total = len(all_targets)
    for url, key in all_targets:
        count += 1; src_type = "Webshare" if key else "Manual"
        logger.info(f"[{count}/{total}] Downloading ({src_type}) from {url[:70]}...")
        _, proxies, error = fetch_from_api(url, key)
        if not error: logger.info(f"   -> Downloaded {len(proxies)} lines."); all_proxies.extend(proxies)
        time.sleep(1)

    if not all_proxies: logger.warning("No proxies downloaded."); return []

    # 4. Simpan ke file sementara
    try:
        os.makedirs(os.path.dirname(PROXYLIST_SOURCE_FILE), exist_ok=True)
        with open(PROXYLIST_SOURCE_FILE, "w", encoding='utf-8') as f: f.write('\n'.join(p for p in all_proxies if p) + '\n') # Filter baris kosong juga
        logger.info(f"Saved {len(all_proxies)} lines to temp file '{os.path.basename(PROXYLIST_SOURCE_FILE)}'.")
        return all_proxies
    except IOError as e: logger.error(f"Failed write to '{PROXYLIST_SOURCE_FILE}': {e}"); return []


def convert_proxylist_to_http(input_file, output_file):
    """Konversi format proxy ke format http."""
    if not os.path.exists(input_file): logger.error(f"Convert Error: Input '{input_file}' not found."); return False
    try:
        with open(input_file, "r", encoding='utf-8', errors='ignore') as f: lines = f.readlines()
    except IOError as e: logger.error(f"Failed read '{input_file}': {e}"); return False

    if not lines:
        logger.info(f"'{os.path.basename(input_file)}' is empty. Convert skipped.")
        
        # --- FIX 1 (Area ~Baris 293) ---
        if os.path.exists(output_file):
            try:
                os.remove(output_file)
                logger.info(f"Removed empty output '{os.path.basename(output_file)}'.")
            except OSError as e:
                logger.warning(f"Could not remove '{output_file}': {e}")
        
        try:
            os.remove(input_file)
            logger.info(f"Removed empty input '{os.path.basename(input_file)}'.")
        except OSError as e:
            logger.warning(f"Could not remove '{input_file}': {e}")
        # --- AKHIR FIX 1 ---
            
        return True

    cleaned_raw = []
    for line in lines:
        line = line.strip()
        if not line or line.startswith("#"): continue
        if line.startswith("http://"): line = line[7:]
        elif line.startswith("https://"): line = line[8:]
        cleaned_raw.append(line)

    if not cleaned_raw:
        logger.info(f"'{os.path.basename(input_file)}' has no valid content. Convert skipped.")
        try:
            os.remove(input_file)
            logger.info(f"Removed empty/commented '{os.path.basename(input_file)}'.")
        except OSError as e:
            logger.warning(f"Could not remove temporary file '{input_file}': {e}")
        return True

    converted = []; malformed = 0; count = 0; total = len(cleaned_raw)
    logger.info(f"Converting {total} raw lines...")
    host_pat = r"((?:[0-9]{1,3}\.){3}[0-9]{1,3}|(?:[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?\.)+[a-zA-Z]{2,})"
    port_pat = r"[0-9]{1,5}"

    for p in cleaned_raw:
        count += 1; result = None
        m_a = re.match(rf"^(?P<up>.+)@(?P<h>{host_pat}):(?P<p>{port_pat})$", p)
        if m_a and m_a.group("p").isdigit() and 1 <= int(m_a.group("p")) <= 65535: result = f"http://{p}"
        elif p.count(':') == 3 and '@' not in p:
            parts = p.split(':'); h, pt, u, pw = parts
            if re.match(rf"^{host_pat}$", h) and pt.isdigit() and 1 <= int(pt) <= 65535: result = f"http://{u}:{pw}@{h}:{pt}"
            else: malformed += 1; logger.debug(f"Skip invalid B: {p}")
        elif p.count(':') == 1 and '@' not in p:
            parts = p.split(':'); h, pt = parts
            if re.match(rf"^{host_pat}$", h) and pt.isdigit() and 1 <= int(pt) <= 65535: result = f"http://{h}:{pt}"
            else: malformed += 1; logger.debug(f"Skip invalid C: {p}")
        elif '@' in p and p.count(':') == 2:
             try: hp, up = p.split('@', 1); h, pt = hp.split(':', 1); u, pw = up.split(':', 1)
             except ValueError: malformed += 1; logger.debug(f"Skip malformed D: {p}"); continue
             if re.match(rf"^{host_pat}$", h) and pt.isdigit() and 1 <= int(pt) <= 65535: result = f"http://{u}:{pw}@{h}:{pt}"
             else: malformed += 1; logger.debug(f"Skip invalid D: {p}")

        if result: converted.append(result)
        elif result is None: malformed += 1

        if count % 1000 == 0: logger.info(f"Convert progress: {count}/{total} lines...")

    if malformed > 0: logger.warning(f"Skipped {malformed} lines (format).")
    
    if not converted:
        logger.error("No valid proxies converted.");
        
        # --- FIX 2 (Area ~Baris 361) ---
        try:
            os.remove(input_file)
            logger.info(f"Removed failed '{os.path.basename(input_file)}'.")
        except OSError as e:
            logger.warning(f"Could not remove '{input_file}': {e}")
        # --- AKHIR FIX 2 ---
            
        return False

    try:
        os.makedirs(os.path.dirname(output_file), exist_ok=True)
        unique = sorted(list(set(converted)))
        dups = len(converted) - len(unique)
        if dups > 0: logger.info(f"Removed {dups} duplicates.")
        with open(output_file, "w", encoding='utf-8') as f: f.write('\n'.join(unique) + '\n')
        logger.info(f"Converted {len(unique)} unique proxies to '{os.path.basename(output_file)}'.")
        try: os.remove(input_file); logger.info(f"Removed temp '{os.path.basename(input_file)}'.") except OSError as e: logger.warning(f"Could not remove '{input_file}': {e}")
        return True
    except IOError as e: logger.error(f"Failed write to '{output_file}': {e}"); return False


def load_and_deduplicate_proxies(file_path):
    """Load, deduplicate, and overwrite file."""
    if not os.path.exists(file_path): logger.warning(f"Dedupe Error: Not found: {file_path}"); return []
    try:
        with open(file_path, "r", encoding='utf-8', errors='ignore') as f: proxies = [l.strip() for l in f if l.strip() and not l.startswith("#")]
    except IOError as e: logger.error(f"Failed read {file_path} for dedupe: {e}"); return []
    if not proxies: logger.info(f"'{os.path.basename(file_path)}' empty for dedupe."); return []

    unique = sorted(list(set(proxies)))
    removed = len(proxies) - len(unique)
    if removed > 0:
        logger.info(f"Removed {removed} duplicates from '{os.path.basename(file_path)}'.")
        try:
            with open(file_path, "w", encoding='utf-8') as f: f.write('\n'.join(unique) + '\n')
            logger.info(f"Overwrote '{os.path.basename(file_path)}' with {len(unique)} unique.")
        except IOError as e: logger.error(f"Failed overwrite {file_path} after dedupe: {e}"); return unique
    else: logger.info(f"No duplicates in '{os.path.basename(file_path)}' ({len(proxies)} unique).")
    return unique


def check_proxy_final(proxy):
    """Tes koneksi proxy ke CHECK_URLS."""
    proxies_dict = {"http": proxy, "https": proxy}
    headers = {'User-Agent': 'Mozilla/5.0'} # User agent simple
    for url in CHECK_URLS:
        try:
            with requests.Session() as s:
                 s.proxies = proxies_dict; s.headers.update(headers)
                 r = s.get(url, timeout=PROXY_TIMEOUT)
            r.raise_for_status()
            content = r.text.strip()
            is_json_ip = False
            try: j = r.json(); is_json_ip = isinstance(j, dict) and ('ip' in j or 'origin' in j)
            except json.JSONDecodeError: pass
            
            # --- FIX 3 (Area ~Baris 417) ---
            # Menutup string literal r'...' dengan benar
            if is_json_ip or re.search(r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}', content): 
                return proxy, True, f"OK via {url}"
            # --- AKHIR FIX 3 ---
            
            else: logger.debug(f"Proxy {proxy.split('@')[-1]} unexpected content {url}: {content[:60]}...")
        except requests.exceptions.HTTPError as e:
             if e.response.status_code == 407: return proxy, False, "Auth Required (407)"
             else: logger.debug(f"HTTP Error {proxy.split('@')[-1]} {url}: {e.response.status_code}")
        except requests.exceptions.Timeout: logger.debug(f"Timeout {proxy.split('@')[-1]} {url}")
        except requests.exceptions.ProxyError as e: r = str(e).split(':')[-1].strip(); logger.debug(f"Proxy Error {proxy.split('@')[-1]} {url}: {r[:40]}"); return proxy, False, f"Proxy Error ({r[:30]})"
        except requests.exceptions.RequestException as e: logger.debug(f"Connection Error {proxy.split('@')[-1]} {url}: {e.__class__.__name__}")
    logger.debug(f"Proxy {proxy.split('@')[-1]} failed checks.")
    return proxy, False, "Connection Failed / Bad Response"


def run_proxy_test(proxies_to_test):
    """Tes proxy secara concurrent."""
    if not proxies_to_test: logger.info("No proxies to test."); return []
    total = len(proxies_to_test)
    logger.info(f"Testing {total} proxies (Workers: {MAX_WORKERS}, Timeout: {PROXY_TIMEOUT}s)...")
    good, failed = [], []; count = 0
    executor = ThreadPoolExecutor(max_workers=MAX_WORKERS)
    try:
        future_map = {executor.submit(check_proxy_final, p): p for p in proxies_to_test}
        log_interval = max(1, total // 20) if total > 0 else 1
        for future in as_completed(future_map):
            try:
                p, ok, msg = future.result(); count += 1
                if ok: good.append(p)
                else: failed.append((p, msg))
                if count % log_interval == 0 or count == total: logger.info(f"Test Progress: {count}/{total} ({(count/total)*100:.1f}%) - Good: {len(good)}")
            except Exception as exc: pk = future_map[future]; logger.error(f"Error testing {pk.split('@')[-1]}: {exc}"); failed.append((pk, f"Task Error: {exc}")); count += 1
    finally: executor.shutdown(wait=True)
    if failed:
        try:
            os.makedirs(os.path.dirname(FAIL_PROXY_FILE), exist_ok=True)
            with open(FAIL_PROXY_FILE, "w", encoding='utf-8') as f: f.write('\n'.join(f"{p} # {r}" for p, r in failed) + '\n')
            logger.info(f"Saved {len(failed)} failed to '{os.path.basename(FAIL_PROXY_FILE)}'.")
        except IOError as e: logger.error(f"Failed save failed proxies: {e}")
    logger.info(f"Test complete. Good: {len(good)}/{total}.")
    return good

def sync_proxies() -> bool:
    """Fungsi utama: Sync IP -> Download -> Convert -> Backup -> Test -> Update."""
    start = time.time(); logger.info("===== Starting Proxy Sync Process ====="); status = True

    if ENABLE_WEBSHARE_IP_SYNC:
        logger.info("--- Step 0: Webshare IP Sync ---")
        if not run_webshare_ip_sync(): logger.warning("Webshare IP Sync errors. Continuing...")
    else: logger.info("--- Step 0: Webshare IP Sync (Skipped) ---")

    logger.info("--- Step 1: Downloading ---"); downloaded = download_proxies_from_apis()
    if downloaded:
        logger.info("--- Step 2: Converting ---")
        if not convert_proxylist_to_http(PROXYLIST_SOURCE_FILE, PROXY_SOURCE_FILE): logger.error("Conversion failed. Aborting."); return False
    else: logger.warning("No proxies downloaded. Using existing 'proxy.txt'.")

    logger.info("--- Step 3: Backup ---")
    try:
        if os.path.exists(PROXY_SOURCE_FILE): os.makedirs(os.path.dirname(PROXY_BACKUP_FILE), exist_ok=True); shutil.copy(PROXY_SOURCE_FILE, PROXY_BACKUP_FILE); logger.info(f"Backup: '{os.path.basename(PROXY_BACKUP_FILE)}'")
        else: logger.info("No 'proxy.txt' to back up.")
    except Exception as e: logger.warning(f"Backup failed: {e}")

    logger.info("--- Step 4: Load & Dedupe ---"); to_test = load_and_deduplicate_proxies(PROXY_SOURCE_FILE)
    if not to_test: logger.error("No unique proxies to test. Aborting."); return False

    logger.info("--- Step 5: Testing ---"); good = run_proxy_test(to_test)

    logger.info("--- Step 6: Updating List ---")
    if not good: logger.error("No working proxies. 'proxy.txt' NOT updated."); status = False
    else:
        try:
            random.shuffle(good)
            with open(PROXY_SOURCE_FILE, "w", encoding='utf-8') as f: f.write('\n'.join(good) + '\n')
            logger.info(f"Updated '{os.path.basename(PROXY_SOURCE_FILE)}' with {len(good)} working proxies.")
        except IOError as e: logger.error(f"Failed update '{os.path.basename(PROXY_SOURCE_FILE)}': {e}"); status = False

    duration = time.time() - start; logger.info(f"===== Proxy Sync Finished in {duration:.2f}s (Success: {status}) =====")
    return status

# Testing entry point
if __name__ == "__main__":
    print("Running proxy module directly for testing...")
    if not logging.getLogger().hasHandlers(): logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - [%(name)s] - %(message)s')
    if not os.path.exists(APILIST_SOURCE_FILE): os.makedirs(os.path.dirname(APILIST_SOURCE_FILE), exist_ok=True); open(APILIST_SOURCE_FILE, 'a').close(); print(f"Created dummy {os.path.basename(APILIST_SOURCE_FILE)}")
    if not os.path.exists(WEBSHARE_APIKEYS_FILE): os.makedirs(os.path.dirname(WEBSHARE_APIKEYS_FILE), exist_ok=True); open(WEBSHARE_APIKEYS_FILE, 'a').close(); print(f"Created dummy {os.path.basename(WEBSHARE_APIKEYS_FILE)}")
    os.environ['ENABLE_WEBSHARE_IP_SYNC'] = 'true'
    from ..config import ENABLE_WEBSHARE_IP_SYNC; print(f"Webshare IP Sync Enabled: {ENABLE_WEBSHARE_IP_SYNC}")
    success = sync_proxies(); print(f"\nSync process completed. Success: {success}")
