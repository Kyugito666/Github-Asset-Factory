"""
Telegram Formatters - Format data untuk Telegram messages

Functions:
- format_profile_message: Format persona profile data
- format_code_message: Format code files sebagai code blocks
"""

import os
from typing import List, Dict, Optional


def format_profile_message(persona_type: str, data: dict) -> str:
    """
    Format persona data sesuai GitHub UI structure.
    
    Field order: username, name, bio, pronouns, website, social_links, company, location
    
    Args:
        persona_type: Tipe persona
        data: Persona data dict
        
    Returns:
        str: Formatted message untuk Telegram
    """
    persona_title = persona_type.replace('_', ' ').title()
    message = f"✅ *Aset Persona Dibuat: {persona_title}*\n\n"
    message += "*--- PROFIL DATA ---*\n"

    # Field order sesuai GitHub UI
    profile_order = ["username", "name", "bio", "pronouns", "website", "social_links", "company", "location"]

    for key in profile_order:
        value = data.get(key)
        display_key = key.replace('_', ' ').title()

        if value is None or value == "":
            display_value = "_kosong_"
        elif key == "social_links":
            if isinstance(value, dict) and any(value.values()):
                social_lines = []
                link_count = 0
                
                for platform, link in value.items():
                    if link and link_count < 4:
                        # Format platform name
                        platform_display = platform.replace('_', ' ').title()
                        if platform_display == 'Twitter':
                            platform_display = 'X (Twitter)'
                        if platform_display == 'Dev To':
                            platform_display = 'Dev.to'
                        if platform_display == 'Stackoverflow':
                            platform_display = 'Stack Overflow'
                        
                        social_lines.append(f"  • *{platform_display}:* `{link}`")
                        link_count += 1
                
                if social_lines:
                    message += f"*{display_key}:*\n" + "\n".join(social_lines) + "\n"
                else:
                    message += f"*{display_key}:* _kosong_\n"
                continue
            else:
                display_value = "_kosong_"
        elif isinstance(value, str):
            display_value = f"`{value}`"
        else:
            display_value = f"`{str(value)}`"

        if key != "social_links":
            message += f"*{display_key}:* {display_value}\n"

    # Activity List
    activity_list: Optional[List[str]] = data.get('activity_list')
    if activity_list:
        message += "\n*--- SARAN AKTIVITAS ---*\n"
        for i, activity in enumerate(activity_list, 1):
            message += f"*{i}.* {activity}\n"

    # Repo Info
    repo_name = data.get('repo_name')
    if repo_name:
        if activity_list:
            message += "\n"
        message += f"\n*--- REPO TARGET ---*\n"
        message += f"📁 `{repo_name}`\n"
        
        repo_description = data.get('repo_description')
        if repo_description:
            message += f"📝 `{repo_description}`\n"

    return message


def format_code_message(file_name: str, file_content: str, max_length: int = 3500) -> str:
    """
    Format code file sebagai Telegram code block.
    
    Args:
        file_name: Nama file (untuk detect language)
        file_content: Isi file
        max_length: Max length sebelum truncate
        
    Returns:
        str: Formatted code block message
    """
    # Extension to language mapping
    ext_to_lang = {
        '.py': 'python', '.js': 'javascript', '.sh': 'bash', '.go': 'go',
        '.rs': 'rust', '.rb': 'ruby', '.php': 'php', '.java': 'java',
        '.cpp': 'cpp', '.c': 'c', '.ts': 'typescript', '.yml': 'yaml',
        '.yaml': 'yaml', '.json': 'json', '.md': 'markdown', '.txt': 'text',
        '.conf': 'nginx', '.Dockerfile': 'dockerfile', '.tf': 'terraform',
        '.ipynb': 'json'
    }
    
    ext = os.path.splitext(file_name)[1]
    lang = ext_to_lang.get(ext, 'text')
    
    content = file_content
    if len(content) > max_length:
        content = content[:max_length] + "\n\n... (truncated)"
    
    # Wrap filename dengan backtick agar bisa di-copy
    message = f"📄 *File:* `{file_name}`\n\n```{lang}\n{content}\n```"
    
    return message
