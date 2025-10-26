"""
LLM Package - AI Integration Layer

Menyediakan:
- LLM call options building (multi-provider)
- Core AI caller dengan manual fallback
- Persona generation dengan deduplication
- Utility functions untuk response processing

Entry point: generate_persona_data() di generator.py
"""

# Re-export main functions untuk backward compatibility
from .generator import generate_persona_data
from .caller import call_llm
from .options import llm_call_options
from .utils import clean_ai_response, ai_decide_send_method

# Re-export prompts (loaded di options.py)
from .options import BASE_PERSONA_PROMPT, ASSET_PROMPTS

__all__ = [
    # Main functions
    'generate_persona_data',
    'call_llm',
    
    # Options & prompts
    'llm_call_options',
    'BASE_PERSONA_PROMPT',
    'ASSET_PROMPTS',
    
    # Utilities
    'clean_ai_response',
    'ai_decide_send_method'
]
