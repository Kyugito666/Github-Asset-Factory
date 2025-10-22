import litellm
import json
import logging
import random
import time
from typing import Optional, Dict, List

# Tambahkan import exceptions
from litellm import exceptions as litellm_exceptions

from ..prompts.prompts import BASE_PERSONA_PROMPT, ASSET_PROMPTS
from ..config import (
    GEMINI_API_KEYS, GROQ_API_KEYS, COHERE_API_KEYS, REPLICATE_API_KEYS,
    HF_API_TOKENS, OPENROUTER_API_KEYS, MISTRAL_API_KEYS, FIREWORKS_API_KEYS,
    PROXY_POOL
)
from ..modules.persona_history import load_used_data, add_to_history, load_history_data

logger = logging.getLogger(__name__)
# litellm.set_verbose = True # Uncomment for debugging LiteLLM calls

# ============================================================
# LITELMM ROUTER SETUP
# ============================================================
model_list = []
def get_proxy_for_provider(provider_prefix: str) -> Optional[str]:
    # ... (fungsi ini sama seperti sebelumnya) ...
    if not PROXY_POOL: return None
    proxy_url = PROXY_POOL.get_next_proxy();
    if not proxy_url: return None
    if provider_prefix in ["gemini", "cohere", "groq", "huggingface", "mistral"]: return f"{provider_prefix}:{proxy_url}"
    elif provider_prefix in ["openrouter", "replicate", "fireworks"]: return proxy_url
    else: return proxy_url

def add_models_to_router(keys: list, provider: str, model_configs: List[Dict]):
    # ... (fungsi ini sama seperti sebelumnya) ...
    if not keys: return
    provider_lower = provider.lower()
    for key_index, key in enumerate(keys):
        for model_config in model_configs:
            unique_model_name = f"{provider_lower}-{model_config['suffix']}_{key_index}"
            litellm_params = {"model": model_config["litellm_id"], "api_key": key}
            if "max_tokens" in model_config: litellm_params["max_tokens"] = model_config["max_tokens"]
            litellm_params["proxy"] = get_proxy_for_provider(provider_lower)
            model_list.append({
                "model_name": unique_model_name,
                "litellm_params": litellm_params,
                "model_info": {"provider": provider}
            })

# --- Define Models for Each Provider (PERIKSA LAGI ID MODEL INI!) ---

# Gemini
gemini_models = [
    # Pastikan ID ini valid di LiteLLM/Google AI
    {"suffix": "2.5-flash", "litellm_id": "gemini/gemini-2.5-flash", "max_tokens": 8192},
]
add_models_to_router(GEMINI_API_KEYS, "Gemini", gemini_models)

# Cohere
cohere_models = [
    # Pastikan ID ini valid
    {"suffix": "command-r-plus", "litellm_id": "cohere/command-r-plus", "max_tokens": 4096},
]
add_models_to_router(COHERE_API_KEYS, "Cohere", cohere_models)

# Mistral AI
mistral_models = [
    # Pastikan ID ini valid
    {"suffix": "large-latest", "litellm_id": "mistral/mistral-large-latest", "max_tokens": 8000},
    {"suffix": "codestral-latest", "litellm_id": "mistral/codestral-latest", "max_tokens": 8000},
]
add_models_to_router(MISTRAL_API_KEYS, "Mistral", mistral_models)

# Fireworks AI
fireworks_models = [
    # Pastikan ID ini valid di Fireworks/LiteLLM
    {"suffix": "mixtral-8x7b", "litellm_id": "fireworks/accounts/fireworks/models/mixtral-8x7b-instruct", "max_tokens": 32768},
    {"suffix": "llama-v3-70b", "litellm_id": "fireworks/accounts/fireworks/models/llama-v3-70b-instruct", "max_tokens": 8192},
]
add_models_to_router(FIREWORKS_API_KEYS, "Fireworks", fireworks_models)

# OpenRouter
openrouter_models = [
    # Pastikan ID ini valid di OpenRouter/LiteLLM
    {"suffix": "llama-3.3-8b-free", "litellm_id": "openrouter/meta-llama/llama-3.3-8b-instruct:free", "max_tokens": 8000},
    {"suffix": "gemma-3n-e4b-free", "litellm_id": "openrouter/google/gemma-3n-e4b-it:free", "max_tokens": 8000},
    # Tambahkan model berbayar jika perlu & API key support
    # {"suffix": "claude-3-haiku", "litellm_id": "openrouter/anthropic/claude-3-haiku", "max_tokens": 4096},
]
add_models_to_router(OPENROUTER_API_KEYS, "OpenRouter", openrouter_models)

# Hugging Face
hf_models = [
    # Pastikan ID ini valid dan modelnya support Inference API
    # {"suffix": "mistral-7b", "litellm_id": "huggingface/mistralai/Mistral-7B-Instruct-v0.1", "max_tokens": 4096},
    {"suffix": "gpt-oss-20b-hf", "litellm_id": "huggingface/openai/gpt-oss-20b", "max_tokens": 4096}, # Cek ketersediaan
]
add_models_to_router(HF_API_TOKENS, "HuggingFace", hf_models)

# Replicate (BUTUH HASH!)
replicate_models = [
    # Ganti <hash> dengan hash asli dari Replicate! Kalau tidak, baris ini akan di-skip.
    {"suffix": "llama-3-70b", "litellm_id": "replicate/meta/meta-llama-3-70b-instruct:<hash_untuk_llama3_70b>", "max_tokens": 8000},
]
valid_replicate_models = []
for m in replicate_models:
    if "<hash" not in m["litellm_id"]: valid_replicate_models.append(m)
    else: logger.warning(f"Replicate model {m['suffix']} skipped: Hash placeholder found in '{m['litellm_id']}'. Please update llm_service.py.")
add_models_to_router(REPLICATE_API_KEYS, "Replicate", valid_replicate_models)

# Groq (Jika keys valid lagi)
groq_models = [
    {"suffix": "llama-3.1-8b", "litellm_id": "groq/llama-3.1-8b-instant", "max_tokens": 8000},
]
add_models_to_router(GROQ_API_KEYS, "Groq", groq_models)


# 2. Inisialisasi Router
if model_list:
    router = litellm.Router(model_list=model_list, routing_strategy="latency", set_verbose=False, num_retries=1, allowed_fails=10)
    logger.info(f"✅ LiteLLM Router initialized with {len(model_list)} model deployments and 'latency' strategy.")
    registered_models_short = list(dict.fromkeys([m["litellm_params"]["model"] for m in model_list]))
    logger.info(f"Registered model IDs (across all keys): {', '.join(registered_models_short)}")
else:
    router = None
    logger.critical("❌ No valid API keys/models defined OR issue loading keys. LiteLLM Router cannot be initialized.")

# ============================================================
# UTILITY FUNCTIONS (Tidak berubah)
# ============================================================
def clean_ai_response(raw_text: str) -> str: /* ... sama ... */
def ai_decide_send_method(persona_type: str, has_files: bool) -> str: /* ... sama ... */

# ============================================================
# CORE AI CALLER (EXCEPT BLOCK DIPERBAIKI)
# ============================================================
def call_llm(prompt: str) -> Optional[str]:
    """Panggil AI menggunakan LiteLLM Router."""
    if not router: logger.error("LiteLLM Router not initialized."); return None
    try:
        response = router.completion(model="available", messages=[{"role": "user", "content": prompt}], temperature=0.8, timeout=120)
        result = response.choices[0].message.content
        chosen_model_router_name = response.model
        chosen_llm_params = response._hidden_params.get('litellm_params', {})
        original_model_id = chosen_llm_params.get('model', chosen_model_router_name)
        provider = chosen_llm_params.get('model_info', {}).get('provider', 'Unknown')
        logger.info(f"✅ Router chose '{chosen_model_router_name}' (Model: {original_model_id}, Provider: {provider})")
        if result: return result
        else: logger.warning(f"AI Router ({provider}) returned an empty response."); return None
    except litellm_exceptions.Timeout as e: logger.error(f"AI Router call timed out: {e}"); return None # Pakai litellm_exceptions
    except litellm_exceptions.APIConnectionError as e: logger.error(f"AI Router connection error: {e}"); return None # Pakai litellm_exceptions
    # --- EXCEPT BLOCK DIPERBAIKI ---
    except (litellm_exceptions.AuthenticationError, litellm_exceptions.BadRequestError,
            litellm_exceptions.RateLimitError, litellm_exceptions.NotFound) as e:
         # Tangkap error API spesifik DARI litellm.exceptions
         logger.error(f"AI Router API Error: {type(e).__name__} - {str(e)[:200]}")
         return None # Router akan handle fallback
    # -----------------------------
    except Exception as e:
        # Tangkap error umum lainnya
        logger.error(f"AI Router generic error: {type(e).__name__} - {str(e)[:200]}", exc_info=False)
        return None

# ============================================================
# MAIN GENERATION (Tidak berubah)
# ============================================================
def generate_persona_data(persona_type: str) -> Optional[Dict]:
    # ... (Sama persis seperti versi sebelumnya) ...
    logger.info(f"🔄 AI Chaining: '{persona_type}'")
    used_usernames, used_names = load_used_data()
    logger.info("📝 Step 1: Base Persona (with duplicate check)")
    base_prompt = BASE_PERSONA_PROMPT.format(persona_type=persona_type)
    base_data = None; MAX_RETRIES = 5
    for attempt in range(MAX_RETRIES):
        raw_1 = call_llm(base_prompt)
        if not raw_1: logger.error("❌ Step 1 failed (AI call failed or Router exhausted)"); return None
        try:
            data = json.loads(clean_ai_response(raw_1)); username = data.get('username'); name = data.get('name')
            if not username or not name: logger.warning(f"AI returned no username/name. Retrying... ({attempt+1}/{MAX_RETRIES})"); continue
            duplicate_reason = f"username '{username}'" if username in used_usernames else f"name '{name}'" if name in used_names else None
            if duplicate_reason:
                logger.warning(f"DUPLICATE {duplicate_reason} found. Retrying... ({attempt+1}/{MAX_RETRIES})")
                recent_history = load_history_data()[-10:]; forbidden_names = {h.get('name') for h in recent_history if h.get('name')}; forbidden_usernames = {h.get('username') for h in recent_history if h.get('username')}
                retry_instruction = f"\n\nCRITICAL: DO NOT use the name '{name}' or the username '{username}' again. Also AVOID these recent names/usernames:\n"
                if forbidden_names: retry_instruction += f"- Forbidden Names: {', '.join(forbidden_names)}\n"
                if forbidden_usernames: retry_instruction += f"- Forbidden Usernames: {', '.join(forbidden_usernames)}\n"
                retry_instruction += "Generate a COMPLETELY NEW and UNIQUE name and username."
                base_prompt = BASE_PERSONA_PROMPT.format(persona_type=persona_type) + retry_instruction
                continue
            base_data = data; break
        except Exception as e: logger.error(f"❌ Step 1 JSON parse error: {e}. Raw: {raw_1[:100]}..."); return None
    if not base_data: logger.error(f"❌ Step 1 FAILED after {MAX_RETRIES} retries (duplicates persisted)."); return None
    add_to_history(base_data.get('username'), base_data.get('name'))
    logger.info(f"✅ Seed (Unique): {base_data.get('name')} (@{base_data.get('username')})")
    asset_template = ASSET_PROMPTS.get(persona_type)
    if not asset_template: logger.info(f"ℹ️ No asset needed for '{persona_type}'"); base_data.update({"repo_name": None, "repo_description": None, "files": None, "send_method": "none"}); return base_data
    logger.info("📄 Step 2: Asset Generation (including README)")
    asset_prompt = asset_template.format(base_persona_json=json.dumps(base_data, indent=2), username_dari_konteks=base_data.get('username'))
    raw_2 = call_llm(asset_prompt)
    if not raw_2: logger.error("❌ Step 2 failed"); return None
    try:
        asset_data = json.loads(clean_ai_response(raw_2))
        is_profile_readme = persona_type in ["profile_architect", "ui_ux_designer", "technical_writer_dev", "minimalist_dev", "data_viz_enthusiast", "open_source_advocate"]
        if "repo_name" not in asset_data and not is_profile_readme : logger.error(f"❌ Step 2 JSON invalid: 'repo_name' missing. Raw: {raw_2[:100]}..."); return None
        if "files" not in asset_data or not isinstance(asset_data.get("files"), list): logger.error(f"❌ Step 2 JSON invalid: 'files' array missing. Raw: {raw_2[:100]}..."); return None
        if "repo_description" in asset_data and not isinstance(asset_data.get("repo_description"), (str, type(None))): logger.warning(f"⚠️ Step 2 JSON unusual: 'repo_description' not str/null. Raw: {raw_2[:100]}...")
        for file_item in asset_data.get("files", []):
            if "file_name" not in file_item or "file_content" not in file_item: logger.error(f"❌ Step 2 JSON invalid: item in 'files' missing keys. Raw: {raw_2[:100]}..."); return None
        logger.info(f"✅ Assets generated for repo '{asset_data.get('repo_name', base_data.get('username'))}'.")
    except Exception as e: logger.error(f"❌ Step 2 JSON parse error: {e}. Raw: {raw_2[:100]}..."); return None
    final_data = base_data.copy(); final_data.update(asset_data)
    has_files = bool(final_data.get('files'))
    final_data['send_method'] = ai_decide_send_method(persona_type, has_files)
    logger.info(f"✅ Complete: '{persona_type}' (Method: {final_data['send_method']})")
    return final_data
