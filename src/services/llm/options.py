"""
LLM Options Builder - Build llm_call_options dari models.json

Responsibilities:
- Load models.json
- Load prompts (persona.json, assets.json)
- Build llm_call_options dengan kombinasi (provider, model, api_key, proxy)
- Handle proxy compatibility per provider
"""

import os
import json
import logging

from ...config import (
    GEMINI_API_KEYS, GROQ_API_KEYS, COHERE_API_KEYS, REPLICATE_API_KEYS,
    HF_API_TOKENS, OPENROUTER_API_KEYS, MISTRAL_API_KEYS,
    PROXY_POOL
)

logger = logging.getLogger(__name__)

# Path setup
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
# === PERBAIKAN DI BAWAH INI ===
# Path diubah dari os.path.dirname(SCRIPT_DIR) menjadi os.path.dirname(os.path.dirname(SCRIPT_DIR))
# untuk naik dua level (dari .../src/services/llm ke .../src)
PROMPTS_DIR = os.path.join(os.path.dirname(os.path.dirname(SCRIPT_DIR)), "prompts")
# === AKHIR PERBAIKAN ===

# Global variables (akan di-populate di module load)
BASE_PERSONA_PROMPT = ""
ASSET_PROMPTS = {}


# ============================================================
# LOAD PROMPTS
# ============================================================

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


# ============================================================
# PROXY HELPER
# ============================================================

def get_proxy_for_provider(provider_prefix: str):
    """
    Return proxy string untuk provider, skip jika incompatible.
    
    Incompatible providers:
    - groq: Tidak support proxy
    - huggingface: Tidak support proxy
    
    Args:
        provider_prefix: Provider name (lowercase)
        
    Returns:
        Optional[str]: Proxy URL or None
    """
    if not PROXY_POOL:
        return None
    
    # List provider yang tidak support proxy
    incompatible_providers = ["groq", "huggingface"]
    
    if provider_prefix in incompatible_providers:
        logger.warning(f"Skipping proxy for incompatible provider: {provider_prefix}")
        return None
    
    proxy_url = PROXY_POOL.get_next_proxy()
    if not proxy_url:
        return None
    
    return proxy_url


# ============================================================
# BUILD CALL OPTIONS
# ============================================================

def add_call_options(keys: list, provider: str, model_configs: list):
    """
    Add call options untuk satu provider.
    
    Args:
        keys: List of API keys
        provider: Provider display name (e.g., "Gemini")
        model_configs: List of model config dicts dari models.json
    """
    if not keys:
        return
    
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
            
            # Add custom_llm_provider jika ada
            if "custom_llm_provider" in model_config:
                call_params["custom_llm_provider"] = model_config["custom_llm_provider"]
            
            # Remove None values
            call_params = {k: v for k, v in call_params.items() if v is not None}
            
            llm_call_options.append({
                "provider": provider,
                "params": call_params
            })


# ============================================================
# API KEY MAP
# ============================================================

API_KEY_MAP = {
    "gemini": (GEMINI_API_KEYS, "Gemini"),
    "cohere": (COHERE_API_KEYS, "Cohere"),
    "mistral": (MISTRAL_API_KEYS, "Mistral"),
    "openrouter": (OPENROUTER_API_KEYS, "OpenRouter"),
    "huggingface": (HF_API_TOKENS, "HuggingFace"),
    "replicate": (REPLICATE_API_KEYS, "Replicate"),
    "groq": (GROQ_API_KEYS, "Groq")
}


# ============================================================
# INITIALIZE OPTIONS (Module Load Time)
# ============================================================

models_json_path = os.path.join(os.path.dirname(SCRIPT_DIR), "models.json")

try:
    with open(models_json_path, 'r', encoding='utf-8') as f:
        model_definitions = json.load(f)
    
    logger.info(f"Successfully loaded model definitions from {models_json_path}")
    
    # Build call options untuk setiap provider
    for provider_key, models_list in model_definitions.items():
        if provider_key in API_KEY_MAP:
            api_keys, display_name = API_KEY_MAP[provider_key]
            
            if api_keys:
                add_call_options(api_keys, display_name, models_list)
            else:
                logger.warning(f"No API keys for '{provider_key}', skipping.")
        else:
            logger.warning(f"Provider '{provider_key}' in models.json unknown. Skipping.")
    
    if llm_call_options:
        # NOTE: Random shuffle dilakukan di caller.py setiap kali call
        logger.info(f"✅ Initialized {len(llm_call_options)} LLM call options.")
    else:
        logger.critical("❌ No valid LLM call options generated.")
        
except Exception as e:
    logger.critical(f"FATAL: Error loading models/keys: {e}")
