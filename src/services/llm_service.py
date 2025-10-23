import litellm
import json
import logging
import random
from typing import Optional, Dict, List
from litellm import exceptions as litellm_exceptions

from ..prompts.prompts import BASE_PERSONA_PROMPT
from ..prompts.asset_prompts import ASSET_PROMPTS
from ..config import (
    GEMINI_API_KEYS, GROQ_API_KEYS, COHERE_API_KEYS, REPLICATE_API_KEYS,
    HF_API_TOKENS, OPENROUTER_API_KEYS, MISTRAL_API_KEYS, FIREWORKS_API_KEYS,
    PROXY_POOL
)
from ..modules.persona_history import load_used_data, add_to_history, load_history_data

logger = logging.getLogger(__name__)

# ============================================================
# LITELLM ROUTER SETUP
# ============================================================

model_list = []

def get_proxy_for_provider(provider_prefix: str) -> Optional[str]:
    if not PROXY_POOL:
        return None
    proxy_url = PROXY_POOL.get_next_proxy()
    if not proxy_url:
        return None
    if provider_prefix in ["gemini", "cohere", "groq", "huggingface", "mistral"]:
        return f"{provider_prefix}:{proxy_url}"
    return proxy_url

def add_models_to_router(keys: list, provider: str, model_configs: List[Dict]):
    """Helper to add multiple models for a provider using their keys."""
    if not keys:
        return
    provider_lower = provider.lower()
    for key_index, key in enumerate(keys):
        for model_config in model_configs:
            unique_model_name = f"{provider_lower}-{model_config['suffix']}_{key_index}"
            litellm_params = {
                "model": model_config["litellm_id"],
                "api_key": key,
            }
            if "max_tokens" in model_config:
                litellm_params["max_tokens"] = model_config["max_tokens"]
            if "base_url" in model_config:
                litellm_params["base_url"] = model_config["base_url"]
            litellm_params["proxy"] = get_proxy_for_provider(provider_lower)
            
            model_list.append({
                "model_name": unique_model_name,
                "litellm_params": litellm_params,
                "model_info": {"provider": provider}
            })

# Define Models for Each Provider
gemini_models = [
    {"suffix": "2.5-flash", "litellm_id": "gemini/gemini-2.5-flash", "max_tokens": 8192},
    {"suffix": "2.5-pro", "litellm_id": "gemini/gemini-2.5-pro", "max_tokens": 8192},
    {"suffix": "2.0-flash", "litellm_id": "gemini/gemini-2.0-flash", "max_tokens": 8192},
]
add_models_to_router(GEMINI_API_KEYS, "Gemini", gemini_models)

cohere_models = [
    {"suffix": "command-r-plus", "litellm_id": "cohere/command-r-plus", "max_tokens": 4096},
    {"suffix": "command-r", "litellm_id": "cohere/command-r", "max_tokens": 4096},
]
add_models_to_router(COHERE_API_KEYS, "Cohere", cohere_models)

mistral_models = [
    {"suffix": "large-latest", "litellm_id": "mistral/mistral-large-latest", "max_tokens": 8000},
    {"suffix": "codestral-latest", "litellm_id": "mistral/codestral-latest", "max_tokens": 8000},
]
add_models_to_router(MISTRAL_API_KEYS, "Mistral", mistral_models)

fireworks_base_url = "https://api.fireworks.ai/inference/v1"
fireworks_models = [
    {"suffix": "mixtral-8x7b", "litellm_id": "accounts/fireworks/models/mixtral-8x7b-instruct", "max_tokens": 32768, "base_url": fireworks_base_url},
    {"suffix": "llama-v3-70b", "litellm_id": "accounts/fireworks/models/llama-v3-70b-instruct", "max_tokens": 8192, "base_url": fireworks_base_url},
]
add_models_to_router(FIREWORKS_API_KEYS, "Fireworks", fireworks_models)

openrouter_models = [
    {"suffix": "llama-3.3-8b-free", "litellm_id": "openrouter/meta-llama/llama-3.3-8b-instruct:free", "max_tokens": 8000},
    {"suffix": "claude-3-haiku", "litellm_id": "openrouter/anthropic/claude-3-haiku", "max_tokens": 4096},
]
add_models_to_router(OPENROUTER_API_KEYS, "OpenRouter", openrouter_models)

hf_models = [
    {"suffix": "gpt-oss-20b-hf", "litellm_id": "huggingface/openai/gpt-oss-20b", "max_tokens": 4096},
]
add_models_to_router(HF_API_TOKENS, "HuggingFace", hf_models)

replicate_models = [
    {"suffix": "llama-3-70b-instruct-rep", "litellm_id": "replicate/meta/meta-llama-3-70b-instruct", "max_tokens": 8000},
]
add_models_to_router(REPLICATE_API_KEYS, "Replicate", replicate_models)

groq_models = [
    {"suffix": "llama-3.1-8b", "litellm_id": "groq/llama-3.1-8b-instant", "max_tokens": 8000},
]
add_models_to_router(GROQ_API_KEYS, "Groq", groq_models)

if model_list:
    router = litellm.Router(
        model_list=model_list,
        routing_strategy="latency",
        set_verbose=False,
        num_retries=1,
        allowed_fails=10
    )
    logger.info(f"✅ LiteLLM Router initialized with {len(model_list)} deployments")
else:
    router = None
    logger.critical("❌ No valid API keys found. Router cannot be initialized.")

# ============================================================
# UTILITY FUNCTIONS
# ============================================================

def clean_ai_response(raw_text: str) -> str:
    cleaned = raw_text.strip()
    if cleaned.startswith("```"):
        lines = cleaned.split('\n')
        if lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        cleaned = '\n'.join(lines).strip()
    
    first_brace = cleaned.find('{')
    last_brace = cleaned.rfind('}')
    if first_brace != -1 and last_brace != -1:
        cleaned = cleaned[first_brace:last_brace+1]
    return cleaned

def ai_decide_send_method(persona_type: str, has_files: bool) -> str:
    return 'text' if has_files else 'none'

# ============================================================
# CORE AI CALLER
# ============================================================

def call_llm(prompt: str) -> Optional[str]:
    """Call AI using LiteLLM Router with proper error handling."""
    if not router:
        logger.error("LiteLLM Router not initialized.")
        return None
    
    try:
        response = router.completion(
            model="available",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.8,
            timeout=180
        )
        
        if not response or not response.choices:
            logger.error("AI Router returned invalid or empty response object.")
            return None
        
        result = response.choices[0].message.content
        chosen_model = response.model
        
        original_model_id = chosen_model
        provider = 'Unknown'
        if hasattr(response, '_hidden_params') and response._hidden_params:
            chosen_llm_params = response._hidden_params.get('litellm_params', {})
            original_model_id = chosen_llm_params.get('model', chosen_model)
            provider = chosen_llm_params.get('model_info', {}).get('provider', 'Unknown')
        
        logger.info(f"✅ Router chose '{chosen_model}' (Model: {original_model_id}, Provider: {provider})")
        return result if result else None
    
    except litellm_exceptions.Timeout as e:
        logger.error(f"AI Router timeout: {e}")
        return None
    except litellm_exceptions.APIConnectionError as e:
        logger.error(f"AI Router connection error: {e}")
        return None
    except (litellm_exceptions.AuthenticationError, litellm_exceptions.BadRequestError,
            litellm_exceptions.RateLimitError, litellm_exceptions.NotFound,
            litellm_exceptions.ContextWindowExceededError, litellm_exceptions.APIError) as e:
        logger.error(f"AI Router API Error: {type(e).__name__} - {str(e)[:250]}")
        return None
    except Exception as e:
        logger.error(f"AI Router generic error: {type(e).__name__} - {str(e)[:250]}")
        return None

# ============================================================
# MAIN GENERATION
# ============================================================

def generate_persona_data(persona_type: str) -> Optional[Dict]:
    logger.info(f"🔄 AI Chaining: '{persona_type}'")
    used_usernames, used_names = load_used_data()
    
    logger.info("📝 Step 1: Base Persona (with duplicate check)")
    base_prompt = BASE_PERSONA_PROMPT.format(persona_type=persona_type)
    base_data = None
    MAX_RETRIES = 5
    
    for attempt in range(MAX_RETRIES):
        raw_1 = call_llm(base_prompt)
        if not raw_1:
            logger.error("❌ Step 1 failed (AI call failed)")
            return None
        
        try:
            data = json.loads(clean_ai_response(raw_1))
            username = data.get('username')
            name = data.get('name')
            
            if not username or not name:
                logger.warning(f"AI returned no username/name. Retrying... ({attempt+1}/{MAX_RETRIES})")
                continue
            
            if username in used_usernames:
                logger.warning(f"DUPLICATE username '{username}'. Retrying... ({attempt+1}/{MAX_RETRIES})")
                base_prompt = BASE_PERSONA_PROMPT.format(persona_type=persona_type) + f"\n\nCRITICAL: DO NOT use username '{username}'. Generate a COMPLETELY NEW username."
                continue
            
            if name in used_names:
                logger.warning(f"DUPLICATE name '{name}'. Retrying... ({attempt+1}/{MAX_RETRIES})")
                base_prompt = BASE_PERSONA_PROMPT.format(persona_type=persona_type) + f"\n\nCRITICAL: DO NOT use name '{name}'. Generate a COMPLETELY NEW name."
                continue
            
            base_data = data
            break
        
        except Exception as e:
            logger.error(f"❌ Step 1 JSON parse error: {e}. Raw: {raw_1[:100]}...")
            return None
    
    if not base_data:
        logger.error(f"❌ Step 1 FAILED after {MAX_RETRIES} retries.")
        return None
    
    add_to_history(base_data.get('username'), base_data.get('name'))
    logger.info(f"✅ Seed (Unique): {base_data.get('name')} (@{base_data.get('username')})")
    
    asset_template = ASSET_PROMPTS.get(persona_type)
    if not asset_template:
        logger.info(f"ℹ️ No asset needed for '{persona_type}'")
        base_data.update({"repo_name": None, "repo_description": None, "files": None, "send_method": "none"})
        return base_data
    
    logger.info("📄 Step 2: Asset Generation")
    asset_prompt = asset_template.format(
        base_persona_json=json.dumps(base_data, indent=2),
        username_dari_konteks=base_data.get('username')
    )
    
    raw_2 = call_llm(asset_prompt)
    if not raw_2:
        logger.error("❌ Step 2 failed")
        return None
    
    try:
        asset_data = json.loads(clean_ai_response(raw_2))
        is_profile_readme = persona_type in [
            "profile_architect", "ui_ux_designer", "technical_writer_dev",
            "minimalist_dev", "data_viz_enthusiast", "open_source_advocate"
        ]
        
        if "repo_name" not in asset_data and not is_profile_readme:
            if "{username_dari_konteks}" in asset_template and base_data.get('username'):
                asset_data['repo_name'] = base_data['username']
                logger.warning(f"repo_name missing, using username '{base_data['username']}' as fallback.")
            else:
                logger.error(f"❌ Step 2 JSON invalid: 'repo_name' missing. Raw: {raw_2[:100]}...")
                return None
        
        if "files" not in asset_data or not isinstance(asset_data.get("files"), list):
            logger.error(f"❌ Step 2 JSON invalid: 'files' array missing. Raw: {raw_2[:100]}...")
            return None
        
        for file_item in asset_data.get("files", []):
            if "file_name" not in file_item or "file_content" not in file_item:
                logger.error(f"❌ Step 2 JSON invalid: item in 'files' missing keys. Raw: {raw_2[:100]}...")
                return None
        
        logger.info(f"✅ Assets generated for repo '{asset_data.get('repo_name', base_data.get('username'))}'.")
    
    except Exception as e:
        logger.error(f"❌ Step 2 JSON parse error: {e}. Raw: {raw_2[:100]}...")
        return None
    
    final_data = base_data.copy()
    final_data.update(asset_data)
    has_files = bool(final_data.get('files'))
    final_data['send_method'] = ai_decide_send_method(persona_type, has_files)
    
    logger.info(f"✅ Complete: '{persona_type}' (Method: {final_data['send_method']})")
    return final_data
