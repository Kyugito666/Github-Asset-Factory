import requests
import os
import time
import logging
from typing import Optional, List, Dict # Tambah Dict

# Import PROXY_POOL (Relative)
from ..config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, PROXY_POOL

logger = logging.getLogger(__name__)

# === PERBAIKAN DI FUNGSI INI ===
def format_profile_message(persona_type: str, data: dict) -> str:
    """Formats the persona data according to the new GitHub UI structure."""
    persona_title = persona_type.replace('_', ' ').title()
    message = f"✅ *Aset Persona Dibuat: {persona_title}*\n\n"
    message += "*--- PROFIL DATA ---*\n"

    # Define fields in the desired GitHub order (Username dulu baru Name)
    profile_order = ["username", "name", "bio", "pronouns", "website", "social_links", "company", "location"]

    for key in profile_order:
        value = data.get(key)
        display_key = key.replace('_', ' ').title()

        if value is None or value == "":
            display_value = "_kosong_"
        elif key == "social_links":
            if isinstance(value, dict) and any(value.values()): # Pastikan object & tidak kosong
                social_lines = []
                # Iterasi max 4 link sosial dari object
                link_count = 0
                for platform, link in value.items():
                    if link and link_count < 4: # Hanya tampilkan jika ada link & belum max
                         # Format nama platform (contoh: Dev.to, Stack Overflow)
                         platform_display = platform.replace('_', ' ').title()
                         if platform_display == 'Twitter': platform_display = 'X (Twitter)'
                         if platform_display == 'Dev To': platform_display = 'Dev.to'
                         if platform_display == 'Stackoverflow': platform_display = 'Stack Overflow'
                         social_lines.append(f"  • *{platform_display}:* `{link}`")
                         link_count += 1
                if social_lines:
                     message += f"*{display_key}:*\n" + "\n".join(social_lines) + "\n"
                else: # Jika object ada tapi isinya null semua
                     message += f"*{display_key}:* _kosong_\n"
                continue # Lanjut ke field berikutnya setelah handle social_links
            else: # Jika social_links bukan dict atau kosong
                 display_value = "_kosong_"
        elif isinstance(value, str):
            display_value = f"`{value}`"
        else: # Handle tipe data lain jika perlu (jarang terjadi di sini)
            display_value = f"`{str(value)}`"

        # Tambahkan baris ke pesan (kecuali social_links yg sudah ditangani)
        if key != "social_links":
             message += f"*{display_key}:* {display_value}\n"

    # --- Bagian Activity & Repo (Tidak Berubah) ---
    activity_list: Optional[List[str]] = data.get('activity_list')
    if activity_list:
        message += "\n*--- SARAN AKTIVITAS ---*\n"
        for i, activity in enumerate(activity_list, 1): message += f"*{i}.* {activity}\n"

    repo_name = data.get('repo_name')
    if repo_name:
        if activity_list: message += "\n" # Add newline if activities exist
        message += f"\n*--- REPO TARGET ---*\n" # Tambah newline pemisah
        message += f"📁 `{repo_name}`\n"
        repo_description = data.get('repo_description')
        if repo_description:
             message += f"📝 `{repo_description}`\n"

    return message
# === AKHIR FUNGSI format_profile_message ===


def format_code_message(file_name: str, file_content: str, max_length: int = 3500) -> str:
    ext_to_lang = {'.py':'python','.js':'javascript','.sh':'bash','.go':'go','.rs':'rust','.rb':'ruby','.php':'php','.java':'java','.cpp':'cpp','.c':'c','.ts':'typescript','.yml':'yaml','.yaml':'yaml','.json':'json','.md':'markdown','.txt':'text','.conf':'nginx','.Dockerfile':'dockerfile','.tf':'terraform','.ipynb':'json'}
    ext = os.path.splitext(file_name)[1]; lang = ext_to_lang.get(ext, 'text')
    content = file_content
    if len(content) > max_length: content = content[:max_length] + "\n\n... (truncated)"
    
    # === PERUBAHAN DI SINI ===
    # Bungkus file_name dengan backtick (`) agar bisa di-copy
    message = f"📄 *File:* `{file_name}`\n\n```{lang}\n{content}\n```"
    # === AKHIR PERUBAHAN ===
    
    return message


def send_text_message(message: str, chat_id: str = None) -> bool:
    """Kirim text message ke Telegram (DENGAN PROXY)"""
    target_chat_id = chat_id or TELEGRAM_CHAT_ID
    if not target_chat_id or not TELEGRAM_BOT_TOKEN:
        logger.error("Telegram token or chat ID is missing.")
        return False
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {'chat_id': target_chat_id, 'text': message, 'parse_mode': 'Markdown', 'disable_web_page_preview': True}
    max_retries = 3

    for attempt in range(1, max_retries + 1):
        proxies, proxy_url_display = None, "None"
        if PROXY_POOL:
            proxy_url = PROXY_POOL.get_next_proxy()
            if proxy_url:
                proxies = {"http": proxy_url, "https": proxy_url}
                proxy_url_display = proxy_url.split('@')[-1] # Hanya host:port untuk log

        # Log sebelum request
        # logger.debug(f"Attempt {attempt}: Sending text to {target_chat_id} via proxy: {proxy_url_display}")

        try:
            response = requests.post(url, json=payload, timeout=20, proxies=proxies) # Timeout naikkan sedikit
            response.raise_for_status()
            logger.info(f"Text message sent to {target_chat_id} (Proxy: {proxy_url_display})")
            return True
        except requests.exceptions.HTTPError as e:
            logger.error(f"HTTP Error sending text (Attempt {attempt}, Proxy: {proxy_url_display}): {e.response.status_code} - {e.response.text[:200]}")
            # Handle specific errors
            if e.response.status_code == 400 and 'parse' in e.response.text.lower():
                logger.warning("Markdown parse error, retrying without Markdown...")
                payload['parse_mode'] = None # Coba lagi tanpa markdown
                continue # Langsung ke attempt berikutnya
            elif e.response.status_code == 429: # Rate limit
                 logger.warning(f"Rate limited by Telegram. Waiting before retry...")
                 time.sleep(5 * attempt) # Tunggu lebih lama
                 continue
            # Jika error lain atau bukan parse error, tandai proxy gagal (jika pakai)
            if PROXY_POOL and proxies:
                 PROXY_POOL.mark_failed(proxy_url)
            # Jangan langsung break, biarkan loop coba lagi (mungkin network error sementara)

        except requests.exceptions.RequestException as e: # Tangkap error koneksi/timeout
            logger.error(f"Network Error sending text (Attempt {attempt}, Proxy: {proxy_url_display}): {e}")
            if PROXY_POOL and proxies:
                PROXY_POOL.mark_failed(proxy_url)
            # Jangan break, biarkan loop coba lagi

        except Exception as e: # Tangkap error tak terduga
            logger.error(f"Unexpected Error sending text (Attempt {attempt}, Proxy: {proxy_url_display}): {e}", exc_info=False)
            if PROXY_POOL and proxies:
                PROXY_POOL.mark_failed(proxy_url)
            # Jangan break

        # Jeda sebelum retry berikutnya
        if attempt < max_retries:
             wait_time = 2 * attempt
             logger.info(f"Waiting {wait_time}s before retry...")
             time.sleep(wait_time)

    logger.error(f"Failed to send text message to {target_chat_id} after {max_retries} attempts.")
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
    total_files = len(files_to_send)
    for i, file_data in enumerate(files_to_send):
        file_name = file_data.get('file_name'); file_content = file_data.get('file_content')
        if not file_name or file_content is None:
            logger.warning(f"Skipping file {i+1}/{total_files} due to missing name or content."); continue

        logger.info(f"📝 Sending file {i+1}/{total_files} as code block: {file_name}")
        # Jeda antar pesan file (bukan sebelum file pertama)
        if i > 0:
             time.sleep(1.5) # Jeda tetap 1.5 detik

        code_message = format_code_message(file_name, file_content)
        if send_text_message(code_message, chat_id=target_chat_id):
            success_count += 1
        else:
            logger.error(f"❌ Failed to send code block for: {file_name}")
            # Pertimbangkan: Mau lanjut kirim file lain atau stop?
            # Untuk sekarang, kita lanjut aja.

    if success_count == total_files:
        logger.info(f"✅ Profile + {success_count} Code Block(s) sent successfully!")
        return True
    else:
        logger.warning(f"[!] Profile sent, but only {success_count}/{total_files} file(s) were sent successfully.")
        return False # Anggap gagal jika tidak semua file terkirim
