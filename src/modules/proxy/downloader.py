"""
Proxy Downloader - Download proxies dari berbagai sumber

Supports:
- Webshare API (dengan auto-discovery via API keys)
- Manual API list dari apilist.txt
- Multiple API formats
"""

import os
import time
import logging
import requests

from .core import PROXYLIST_SOURCE_FILE, APILIST_SOURCE_FILE, WEBSHARE_APIKEYS_FILE
from .webshare import (
    load_webshare_apikeys,
    get_account_email,
    get_target_plan_id,
    get_webshare_download_url
)

logger = logging.getLogger(__name__)

WEBSHARE_API_TIMEOUT = 60


def load_apis(file_path):
    """
    Load manual API URLs dari apilist.txt.
    
    Returns:
        List[str]: List of API URLs
    """
    if not os.path.exists(file_path):
        logger.warning(f"Manual API list not found: {file_path}. Creating empty.")
        try:
            os.makedirs(os.path.dirname(file_path), exist_ok=True)
            open(file_path, 'a', encoding='utf-8').close()
        except IOError as e:
            logger.error(f"Failed create manual API list: {e}")
        return []
    
    try:
        with open(file_path, "r", encoding='utf-8') as f:
            urls = [line.strip() for line in f 
                   if line.strip() and not line.strip().startswith("#")]
            logger.info(f"Loaded {len(urls)} manual API URL(s) from {os.path.basename(file_path)}.")
            return urls
    except IOError as e:
        logger.error(f"Failed read manual API list {file_path}: {e}")
        return []


def fetch_from_api(url, api_key: str = None):
    """
    Fetch proxy list dari satu API URL.
    
    Args:
        url: API URL
        api_key: Optional API key untuk authorization
        
    Returns:
        Tuple[str, List[str], Optional[str]]: (url, proxy_lines, error_message)
    """
    max_retries = 2
    headers = {'User-Agent': 'Mozilla/5.0'}
    
    if api_key:
        headers['Authorization'] = f"Token {api_key}"
    
    for attempt in range(max_retries):
        try:
            response = requests.get(url, timeout=45, headers=headers)
            response.raise_for_status()
            content = response.text.strip()
            
            if content:
                # Check if HTML page (error)
                if content.lower().startswith("<!doctype html") or "<html" in content.lower():
                    error_message = f"API returned HTML page."
                    logger.warning(f"Warn {url}: {error_message}")
                    return url, [], error_message
                
                # Validate format
                first_line = content.splitlines()[0] if '\n' in content else content
                
                # Check if valid proxy format
                import re
                is_valid = (
                    '\n' in content or 
                    re.match(r"^\d{1,3}(\.\d{1,3}){3}:\d+", first_line) or 
                    ('@' in first_line and ':' in first_line)
                )
                
                if is_valid:
                    return url, content.splitlines(), None
                else:
                    error_message = "API response format invalid."
                    logger.warning(f"Warn {url}: {error_message}. Content: {content[:100]}...")
                    return url, [], error_message
            
            error_message = "API returned no content"
            
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 401 and api_key:
                error_message = "Unauthorized (401)"
                logger.error(f"Failed {url}: {error_message}")
                break
            elif e.response.status_code == 429:
                wait_time = 5 * (attempt + 1)
                logger.warning(f"Rate limit {url}. Wait {wait_time}s...")
                time.sleep(wait_time)
                error_message = str(e)
                continue
            else:
                error_message = f"HTTP Error {e.response.status_code}"
                logger.error(f"Failed {url}: {error_message}")
                break
                
        except requests.exceptions.RequestException as e:
            error_message = f"Connection Error: {e}"
            logger.warning(f"Attempt {attempt+1}/{max_retries} {url}: {error_message}")
            time.sleep(2 * (attempt + 1))
    
    logger.error(f"Final failure {url} after {max_retries} attempts: {error_message}")
    return url, [], error_message


def download_proxies_from_apis():
    """
    Download proxies dari semua sumber (Webshare + Manual APIs).
    
    Process:
    1. Auto-discovery Webshare accounts dari apikeys.txt
    2. Generate download URLs untuk setiap account
    3. Load manual API URLs dari apilist.txt
    4. Download dari semua sumber
    5. Save ke temporary file
    
    Returns:
        List[str]: List of proxy lines (raw format)
    """
    all_targets = []  # List of (url, api_key) tuples

    # --- Step 1: Webshare Auto-Discovery ---
    logger.info("--- Starting Auto-Discovery from Webshare ---")
    ws_keys = load_webshare_apikeys(WEBSHARE_APIKEYS_FILE)
    
    if not ws_keys:
        logger.info(f"'{os.path.basename(WEBSHARE_APIKEYS_FILE)}' empty. Skip Webshare.")
    else:
        for key in ws_keys:
            email = "[Fetching Email...]"
            logger.info(f"\n--- Processing Webshare Key: [...{key[-6:]}] ---")
            
            try:
                with requests.Session() as es:
                    es.headers.update({
                        "Authorization": f"Token {key}",
                        "Accept": "application/json"
                    })
                    email = get_account_email(es)
                    logger.info(f"   Account Email: {email}")
            except Exception:
                logger.warning("   Could not fetch account email.")
            
            with requests.Session() as s:
                s.headers.update({
                    "Authorization": f"Token {key}",
                    "Accept": "application/json"
                })
                
                try:
                    plan_id = get_target_plan_id(s)
                    if not plan_id:
                        logger.error("   -> Skip: No Plan ID.")
                        continue
                    
                    dl_url = get_webshare_download_url(s, plan_id)
                    if dl_url:
                        all_targets.append((dl_url, key))
                        logger.info("   -> Added Webshare URL.")
                    else:
                        logger.error("   -> Failed get download URL.")
                        
                except Exception as e:
                    logger.error(f"   -> !!! ERROR processing key: {e}", exc_info=False)

    # --- Step 2: Load Manual URLs ---
    logger.info(f"\n--- Loading Manual URLs ---")
    manuals = load_apis(APILIST_SOURCE_FILE)
    
    if not manuals:
        logger.info("No manual URLs.")
    else:
        logger.info(f"Found {len(manuals)} manual URL(s).")
        all_targets.extend([(url, None) for url in manuals])

    # --- Step 3: Download dari Semua Sumber ---
    if not all_targets:
        logger.error("No API URLs found.")
        return []
    
    logger.info(f"\n--- Starting Download from {len(all_targets)} Sources ---")
    all_proxies = []
    count = 0
    total = len(all_targets)
    
    for url, key in all_targets:
        count += 1
        src_type = "Webshare" if key else "Manual"
        logger.info(f"[{count}/{total}] Downloading ({src_type}) from {url[:70]}...")
        
        _, proxies, error = fetch_from_api(url, key)
        
        if not error:
            logger.info(f"   -> Downloaded {len(proxies)} lines.")
            all_proxies.extend(proxies)
        
        # Wait before next download (be nice to APIs)
        if count < total:
            logger.info(f"   -> Waiting 5s before next download...")
            time.sleep(5)

    # --- Step 4: Save to Temporary File ---
    if not all_proxies:
        logger.warning("No proxies downloaded.")
        return []

    try:
        os.makedirs(os.path.dirname(PROXYLIST_SOURCE_FILE), exist_ok=True)
        with open(PROXYLIST_SOURCE_FILE, "w", encoding='utf-8') as f:
            f.write('\n'.join(p for p in all_proxies if p) + '\n')
        logger.info(f"Saved {len(all_proxies)} lines to temp file '{os.path.basename(PROXYLIST_SOURCE_FILE)}'.")
        return all_proxies
    except IOError as e:
        logger.error(f"Failed write to '{PROXYLIST_SOURCE_FILE}': {e}")
        return []
