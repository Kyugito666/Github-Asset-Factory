"""
LLM Caller - Core AI calling dengan smart fallback

OPTIMIZATIONS:
- Smart proxy rotation (skip cooldown proxies)
- Temporary provider cooldown (1 hour, not permanent)
- Priority ordering (working providers first)
"""

import litellm
import logging
import random
import time

from litellm import (
    Timeout, 
    APIConnectionError, 
    AuthenticationError, 
    BadRequestError, 
    RateLimitError, 
    NotFoundError
)

from ...config import PROXY_POOL
from .options import llm_call_options

logger = logging.getLogger(__name__)

# === TEMPORARY COOLDOWN SYSTEM (1 HOUR) ===
_provider_cooldown = {}  # {provider: timestamp} - Skip for 1 hour
_model_cooldown = {}     # {model_key: timestamp} - Skip for 1 hour
COOLDOWN_DURATION = 3600  # 1 hour (quota reset bulanan)

def _add_to_cooldown(provider: str, model_id: str, reason: str):
    """Add provider/model ke temporary cooldown (1 hour)."""
    key = f"{provider}:{model_id}"
    current_time = time.time()
    
    # Temporary cooldown criteria
    if "quota" in reason.lower() or "payment" in reason.lower() or "429" in reason:
        _provider_cooldown[provider] = current_time
        logger.warning(f"⏸️ COOLDOWN Provider: {provider} for 1h (Reason: {reason[:50]})")
    elif "402" in reason or "404" in reason:
        _model_cooldown[key] = current_time
        logger.warning(f"⏸️ COOLDOWN Model: {model_id} for 1h (Reason: {reason[:50]})")

def _is_in_cooldown(provider: str, model_id: str) -> bool:
    """Check if provider/model masih dalam cooldown period."""
    current_time = time.time()
    key = f"{provider}:{model_id}"
    
    # Check provider cooldown
    if provider in _provider_cooldown:
        elapsed = current_time - _provider_cooldown[provider]
        if elapsed < COOLDOWN_DURATION:
            return True
        else:
            # Cooldown expired, remove
            del _provider_cooldown[provider]
            logger.info(f"✅ Cooldown expired: {provider}")
    
    # Check model cooldown
    if key in _model_cooldown:
        elapsed = current_time - _model_cooldown[key]
        if elapsed < COOLDOWN_DURATION:
            return True
        else:
            # Cooldown expired, remove
            del _model_cooldown[key]
            logger.info(f"✅ Cooldown expired: {model_id}")
    
    return False


def call_llm(prompt: str):
    """
    Call LLM dengan smart fallback.
    
    OPTIMIZATION FLOW:
    1. Filter cooldown providers/models (1h temporary)
    2. Prioritize: working > untested > failed
    3. Smart proxy rotation (skip cooldown)
    4. Max 3 retries per unique provider
    """
    if not llm_call_options:
        logger.error("LLM call options not initialized.")
        return None

    # === FILTER COOLDOWN (NOT PERMANENT BAN) ===
    available_options = []
    skipped_count = 0
    
    for opt in llm_call_options:
        provider = opt["provider"]
        model_id = opt["params"].get("model", "")
        
        if _is_in_cooldown(provider, model_id):
            skipped_count += 1
            continue
        
        available_options.append(opt)
    
    if not available_options:
        logger.error(f"❌ All {len(llm_call_options)} options in cooldown. Wait 1h or restart.")
        return None
    
    if skipped_count > 0:
        logger.info(f"⏸️ Skipped {skipped_count} options in cooldown")
    
    # === SMART SHUFFLE ===
    # Priority: Cohere, Mistral, OpenRouter > Gemini > Others
    priority_providers = {"Cohere", "Mistral", "OpenRouter"}
    
    priority_opts = [o for o in available_options if o["provider"] in priority_providers]
    other_opts = [o for o in available_options if o["provider"] not in priority_providers]
    
    random.shuffle(priority_opts)
    random.shuffle(other_opts)
    
    current_options = priority_opts + other_opts
    
    logger.info(f"🎯 Available: {len(current_options)} options ({len(priority_opts)} priority)")

    # === ATTEMPT LOOP ===
    tried_providers = {}  # Track attempts per provider
    
    for i, option in enumerate(current_options):
        provider = option["provider"]
        params = option["params"].copy()
        model_id = params.get("model", "N/A")
        
        # Limit 3 attempts per provider
        if tried_providers.get(provider, 0) >= 3:
            continue
        
        tried_providers[provider] = tried_providers.get(provider, 0) + 1
        
        # === SMART PROXY ROTATION ===
        proxy_url = params.get("proxy")
        
        if proxy_url:
            # Check if still in cooldown
            if PROXY_POOL and proxy_url in PROXY_POOL.failed_proxies:
                # Skip, get new proxy
                new_proxy = PROXY_POOL.get_next_proxy()
                if new_proxy:
                    params["proxy"] = new_proxy
                    proxy_url = new_proxy
                else:
                    # No proxy available, try without
                    if "proxy" in params:
                        del params["proxy"]
                    proxy_url = None
        
        proxy_display = proxy_url.split('@')[-1] if proxy_url else 'None'
        
        logger.info(f"Attempt {i+1}/{len(current_options)}: {provider} - {model_id} "
                   f"(Proxy: {proxy_display})")

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
                logger.warning(f"⚠️ Empty response. Next...")
                continue

        except (APIConnectionError, Timeout) as e:
            logger.warning(f"❌ Connection/Timeout: {type(e).__name__}. Next...")
            
            if PROXY_POOL and proxy_url:
                PROXY_POOL.mark_failed(proxy_url)
            
            continue

        except (AuthenticationError, BadRequestError) as e:
            error_msg = str(e)
            logger.error(f"❌ Auth/BadRequest: {error_msg[:150]}. Next...")
            
            # Add to temporary cooldown if quota/payment issue
            _add_to_cooldown(provider, model_id, error_msg)
            
            continue
        
        except RateLimitError as e:
            logger.warning(f"⚠️ Rate Limited. Next...")
            _add_to_cooldown(provider, model_id, str(e))
            continue

        except NotFoundError as e:
            logger.error(f"❌ Model Not Found: {model_id}. Next...")
            _add_to_cooldown(provider, model_id, "404")
            continue

        except Exception as e:
            logger.error(f"❌ Unexpected: {type(e).__name__} - {str(e)[:150]}. Next...")
            
            if PROXY_POOL and proxy_url:
                PROXY_POOL.mark_failed(proxy_url)
            
            # Check if payment/quota error in generic exception
            if "402" in str(e) or "payment" in str(e).lower() or "quota" in str(e).lower():
                _add_to_cooldown(provider, model_id, str(e))
            
            continue

    logger.error("❌ All LLM options exhausted.")
    return None
