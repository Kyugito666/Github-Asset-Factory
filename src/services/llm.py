import litellm
import json
import logging
import random
import time
import os
from typing import Optional, Dict, List, Tuple

# Import exception yang relevan
from litellm import Timeout, APIConnectionError, AuthenticationError, BadRequestError, RateLimitError, NotFoundError
from litellm.types.router import RouterRateLimitError # Jika masih pakai router, tapi kita tidak

# --- Load Prompts (Tidak berubah) ---
logger = logging.getLogger(__name__)
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROMPTS_DIR = os.path.join(os.path.dirname(SCRIPT_DIR), "prompts")

try:
    with open(os.path.join(PROMPTS_DIR, "persona.json"), 'r', encoding='utf-8') as f:
        BASE_PERSONA_PROMPT = json.load(f)["base_prompt"]
except Exception as e:
    logger.critical(f"Failed to load persona.json: {e}")
    BASE_PERSONA_PROMPT = ""

try:
    with open(os.path.join(PROMPTS_DIR, "assets.json"), 'r', encoding='utf-8') as f:
        ASSET_PROMPTS = json.load(f)
except Exception as e:
    logger.critical(f"Failed to load assets.json: {e}")
    ASSET_PROMPTS = {}
# ------------------------------------


# --- Relative Imports (Tidak berubah) ---
from ..config import (
    GEMINI_API_KEYS, GROQ_API_KEYS, COHERE_API_KEYS, REPLICATE_API_KEYS,
    HF_API_TOKENS, OPENROUTER_API_KEYS, MISTRAL_API_KEYS,
    PROXY_POOL
)
from ..modules.persona import load_used_data, add_to_history, load_history_data
# ------------------------------------

# litellm.set_verbose = True # Aktifkan jika perlu detail error litellm

# ============================================================
# MANUAL FALLBACK SETUP (Tidak berubah)
# ============================================================

llm_call_options: List[Dict] = []

def get_proxy_for_provider(provider_prefix: str) -> Optional[str]:
    if not PROXY_POOL: return None
    proxy_url = PROXY_POOL.get_next_proxy()
    if not proxy_url: return None
    if provider_prefix in ["gemini", "cohere", "groq", "huggingface", "mistral"]:
        return f"{provider_prefix}:{proxy_url}"
    else:
        return proxy_url

def add_call_options(keys: list, provider: str, model_configs: List[Dict]):
    if not keys: return
    provider_lower = provider.lower()
    for key in keys:
        for model_config in model_configs:
            model_id = model_config["litellm_id"]
            call_params = {
                "model": model_id,
                "api_key": key,
                "max_tokens": model_config.get("max_tokens"),
                "proxy": get_proxy_for_provider(provider_lower)
            }
            if "custom_llm_provider" in model_config:
                call_params["custom_llm_provider"] = model_config["custom_llm_provider"]

            call_params = {k: v for k, v in call_params.items() if v is not None}

            llm_call_options.append({
                "provider": provider,
                "params": call_params
            })

API_KEY_MAP = {
    "gemini": (GEMINI_API_KEYS, "Gemini"),
    "cohere": (COHERE_API_KEYS, "Cohere"),
    "mistral": (MISTRAL_API_KEYS, "Mistral"),
    "openrouter": (OPENROUTER_API_KEYS, "OpenRouter"),
    "huggingface": (HF_API_TOKENS, "HuggingFace"),
    "replicate": (REPLICATE_API_KEYS, "Replicate"),
    "groq": (GROQ_API_KEYS, "Groq")
}

models_json_path = os.path.join(SCRIPT_DIR, "models.json")
try:
    with open(models_json_path, 'r', encoding='utf-8') as f:
        model_definitions = json.load(f)
    logger.info(f"Successfully loaded model definitions from {models_json_path}")

    for provider_key, models_list in model_definitions.items():
        if provider_key in API_KEY_MAP:
            api_keys, display_name = API_KEY_MAP[provider_key]
            if api_keys:
                add_call_options(api_keys, display_name, models_list)
            else:
                logger.warning(f"No API keys found in config for '{provider_key}', skipping models.")
        else:
            logger.warning(f"Provider '{provider_key}' in models.json has no mapping in API_KEY_MAP. Skipping.")

    if llm_call_options:
        random.shuffle(llm_call_options)
        logger.info(f"✅ Initialized {len(llm_call_options)} LLM call options with manual fallback.")
    else:
         logger.critical("❌ No valid LLM call options could be generated. Check keys and models.json.")

except FileNotFoundError:
    logger.critical(f"FATAL: {models_json_path} not found. Cannot initialize models.")
except json.JSONDecodeError:
    logger.critical(f"FATAL: Failed to decode {models_json_path}. Check for JSON syntax errors.")
except Exception as e:
    logger.critical(f"FATAL: Error loading models or keys: {e}")

# ============================================================
# UTILITY FUNCTIONS (DIPERBAIKI)
# ============================================================

# === PERBAIKAN DI FUNGSI INI ===
def clean_ai_response(raw_text: str) -> str:
    """Cleans AI response: removes markdown code fences and extracts JSON block."""
    text = raw_text.strip()
    cleaned_text = text # Mulai dengan teks asli

    # Step 1: Remove markdown fences if they exist
    if text.startswith("```") and text.endswith("```"):
        lines = text.split('\n')
        if len(lines) > 1:
            # Hapus baris pertama (e.g., ```json) dan baris terakhir (```)
            cleaned_text = '\n'.join(lines[1:-1]).strip()
        else:
            # Handle kasus satu baris seperti ```json { ... } ```
            try:
                # Cari spasi pertama setelah ``` dan ``` terakhir
                first_space_index = text.index(' ')
                last_backticks_index = text.rindex('```')
                # Ekstrak konten di antaranya
                if first_space_index < last_backticks_index:
                    cleaned_text = text[first_space_index + 1:last_backticks_index].strip()
                else: # Jika format aneh, coba hapus ``` awal & akhir saja
                    cleaned_text = text[3:-3].strip()
            except ValueError: # Jika ' ' atau '```' tidak ditemukan
                 cleaned_text = text[3:-3].strip() # Fallback hapus ``` awal & akhir
    
    # Step 2: Find the outermost JSON object/array dari cleaned_text
    first_brace = cleaned_text.find('{')
    first_bracket = cleaned_text.find('[')
    last_brace = cleaned_text.rfind('}')
    last_bracket = cleaned_text.rfind(']')

    start = -1
    end = -1

    # Cek apakah object {...} valid terdeteksi
    if first_brace != -1 and last_brace != -1 and first_brace < last_brace:
        start = first_brace
        end = last_brace
    # Jika tidak ada object, cek apakah array [...] valid terdeteksi
    elif first_bracket != -1 and last_bracket != -1 and first_bracket < last_bracket:
         start = first_bracket
         end = last_bracket

    # Jika start dan end valid ditemukan, ekstrak bagian itu
    if start != -1 and end != -1:
        return cleaned_text[start:end+1]
    else:
        # Jika tidak ada struktur JSON yang jelas, kembalikan teks yang sudah dibersihkan
        # Ini mungkin masih gagal parsing JSON nanti, tapi fungsi ini sudah berusaha
        logger.warning("Could not clearly identify JSON structure in cleaned AI response.")
        return cleaned_text
# === AKHIR PERBAIKAN ===


def ai_decide_send_method(persona_type: str, has_files: bool) -> str: return 'text' if has_files else 'none'

# ============================================================
# CORE AI CALLER (MANUAL FALLBACK) (Tidak berubah)
# ============================================================
def call_llm(prompt: str) -> Optional[str]:
    """Panggil AI menggunakan fallback manual."""
    if not llm_call_options:
        logger.error("LLM call options not initialized."); return None

    for i, option in enumerate(llm_call_options):
        provider = option["provider"]
        params = option["params"].copy()
        model_id = params.get("model", "N/A")

        logger.info(f"Attempt {i+1}/{len(llm_call_options)}: Trying {provider} - {model_id}")

        try:
            response = litellm.completion(
                **params,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.8,
                timeout=120
            )

            result = response.choices[0].message.content
            logger.info(f"✅ Success with {provider} - {model_id}")
            if result:
                return result
            else:
                logger.warning(f"⚠️ {provider} - {model_id} returned an empty response. Trying next...")
                continue

        except (AuthenticationError, BadRequestError, RateLimitError, NotFoundError, APIConnectionError, Timeout) as e:
            logger.warning(f"❌ Failed with {provider} - {model_id}: {type(e).__name__} - {str(e)[:150]}. Trying next...")
            continue
        except Exception as e:
            logger.error(f"❌ Unexpected error with {provider} - {model_id}: {type(e).__name__} - {str(e)[:150]}. Trying next...", exc_info=False)
            continue

    logger.error("❌ All LLM call options failed.")
    return None

# ============================================================
# MAIN GENERATION (DIPERBAIKI sedikit di error handling JSON)
# ============================================================
def generate_persona_data(persona_type: str) -> Optional[Dict]:
    logger.info(f"🔄 AI Chaining: '{persona_type}'")
    used_usernames, used_names = load_used_data()
    logger.info("📝 Step 1: Base Persona (with duplicate check)")
    base_prompt = BASE_PERSONA_PROMPT.format(persona_type=persona_type)
    base_data = None
    MAX_DUPLICATE_RETRIES = 3
    duplicate_retry_count = 0

    while duplicate_retry_count <= MAX_DUPLICATE_RETRIES:
        if duplicate_retry_count > 0:
             logger.info(f"Retrying Step 1 generation due to duplicate (Attempt {duplicate_retry_count})")
             # Buat prompt baru dengan instruksi anti-duplikat
             recent_history = load_history_data()[-10:]
             forbidden_names = {h.get('name') for h in recent_history if h.get('name')}
             forbidden_usernames = {h.get('username') for h in recent_history if h.get('username')}
             retry_instruction = f"\n\nCRITICAL: DO NOT use the name '{name}' or the username '{username}' again. Also AVOID these recent names/usernames:\n" # name & username dari iterasi sebelumnya
             if forbidden_names: retry_instruction += f"- Forbidden Names: {', '.join(forbidden_names)}\n"
             if forbidden_usernames: retry_instruction += f"- Forbidden Usernames: {', '.join(forbidden_usernames)}\n"
             retry_instruction += "Generate a COMPLETELY NEW and UNIQUE name and username."
             current_prompt = BASE_PERSONA_PROMPT.format(persona_type=persona_type) + retry_instruction
        else:
             current_prompt = base_prompt

        raw_1 = call_llm(current_prompt)
        if not raw_1:
            logger.error(f"❌ Step 1 failed (Manual fallback exhausted on attempt {duplicate_retry_count})")
            return None # Gagal total jika LLM call gagal

        try:
            # Coba parse JSON SETELAH memanggil clean_ai_response
            cleaned_response = clean_ai_response(raw_1)
            if not cleaned_response: # Jika cleaning menghasilkan string kosong
                 logger.error(f"❌ Step 1 clean_ai_response resulted in empty string. Raw: {raw_1[:100]}...")
                 duplicate_retry_count +=1 # Anggap ini sbg kegagalan & coba lagi
                 continue

            data = json.loads(cleaned_response)
            username = data.get('username')
            name = data.get('name')

            if not username or not name:
                logger.warning(f"AI returned no username/name. Retrying... ({duplicate_retry_count+1}/{MAX_DUPLICATE_RETRIES})")
                duplicate_retry_count += 1
                continue # Coba generate lagi

            # Cek duplikat
            duplicate_reason = None
            if username in used_usernames: duplicate_reason = f"username '{username}'"
            elif name in used_names: duplicate_reason = f"name '{name}'"

            if duplicate_reason:
                logger.warning(f"DUPLICATE {duplicate_reason} found.")
                duplicate_retry_count += 1
                if duplicate_retry_count > MAX_DUPLICATE_RETRIES:
                    logger.error(f"❌ Step 1 FAILED after {MAX_DUPLICATE_RETRIES} retries (duplicates persisted).")
                    return None
                # Loop akan lanjut ke iterasi berikutnya
            else:
                base_data = data # Sukses, tidak duplikat
                break # Keluar dari while loop

        except json.JSONDecodeError as e:
            logger.error(f"❌ Step 1 JSON parse error: {e}. Cleaned: {cleaned_response[:100]}... Raw: {raw_1[:100]}...")
            # Mungkin coba lagi? Atau gagal? Untuk sekarang, anggap gagal.
            return None
        except Exception as e: # Tangkap error lain saat parsing/checking
             logger.error(f"❌ Unexpected error in Step 1 processing: {e}. Raw: {raw_1[:100]}...")
             return None

    # Jika loop selesai tanpa break (artinya base_data masih None setelah retry)
    if not base_data:
         logger.error("❌ Step 1 failed after retries.") # Seharusnya sudah ditangani di dalam loop
         return None

    # ---- Lanjut ke Step 2 jika Step 1 sukses ----
    add_to_history(base_data.get('username'), base_data.get('name'))
    logger.info(f"✅ Seed (Unique): {base_data.get('name')} (@{base_data.get('username')})")

    asset_template = ASSET_PROMPTS.get(persona_type)
    if not asset_template:
        logger.info(f"ℹ️ No asset needed for '{persona_type}'")
        base_data.update({"repo_name": None, "repo_description": None, "files": None, "send_method": "none"})
        return base_data

    logger.info("📄 Step 2: Asset Generation (including README)")
    asset_prompt = asset_template.format(base_persona_json=json.dumps(base_data, indent=2), username_dari_konteks=base_data.get('username'))
    raw_2 = call_llm(asset_prompt)
    if not raw_2:
        logger.error("❌ Step 2 failed (Manual fallback exhausted)")
        return None # Gagal total jika Step 2 gagal

    try:
        cleaned_response_2 = clean_ai_response(raw_2)
        if not cleaned_response_2:
             logger.error(f"❌ Step 2 clean_ai_response resulted in empty string. Raw: {raw_2[:100]}...")
             return None
        asset_data = json.loads(cleaned_response_2)

        is_profile_readme = persona_type in ["profile_architect", "ui_ux_designer", "technical_writer_dev", "minimalist_dev", "data_viz_enthusiast", "open_source_advocate"]
        if "repo_name" not in asset_data and not is_profile_readme : logger.error(f"❌ Step 2 JSON invalid: 'repo_name' missing. Cleaned: {cleaned_response_2[:100]}..."); return None
        if "files" not in asset_data or not isinstance(asset_data.get("files"), list): logger.error(f"❌ Step 2 JSON invalid: 'files' array missing. Cleaned: {cleaned_response_2[:100]}..."); return None
        if "repo_description" in asset_data and not isinstance(asset_data.get("repo_description"), (str, type(None))): logger.warning(f"⚠️ Step 2 JSON unusual: 'repo_description' not str/null. Cleaned: {cleaned_response_2[:100]}...")
        for file_item in asset_data.get("files", []):
            if "file_name" not in file_item or "file_content" not in file_item: logger.error(f"❌ Step 2 JSON invalid: item in 'files' missing keys. Cleaned: {cleaned_response_2[:100]}..."); return None
        logger.info(f"✅ Assets generated for repo '{asset_data.get('repo_name', base_data.get('username'))}'.")

    except json.JSONDecodeError as e:
         logger.error(f"❌ Step 2 JSON parse error: {e}. Cleaned: {cleaned_response_2[:100]}... Raw: {raw_2[:100]}...")
         return None
    except Exception as e:
         logger.error(f"❌ Unexpected error in Step 2 processing: {e}. Raw: {raw_2[:100]}...")
         return None

    final_data = base_data.copy(); final_data.update(asset_data)
    has_files = bool(final_data.get('files'))
    final_data['send_method'] = ai_decide_send_method(persona_type, has_files)
    logger.info(f"✅ Complete: '{persona_type}' (Method: {final_data['send_method']})")
    return final_data
