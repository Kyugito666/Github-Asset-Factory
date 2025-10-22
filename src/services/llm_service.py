import litellm
import json
import logging
import random
import time
from typing import Optional, Dict, List

from ..prompts.prompts import BASE_PERSONA_PROMPT, ASSET_PROMPTS # Naik 1 level (..) lalu ke prompts
from ..config import ( # Naik 1 level (..) lalu ke config
    GEMINI_API_KEYS, GROQ_API_KEYS, COHERE_API_KEYS, REPLICATE_API_KEYS,
    HF_API_TOKENS, OPENROUTER_API_KEYS, MISTRAL_API_KEYS, FIREWORKS_API_KEYS,
    PROXY_POOL
)
from ..modules.persona_history import load_used_data, add_to_history, load_history_data # Naik 1 level (..) lalu ke modules

logger = logging.getLogger(__name__)
# litellm.set_verbose = True # Uncomment for debugging LiteLLM calls

# ============================================================
# LITELMM ROUTER SETUP
# ============================================================

# 1. Definisikan Model List untuk Router
model_list = []

# --- Helper Function for Proxy ---
def get_proxy_for_provider(provider_prefix: str) -> Optional[str]:
    if not PROXY_POOL: return None
    proxy_url = PROXY_POOL.get_next_proxy() # Ambil proxy dari pool kita
    if not proxy_url: return None
    # Provider yang biasanya butuh prefix
    if provider_prefix in ["gemini", "cohere", "groq", "huggingface", "mistral"]:
        return f"{provider_prefix}:{proxy_url}"
    # Provider yang mungkin tidak butuh
    elif provider_prefix in ["openrouter", "replicate", "fireworks"]:
        return proxy_url
    else: # Default
        return proxy_url

# --- Helper Function to Add Models ---
def add_models_to_router(keys: list, provider: str, model_configs: List[Dict]):
    """Helper to add multiple models for a provider using their keys."""
    if not keys: return # Skip if no keys for this provider

    provider_lower = provider.lower()

    for key_index, key in enumerate(keys):
        for model_config in model_configs:
            # Create a unique model_name for the router for this specific key and model variant
            unique_model_name = f"{provider_lower}-{model_config['suffix']}_{key_index}"

            litellm_params = {
                "model": model_config["litellm_id"],
                "api_key": key,
                # Add base_url if needed (e.g., for Fireworks, though LiteLLM might handle it)
            }
            # Add optional params if they exist in config
            if "max_tokens" in model_config: litellm_params["max_tokens"] = model_config["max_tokens"]

            # Get proxy (rotate proxy per model deployment for better distribution)
            litellm_params["proxy"] = get_proxy_for_provider(provider_lower)

            model_list.append({
                "model_name": unique_model_name,
                "litellm_params": litellm_params,
                "model_info": {"provider": provider} # Store original provider name
            })

# --- Define Models for Each Provider (SESUAI LIST USER TERAKHIR) ---

# Gemini (Dari list user)
gemini_models = [
    {"suffix": "2.5-pro", "litellm_id": "gemini/gemini-2.5-pro", "max_tokens": 8192},
    {"suffix": "2.5-flash", "litellm_id": "gemini/gemini-2.5-flash", "max_tokens": 8192},
    {"suffix": "2.5-flash-preview", "litellm_id": "gemini/gemini-2.5-flash-preview-09-2025", "max_tokens": 8192}, # Asumsi nama preview
    {"suffix": "2.5-flash-lite", "litellm_id": "gemini/gemini-2.5-flash-lite", "max_tokens": 8192}, # Asumsi nama lite
    {"suffix": "2.5-flash-lite-preview", "litellm_id": "gemini/gemini-2.5-flash-lite-preview-09-2025", "max_tokens": 8192}, # Asumsi
    {"suffix": "2.0-flash", "litellm_id": "gemini/gemini-2.0-flash", "max_tokens": 8192},
    {"suffix": "2.0-flash-lite", "litellm_id": "gemini/gemini-2.0-flash-lite", "max_tokens": 8192}, # Asumsi
]
add_models_to_router(GEMINI_API_KEYS, "Gemini", gemini_models)

# Cohere (Dari list user)
cohere_models = [
    {"suffix": "aya-expanse-32b", "litellm_id": "cohere/c4ai-aya-expanse-32b", "max_tokens": 4096},
    {"suffix": "aya-expanse-8b", "litellm_id": "cohere/c4ai-aya-expanse-8b", "max_tokens": 4096},
    {"suffix": "command-r-08-2024", "litellm_id": "cohere/command-r-08-2024", "max_tokens": 4096}, # Mungkin versi lama
    {"suffix": "command-r-plus-08-2024", "litellm_id": "cohere/command-r-plus-08-2024", "max_tokens": 4096}, # Mungkin versi lama
]
add_models_to_router(COHERE_API_KEYS, "Cohere", cohere_models)

# Mistral AI (Dari list user)
mistral_models = [
    {"suffix": "medium-chat", "litellm_id": "mistral/mistral-medium-latest", "max_tokens": 8000}, # Chat model
    {"suffix": "codestral-code", "litellm_id": "mistral/codestral-latest", "max_tokens": 8000}, # Code model
]
add_models_to_router(MISTRAL_API_KEYS, "Mistral", mistral_models)

# Fireworks AI (Dari list user)
fireworks_models = [
    # Format: fireworks/accounts/fireworks/models/<model-id>
    {"suffix": "deepseek-v3p1-terminus", "litellm_id": "fireworks/accounts/fireworks/models/deepseek-v3p1-terminus", "max_tokens": 8000},
    {"suffix": "kimi-k2-instruct-0905", "litellm_id": "fireworks/accounts/fireworks/models/kimi-k2-instruct-0905", "max_tokens": 8000},
    {"suffix": "deepseek-v3p1", "litellm_id": "fireworks/accounts/fireworks/models/deepseek-v3p1", "max_tokens": 8000},
    {"suffix": "gpt-oss-120b", "litellm_id": "fireworks/accounts/fireworks/models/gpt-oss-120b", "max_tokens": 4096}, # Check limits
    {"suffix": "gpt-oss-20b", "litellm_id": "fireworks/accounts/fireworks/models/gpt-oss-20b", "max_tokens": 4096}, # Check limits
    {"suffix": "glm-4p6", "litellm_id": "fireworks/accounts/fireworks/models/glm-4p6", "max_tokens": 8000},
    {"suffix": "qwen3-235b-thinking", "litellm_id": "fireworks/accounts/fireworks/models/qwen3-235b-a22b-thinking-2507", "max_tokens": 8000}, # Check ID
    {"suffix": "qwen3-coder-480b", "litellm_id": "fireworks/accounts/fireworks/models/qwen3-coder-480b-a35b-instruct", "max_tokens": 8000}, # Check ID
    {"suffix": "qwen3-235b-instruct", "litellm_id": "fireworks/accounts/fireworks/models/qwen3-235b-a22b-instruct-2507", "max_tokens": 8000}, # Check ID
    {"suffix": "kimi-k2-instruct", "litellm_id": "fireworks/accounts/fireworks/models/kimi-k2-instruct", "max_tokens": 8000},
]
add_models_to_router(FIREWORKS_API_KEYS, "Fireworks", fireworks_models)

# OpenRouter (Dari list user, pakai ID langsung)
openrouter_models = [
    {"suffix": "andromeda-alpha", "litellm_id": "openrouter/andromeda-alpha", "max_tokens": 8000},
    {"suffix": "tongyi-deepresearch", "litellm_id": "openrouter/alibaba/tongyi-deepresearch-30b-a3b:free", "max_tokens": 8000},
    {"suffix": "longcat-flash", "litellm_id": "openrouter/meituan/longcat-flash-chat:free", "max_tokens": 8000},
    {"suffix": "nemotron-nano", "litellm_id": "openrouter/nvidia/nemotron-nano-9b-v2:free", "max_tokens": 8000},
    {"suffix": "deepseek-chat-v3", "litellm_id": "openrouter/deepseek/deepseek-chat-v3.1:free", "max_tokens": 8000},
    {"suffix": "gpt-oss-20b-free", "litellm_id": "openrouter/openai/gpt-oss-20b:free", "max_tokens": 4096},
    {"suffix": "glm-4.5-air", "litellm_id": "openrouter/z-ai/glm-4.5-air:free", "max_tokens": 8000},
    {"suffix": "qwen3-coder-free", "litellm_id": "openrouter/qwen/qwen3-coder:free", "max_tokens": 8000},
    {"suffix": "kimi-k2-free", "litellm_id": "openrouter/moonshotai/kimi-k2:free", "max_tokens": 8000},
    {"suffix": "dolphin-mistral-venice", "litellm_id": "openrouter/cognitivecomputations/dolphin-mistral-24b-venice-edition:free", "max_tokens": 8000},
    {"suffix": "gemma-3n-e2b", "litellm_id": "openrouter/google/gemma-3n-e2b-it:free", "max_tokens": 8000},
    {"suffix": "hunyuan-a13b", "litellm_id": "openrouter/tencent/hunyuan-a13b-instruct:free", "max_tokens": 8000},
    {"suffix": "deepseek-chimera", "litellm_id": "openrouter/tngtech/deepseek-r1t2-chimera:free", "max_tokens": 8000},
    {"suffix": "mistral-small-3.2", "litellm_id": "openrouter/mistralai/mistral-small-3.2-24b-instruct:free", "max_tokens": 8000},
    {"suffix": "kimi-dev-72b", "litellm_id": "openrouter/moonshotai/kimi-dev-72b:free", "max_tokens": 8000},
    {"suffix": "deepseek-r1-qwen3", "litellm_id": "openrouter/deepseek/deepseek-r1-0528-qwen3-8b:free", "max_tokens": 8000},
    {"suffix": "deepseek-r1-0528", "litellm_id": "openrouter/deepseek/deepseek-r1-0528:free", "max_tokens": 8000},
    {"suffix": "devstral-small", "litellm_id": "openrouter/mistralai/devstral-small-2505:free", "max_tokens": 8000},
    {"suffix": "gemma-3n-e4b", "litellm_id": "openrouter/google/gemma-3n-e4b-it:free", "max_tokens": 8000},
    {"suffix": "llama-3.3-8b", "litellm_id": "openrouter/meta-llama/llama-3.3-8b-instruct:free", "max_tokens": 8000},
    {"suffix": "qwen3-4b", "litellm_id": "openrouter/qwen/qwen3-4b:free", "max_tokens": 8000},
]
add_models_to_router(OPENROUTER_API_KEYS, "OpenRouter", openrouter_models)

# Hugging Face (Dari list user, format: huggingface/owner/repo)
hf_models = [
    {"suffix": "C2S-Scale-Gemma", "litellm_id": "huggingface/vandijklab/C2S-Scale-Gemma-2-27B", "max_tokens": 4096},
    # {"suffix": "Ling-1T", "litellm_id": "huggingface/inclusionAI/Ling-1T", "max_tokens": 4096}, # Skip?
    {"suffix": "GLM-4.6", "litellm_id": "huggingface/zai-org/GLM-4.6", "max_tokens": 8000},
    # {"suffix": "Arch-Router", "litellm_id": "huggingface/katanemo/Arch-Router-1.5B", "max_tokens": 4096}, # Skip?
    {"suffix": "UserLM-8b", "litellm_id": "huggingface/microsoft/UserLM-8b", "max_tokens": 4096},
    # {"suffix": "Schematron-3B", "litellm_id": "huggingface/inference-net/Schematron-3B", "max_tokens": 4096}, # Skip?
    {"suffix": "gpt-oss-20b-hf", "litellm_id": "huggingface/openai/gpt-oss-20b", "max_tokens": 4096},
    {"suffix": "DeepSeek-V3.2-Exp", "litellm_id": "huggingface/deepseek-ai/DeepSeek-V3.2-Exp", "max_tokens": 8000},
    # {"suffix": "Ring-1T", "litellm_id": "huggingface/inclusionAI/Ring-1T", "max_tokens": 4096}, # Skip?
    {"suffix": "gpt-oss-120b-hf", "litellm_id": "huggingface/openai/gpt-oss-120b", "max_tokens": 4096},
]
add_models_to_router(HF_API_TOKENS, "HuggingFace", hf_models)

# Replicate (Dari list user, format: replicate/owner/model - Coba tanpa hash)
# WARNING: GPT-5, Llama-4, Gemini via Replicate likely won't work. Included as requested.
replicate_models = [
    # {"suffix": "gpt-5", "litellm_id": "replicate/openai/gpt-5", "max_tokens": 8000}, # Fiksi?
    # {"suffix": "o4-mini", "litellm_id": "replicate/openai/o4-mini", "max_tokens": 8000}, # Fiksi?
    {"suffix": "kimi-k2-instruct-rep", "litellm_id": "replicate/moonshotai/kimi-k2-instruct", "max_tokens": 8000},
    # {"suffix": "llama-4-maverick", "litellm_id": "replicate/meta/llama-4-maverick-instruct", "max_tokens": 8000}, # Fiksi?
    {"suffix": "granite-3.3-8b", "litellm_id": "replicate/ibm-granite/granite-3.3-8b-instruct", "max_tokens": 4096},
    # {"suffix": "deepseek-v3", "litellm_id": "replicate/deepseek-ai/deepseek-v3", "max_tokens": 8000}, # Kurang spesifik
    {"suffix": "qwen3-235b-instruct-rep", "litellm_id": "replicate/qwen/qwen3-235b-a22b-instruct-2507", "max_tokens": 8000}, # Perlu cek ID
    # {"suffix": "gemini-2.5-flash", "litellm_id": "replicate/google/gemini-2.5-flash", "max_tokens": 8192}, # Unlikely.
    {"suffix": "llama-3-70b-instruct-rep", "litellm_id": "replicate/meta/meta-llama-3-70b-instruct", "max_tokens": 8000},
    {"suffix": "llama-3-70b-rep", "litellm_id": "replicate/meta/meta-llama-3-70b", "max_tokens": 8000},
    {"suffix": "llama-2-70b-chat-rep", "litellm_id": "replicate/meta/llama-2-70b-chat", "max_tokens": 4096},
]
add_models_to_router(REPLICATE_API_KEYS, "Replicate", replicate_models)

# Groq (Dari list user, hapus yg bukan text/safety)
groq_models = [
    {"suffix": "llama-3.1-8b", "litellm_id": "groq/llama-3.1-8b-instant", "max_tokens": 8000},
    {"suffix": "llama-3.3-70b", "litellm_id": "groq/llama-3.3-70b-versatile", "max_tokens": 8000},
    {"suffix": "gpt-oss-120b-groq", "litellm_id": "groq/openai/gpt-oss-120b", "max_tokens": 4096}, # Check availability
    {"suffix": "gpt-oss-20b-groq", "litellm_id": "groq/openai/gpt-oss-20b", "max_tokens": 4096}, # Check availability
    # Skipping Whisper, Llama Guard, Compound
    # {"suffix": "llama-4-maverick-groq", "litellm_id": "groq/meta-llama/llama-4-maverick-17b-128e-instruct", "max_tokens": 8000}, # Fiksi?
    # {"suffix": "llama-4-scout-groq", "litellm_id": "groq/meta-llama/llama-4-scout-17b-16e-instruct", "max_tokens": 8000}, # Fiksi?
    {"suffix": "kimi-k2-instruct-groq", "litellm_id": "groq/moonshotai/kimi-k2-instruct-0905", "max_tokens": 8000}, # Check availability
    {"suffix": "qwen3-32b-groq", "litellm_id": "groq/qwen/qwen3-32b", "max_tokens": 8000}, # Check availability
]
add_models_to_router(GROQ_API_KEYS, "Groq", groq_models)

# 2. Inisialisasi Router
if model_list:
    router = litellm.Router(
        model_list=model_list,
        routing_strategy="latency", # Pilih berdasarkan latensi tercepat
        set_verbose=False,          # Set True untuk debug Router
        num_retries=1,              # Router fallback otomatis jika model tercepat gagal 1x
        allowed_fails=10            # Toleransi error sebelum model/key ditandai 'down'
    )
    logger.info(f"✅ LiteLLM Router initialized with {len(model_list)} model deployments and 'latency' strategy.")
    # Log model yang terdaftar (versi pendek)
    registered_models_short = list(dict.fromkeys([m["litellm_params"]["model"] for m in model_list])) # Unik model IDs
    logger.info(f"Registered model IDs (across all keys): {', '.join(registered_models_short)}")
else:
    router = None
    logger.critical("❌ No valid API keys/models defined. LiteLLM Router cannot be initialized.")

# ============================================================
# UTILITY FUNCTIONS (Tidak berubah)
# ============================================================
def clean_ai_response(raw_text: str) -> str:
    cleaned=raw_text.strip();
    if cleaned.startswith("```"): lines=cleaned.split('\n')[1:];
    if lines and lines[-1].strip()=="```": lines=lines[:-1]; cleaned='\n'.join(lines).strip()
    first_brace=cleaned.find('{'); last_brace=cleaned.rfind('}')
    if first_brace!=-1 and last_brace!=-1: cleaned=cleaned[first_brace:last_brace+1]
    return cleaned
def ai_decide_send_method(persona_type: str, has_files: bool) -> str: return 'text' if has_files else 'none'

# ============================================================
# CORE AI CALLER (PAKAI ROUTER)
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
    except litellm.Timeout as e: logger.error(f"AI Router call timed out: {e}"); return None
    except litellm.APIConnectionError as e: logger.error(f"AI Router connection error: {e}"); return None
    except (litellm.AuthenticationError, litellm.BadRequestError, litellm.RateLimitError, litellm.NotFound) as e:
         logger.error(f"AI Router API Error: {type(e).__name__} - {str(e)[:200]}")
         return None
    except Exception as e:
        logger.error(f"AI Router generic error: {type(e).__name__} - {str(e)[:200]}", exc_info=False)
        return None

# ============================================================
# MAIN GENERATION (Tidak berubah)
# ============================================================
def generate_persona_data(persona_type: str) -> Optional[Dict]:
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
