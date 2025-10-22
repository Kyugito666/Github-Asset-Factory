import litellm
import json
import logging
import random
import time
from typing import Optional, Dict, List

# Tambahkan import exceptions
from litellm import exceptions as litellm_exceptions

from ..prompts.prompts import BASE_PERSONA_PROMPT # Import BASE saja
# Import ASSET_PROMPTS dari file baru
try:
    from ..prompts.asset_prompts import ASSET_PROMPTS
except ImportError:
    logger.error("Could not import ASSET_PROMPTS from src/prompts/asset_prompts.py. Ensure the file exists and is correct.")
    ASSET_PROMPTS = {} # Fallback ke dictionary kosong

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
    proxy_url = PROXY_POOL.get_next_proxy()
    if not proxy_url: return None
    if provider_prefix in ["gemini", "cohere", "groq", "huggingface", "mistral"]:
        return f"{provider_prefix}:{proxy_url}"
    elif provider_prefix in ["openrouter", "replicate", "fireworks"]:
        return proxy_url
    else: return proxy_url

# --- Helper Function to Add Models ---
def add_models_to_router(keys: list, provider: str, model_configs: List[Dict]):
    """Helper to add multiple models for a provider using their keys."""
    if not keys:
        # logger.info(f"Skipping {provider}: No API keys provided.") # Kurangi log
        return
    provider_lower = provider.lower()
    for key_index, key in enumerate(keys):
        for model_config in model_configs:
            # Create a unique model_name for the router for this specific key and model variant
            unique_model_name = f"{provider_lower}-{model_config['suffix']}_{key_index}"

            litellm_params = {
                "model": model_config["litellm_id"],
                "api_key": key,
            }
            if "max_tokens" in model_config: litellm_params["max_tokens"] = model_config["max_tokens"]
            # Add base_url if needed (e.g., Fireworks)
            if "base_url" in model_config: litellm_params["base_url"] = model_config["base_url"]

            litellm_params["proxy"] = get_proxy_for_provider(provider_lower)

            model_list.append({
                "model_name": unique_model_name,
                "litellm_params": litellm_params,
                "model_info": {"provider": provider}
            })
            # logger.debug(f"Added model deployment to router: {unique_model_name}") # Terlalu berisik

# --- Define Models for Each Provider (SESUAI LIST USER) ---

# Gemini (Dari list user)
gemini_models = [
    # Pastikan ID ini valid di LiteLLM/Google AI
    {"suffix": "2.5-flash", "litellm_id": "gemini/gemini-2.5-flash", "max_tokens": 8192},
    {"suffix": "2.5-pro", "litellm_id": "gemini/gemini-2.5-pro", "max_tokens": 8192}, # Mungkin perlu akses khusus
    # ID Preview mungkin sudah tidak valid di 2025 akhir
    # {"suffix": "2.5-flash-preview", "litellm_id": "gemini/gemini-2.5-flash-preview-09-2025", "max_tokens": 8192},
    # Lite models mungkin tidak ada via API standar
    # {"suffix": "2.5-flash-lite", "litellm_id": "gemini/gemini-2.5-flash-lite", "max_tokens": 8192},
    # {"suffix": "2.5-flash-lite-preview", "litellm_id": "gemini/gemini-2.5-flash-lite-preview-09-2025", "max_tokens": 8192},
    {"suffix": "2.0-flash", "litellm_id": "gemini/gemini-2.0-flash", "max_tokens": 8192}, # Versi lama sbg fallback
]
add_models_to_router(GEMINI_API_KEYS, "Gemini", gemini_models)

# Cohere (Dari list user, pilih yang relevan)
cohere_models = [
    # Pilih model Command R terbaru
    {"suffix": "command-r-plus", "litellm_id": "cohere/command-r-plus", "max_tokens": 4096}, # Versi Agustus 2024? Cek versi terbaru
    {"suffix": "command-r", "litellm_id": "cohere/command-r", "max_tokens": 4096}, # Versi Agustus 2024? Cek versi terbaru
    # Aya mungkin model multilingual, bisa dicoba
    # {"suffix": "aya-expanse-32b", "litellm_id": "cohere/c4ai-aya-expanse-32b", "max_tokens": 4096},
]
add_models_to_router(COHERE_API_KEYS, "Cohere", cohere_models)

# Mistral AI (Dari list user)
mistral_models = [
    {"suffix": "large-latest", "litellm_id": "mistral/mistral-large-latest", "max_tokens": 8000}, # Chat model
    {"suffix": "codestral-latest", "litellm_id": "mistral/codestral-latest", "max_tokens": 8000}, # Code model
    # {"suffix": "medium-latest", "litellm_id": "mistral/mistral-medium-latest", "max_tokens": 8000}, # Medium bisa jadi pilihan
]
add_models_to_router(MISTRAL_API_KEYS, "Mistral", mistral_models)

# Fireworks AI (Dari list user, perbaiki ID jika perlu)
# Base URL mungkin diperlukan jika LiteLLM tidak otomatis
fireworks_base_url = "https://api.fireworks.ai/inference/v1" # Cek dokumentasi
fireworks_models = [
    {"suffix": "mixtral-8x7b", "litellm_id": "accounts/fireworks/models/mixtral-8x7b-instruct", "max_tokens": 32768, "base_url": fireworks_base_url},
    {"suffix": "llama-v3-70b", "litellm_id": "accounts/fireworks/models/llama-v3-70b-instruct", "max_tokens": 8192, "base_url": fireworks_base_url},
    {"suffix": "deepseek-v3p1-terminus", "litellm_id": "accounts/fireworks/models/deepseek-v3p1-terminus", "max_tokens": 8000, "base_url": fireworks_base_url}, # Cek ketersediaan
    # Kimi mungkin tidak tersedia di Fireworks
    # {"suffix": "kimi-k2-instruct", "litellm_id": "accounts/fireworks/models/kimi-k2-instruct", "max_tokens": 8000, "base_url": fireworks_base_url},
    # Qwen mungkin perlu base_url beda atau ID beda
    # {"suffix": "qwen3-235b-instruct", "litellm_id": "accounts/fireworks/models/qwen3-235b-a22b-instruct-2507", "max_tokens": 8000, "base_url": fireworks_base_url},
    # GPT OSS models? Cek ketersediaan di Fireworks
    # {"suffix": "gpt-oss-120b", "litellm_id": "accounts/fireworks/models/gpt-oss-120b", "max_tokens": 4096, "base_url": fireworks_base_url},
    # {"suffix": "gpt-oss-20b", "litellm_id": "accounts/fireworks/models/gpt-oss-20b", "max_tokens": 4096, "base_url": fireworks_base_url},
]
add_models_to_router(FIREWORKS_API_KEYS, "Fireworks", fireworks_models)

# OpenRouter (Dari list user, pakai ID langsung)
openrouter_models = [
    # Free Tier (limit ketat)
    {"suffix": "llama-3.3-8b-free", "litellm_id": "openrouter/meta-llama/llama-3.3-8b-instruct:free", "max_tokens": 8000},
    {"suffix": "gemma-3n-e4b-free", "litellm_id": "openrouter/google/gemma-3n-e4b-it:free", "max_tokens": 8000},
    {"suffix": "qwen3-4b-free", "litellm_id": "openrouter/qwen/qwen3-4b:free", "max_tokens": 8000},
    {"suffix": "mistral-small-3.2-free", "litellm_id": "openrouter/mistralai/mistral-small-3.2-24b-instruct:free", "max_tokens": 8000},
    {"suffix": "kimi-k2-free", "litellm_id": "openrouter/moonshotai/kimi-k2:free", "max_tokens": 8000},
    # Paid/Standard Tier (lebih reliable)
    {"suffix": "claude-3-haiku", "litellm_id": "openrouter/anthropic/claude-3-haiku", "max_tokens": 4096}, # Murah & cepat
    # {"suffix": "gpt-4o-mini", "litellm_id": "openrouter/openai/gpt-4o-mini", "max_tokens": 8000}, # Jika punya budget
]
add_models_to_router(OPENROUTER_API_KEYS, "OpenRouter", openrouter_models)

# Hugging Face (Dari list user, pilih yg mungkin text gen & via API)
hf_models = [
    # Pastikan model ini punya endpoint Inference API aktif
    # {"suffix": "GLM-4.6", "litellm_id": "huggingface/zai-org/GLM-4.6", "max_tokens": 8000}, # Mungkin butuh setup khusus
    {"suffix": "gpt-oss-20b-hf", "litellm_id": "huggingface/openai/gpt-oss-20b", "max_tokens": 4096}, # Cek ketersediaan
    # {"suffix": "DeepSeek-V3.2-Exp", "litellm_id": "huggingface/deepseek-ai/DeepSeek-V3.2-Exp", "max_tokens": 8000}, # Cek ketersediaan
    # {"suffix": "gpt-oss-120b-hf", "litellm_id": "huggingface/openai/gpt-oss-120b", "max_tokens": 4096}, # Cek ketersediaan
]
add_models_to_router(HF_API_TOKENS, "HuggingFace", hf_models)

# Replicate (Dari list user, coba tanpa hash, skip yg fiksi)
replicate_models = [
    {"suffix": "llama-3-70b-instruct-rep", "litellm_id": "replicate/meta/meta-llama-3-70b-instruct", "max_tokens": 8000},
    # Kimi mungkin perlu ID dg hash
    # {"suffix": "kimi-k2-instruct-rep", "litellm_id": "replicate/moonshotai/kimi-k2-instruct", "max_tokens": 8000},
    # Granite? Cek ketersediaan
    # {"suffix": "granite-3.3-8b", "litellm_id": "replicate/ibm-granite/granite-3.3-8b-instruct", "max_tokens": 4096},
    # Qwen? Cek ID & ketersediaan
    # {"suffix": "qwen3-235b-instruct-rep", "litellm_id": "replicate/qwen/qwen3-235b-a22b-instruct-2507", "max_tokens": 8000},
    {"suffix": "llama-2-70b-chat-rep", "litellm_id": "replicate/meta/llama-2-70b-chat", "max_tokens": 4096}, # Versi lama sbg fallback
]
add_models_to_router(REPLICATE_API_KEYS, "Replicate", replicate_models)

# Groq (Jika keys valid lagi)
groq_models = [
    {"suffix": "llama-3.1-8b", "litellm_id": "groq/llama-3.1-8b-instant", "max_tokens": 8000},
    {"suffix": "llama-3.3-70b", "litellm_id": "groq/llama-3.3-70b-versatile", "max_tokens": 8000},
]
add_models_to_router(GROQ_API_KEYS, "Groq", groq_models)

# 2. Inisialisasi Router
if model_list:
    router = litellm.Router(
        model_list=model_list,
        routing_strategy="latency", # Pilih berdasarkan latensi tercepat
        set_verbose=False,          # Set True untuk debug Router detail
        num_retries=1,              # Router fallback otomatis jika model tercepat gagal 1x
        allowed_fails=10            # Toleransi error sebelum model/key ditandai 'down' sementara
    )
    logger.info(f"✅ LiteLLM Router initialized with {len(model_list)} total model deployments and 'latency' strategy.")
    # Log model ID unik yang terdaftar
    registered_model_ids = sorted(list(set(m["litellm_params"]["model"] for m in model_list)))
    logger.info(f"Registered unique model IDs (across all keys): {len(registered_model_ids)}")
    # for model_id in registered_model_ids: logger.debug(f"- {model_id}") # Uncomment for full list
else:
    router = None
    logger.critical("❌ No valid API keys found OR no models configured in llm_service.py. LiteLLM Router cannot be initialized.")

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
# CORE AI CALLER (PAKAI ROUTER - Exception Handling Diperbaiki)
# ============================================================
def call_llm(prompt: str) -> Optional[str]:
    """Panggil AI menggunakan LiteLLM Router."""
    if not router:
        logger.error("LiteLLM Router not initialized.")
        return None
    try:
        response = router.completion(
            model="available", # Router pilih model tercepat dari list yang 'healthy'
            messages=[{"role": "user", "content": prompt}],
            temperature=0.8,
            timeout=180 # Naikkan timeout lagi untuk model yg mungkin besar/lambat
        )
        # Handle jika response tidak punya 'choices' (error aneh)
        if not response or not response.choices:
             logger.error("AI Router returned invalid or empty response object.")
             # Coba ambil info model dari respons jika ada
             chosen_model = getattr(response, 'model', 'unknown')
             logger.error(f"Router attempted model: {chosen_model}")
             return None

        result = response.choices[0].message.content
        chosen_model_router_name = response.model # Nama unik yg kita define
        # Ambil info asli model dan provider dari _hidden_params jika ada
        original_model_id = chosen_model_router_name
        provider = 'Unknown'
        if hasattr(response, '_hidden_params') and response._hidden_params:
             chosen_llm_params = response._hidden_params.get('litellm_params', {})
             original_model_id = chosen_llm_params.get('model', chosen_model_router_name)
             provider = chosen_llm_params.get('model_info', {}).get('provider', 'Unknown')

        logger.info(f"✅ Router chose '{chosen_model_router_name}' (Model ID: {original_model_id}, Provider: {provider})")

        if result:
            return result
        else:
            logger.warning(f"AI Router ({provider}) returned an empty response content.")
            return None

    except litellm_exceptions.Timeout as e:
        logger.error(f"AI Router call timed out: {e}")
        return None
    except litellm_exceptions.APIConnectionError as e:
        logger.error(f"AI Router connection error: {e}")
        # Router should handle fallback, log and return None
        return None
    except (litellm_exceptions.AuthenticationError, litellm_exceptions.BadRequestError,
            litellm_exceptions.RateLimitError, litellm_exceptions.NotFound,
            litellm_exceptions.ContextWindowExceededError, litellm_exceptions.APIError) as e:
         # Tangkap error API spesifik DARI litellm.exceptions
         logger.error(f"AI Router API Error: {type(e).__name__} - {str(e)[:250]}")
         # Router should handle fallback, log and return None
         return None
    except Exception as e:
        # Tangkap error umum lainnya
        logger.error(f"AI Router generic error: {type(e).__name__} - {str(e)[:250]}", exc_info=False) # Set True for full trace if needed
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
        # Allow repo_name to be missing for profile readme personas
        if "repo_name" not in asset_data and not is_profile_readme :
            # Check if username_dari_konteks should be used (for profile_architect style prompts)
             if "{username_dari_konteks}" in asset_template and base_data.get('username'):
                 asset_data['repo_name'] = base_data['username'] # Fallback for profile repos
                 logger.warning(f"repo_name missing in Step 2 JSON for {persona_type}, using username '{base_data['username']}' as fallback.")
             else:
                 logger.error(f"❌ Step 2 JSON invalid: 'repo_name' missing and not a profile persona. Raw: {raw_2[:100]}..."); return None

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
