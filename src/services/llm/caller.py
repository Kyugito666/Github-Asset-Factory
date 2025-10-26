"""
LLM Caller - Core AI calling function dengan manual fallback

Features:
- Random shuffle setiap call (load distribution)
- Sequential fallback through all options
- Proxy failure tracking
- Specific exception handling per error type
"""

import litellm
import logging
import random

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

# litellm.set_verbose = True  # Uncomment untuk debug


def call_llm(prompt: str):
    """
    Call LLM dengan manual fallback system.
    
    Process:
    1. Random shuffle llm_call_options (load distribution)
    2. Try setiap option secara sequential
    3. Handle specific errors:
       - Connection/Timeout: Mark proxy failed, continue
       - Auth/BadRequest/RateLimit/NotFound: Continue (error permanent)
       - Unexpected: Mark proxy failed, continue
    4. Return response atau None jika semua gagal
    
    Args:
        prompt: User prompt string
        
    Returns:
        Optional[str]: AI response atau None jika gagal
    """
    if not llm_call_options:
        logger.error("LLM call options not initialized.")
        return None

    # Random shuffle setiap call untuk load distribution
    current_options = random.sample(llm_call_options, len(llm_call_options))

    for i, option in enumerate(current_options):
        provider = option["provider"]
        params = option["params"].copy()  # Copy untuk avoid mutation
        model_id = params.get("model", "N/A")
        proxy_used = params.get("proxy")

        # Remove proxy param jika None (litellm tidak suka None value)
        if proxy_used is None:
            if "proxy" in params:
                del params["proxy"]

        logger.info(f"Attempt {i+1}/{len(current_options)}: Trying {provider} - {model_id} "
                   f"(Proxy: {proxy_used.split('@')[-1] if proxy_used else 'None'})")

        try:
            # Direct call ke litellm.completion dengan params
            response = litellm.completion(
                **params,  # Unpack: model, api_key, proxy (optional), max_tokens
                messages=[{"role": "user", "content": prompt}],
                temperature=0.8,
                timeout=120  # Timeout per attempt
            )

            result = response.choices[0].message.content
            logger.info(f"✅ Success with {provider} - {model_id}")
            
            if result:
                return result
            else:
                logger.warning(f"⚠️ Empty response. Trying next...")
                continue

        except (APIConnectionError, Timeout) as e:
            logger.warning(f"❌ Connection/Timeout with {provider} - {model_id}: "
                          f"{type(e).__name__}. Trying next...")
            
            # Mark proxy failed jika pakai proxy
            if PROXY_POOL and proxy_used:
                PROXY_POOL.mark_failed(proxy_used)
            
            continue

        except (AuthenticationError, BadRequestError, RateLimitError, NotFoundError) as e:
            # Log level berbeda untuk rate limit (warning) vs error lain (error)
            log_level = logging.WARNING if isinstance(e, RateLimitError) else logging.ERROR
            
            logger.log(log_level, f"❌ API Error with {provider} - {model_id}: "
                      f"{type(e).__name__} - {str(e)[:150]}. Trying next...")
            
            continue

        except Exception as e:
            logger.error(f"❌ Unexpected error with {provider} - {model_id}: "
                        f"{type(e).__name__} - {str(e)[:150]}. Trying next...", 
                        exc_info=False)
            
            # Mark proxy failed untuk unexpected errors
            if PROXY_POOL and proxy_used:
                PROXY_POOL.mark_failed(proxy_used)
            
            continue

    logger.error("❌ All LLM call options failed.")
    return None
