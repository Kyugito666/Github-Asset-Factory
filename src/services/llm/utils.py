"""
LLM Utilities - Helper functions untuk AI response processing

Functions:
- clean_ai_response: Extract JSON dari AI response
- ai_decide_send_method: Tentukan send method untuk persona
"""

import logging

logger = logging.getLogger(__name__)


def clean_ai_response(raw_text: str) -> str:
    """
    Clean AI response dan extract JSON.
    
    Handles:
    - Code blocks (```json ... ```)
    - Leading/trailing whitespace
    - Text before/after JSON
    
    Args:
        raw_text: Raw AI response
        
    Returns:
        str: Cleaned JSON string
    """
    text = raw_text.strip()
    cleaned_text = text
    
    # Remove code blocks if present
    if text.startswith("```") and text.endswith("```"):
        lines = text.split('\n')
        if len(lines) > 1:
            # Remove first and last line (``` markers)
            cleaned_text = '\n'.join(lines[1:-1]).strip()
        else:
            # Single line, try to extract between markers
            try:
                first_space = text.index(' ')
                last_ticks = text.rindex('```')
                
                if first_space < last_ticks:
                    cleaned_text = text[first_space + 1:last_ticks].strip()
                else:
                    cleaned_text = text[3:-3].strip()
            except ValueError:
                cleaned_text = text[3:-3].strip()
    
    # Find JSON boundaries
    first_b = cleaned_text.find('{')
    first_s = cleaned_text.find('[')
    last_b = cleaned_text.rfind('}')
    last_s = cleaned_text.rfind(']')
    
    start, end = -1, -1
    
    # Prefer object ({}) over array ([])
    if first_b != -1 and last_b != -1 and first_b < last_b:
        start, end = first_b, last_b
    elif first_s != -1 and last_s != -1 and first_s < last_s:
        start, end = first_s, last_s
    
    if start != -1:
        return cleaned_text[start:end+1]
    
    logger.warning("Could not identify JSON structure.")
    return cleaned_text


def ai_decide_send_method(persona_type: str, has_files: bool) -> str:
    """
    Tentukan method untuk send persona ke Telegram.
    
    Logic:
    - 'text': Jika ada files (kirim sebagai code blocks)
    - 'none': Jika tidak ada files (profile only)
    
    Args:
        persona_type: Tipe persona
        has_files: Apakah ada files untuk dikirim
        
    Returns:
        str: Send method ('text' atau 'none')
    """
    return 'text' if has_files else 'none'
