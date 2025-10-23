import litellm
import json
import logging
import random
import time
import os
from typing import Optional, Dict, List, Tuple

# Import exception yang relevan
from litellm import Timeout, APIConnectionError, AuthenticationError, BadRequestError, RateLimitError, NotFoundError
# from litellm.types.router import RouterRateLimitError # Tidak dipakai lagi

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
    PROXY_POOL, reload_proxy_pool
)
from ..modules.persona import load_used_data, add_to_history, load_history_data
# ------------------------------------

# litellm.set_verbose = True # Aktifkan jika perlu detail error litellm

# ============================================================
# MANUAL FALLBACK SETUP (Tidak berubah)
# ============================================================

llm_call_options: List[Dict] = []

def get_proxy_for_provider(provider_prefix: str) -> Optional[str]:
    """Return proxy string based on provider, skip if incompatible."""
    if not PROXY_POOL: return None
    incompatible_providers = ["groq", "huggingface"]
    if provider_prefix in incompatible_providers:
        logger.warning(f"Skipping proxy for incompatible provider: {provider_prefix}")
        return None
    proxy_url = PROXY_POOL.get_next_proxy()
    if not proxy_url: return None
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
            llm_call_options.append({"provider": provider, "params": call_params})

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
            if api_keys: add_call_options(api_keys, display_name, models_list)
            else: logger.warning(f"No API keys for '{provider_key}', skipping.")
        else: logger.warning(f"Provider '{provider_key}' in models.json unknown. Skipping.")
    if llm_call_options:
        # Tidak perlu shuffle di sini, kita shuffle di call_llm
        # random.shuffle(llm_call_options)
        logger.info(f"✅ Initialized {len(llm_call_options)} LLM call options.")
    else: logger.critical("❌ No valid LLM call options generated.")
except Exception as e: logger.critical(f"FATAL: Error loading models/keys: {e}")

# ============================================================
# UTILITY FUNCTIONS (Tidak berubah)
# ============================================================
def clean_ai_response(raw_text: str) -> str:
    # ... (kode clean_ai_response tidak berubah) ...
    text = raw_text.strip(); cleaned_text = text
    if text.startswith("```") and text.endswith("```"):
        lines = text.split('\n')
        if len(lines) > 1: cleaned_text = '\n'.join(lines[1:-1]).strip()
        else:
            try: first_space=text.index(' '); last_ticks=text.rindex('```'); cleaned_text = text[first_space + 1:last_ticks].strip() if first_space < last_ticks else text[3:-3].strip()
            except ValueError: cleaned_text = text[3:-3].strip()
    first_b = cleaned_text.find('{'); first_s = cleaned_text.find('['); last_b = cleaned_text.rfind('}'); last_s = cleaned_text.rfind(']')
    start, end = -1, -1
    if first_b != -1 and last_b != -1 and first_b < last_b: start, end = first_b, last_b
    elif first_s != -1 and last_s != -1 and first_s < last_s: start, end = first_s, last_s
    if start != -1: return cleaned_text[start:end+1]
    logger.warning("Could not identify JSON structure."); return cleaned_text

def ai_decide_send_method(persona_type: str, has_files: bool) -> str: return 'text' if has_files else 'none'

# ============================================================
# CORE AI CALLER (MANUAL FALLBACK - DIPERBAIKI)
# ============================================================
def call_llm(prompt: str) -> Optional[str]:
    """Panggil AI menggunakan fallback manual LANGSUNG."""
    if not llm_call_options:
        logger.error("LLM call options not initialized."); return None

    # Acak urutan opsi SETIAP KALI dipanggil
    current_options = random.sample(llm_call_options, len(llm_call_options))

    for i, option in enumerate(current_options):
        provider = option["provider"]
        params = option["params"].copy() # AMBIL SEMUA PARAMS (model, api_key, proxy, max_tokens)
        model_id = params.get("model", "N/A")
        proxy_used = params.get("proxy")

        # Hapus proxy param jika None
        if proxy_used is None:
            if "proxy" in params: del params["proxy"]

        logger.info(f"Attempt {i+1}/{len(current_options)}: Trying {provider} - {model_id} (Proxy: {proxy_used.split('@')[-1] if proxy_used else 'None'})")

        try:
            # === PERBAIKAN DI SINI ===
            # LANGSUNG panggil litellm.completion dengan params spesifik
            response = litellm.completion(
                **params, # Ini unpack model, api_key, proxy (jika ada), max_tokens
                messages=[{"role": "user", "content": prompt}],
                temperature=0.8,
                timeout=120 # Timeout per attempt
            )
            # === AKHIR PERBAIKAN ===

            result = response.choices[0].message.content
            logger.info(f"✅ Success with {provider} - {model_id}")
            if result: return result
            else: logger.warning(f"⚠️ Empty response. Trying next..."); continue

        except (APIConnectionError, Timeout) as e:
            logger.warning(f"❌ Connection/Timeout with {provider} - {model_id}: {type(e).__name__}. Trying next...")
            if PROXY_POOL and proxy_used: PROXY_POOL.mark_failed(proxy_used)
            continue
        except (AuthenticationError, BadRequestError, RateLimitError, NotFoundError) as e:
             # Jangan log rate limit sebagai error, tapi warning
             log_level = logging.WARNING if isinstance(e, RateLimitError) else logging.ERROR
             logger.log(log_level, f"❌ API Error with {provider} - {model_id}: {type(e).__name__} - {str(e)[:150]}. Trying next...")
             continue
        except Exception as e:
            logger.error(f"❌ Unexpected error with {provider} - {model_id}: {type(e).__name__} - {str(e)[:150]}. Trying next...", exc_info=False)
            if PROXY_POOL and proxy_used: PROXY_POOL.mark_failed(proxy_used)
            continue

    logger.error("❌ All LLM call options failed.")
    return None

# ============================================================
# MAIN GENERATION (Tidak berubah)
# ============================================================
def generate_persona_data(persona_type: str) -> Optional[Dict]:
    # ... (kode generate_persona_data tidak berubah) ...
    logger.info(f"🔄 AI Chaining: '{persona_type}'")
    used_usernames, used_names = load_used_data()
    logger.info("📝 Step 1: Base Persona (with duplicate check)")
    base_prompt = BASE_PERSONA_PROMPT.format(persona_type=persona_type)
    base_data = None; MAX_DUPLICATE_RETRIES = 3; duplicate_retry_count = 0
    while duplicate_retry_count <= MAX_DUPLICATE_RETRIES:
        if duplicate_retry_count > 0:
             logger.info(f"Retrying Step 1 generation (Attempt {duplicate_retry_count})")
             recent_history = load_history_data()[-10:]; forbidden_names = {h.get('name') for h in recent_history if h.get('name')}; forbidden_usernames = {h.get('username') for h in recent_history if h.get('username')}
             retry_instruction = f"\n\nCRITICAL: DO NOT use name '{name}' or username '{username}'. AVOID recent: Names={forbidden_names}, Usernames={forbidden_usernames}. Generate COMPLETELY NEW.\n"
             current_prompt = BASE_PERSONA_PROMPT.format(persona_type=persona_type) + retry_instruction
        else: current_prompt = base_prompt
        raw_1 = call_llm(current_prompt)
        if not raw_1: logger.error(f"❌ Step 1 failed (Fallback exhausted)"); return None
        try:
            cleaned_response = clean_ai_response(raw_1)
            if not cleaned_response: logger.error(f"❌ Step 1 clean empty. Raw: {raw_1[:100]}..."); duplicate_retry_count +=1; continue
            data = json.loads(cleaned_response); username = data.get('username'); name = data.get('name')
            if not username or not name: logger.warning(f"AI no user/name. Retrying... ({duplicate_retry_count+1}/{MAX_DUPLICATE_RETRIES})"); duplicate_retry_count += 1; continue
            duplicate_reason = None
            if username in used_usernames: duplicate_reason = f"username '{username}'"
            elif name in used_names: duplicate_reason = f"name '{name}'"
            if duplicate_reason:
                logger.warning(f"DUPLICATE {duplicate_reason} found."); duplicate_retry_count += 1
                if duplicate_retry_count > MAX_DUPLICATE_RETRIES: logger.error(f"❌ Step 1 FAILED (duplicates persisted)."); return None
            else: base_data = data; break
        except json.JSONDecodeError as e: logger.error(f"❌ Step 1 JSON parse error: {e}. Cleaned: {cleaned_response[:100]}..."); return None
        except Exception as e: logger.error(f"❌ Unexpected Step 1 error: {e}. Raw: {raw_1[:100]}..."); return None
    if not base_data: logger.error("❌ Step 1 failed after retries."); return None
    add_to_history(base_data.get('username'), base_data.get('name')); logger.info(f"✅ Seed: {base_data.get('name')} (@{base_data.get('username')})")
    asset_template = ASSET_PROMPTS.get(persona_type)
    if not asset_template: logger.info(f"ℹ️ No asset needed."); base_data.update({"repo_name": None, "repo_description": None, "files": None, "send_method": "none"}); return base_data
    logger.info("📄 Step 2: Asset Generation")
    asset_prompt = asset_template.format(base_persona_json=json.dumps(base_data, indent=2), username_dari_konteks=base_data.get('username'))
    raw_2 = call_llm(asset_prompt)
    if not raw_2: logger.error("❌ Step 2 failed (Fallback exhausted)"); return None
    try:
        cleaned_response_2 = clean_ai_response(raw_2)
        if not cleaned_response_2: logger.error(f"❌ Step 2 clean empty. Raw: {raw_2[:100]}..."); return None
        asset_data = json.loads(cleaned_response_2)
        is_profile_readme = persona_type in ["profile_architect", "ui_ux_designer", "technical_writer_dev", "minimalist_dev", "data_viz_enthusiast", "open_source_advocate"]
        if "repo_name" not in asset_data and not is_profile_readme : logger.error(f"❌ Step 2 JSON invalid: 'repo_name' missing. Cleaned: {cleaned_response_2[:100]}..."); return None
        if "files" not in asset_data or not isinstance(asset_data.get("files"), list): logger.error(f"❌ Step 2 JSON invalid: 'files' array missing. Cleaned: {cleaned_response_2[:100]}..."); return None
        # ... (validasi asset_data lain tidak berubah) ...
        logger.info(f"✅ Assets generated for repo '{asset_data.get('repo_name', base_data.get('username'))}'.")
    except json.JSONDecodeError as e: logger.error(f"❌ Step 2 JSON parse error: {e}. Cleaned: {cleaned_response_2[:100]}..."); return None
    except Exception as e: logger.error(f"❌ Unexpected Step 2 error: {e}. Raw: {raw_2[:100]}..."); return None
    final_data = base_data.copy(); final_data.update(asset_data); has_files = bool(final_data.get('files'))
    final_data['send_method'] = ai_decide_send_method(persona_type, has_files)
    logger.info(f"✅ Complete: '{persona_type}' (Method: {final_data['send_method']})")
    return final_data
