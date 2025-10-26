"""
Proxy Core - Main Orchestration

Main function: sync_proxies()
Orchestrates full proxy sync pipeline:
1. Webshare IP sync (optional)
2. Download from APIs
3. Convert format
4. Backup old proxies
5. Deduplicate
6. Test proxies
7. Save working proxies
"""

import os
import time
import shutil
import logging

from ...config import ROOT_DIR, ENABLE_WEBSHARE_IP_SYNC

logger = logging.getLogger(__name__)

# File paths
PROXYLIST_SOURCE_FILE = os.path.join(ROOT_DIR, "data", "proxylist_downloaded.txt")
PROXY_SOURCE_FILE = os.path.join(ROOT_DIR, "data", "proxy.txt")
APILIST_SOURCE_FILE = os.path.join(ROOT_DIR, "data", "apilist.txt")
FAIL_PROXY_FILE = os.path.join(ROOT_DIR, "history", "fail_proxy.txt")
PROXY_BACKUP_FILE = os.path.join(ROOT_DIR, "history", "proxy_backup.txt")
WEBSHARE_APIKEYS_FILE = os.path.join(ROOT_DIR, "data", "apikeys.txt")


def sync_proxies() -> bool:
    """
    Main proxy sync orchestration function.
    
    Pipeline:
    0. Webshare IP sync (if enabled)
    1. Download proxies from APIs
    2. Convert to HTTP format
    3. Backup existing proxies
    4. Load & deduplicate
    5. Test proxies
    6. Save working proxies
    
    Returns:
        bool: True if successful, False otherwise
    """
    start = time.time()
    logger.info("===== Starting Proxy Sync Process =====")
    status = True

    # Import functions dari submodules
    from .webshare import run_webshare_ip_sync
    from .downloader import download_proxies_from_apis
    from .converter import convert_proxylist_to_http, load_and_deduplicate_proxies
    from .tester import run_proxy_test

    # --- Step 0: Webshare IP Sync (Optional) ---
    if ENABLE_WEBSHARE_IP_SYNC:
        logger.info("--- Step 0: Webshare IP Sync ---")
        if not run_webshare_ip_sync():
            logger.warning("Webshare IP Sync errors. Continuing...")
    else:
        logger.info("--- Step 0: Webshare IP Sync (Skipped) ---")

    # --- Step 1: Download Proxies ---
    logger.info("--- Step 1: Downloading ---")
    downloaded = download_proxies_from_apis()
    
    if downloaded:
        # --- Step 2: Convert Format ---
        logger.info("--- Step 2: Converting ---")
        if not convert_proxylist_to_http(PROXYLIST_SOURCE_FILE, PROXY_SOURCE_FILE):
            logger.error("Conversion failed. Aborting.")
            return False
    else:
        logger.warning("No proxies downloaded. Using existing 'proxy.txt'.")

    # --- Step 3: Backup ---
    logger.info("--- Step 3: Backup ---")
    try:
        if os.path.exists(PROXY_SOURCE_FILE):
            os.makedirs(os.path.dirname(PROXY_BACKUP_FILE), exist_ok=True)
            shutil.copy(PROXY_SOURCE_FILE, PROXY_BACKUP_FILE)
            logger.info(f"Backup: '{os.path.basename(PROXY_BACKUP_FILE)}'")
        else:
            logger.info("No 'proxy.txt' to back up.")
    except Exception as e:
        logger.warning(f"Backup failed: {e}")

    # --- Step 4: Load & Deduplicate ---
    logger.info("--- Step 4: Load & Dedupe ---")
    to_test = load_and_deduplicate_proxies(PROXY_SOURCE_FILE)
    if not to_test:
        logger.error("No unique proxies to test. Aborting.")
        return False

    # --- Step 5: Test Proxies ---
    logger.info("--- Step 5: Testing ---")
    good = run_proxy_test(to_test)

    # --- Step 6: Update Proxy List ---
    logger.info("--- Step 6: Updating List ---")
    if not good:
        logger.error("No working proxies. 'proxy.txt' NOT updated.")
        status = False
    else:
        try:
            import random
            random.shuffle(good)
            with open(PROXY_SOURCE_FILE, "w", encoding='utf-8') as f:
                f.write('\n'.join(good) + '\n')
            logger.info(f"Updated '{os.path.basename(PROXY_SOURCE_FILE)}' with {len(good)} working proxies.")
        except IOError as e:
            logger.error(f"Failed update '{os.path.basename(PROXY_SOURCE_FILE)}': {e}")
            status = False

    duration = time.time() - start
    logger.info(f"===== Proxy Sync Finished in {duration:.2f}s (Success: {status}) =====")
    return status


if __name__ == "__main__":
    # Testing module directly
    print("Running proxy.core module directly for testing...")
    if not logging.getLogger().hasHandlers():
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - [%(name)s] - %(message)s'
        )
    
    success = sync_proxies()
    print(f"\nSync process completed. Success: {success}")
