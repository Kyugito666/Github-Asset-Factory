"""
Telegram Sender - Send messages ke Telegram dengan proxy support

Functions:
- send_text_message: Send text message dengan retry & proxy
- send_persona_to_telegram: Send complete persona data (profile + files)
"""

import logging
import time
import requests
from typing import Optional, List, Dict

from ...config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, PROXY_POOL
from .formatters import format_profile_message, format_code_message

logger = logging.getLogger(__name__)


def send_text_message(message: str, chat_id: str = None) -> bool:
    """
    Send text message ke Telegram dengan proxy support & retry.
    
    Features:
    - Proxy rotation dari PROXY_POOL
    - Retry mechanism (max 3x)
    - Exponential backoff
    - Error handling (rate limit, parse error, connection error)
    
    Args:
        message: Text message untuk dikirim
        chat_id: Target chat ID (default: TELEGRAM_CHAT_ID dari config)
        
    Returns:
        bool: True jika berhasil, False jika gagal
    """
    target_chat_id = chat_id or TELEGRAM_CHAT_ID
    
    if not target_chat_id or not TELEGRAM_BOT_TOKEN:
        logger.error("Telegram token or chat ID is missing.")
        return False
    
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        'chat_id': target_chat_id,
        'text': message,
        'parse_mode': 'Markdown',
        'disable_web_page_preview': True
    }
    
    max_retries = 3

    for attempt in range(1, max_retries + 1):
        proxies, proxy_url_display = None, "None"
        
        # Get proxy dari pool
        if PROXY_POOL:
            proxy_url = PROXY_POOL.get_next_proxy()
            if proxy_url:
                proxies = {"http": proxy_url, "https": proxy_url}
                proxy_url_display = proxy_url.split('@')[-1]

        try:
            response = requests.post(url, json=payload, timeout=20, proxies=proxies)
            response.raise_for_status()
            logger.info(f"Text message sent to {target_chat_id} (Proxy: {proxy_url_display})")
            return True
            
        except requests.exceptions.HTTPError as e:
            logger.error(f"HTTP Error sending text (Attempt {attempt}, Proxy: {proxy_url_display}): "
                        f"{e.response.status_code} - {e.response.text[:200]}")
            
            # Handle specific errors
            if e.response.status_code == 400 and 'parse' in e.response.text.lower():
                logger.warning("Markdown parse error, retrying without Markdown...")
                payload['parse_mode'] = None
                continue
            elif e.response.status_code == 429:
                logger.warning(f"Rate limited by Telegram. Waiting before retry...")
                time.sleep(5 * attempt)
                continue
            
            # Mark proxy failed untuk error lain
            if PROXY_POOL and proxies:
                PROXY_POOL.mark_failed(proxy_url)

        except requests.exceptions.RequestException as e:
            logger.error(f"Network Error sending text (Attempt {attempt}, Proxy: {proxy_url_display}): {e}")
            if PROXY_POOL and proxies:
                PROXY_POOL.mark_failed(proxy_url)

        except Exception as e:
            logger.error(f"Unexpected Error sending text (Attempt {attempt}, Proxy: {proxy_url_display}): {e}",
                        exc_info=False)
            if PROXY_POOL and proxies:
                PROXY_POOL.mark_failed(proxy_url)

        # Wait before retry
        if attempt < max_retries:
            wait_time = 2 * attempt
            logger.info(f"Waiting {wait_time}s before retry...")
            time.sleep(wait_time)

    logger.error(f"Failed to send text message to {target_chat_id} after {max_retries} attempts.")
    return False


def send_persona_to_telegram(persona_type: str, data: dict, chat_id: str = None) -> bool:
    """
    Send complete persona data ke Telegram (profile + files).
    
    Process:
    1. Send profile message (formatted)
    2. Loop send setiap file sebagai code block
    
    Args:
        persona_type: Tipe persona
        data: Persona data dict
        chat_id: Target chat ID
        
    Returns:
        bool: True jika semua berhasil, False jika ada yang gagal
    """
    logger.info(f"Sending assets to Telegram (Target: {chat_id or 'default'})...")
    target_chat_id = chat_id or TELEGRAM_CHAT_ID

    # 1. SEND PROFILE
    profile_message = format_profile_message(persona_type, data)
    if not send_text_message(profile_message, chat_id=target_chat_id):
        logger.error("❌ Failed to send profile data")
        return False

    # 2. PROCESS FILES
    files_to_send: Optional[List[Dict]] = data.get('files')
    if not files_to_send:
        logger.info("✅ Profile sent (no files to send)!")
        return True
    
    logger.info(f"📄 Found {len(files_to_send)} file(s) to send as text.")

    # 3. SEND EACH FILE
    success_count = 0
    total_files = len(files_to_send)
    
    for i, file_data in enumerate(files_to_send):
        file_name = file_data.get('file_name')
        file_content = file_data.get('file_content')
        
        if not file_name or file_content is None:
            logger.warning(f"Skipping file {i+1}/{total_files} due to missing name or content.")
            continue

        logger.info(f"📝 Sending file {i+1}/{total_files} as code block: {file_name}")
        
        # Jeda antar file (kecuali file pertama)
        if i > 0:
            time.sleep(1.5)

        code_message = format_code_message(file_name, file_content)
        if send_text_message(code_message, chat_id=target_chat_id):
            success_count += 1
        else:
            logger.error(f"❌ Failed to send code block for: {file_name}")

    if success_count == total_files:
        logger.info(f"✅ Profile + {success_count} Code Block(s) sent successfully!")
        return True
    else:
        logger.warning(f"[!] Profile sent, but only {success_count}/{total_files} file(s) were sent successfully.")
        return False
