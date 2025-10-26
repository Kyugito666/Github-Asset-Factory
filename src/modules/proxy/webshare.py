"""
Webshare Integration - IP Authorization & Proxy Download

Features:
- Auto IP authorization untuk semua Webshare accounts
- Get current public IP
- Remove old IPs
- Add new IP
- Generate proxy download URLs
"""

import os
import json
import logging
import requests


logger = logging.getLogger(__name__)

# Webshare API endpoints
WEBSHARE_AUTH_URL = "https://proxy.webshare.io/api/v2/proxy/ipauthorization/"
WEBSHARE_SUB_URL = "https://proxy.webshare.io/api/v2/subscription/"
WEBSHARE_CONFIG_URL = "https://proxy.webshare.io/api/v2/proxy/config/"
WEBSHARE_PROFILE_URL = "https://proxy.webshare.io/api/v2/profile/"
WEBSHARE_DOWNLOAD_URL_FORMAT = "https://proxy.webshare.io/api/v2/proxy/list/download/{token}/-/any/username/direct/-/"
IP_CHECK_SERVICE_URL = "https://api.ipify.org?format=json"
WEBSHARE_API_TIMEOUT = 60


def load_webshare_apikeys(file_path):
    """
    Load Webshare API keys dari apikeys.txt.
    
    Args:
        file_path: Path ke data/apikeys.txt
        
    Returns:
        List[str]: List of API keys
    """
    if not os.path.exists(file_path):
        logger.warning(f"Webshare API key file not found: {file_path}. Creating empty file.")
        try:
            os.makedirs(os.path.dirname(file_path), exist_ok=True)
            with open(file_path, "w", encoding='utf-8') as f:
                f.write("# Masukkan API key Webshare Anda di sini, SATU per baris\n")
        except IOError as e:
            logger.error(f"Failed create Webshare API key file: {e}")
        return []
    
    try:
        with open(file_path, "r", encoding='utf-8') as f:
            keys = [line.strip() for line in f 
                   if line.strip() and not line.strip().startswith("#")]
            logger.info(f"Loaded {len(keys)} Webshare API key(s) from {os.path.basename(file_path)}.")
            return keys
    except IOError as e:
        logger.error(f"Failed read Webshare API key file {file_path}: {e}")
        return []


def get_current_public_ip():
    """
    Get current public IP address dari ipify.org.
    
    Returns:
        Optional[str]: Public IP address or None if failed
    """
    logger.info("Webshare IP Sync: 1. Fetching current public IP...")
    try:
        response = requests.get(IP_CHECK_SERVICE_URL, timeout=15)
        response.raise_for_status()
        new_ip = response.json().get("ip")
        
        if new_ip:
            logger.info(f"   -> Public IP found: {new_ip}")
            return new_ip
        else:
            logger.error("   -> ERROR: IP address not found in ipify response.")
            return None
            
    except requests.RequestException as e:
        logger.error(f"   -> ERROR: Failed get public IP: {e}")
        return None
    except json.JSONDecodeError as e:
        logger.error(f"   -> ERROR: Failed parse ipify response: {e}")
        return None


def get_account_email(session: requests.Session) -> str:
    """
    Get account email dari Webshare profile API.
    
    Args:
        session: Requests session with Authorization header
        
    Returns:
        str: Account email or error message
    """
    try:
        response = session.get(WEBSHARE_PROFILE_URL, timeout=WEBSHARE_API_TIMEOUT)
        response.raise_for_status()
        email = response.json().get("email")
        return email if email else "[Email N/A]"
    except requests.exceptions.HTTPError as e:
        return "[Invalid API Key]" if e.response.status_code == 401 else f"[HTTP Error {e.response.status_code}]"
    except requests.RequestException:
        return "[Connection Error]"
    except Exception:
        return "[Parsing Error]"


def get_target_plan_id(session: requests.Session):
    """
    Get Plan ID dari Webshare config API.
    
    Args:
        session: Requests session with Authorization header
        
    Returns:
        Optional[str]: Plan ID or None if failed
    """
    logger.info("Webshare IP Sync: 2. Getting target Plan ID via /config/ ...")
    try:
        response = session.get(WEBSHARE_CONFIG_URL, timeout=WEBSHARE_API_TIMEOUT)
        response.raise_for_status()
        plan_id = response.json().get("id")
        
        if plan_id:
            plan_id_str = str(plan_id)
            logger.info(f"   -> Found Plan ID: {plan_id_str}")
            return plan_id_str
        else:
            logger.error("   -> ERROR: '/proxy/config/' no 'id'.")
            return None
            
    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 401:
            logger.error("   -> ERROR: Invalid Webshare API Key (401).")
        else:
            logger.error(f"   -> ERROR: HTTP Error getting config: {e.response.status_code} - {e.response.text[:100]}")
        return None
    except requests.RequestException as e:
        logger.error(f"   -> ERROR: Connection error getting config: {e}")
        return None


def get_authorized_ips(session: requests.Session, plan_id: str):
    """
    Get currently authorized IPs dari Webshare.
    
    Args:
        session: Requests session with Authorization header
        plan_id: Plan ID
        
    Returns:
        Dict[str, int]: Mapping of IP -> authorization_id
    """
    logger.info("Webshare IP Sync: 3. Getting currently authorized IPs...")
    params = {"plan_id": plan_id}
    ip_to_id_map = {}
    
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
        logger.error(f"   -> ERROR: Failed get authorized IPs: {e}")
        return {}


def remove_ip(session: requests.Session, ip: str, authorization_id: int, plan_id: str):
    """
    Remove IP dari authorization list.
    
    Args:
        session: Requests session
        ip: IP address to remove
        authorization_id: Auth ID
        plan_id: Plan ID
        
    Returns:
        bool: True if successful
    """
    logger.info(f"Webshare IP Sync:    -> Removing old IP: {ip} (ID: {authorization_id})")
    params = {"plan_id": plan_id}
    delete_url = f"{WEBSHARE_AUTH_URL}{authorization_id}/"
    
    try:
        response = session.delete(delete_url, params=params, timeout=WEBSHARE_API_TIMEOUT)
        
        if response.status_code == 204:
            logger.info(f"       -> Successfully removed IP: {ip}")
            return True
        else:
            try:
                error_detail = response.json()
            except:
                error_detail = response.text[:100]
            
            logger.error(f"       -> ERROR removing {ip}: Status {response.status_code} - {error_detail}")
            return False
            
    except requests.RequestException as e:
        logger.error(f"       -> ERROR: Connection error removing {ip}: {e}")
        return False


def add_ip(session: requests.Session, ip: str, plan_id: str):
    """
    Add IP ke authorization list.
    
    Args:
        session: Requests session
        ip: IP address to add
        plan_id: Plan ID
        
    Returns:
        bool: True if successful
    """
    logger.info(f"Webshare IP Sync:    -> Adding new IP: {ip}")
    params = {"plan_id": plan_id}
    payload = {"ip_address": ip}
    
    try:
        response = session.post(WEBSHARE_AUTH_URL, json=payload, params=params, timeout=WEBSHARE_API_TIMEOUT)
        
        if response.status_code == 201:
            logger.info(f"       -> Successfully added IP: {ip}")
            return True
        else:
            try:
                error_detail = response.json()
            except:
                error_detail = response.text[:100]
            
            logger.error(f"       -> ERROR adding {ip}: Status {response.status_code} - {error_detail}")
            return False
            
    except requests.RequestException as e:
        logger.error(f"       -> ERROR: Connection error adding {ip}: {e}")
        return False


def get_webshare_download_url(session: requests.Session, plan_id: str):
    """
    Generate proxy download URL dari Webshare config.
    
    Args:
        session: Requests session
        plan_id: Plan ID (not used, kept for compatibility)
        
    Returns:
        Optional[str]: Download URL or None if failed
    """
    logger.info("Webshare Download:    -> Getting download URL via /config/ ...")
    try:
        response = session.get(WEBSHARE_CONFIG_URL, timeout=WEBSHARE_API_TIMEOUT)
        response.raise_for_status()
        data = response.json()
        token = data.get("proxy_list_download_token")
        
        if not token:
            logger.error("   -> ERROR: token missing.")
            return None
        
        dl_url = f"https://proxy.webshare.io/api/v2/proxy/list/download/{token}/-/any/username/direct/-/"
        logger.info(f"       -> OK URL generated.")
        return dl_url
        
    except Exception as e:
        logger.error(f"   -> ERROR: {e}")
        return None


def run_webshare_ip_sync() -> bool:
    """
    Main function untuk sync IP authorization ke semua Webshare accounts.
    ...
    """
    logger.info("===== Starting Webshare IP Authorization Sync =====")
    
    api_keys = load_webshare_apikeys(WEBSHARE_APIKEYS_FILE)
    if not api_keys:
        logger.error(f"IP Sync Aborted: '{os.path.basename(WEBSHARE_APIKEYS_FILE)}' empty.")
        return False
    
    new_ip = get_current_public_ip()
    if not new_ip:
        logger.error("IP Sync Aborted: Failed get public IP.")
        return False
    
    logger.info(f"Syncing IP [{new_ip}] to [{len(api_keys)}] Webshare account(s)...")
    overall_success = True

    for api_key in api_keys:
        email_info = "[Fetching Email...]"
        try:
             with requests.Session() as es:
                 es.headers.update({
                     "Authorization": f"Token {api_key}",
                     "Accept": "application/json"
                 })
                 email_info = get_account_email(es)
        except Exception:
            email_info = "[Error Email]"
        
        logger.info(f"\n--- Processing Key: [...{api_key[-6:]}] ({email_info}) ---")
        account_success = False
        
        with requests.Session() as s:
            s.headers.update({
                "Authorization": f"Token {api_key}",
                "Content-Type": "application/json",
                "Accept": "application/json"
            })
            
            try:
                plan_id = get_target_plan_id(s)
                if not plan_id:
                    logger.error("   -> Skip: No Plan ID.")
                    overall_success = False
                    continue
                
                auth_ips_map = get_authorized_ips(s, plan_id)
                
                # Check if already authorized
                if new_ip in auth_ips_map:
                    logger.info(f"   -> IP ({new_ip}) already authorized.")
                    account_success = True
                    continue

                # Remove old IPs
                logger.info("\nWebshare IP Sync: 4. Removing old IPs...")
                removed, failed_remove = 0, 0
                
                if not auth_ips_map:
                    logger.info("   -> No old IPs.")
                else:
                    for ip_del, id_del in auth_ips_map.items():
                        if ip_del != new_ip:
                            if remove_ip(s, ip_del, id_del, plan_id):
                                removed += 1
                            else:
                                failed_remove += 1
                    
                    logger.info(f"   -> Removal: {removed} removed, {failed_remove} failed.")
                    if failed_remove > 0:
                        overall_success = False

                # Add new IP
                logger.info("\nWebshare IP Sync: 5. Adding new IP...")
                if add_ip(s, new_ip, plan_id):
                    account_success = (failed_remove == 0)
                else:
                    account_success = False
                    overall_success = False
                    
            except Exception as e:
                logger.error(f"   -> !!! UNEXPECTED ERROR: {e}", exc_info=True)
                overall_success = False
        
        if account_success:
            logger.info(f"--- Account [...{api_key[-6:]}] OK. ---")
        else:
            logger.error(f"--- Account [...{api_key[-6:]}] FAILED. ---")
    
    logger.info(f"===== Webshare IP Sync Finished (Overall Success: {overall_success}) =====")
    return overall_success
