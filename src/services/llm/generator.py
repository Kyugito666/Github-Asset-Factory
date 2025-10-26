"""
LLM Generator - Persona generation dengan AI chaining & deduplication

Main function: generate_persona_data()

Process:
1. Generate base persona dengan deduplication check
2. Retry jika duplicate (max 3x)
3. Generate assets (jika applicable)
4. Combine & return final data
"""

import json
import logging
from typing import Optional, Dict

from ...modules.persona import load_used_data, add_to_history, load_history_data

from .caller import call_llm
from .options import BASE_PERSONA_PROMPT, ASSET_PROMPTS
from .utils import clean_ai_response, ai_decide_send_method

logger = logging.getLogger(__name__)


def generate_persona_data(persona_type: str) -> Optional[Dict]:
    """
    Generate complete persona data dengan AI chaining.
    
    Two-step process:
    Step 1: Base persona generation dengan deduplication check
    Step 2: Asset generation (jika ada template untuk persona type)
    
    Args:
        persona_type: Tipe persona (e.g., "backend_dev", "fullstack_dev")
        
    Returns:
        Optional[Dict]: Complete persona data atau None jika gagal
    """
    logger.info(f"🔄 AI Chaining: '{persona_type}'")
    
    # --- STEP 1: BASE PERSONA (with duplicate check) ---
    used_usernames, used_names = load_used_data()
    logger.info("📝 Step 1: Base Persona (with duplicate check)")
    
    base_prompt = BASE_PERSONA_PROMPT.format(persona_type=persona_type)
    base_data = None
    
    MAX_DUPLICATE_RETRIES = 3
    duplicate_retry_count = 0
    
    while duplicate_retry_count <= MAX_DUPLICATE_RETRIES:
        if duplicate_retry_count > 0:
            logger.info(f"Retrying Step 1 generation (Attempt {duplicate_retry_count})")
            
            # Build retry instruction dengan recent history
            recent_history = load_history_data()[-10:]
            forbidden_names = {h.get('name') for h in recent_history if h.get('name')}
            forbidden_usernames = {h.get('username') for h in recent_history if h.get('username')}
            
            retry_instruction = (
                f"\n\nCRITICAL: DO NOT use name '{name}' or username '{username}'. "
                f"AVOID recent: Names={forbidden_names}, Usernames={forbidden_usernames}. "
                f"Generate COMPLETELY NEW.\n"
            )
            
            current_prompt = BASE_PERSONA_PROMPT.format(persona_type=persona_type) + retry_instruction
        else:
            current_prompt = base_prompt
        
        # Call LLM
        raw_1 = call_llm(current_prompt)
        
        if not raw_1:
            logger.error(f"❌ Step 1 failed (Fallback exhausted)")
            return None
        
        try:
            # Clean & parse response
            cleaned_response = clean_ai_response(raw_1)
            
            if not cleaned_response:
                logger.error(f"❌ Step 1 clean empty. Raw: {raw_1[:100]}...")
                duplicate_retry_count += 1
                continue
            
            data = json.loads(cleaned_response)
            username = data.get('username')
            name = data.get('name')
            
            # Validate required fields
            if not username or not name:
                logger.warning(f"AI no user/name. Retrying... "
                              f"({duplicate_retry_count+1}/{MAX_DUPLICATE_RETRIES})")
                duplicate_retry_count += 1
                continue
            
            # Check duplicates
            duplicate_reason = None
            
            if username in used_usernames:
                duplicate_reason = f"username '{username}'"
            elif name in used_names:
                duplicate_reason = f"name '{name}'"
            
            if duplicate_reason:
                logger.warning(f"DUPLICATE {duplicate_reason} found.")
                duplicate_retry_count += 1
                
                if duplicate_retry_count > MAX_DUPLICATE_RETRIES:
                    logger.error(f"❌ Step 1 FAILED (duplicates persisted).")
                    return None
            else:
                # SUCCESS - No duplicates
                base_data = data
                break
                
        except json.JSONDecodeError as e:
            logger.error(f"❌ Step 1 JSON parse error: {e}. "
                        f"Cleaned: {cleaned_response[:100]}...")
            return None
        except Exception as e:
            logger.error(f"❌ Unexpected Step 1 error: {e}. "
                        f"Raw: {raw_1[:100]}...")
            return None
    
    if not base_data:
        logger.error("❌ Step 1 failed after retries.")
        return None
    
    # Save to history
    add_to_history(base_data.get('username'), base_data.get('name'))
    logger.info(f"✅ Seed: {base_data.get('name')} (@{base_data.get('username')})")
    
    # --- STEP 2: ASSET GENERATION (if applicable) ---
    asset_template = ASSET_PROMPTS.get(persona_type)
    
    if not asset_template:
        logger.info(f"ℹ️ No asset needed.")
        base_data.update({
            "repo_name": None,
            "repo_description": None,
            "files": None,
            "send_method": "none"
        })
        return base_data
    
    logger.info("📄 Step 2: Asset Generation")
    
    # Build asset prompt dengan base persona sebagai context
    asset_prompt = asset_template.format(
        base_persona_json=json.dumps(base_data, indent=2),
        username_dari_konteks=base_data.get('username')
    )
    
    raw_2 = call_llm(asset_prompt)
    
    if not raw_2:
        logger.error("❌ Step 2 failed (Fallback exhausted)")
        return None
    
    try:
        # Clean & parse response
        cleaned_response_2 = clean_ai_response(raw_2)
        
        if not cleaned_response_2:
            logger.error(f"❌ Step 2 clean empty. Raw: {raw_2[:100]}...")
            return None
        
        asset_data = json.loads(cleaned_response_2)
        
        # Validate structure
        is_profile_readme = persona_type in [
            "profile_architect", "ui_ux_designer", "technical_writer_dev",
            "minimalist_dev", "data_viz_enthusiast", "open_source_advocate"
        ]
        
        if "repo_name" not in asset_data and not is_profile_readme:
            logger.error(f"❌ Step 2 JSON invalid: 'repo_name' missing. "
                        f"Cleaned: {cleaned_response_2[:100]}...")
            return None
        
        if "files" not in asset_data or not isinstance(asset_data.get("files"), list):
            logger.error(f"❌ Step 2 JSON invalid: 'files' array missing. "
                        f"Cleaned: {cleaned_response_2[:100]}...")
            return None
        
        logger.info(f"✅ Assets generated for repo '{asset_data.get('repo_name', base_data.get('username'))}'.")
        
    except json.JSONDecodeError as e:
        logger.error(f"❌ Step 2 JSON parse error: {e}. "
                    f"Cleaned: {cleaned_response_2[:100]}...")
        return None
    except Exception as e:
        logger.error(f"❌ Unexpected Step 2 error: {e}. "
                    f"Raw: {raw_2[:100]}...")
        return None
    
    # --- COMBINE & RETURN ---
    final_data = base_data.copy()
    final_data.update(asset_data)
    
    has_files = bool(final_data.get('files'))
    final_data['send_method'] = ai_decide_send_method(persona_type, has_files)
    
    logger.info(f"✅ Complete: '{persona_type}' (Method: {final_data['send_method']})")
    return final_data
