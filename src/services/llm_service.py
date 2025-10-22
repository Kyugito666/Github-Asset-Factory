import litellm
import json
import logging
import random
import time
from typing import Optional, Dict, List

# --- IMPORT DARI DALAM 'src' ---
from ..prompts.prompts import BASE_PERSONA_PROMPT, ASSET_PROMPTS # Naik 1 level (..) lalu ke prompts
from ..config import ( # Naik 1 level (..) lalu ke config
    GEMINI_API_KEYS, GROQ_API_KEYS, COHERE_API_KEYS, REPLICATE_API_KEYS,
    HF_API_TOKENS, OPENROUTER_API_KEYS, MISTRAL_API_KEYS, FIREWORKS_API_KEYS,
    PROXY_POOL
)
from ..modules.persona_history import load_used_data, add_to_history, load_history_data # Naik 1 level (..) lalu ke modules
# --------------------------------

logger = logging.getLogger(__name__)
# litellm.set_verbose = True

# --- SISA KODE llm_service.py (Router Setup, call_llm, generate_persona_data) ---
# --- TIDAK BERUBAH SAMA SEKALI DARI VERSI SEBELUMNYA ---
# ... (copy paste SEMUA kode dari llm_service.py lama dari bagian Router Setup sampai akhir) ...
