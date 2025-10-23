import requests
import os
import time
import logging
import random
from typing import Optional, List, Dict

from ..config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, PROXY_POOL, ROOT_DIR

logger = logging.getLogger(__name__)

# ============================================================
# FORMATTING FUNCTIONS
# ============================================================

def format_profile_message(persona_type: str, data: dict) -> str:
    """Format profile data and activities into Markdown message."""
    persona_title = persona_type.replace('_', ' ').title()
    message = f"✅ *Aset Persona Dibuat: {persona_title}*\n\n"
    message += "*--- PROFIL DATA ---*\n"
    
    profile_keys = [
        "name", "username", "bio", "company", "location", "website",
        "linkedin", "twitter", "dev_to", "medium", "gitlab", "bitbucket",
        "stackoverflow", "reddit", "youtube", "twitch"
    ]
    
    for key in profile_keys:
        value = data.get(key)
        display_key = key.replace('_', ' ').title()
        
        # Format display names
        key_mapping = {
            'Twitter': 'X (Twitter)',
            'Dev To': 'Dev.to',
            'Stackoverflow': 'Stack Overflow'
        }
        display_key = key_mapping.get(display_key, display_key)
        display_value = f"`{value}`" if value else "_kosong_"
        message += f"*{display_key}:* {display_value}\n"
    
    # Activity List
    activity_list: Optional[List[str]] = data.get('activity_list')
    if activity_list:
        message += "\n*--- SARAN AKTIVITAS ---*\n"
        for i, activity in enumerate(activity_list, 1):
            message += f"*{i}.* {activity}\n"
    
    # Repo Info
    repo_name = data.get('repo_name')
    if repo_name:
        if activity_list:
            message += "\n"
        message += f"*--- REPO TARGET ---*\n"
        message += f"📁 `{repo_name}`\n"
        repo_description = data.get('repo_description')
        if repo_description:
            message += f"📝 `{repo_description}`\n"
    
    return message

def format_code_message(file_name: str, file_content: str, max_length: int = 3800) -> str:
    """Format file content into Markdown code block."""
    ext_to_lang = {
        '.py': 'python', '.js': 'javascript', '.sh': 'bash', '.go': 'go',
        '.rs': 'rust', '.rb': 'ruby', '.php': 'php', '.java': 'java',
        '.kt': 'kotlin', '.swift': 'swift', '.cpp': 'cpp', '.c': 'c',
        '.ts': 'typescript', '.html': 'html', '.css': 'css', '.yml': 'yaml',
        '.yaml': 'yaml', '.json': 'json', '.sql': 'sql', '.tf': 'terraform',
        '.md': 'markdown', '.txt': 'text', '.conf': 'nginx', '.ini': 'ini',
        '.dockerfile': 'dockerfile', 'dockerfile': 'dockerfile',
        '.gitignore': 'text', '.gitconfig': 'ini', '.bashrc': 'bash',
        '.zshrc': 'bash', '.vimrc': 'vim', '.xml': 'xml'
    }
    
    _, ext = os.path.splitext(file_name)
    lang_key = file_name.lower() if not ext and file_name.startswith('.') else ext.lower()
    lang = ext_to_lang.get(lang_key, 'text')
    
    content = file_content
    if len(content) > max_length:
        content = content[:max_length] + "\n\n... (truncated)"
    
    message = f"📄 *File: `{file_name}`*\n\n"
    message += f"```{lang}\n{content}\n```"
    return message

# ============================================================
# TELEGRAM API INTERACTIONS
# ============================================================

def send_text_message(message: str, chat_id: str = None) -> bool:
    """Send text message to Telegram with proxy support."""
    target_chat_id = chat_id or TELEGRAM_CHAT_ID
    if not target_chat_id or not TELEGRAM_BOT_TOKEN:
        logger.error("Telegram Token or Chat ID is missing.")
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
        proxies, proxy_url = None, None
        if PROXY_POOL:
            proxy_url = PROXY_POOL.get_next_proxy()
            if proxy_url:
                proxies = {"http": proxy_url, "https": proxy_url}
        
        try:
            response = requests.post(url, json=payload, timeout=20, proxies=proxies)
            response.raise_for_status()
            logger.info(f"Text message sent successfully to {target_chat_id}")
            return True
        
        except requests.exceptions.HTTPError as e:
            error_text = e.response.text.lower()
            if e.response.status_code == 400 and 'parse' in error_text:
                logger.warning(f"Markdown parse error (attempt {attempt}/{max_retries}). Retrying without Markdown.")
                payload['parse_mode'] = None
            elif e.response.status_code == 429:
                wait_time = int(e.response.headers.get("Retry-After", 5)) + 1
                logger.warning(f"Rate limit hit (HTTP 429). Waiting {wait_time}s...")
                time.sleep(wait_time)
            else:
                logger.error(f"Telegram HTTP Error {e.response.status_code}: {e.response.text}")
                if PROXY_POOL and proxy_url:
                    PROXY_POOL.mark_failed(proxy_url)
                break
        
        except requests.exceptions.RequestException as e:
            logger.error(f"Network error sending text (attempt {attempt}/{max_retries}): {e}")
            if PROXY_POOL and proxy_url:
                PROXY_POOL.mark_failed(proxy_url)
        
        except Exception as e:
            logger.error(f"Unexpected error sending text (attempt {attempt}/{max_retries}): {e}", exc_info=True)
            break
        
        if attempt < max_retries:
            wait_s = 2 ** attempt
            logger.info(f"Retrying text message in {wait_s}s...")
            time.sleep(wait_s)
    
    logger.error(f"Failed to send text message to {target_chat_id} after {max_retries} attempts.")
    return False

# ============================================================
# MAIN SEND FUNCTION
# ============================================================

def send_persona_to_telegram(persona_type: str, data: dict, chat_id: str = None) -> bool:
    """Send Profile -> Loop send all files as text code blocks."""
    if not data:
        logger.error("Cannot send persona: input data is empty.")
        return False
    
    logger.info(f"Sending assets for persona '{persona_type}' to Telegram...")
    target_chat_id = chat_id or TELEGRAM_CHAT_ID
    
    # 1. Send Profile
    profile_message = format_profile_message(persona_type, data)
    if not send_text_message(profile_message, chat_id=target_chat_id):
        logger.error(f"❌ Failed to send profile data for {persona_type}.")
        return False
    
    # 2. Process Files
    files_to_send: Optional[List[Dict]] = data.get('files')
    if not files_to_send:
        logger.info(f"✅ Profile sent successfully for {persona_type} (no files).")
        return True
    
    logger.info(f"📄 Found {len(files_to_send)} file(s) for {persona_type} to send as text.")
    
    # 3. Loop Send Files as Text Code Blocks
    success_count = 0
    total_files = len(files_to_send)
    
    for i, file_data in enumerate(files_to_send):
        file_name = file_data.get('file_name')
        file_content = file_data.get('file_content')
        
        if not file_name or file_content is None:
            logger.warning(f"Skipping file {i+1}/{total_files} for {persona_type} due to missing name or content.")
            continue
        
        logger.info(f"📝 Sending file {i+1}/{total_files} for {persona_type} as code block: {file_name}")
        
        # Anti-rate limit delay
        if i > 0:
            sleep_duration = random.uniform(1.5, 3.0)
            logger.debug(f"Sleeping for {sleep_duration:.1f}s before sending next file...")
            time.sleep(sleep_duration)
        
        code_message = format_code_message(file_name, file_content)
        if send_text_message(code_message, chat_id=target_chat_id):
            success_count += 1
        else:
            logger.error(f"❌ Failed to send code block for: {file_name} (persona: {persona_type})")
    
    if success_count == total_files:
        logger.info(f"✅ Profile + {success_count} Code Block(s) sent successfully for {persona_type}!")
        return True
    else:
        logger.warning(f"⚠️ Profile sent for {persona_type}, but only {success_count}/{total_files} file(s) were sent successfully.")
        return False
