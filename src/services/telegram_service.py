import requests
import os
import time
import logging
from typing import Optional, List, Dict # Ditambah Dict

# --- IMPORT DARI DALAM 'src' & PATH ---
from ..config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, PROXY_POOL, ROOT_DIR
# -------------------------------------

logger = logging.getLogger(__name__)

# ============================================================
# FORMATTING FUNCTIONS
# ============================================================

def format_profile_message(persona_type: str, data: dict) -> str:
    """Format data profil dan aktivitas menjadi pesan Markdown."""
    persona_title = persona_type.replace('_', ' ').title()
    message = f"✅ *Aset Persona Dibuat: {persona_title}*\n\n"
    message += "*--- PROFIL DATA ---*\n"
    profile_keys = ["name","username","bio","company","location","website","linkedin","twitter","dev_to","medium","gitlab","bitbucket","stackoverflow","reddit","youtube","twitch"]
    for key in profile_keys:
        value = data.get(key)
        display_key = key.replace('_', ' ').title()
        # Formatting nama
        if display_key == 'Twitter': display_key = 'X (Twitter)'
        if display_key == 'Dev To': display_key = 'Dev.to'
        if display_key == 'Stackoverflow': display_key = 'Stack Overflow'
        display_value = f"`{value}`" if value else "_kosong_"
        message += f"*{display_key}:* {display_value}\n"

    # Format Activity List (Bahasa Indonesia)
    activity_list: Optional[List[str]] = data.get('activity_list')
    if activity_list: # Cek jika tidak None dan tidak kosong
        message += "\n*--- SARAN AKTIVITAS ---*\n"
        for i, activity in enumerate(activity_list, 1):
            message += f"*{i}.* {activity}\n"

    # Format Info Repo (jika ada)
    repo_name = data.get('repo_name')
    if repo_name:
        if activity_list: message += "\n" # Tambah spasi jika ada aktivitas
        message += f"*--- REPO TARGET ---*\n"
        message += f"📁 `{repo_name}`\n"
        repo_description = data.get('repo_description')
        if repo_description:
             message += f"📝 `{repo_description}`\n" # Tambah deskripsi repo

    return message

def format_code_message(file_name: str, file_content: str, max_length: int = 3800) -> str:
    """Format konten file menjadi code block Markdown."""
    # Kamus ekstensi ke bahasa markdown (bisa diperluas)
    ext_to_lang = {
        '.py': 'python', '.js': 'javascript', '.sh': 'bash', '.go': 'go', '.rs': 'rust',
        '.rb': 'ruby', '.php': 'php', '.java': 'java', '.kt': 'kotlin', '.swift': 'swift',
        '.cpp': 'cpp', '.c': 'c', '.ts': 'typescript', '.html': 'html', '.css': 'css',
        '.yml': 'yaml', '.yaml': 'yaml', '.json': 'json', '.sql': 'sql', '.tf': 'terraform',
        '.md': 'markdown', '.txt': 'text', '.conf': 'nginx', '.ini': 'ini',
        '.dockerfile': 'dockerfile', 'dockerfile': 'dockerfile', # Handle tanpa titik
        '.gitignore': 'text', '.gitconfig': 'ini', '.bashrc': 'bash', '.zshrc': 'bash',
        '.vimrc': 'vim', '.xml': 'xml'
        # Tambahkan ekstensi lain jika perlu
    }
    # Ambil ekstensi (termasuk dotfile tanpa ekstensi)
    _, ext = os.path.splitext(file_name)
    if not ext and file_name.startswith('.'): # Handle dotfiles like .bashrc
        lang_key = file_name.lower()
    else:
        lang_key = ext.lower()

    lang = ext_to_lang.get(lang_key, 'text') # Default ke 'text'

    content = file_content
    # Potong jika terlalu panjang (batas Telegram ~4096, beri buffer)
    if len(content) > max_length:
        content = content[:max_length] + "\n\n... (truncated)"

    # Format pesan
    message = f"📄 *File: `{file_name}`*\n\n" # Gunakan backtick untuk nama file
    message += f"```{lang}\n{content}\n```"
    return message

# ============================================================
# TELEGRAM API INTERACTIONS
# ============================================================

def send_text_message(message: str, chat_id: str = None) -> bool:
    """Kirim text message ke Telegram (DENGAN PROXY)."""
    target_chat_id = chat_id or TELEGRAM_CHAT_ID
    if not target_chat_id or not TELEGRAM_BOT_TOKEN:
        logger.error("Telegram Token or Chat ID is missing. Cannot send message.")
        return False

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {'chat_id': target_chat_id, 'text': message, 'parse_mode': 'Markdown', 'disable_web_page_preview': True}
    max_retries = 3

    for attempt in range(1, max_retries + 1):
        proxies, proxy_url = None, None
        if PROXY_POOL:
            proxy_url = PROXY_POOL.get_next_proxy()
            if proxy_url:
                proxies = {"http": proxy_url, "https": proxy_url}
                # Kurangi log spam proxy di sini, fokus ke error saja
                # logger.info(f"Telegram (text) using proxy: {proxy_url.split('@')[-1]}")
        try:
            response = requests.post(url, json=payload, timeout=20, proxies=proxies) # Timeout dinaikkan
            response.raise_for_status() # Akan raise error jika status code >= 400
            logger.info(f"Text message sent successfully to {target_chat_id}")
            return True
        except requests.exceptions.HTTPError as e:
            # Handle error spesifik Telegram
            error_text = e.response.text.lower()
            if e.response.status_code == 400 and 'parse' in error_text:
                logger.warning(f"Telegram Markdown parse error (attempt {attempt}/{max_retries}). Retrying without Markdown.")
                payload['parse_mode'] = None # Coba kirim tanpa Markdown
                # Jangan break, coba lagi
            elif e.response.status_code == 429: # Too Many Requests
                 wait_time = int(e.response.headers.get("Retry-After", 5)) + 1 # Ambil waktu tunggu dari header + buffer
                 logger.warning(f"Telegram rate limit hit (HTTP 429). Waiting {wait_time}s...")
                 time.sleep(wait_time)
                 # Jangan break, coba lagi setelah wait
            else:
                logger.error(f"Telegram HTTP Error {e.response.status_code} sending text: {e.response.text}")
                if PROXY_POOL and proxy_url: PROXY_POOL.mark_failed(proxy_url)
                break # Keluar loop jika error HTTP lain
        except requests.exceptions.RequestException as e: # Tangkap error koneksi/timeout
            logger.error(f"Network error sending text (attempt {attempt}/{max_retries}): {e}")
            if PROXY_POOL and proxy_url: PROXY_POOL.mark_failed(proxy_url) # Tandai proxy gagal
            # Jangan break, coba lagi dengan proxy/koneksi lain
        except Exception as e: # Tangkap error tak terduga lain
            logger.error(f"Unexpected error sending text (attempt {attempt}/{max_retries}): {e}", exc_info=True)
            # Mungkin break jika error aneh
            break

        # Tunggu sebelum retry berikutnya
        if attempt < max_retries:
             wait_s = 2 ** attempt # Exponential backoff
             logger.info(f"Retrying text message in {wait_s}s...")
             time.sleep(wait_s)

    logger.error(f"Failed to send text message to {target_chat_id} after {max_retries} attempts.")
    return False

# ============================================================
# MAIN SEND FUNCTION (Hanya pakai send_text_message)
# ============================================================
def send_persona_to_telegram(persona_type: str, data: dict, chat_id: str = None) -> bool:
    """
    Kirim Profile -> (Aktivitas) -> Loop kirim semua file sbg text code blocks.
    """
    if not data:
        logger.error("Cannot send persona: input data is empty.")
        return False

    logger.info(f"Sending assets for persona '{persona_type}' to Telegram (Target: {chat_id or 'default'})...")
    target_chat_id = chat_id or TELEGRAM_CHAT_ID

    # 1. KIRIM PROFIL (+ Aktivitas + Repo Info)
    profile_message = format_profile_message(persona_type, data)
    if not send_text_message(profile_message, chat_id=target_chat_id):
        logger.error(f"❌ Failed to send profile data for {persona_type}.")
        # Pertimbangkan apakah mau stop atau lanjut jika profil gagal
        return False # Gagal jika profil saja tidak terkirim

    # 2. PROSES FILES (jika ada)
    files_to_send: Optional[List[Dict]] = data.get('files')
    if not files_to_send: # Cek jika None atau list kosong
        logger.info(f"✅ Profile sent successfully for {persona_type} (no files).")
        return True

    logger.info(f"📄 Found {len(files_to_send)} file(s) for {persona_type} to send as text.")

    # 3. LOOP KIRIM SETIAP FILE SEBAGAI TEXT CODE BLOCK
    success_count = 0
    total_files = len(files_to_send)
    for i, file_data in enumerate(files_to_send):
        file_name = file_data.get('file_name'); file_content = file_data.get('file_content')

        if not file_name or file_content is None: # Cek content bisa string kosong
            logger.warning(f"Skipping file {i+1}/{total_files} for {persona_type} due to missing name or content.")
            continue

        logger.info(f"📝 Sending file {i+1}/{total_files} for {persona_type} as code block: {file_name}")

        # --- JEDA ANTAR PESAN untuk hindari rate limit ---
        if i > 0: # Jangan jeda sebelum file pertama
             sleep_duration = random.uniform(1.5, 3.0) # Jeda acak
             logger.debug(f"Sleeping for {sleep_duration:.1f}s before sending next file...")
             time.sleep(sleep_duration)

        code_message = format_code_message(file_name, file_content)
        if send_text_message(code_message, chat_id=target_chat_id):
            success_count += 1
        else:
            logger.error(f"❌ Failed to send code block for: {file_name} (persona: {persona_type})")
            # Putuskan: Lanjut atau Stop? Coba lanjut dulu.

    # Selesai loop
    if success_count == total_files:
        logger.info(f"✅ Profile + {success_count} Code Block(s) sent successfully for {persona_type}!")
        return True
    else:
        # Gunakan teks biasa untuk warning
        logger.warning(f"[!] Profile sent for {persona_type}, but only {success_count}/{total_files} file(s) were sent successfully as text.")
        return False # Anggap gagal jika tidak semua file terkirim
