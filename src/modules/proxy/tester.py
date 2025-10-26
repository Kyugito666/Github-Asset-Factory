"""
Proxy Tester - Test proxy validity dengan concurrent workers

Features:
- Concurrent testing (ThreadPoolExecutor)
- Multiple check URLs untuk reliability
- Timeout handling
- Progress logging
- Save failed proxies untuk debugging
"""

import os
import re
import json
import logging
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed

from .core import FAIL_PROXY_FILE

logger = logging.getLogger(__name__)

# Testing configuration
PROXY_TIMEOUT = 15
MAX_WORKERS = 10
CHECK_URLS = ["https://api.ipify.org?format=json", "http://httpbin.org/ip"]


def check_proxy_final(proxy):
    """
    Test satu proxy dengan multiple check URLs.
    
    Args:
        proxy: Proxy URL (format: http://user:pass@host:port)
        
    Returns:
        Tuple[str, bool, str]: (proxy, is_valid, message)
    """
    proxies_dict = {"http": proxy, "https": proxy}
    headers = {'User-Agent': 'Mozilla/5.0'}
    
    for url in CHECK_URLS:
        try:
            with requests.Session() as s:
                s.proxies = proxies_dict
                s.headers.update(headers)
                r = s.get(url, timeout=PROXY_TIMEOUT)
            
            r.raise_for_status()
            content = r.text.strip()
            
            # Check if response contains IP
            is_json_ip = False
            try:
                j = r.json()
                is_json_ip = isinstance(j, dict) and ('ip' in j or 'origin' in j)
            except json.JSONDecodeError:
                pass
            
            # Valid if JSON contains IP or content has IP pattern
            if is_json_ip or re.search(r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}', content):
                return proxy, True, f"OK via {url}"
            else:
                logger.debug(f"Proxy {proxy.split('@')[-1]} unexpected content {url}: {content[:60]}...")
                
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 407:
                return proxy, False, "Auth Required (407)"
            else:
                logger.debug(f"HTTP Error {proxy.split('@')[-1]} {url}: {e.response.status_code}")
                
        except requests.exceptions.Timeout:
            logger.debug(f"Timeout {proxy.split('@')[-1]} {url}")
            
        except requests.exceptions.ProxyError as e:
            r = str(e).split(':')[-1].strip()
            logger.debug(f"Proxy Error {proxy.split('@')[-1]} {url}: {r[:40]}")
            return proxy, False, f"Proxy Error ({r[:30]})"
            
        except requests.exceptions.RequestException as e:
            logger.debug(f"Connection Error {proxy.split('@')[-1]} {url}: {e.__class__.__name__}")
    
    logger.debug(f"Proxy {proxy.split('@')[-1]} failed checks.")
    return proxy, False, "Connection Failed / Bad Response"


def run_proxy_test(proxies_to_test):
    """
    Test multiple proxies secara concurrent.
    
    Args:
        proxies_to_test: List of proxy URLs to test
        
    Returns:
        List[str]: List of working proxies
    """
    if not proxies_to_test:
        logger.info("No proxies to test.")
        return []
    
    total = len(proxies_to_test)
    logger.info(f"Testing {total} proxies (Workers: {MAX_WORKERS}, Timeout: {PROXY_TIMEOUT}s)...")
    
    good = []
    failed = []
    count = 0
    
    executor = ThreadPoolExecutor(max_workers=MAX_WORKERS)
    
    try:
        # Submit all tasks
        future_map = {executor.submit(check_proxy_final, p): p for p in proxies_to_test}
        
        # Progress logging interval
        log_interval = max(1, total // 20) if total > 0 else 1
        
        # Process results as they complete
        for future in as_completed(future_map):
            try:
                p, ok, msg = future.result()
                count += 1
                
                if ok:
                    good.append(p)
                else:
                    failed.append((p, msg))
                
                # Log progress
                if count % log_interval == 0 or count == total:
                    logger.info(f"Test Progress: {count}/{total} ({(count/total)*100:.1f}%) - Good: {len(good)}")
                    
            except Exception as exc:
                pk = future_map[future]
                logger.error(f"Error testing {pk.split('@')[-1]}: {exc}")
                failed.append((pk, f"Task Error: {exc}"))
                count += 1
                
    finally:
        executor.shutdown(wait=True)
    
    # Save failed proxies untuk debugging
    if failed:
        try:
            os.makedirs(os.path.dirname(FAIL_PROXY_FILE), exist_ok=True)
            with open(FAIL_PROXY_FILE, "w", encoding='utf-8') as f:
                f.write('\n'.join(f"{p} # {r}" for p, r in failed) + '\n')
            logger.info(f"Saved {len(failed)} failed to '{os.path.basename(FAIL_PROXY_FILE)}'.")
        except IOError as e:
            logger.error(f"Failed save failed proxies: {e}")
    
    logger.info(f"Test complete. Good: {len(good)}/{total}.")
    return good
