import requests
import os
import time
import logging
from typing import Optional, List

# Import PROXY_POOL (Relative)
# --- DIPERBARUI ---
from ..config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, PROXY_POOL

logger = logging.getLogger(__name__)


def format_profile_message(persona_type: str, data: dict) -> str:
    persona_title = persona_type.replace('_', ' ').title()
    message = f"✅ *Aset Persona Dibuat: {persona_title}*\n\n"
    message += "*--- PROFIL DATA ---*\n"
    profile_keys = ["name","username","bio","company","location","website","linkedin","twitter","dev_to","medium","gitlab","bitbucket","stackoverflow","reddit","youtube","twitch"]
    for key in profile_keys:
        value = data.get(key)
        display_key = key.replace('_', ' ').title()
        if display_key == 'Twitter': display_key = 'X (Twitter)'
        if display_key == 'Dev To': display_key = 'Dev.to'
        if display_key == 'Stackoverflow': display_key = 'Stack Overflow'
        display_value = f"`{value}`" if value else "_kosong_"
        message += f"*{display_key}:* {display_value}\n"
        
    activity_list: Optional[List[str]] = data.get('activity_list')
    if activity_list:
        message += "\n*--- SARAN AKTIVITAS ---*\n"
        for i, activity in enumerate(activity_list, 1): message += f"*{i}.* {activity}\n"
        
    repo_name = data.get('repo_name')
    if repo_name:
        if activity_list: message += "\n" # Add newline if activities exist
        message += f"*--- REPO TARGET ---*\n"
        message += f"📁 `{repo_name}`\n"
        repo_description = data.get('repo_description')
        if repo_description:
             message += f"📝 `{repo_description}`\n"
            
    return message


def format_code_message(file_name: str, file_content: str, max_length: int = 3500) -> str:
    ext_to_lang = {'.py':'python','.js':'javascript','.sh':'bash','.go':'go','.rs':'rust','.rb':'ruby','.php':'php','.java':'java','.cpp':'cpp','.c':'c','.ts':'typescript','.yml':'yaml','.yaml':'yaml','.json':'json','.md':'markdown','.txt':'text','.conf':'nginx','.Dockerfile':'dockerfile','.tf':'terraform','.ipynb':'json'}
    ext = os.path.splitext(file_name)[1]; lang = ext_to_lang.get(ext, 'text')
    content = file_content
    if len(content) > max_length: content = content[:max_length] + "\n\n... (truncated)"
    message = f"📄 *File: {file_name}*\n\n```{lang}\n{content}\n```"
    return message


def send_text_message(message: str, chat_id: str = None) -> bool:
    """Kirim text message ke Telegram (DENGAN PROXY)"""
    target_chat_id = chat_id or TELEGRAM_CHAT_ID
    if not target_chat_id: return False
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {'chat_id': target_chat_id, 'text': message, 'parse_mode': 'Markdown', 'disable_web_page_preview': True}
    max_retries = 3

    for attempt in range(1, max_retries + 1):
        proxies, proxy_url = None, None
        if PROXY_POOL:
            proxy_url = PROXY_POOL.get_next_proxy()
            if proxy_url:
                proxies = {"http": proxy_url, "https": proxy_url}
                logger.info(f"Telegram (text) using proxy: {proxy_url.split('@')[-1]}")
        try:
            response = requests.post(url, json=payload, timeout=15, proxies=proxies)
            response.raise_for_status()
            logger.info(f"Text message sent to {target_chat_id}")
            return True
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 400 and 'parse' in e.response.text.lower():
                payload['parse_mode'] = None
                continue
            logger.error(f"HTTP Error: {e.response.text}")
            if PROXY_POOL and proxy_url:
                PROXY_POOL.mark_failed(proxy_url)
            break
        except Exception as e:
            logger.error(f"Error sending text (attempt {attempt}): {e}")
            if PROXY_POOL and proxy_url:
                PROXY_POOL.mark_failed(proxy_url)
        if attempt < max_retries: time.sleep(2)
    return False


def send_persona_to_telegram(persona_type: str, data: dict, chat_id: str = None) -> bool:
    """
    Kirim Profile -> (Aktivitas) -> Loop kirim semua file sbg text code blocks.
    """
    logger.info(f"Sending assets to Telegram (Target: {chat_id or 'default'})...")
    target_chat_id = chat_id or TELEGRAM_CHAT_ID
    
    # 1. KIRIM PROFIL (+ Aktivitas)
    profile_message = format_profile_message(persona_type, data)
    if not send_text_message(profile_message, chat_id=target_chat_id):
        logger.error("❌ Failed to send profile data")
        return False
    
    # 2. PROSES FILES (jika ada)
    files_to_send: Optional[List[Dict]] = data.get('files')
    if not files_to_send:
        logger.info("✅ Profile sent (no files to send)!")
        return True
    logger.info(f"📄 Found {len(files_to_send)} file(s) to send as text.")
    
    # 3. LOOP KIRIM SETIAP FILE SEBAGAI TEXT CODE BLOCK
    success_count = 0
    for i, file_data in enumerate(files_to_send):
        file_name = file_data.get('file_name'); file_content = file_data.get('file_content')
        if not file_name or file_content is None:
            logger.warning(f"Skipping file {i+1} due to missing name or content."); continue
        logger.info(f"📝 Sending file {i+1}/{len(files_to_send)} as code block: {file_name}")
        if i > 0: time.sleep(1.5) # Jeda antar pesan
        code_message = format_code_message(file_name, file_content)
        if send_text_message(code_message, chat_id=target_chat_id): success_count += 1
        else: logger.error(f"❌ Failed to send code block for: {file_name}")
            
    if success_count == len(files_to_send):
        logger.info(f"✅ Profile + {success_count} Code Block(s) sent successfully!")
        return True
    else:
        # --- EMOJI DI SINI DIGANTI ---
        logger.warning(f"[!] Profile sent, but only {success_count}/{len(files_to_send)} file(s) were sent successfully.")
        # -----------------------------
        return False
