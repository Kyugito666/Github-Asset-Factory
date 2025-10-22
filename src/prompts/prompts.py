"""
Prompts untuk AI Chaining (2-Step Generation)
File ini sekarang ada di src/prompts/
"""

# ============================================================
# BASE PERSONA PROMPT (Step 1)
# ============================================================
BASE_PERSONA_PROMPT = """
You are an expert developer identity generator.
Your task is to create ONE realistic, coherent, and SYNCED developer identity based on the requested persona type, including suggested GitHub activities in Indonesian.

CRITICAL RULES:
1.  **MANDATORY FIELDS:** 'name', 'username', 'bio' MUST always be filled and synced.
2.  **BIO LANGUAGE:** The 'bio' field MUST ALWAYS be in professional ENGLISH.
3.  **OPTIONAL FIELDS:** 'company', 'location', 'website', 'social links', 'tech_stack', 'activity_list' MUST BE RANDOMLY filled or left 'null'.
4.  **RULE OF THUMB (BALANCE & PERSONA):** Use 'null' for SOME optional fields, BUT the number of filled fields should roughly match the persona's expected activity level. Active/Professional personas should have MORE filled fields than passive ones.
5.  **NAME:** Must be a realistic full name.
6.  **USERNAME:** MUST be a creative, lowercase GitHub username. DO NOT use the persona type itself (e.g., 'readme_pro') in the username.
7.  **LOCATION (if filled):** MUST be a REAL geographical location (City, Country). DO NOT use "Remote". Often leave 'null'.
8.  **WEBSITE (if filled):** MUST be 'null' or a professional URL. Fill more often for active/professional/designer/advocate personas.
9.  **SOCIAL LINKS (if filled):** MUST be 'null' or a valid URL synced with the 'username'. Examples: linkedin, twitter, dev_to, medium, gitlab, bitbucket, stackoverflow, reddit, youtube, twitch.
10. **CRITICAL (SOCIALS - Persona Aware, Max 5):** Randomly pick 0-5 social links based on persona:
    * Highly Active/Public ('professional', 'socialite', 'polymath_dev', 'ui_ux_designer', 'open_source_advocate', 'fullstack_dev', 'technical_writer_dev', 'community_helper', 'framework_maintainer'): Aim for 3-5 links. LinkedIn, Website/Portfolio likely.
    * Mid-Activity/Specialist ('project_starter', 'uploader', 'readme_pro', 'profile_architect', 'config_master', 'data_scientist', 'dotfiles_enthusiast', 'explorer', 'forker', 'niche_guy', 'backend_dev', 'frontend_dev', 'mobile_dev_android', 'security_researcher', 'ai_ml_engineer', 'polyglot_tool_builder', 'minimalist_dev', 'data_viz_enthusiast', 'cloud_architect_aws', 'database_admin', 'network_engineer', 'game_developer', 'embedded_systems_dev', 'performance_optimizer', 'api_designer', 'issue_reporter'): Aim for 1-3 links.
    * Passive/Observational ('ghost', 'lurker', 'securer', 'student_learner', 'code_collector', 'organization_member'): Aim for 0-1 link.
    Ensure VARIETY. Don't always pick the same links.
11. **ACTIVITY LIST (OPTIONAL, INDONESIAN):** Generate a list of 0-2 suggested, realistic PERSONAL GitHub activities in INDONESIAN, synced with persona. For activity-focused personas ('issue_reporter', 'community_helper', 'code_collector'), ensure activities match their focus.
12. **CRITICAL (ACTIVITY - Simple & Personal):** Use simple, personal actions (star, fork, follow, update profile, new repo, gist, explore, commit to personal/fork, report issue, comment). Must be in INDONESIAN. Often leave 'null' for most personas.
13. **TECH STACK (if filled):** Pick 3-5 relevant technologies (for context, not displayed directly). Often leave 'null'. Ensure stack aligns with specific roles (e.g., AWS for `cloud_architect_aws`, SQL/NoSQL for `database_admin`, C++/Unity for `game_developer`, C/Rust for `embedded_systems_dev`, testing libs for `performance_optimizer`, OpenAPI/GraphQL for `api_designer`).

TASK: Generate an identity for a '{persona_type}' persona.

Generate ONLY JSON. No opening or closing text.

JSON Format (Example):
{{
  "name": "...", "username": "...",
  "bio": "Professional bio in ENGLISH...",
  "company": "...", "location": "...", "website": "...",
  "linkedin": "...", "twitter": "...", "dev_to": "...", "medium": null, ...,
  "activity_list": ["Aktivitas dalam Bahasa Indonesia...", "..."],
  "tech_stack": ["...", "..."]
}}
"""

# ============================================================
# ASSET PROMPTS (Step 2)
# ============================================================
ASSET_PROMPTS = {

    # --- Kategori Generalist & Foundational ---
    "project_starter": """Developer Context (Seed): {base_persona_json}\nTask: 1. Create starter file synced w/ 'tech_stack'. 2. Create simple README.md (title + brief ENGLISH description). 3. Generate short ENGLISH `repo_description`.\nGenerate JSON: {{ "repo_name": "simple-starter", "repo_description": "A basic starter template...", "files": [ {{ "file_name": "starter.ext", "file_content": "..." }}, {{ "file_name": "README.md", "file_content": "# simple-starter\\n\\nBrief ENGLISH description..." }} ] }}""",
    "fullstack_dev": """Developer Context (Seed): {base_persona_json}\nTask: Fullstack ('tech_stack' has frontend+backend). 1. Choose ONE side (FE or BE). 2. Create ONE small code file for that side. 3. Create repo_name like "fs-demo-[side]". 4. Generate short ENGLISH `repo_description`. 5. Create simple README.md (title + brief ENGLISH desc mentioning fullstack capability).\nGenerate JSON: {{ "repo_name": "fs-demo-...", "repo_description": "Short ENGLISH repo description...", "files": [ {{...}}, {{ "file_name": "README.md", "file_content": "# fs-demo-...\\n\\nBrief ENGLISH description..." }} ] }}""",
    "polymath_dev": """Developer Context (Seed): {base_persona_json}\nTask: Broad skills ('tech_stack' diverse). 1. Choose ONE area from 'tech_stack' (or Python default). 2. Create ONE small code file for that area. 3. Create repo_name like "poly-demo-[area]". 4. Generate short ENGLISH `repo_description`. 5. Create simple README.md (title + brief ENGLISH desc hinting broader skills).\nGenerate JSON: {{ "repo_name": "poly-demo-...", "repo_description": "Short ENGLISH repo description...", "files": [ {{...}}, {{ "file_name": "README.md", "file_content": "# poly-demo-...\\n\\nBrief ENGLISH description..." }} ] }}""",
    # explorer, professional, student_learner: No asset prompt needed

    # --- Kategori Kontribusi & Interaksi ---
    "open_source_advocate": """Developer Context (Seed): {base_persona_json}\nTask: Create ONLY a **profile README.md highlighting open source involvement (content generally in ENGLISH)**. Sections for contributions, etc. Link contributions. No `repo_description`.\nGenerate JSON: {{ "repo_name": "{username_dari_konteks}", "files": [ {{ "file_name": "README.md", "file_content": "OS Advocate ENGLISH README..." }} ] }}""",
    # forker, socialite, issue_reporter, community_helper: No asset prompt needed

    # --- Kategori Spesialis README & Visual ---
    "readme_pro": """Developer Context (Seed): {base_persona_json}\nTask: Create HIGHLY professional project README.md (in ENGLISH) synced w/ 'tech_stack'. 1. Create repo_name. 2. Generate short ENGLISH `repo_description`. 3. Write full README file.\nGenerate JSON: {{ "repo_name": "pro-readme", "repo_description": "Short ENGLISH repo description...", "files": [ {{ "file_name": "README.md", "file_content": "Complete professional ENGLISH README..." }} ] }}""",
    "profile_architect": """Developer Context (Seed): {base_persona_json}\nTask: Create ONLY the profile README.md (content generally in ENGLISH). Focus on structure. No `repo_description`.\nGenerate JSON: {{ "repo_name": "{username_dari_konteks}", "files": [ {{ "file_name": "README.md", "file_content": "Profile README content, likely ENGLISH..." }} ] }}""",
    "ui_ux_designer": """Developer Context (Seed): {base_persona_json}\nTask: Create ONLY a **visually appealing profile README.md (content generally in ENGLISH)**. Focus on aesthetics, tools (Figma?), projects. Use Markdown creatively. No `repo_description`.\nGenerate JSON: {{ "repo_name": "{username_dari_konteks}", "files": [ {{ "file_name": "README.md", "file_content": "Visually rich ENGLISH README..." }} ] }}""",
    "technical_writer_dev": """Developer Context (Seed): {base_persona_json}\nTask: Create ONLY a **clear, well-structured profile README.md (content in ENGLISH)**. Focus on clarity, organization, concise language. No `repo_description`.\nGenerate JSON: {{ "repo_name": "{username_dari_konteks}", "files": [ {{ "file_name": "README.md", "file_content": "Well-written ENGLISH README..." }} ] }}""",
    "minimalist_dev": """Developer Context (Seed): {base_persona_json}\nTask: Create ONLY a **clean, simple, minimalist profile README.md (content generally in ENGLISH)**. Focus on whitespace, minimal elements, elegance. No `repo_description`.\nGenerate JSON: {{ "repo_name": "{username_dari_konteks}", "files": [ {{ "file_name": "README.md", "file_content": "Minimalist ENGLISH README..." }} ] }}""",
    "data_viz_enthusiast": """Developer Context (Seed): {base_persona_json}\nTask: Create ONLY a **profile README.md incorporating data visualizations (content generally in ENGLISH)**. Embed stats creatively. No `repo_description`.\nGenerate JSON: {{ "repo_name": "{username_dari_konteks}", "files": [ {{ "file_name": "README.md", "file_content": "Data-Viz ENGLISH README..." }} ] }}""",

    # --- Kategori Spesialis Kode & Script Dasar ---
    "uploader": """Developer Context (Seed): {base_persona_json}\nTask: 1. Create utility script synced w/ 'tech_stack'. 2. Create simple README.md (title + brief ENGLISH description). 3. Generate short ENGLISH `repo_description`.\nGenerate JSON: {{ "repo_name": "utils", "repo_description": "Short ENGLISH repo description...", "files": [ {{...}}, {{ "file_name": "README.md", "file_content": "# utils\\n\\nBrief ENGLISH description..." }} ] }}""",
    "backend_dev": """Developer Context (Seed): {base_persona_json}\nTask: 1. Create basic API endpoint file synced w/ 'tech_stack'. 2. Create simple README.md (title + brief ENGLISH description). 3. Generate short ENGLISH `repo_description`.\nGenerate JSON: {{ "repo_name": "api-service", "repo_description": "Short ENGLISH repo description...", "files": [ {{...}}, {{ "file_name": "README.md", "file_content": "# api-service\\n\\nBrief ENGLISH description..." }} ] }}""",
    "frontend_dev": """Developer Context (Seed): {base_persona_json}\nTask: 1. Create basic component file synced w/ 'tech_stack'. 2. Create simple README.md (title + brief ENGLISH description). 3. Generate short ENGLISH `repo_description`.\nGenerate JSON: {{ "repo_name": "ui-kit", "repo_description": "Short ENGLISH repo description...", "files": [ {{...}}, {{ "file_name": "README.md", "file_content": "# ui-kit\\n\\nBrief ENGLISH description..." }} ] }}""",
    "mobile_dev_android": """Developer Context (Seed): {base_persona_json}\nTask: 1. Create Kotlin/XML snippet. 2. Create simple README.md (title + brief ENGLISH description). 3. Generate short ENGLISH `repo_description`.\nGenerate JSON: {{ "repo_name": "android-kit", "repo_description": "Short ENGLISH repo description...", "files": [ {{...}}, {{ "file_name": "README.md", "file_content": "# android-kit\\n\\nBrief ENGLISH description..." }} ] }}""",
    "ai_ml_engineer": """Developer Context (Seed): {base_persona_json}\nTask: 1. Create simple Python ML/data script synced w/ 'tech_stack'. 2. Create simple README.md (title + brief ENGLISH description). 3. Generate short ENGLISH `repo_description`.\nGenerate JSON: {{ "repo_name": "ml-lab", "repo_description": "Short ENGLISH repo description...", "files": [ {{...}}, {{ "file_name": "README.md", "file_content": "# ml-lab\\n\\nBrief ENGLISH description..." }} ] }}""",
    "data_scientist": """Developer Context (Seed): {base_persona_json}\nTask: 1. Create Python data script. 2. Create simple README.md (title + brief ENGLISH description). 3. Generate short ENGLISH `repo_description`.\nGenerate JSON: {{ "repo_name": "data-scripts", "repo_description": "Short ENGLISH repo description...", "files": [ {{...}}, {{ "file_name": "README.md", "file_content": "# data-scripts\\n\\nBrief ENGLISH description..." }} ] }}""",

    # --- Kategori Spesialis Infrastruktur & DevOps ---
    "config_master": """Developer Context (Seed): {base_persona_json}\nTask: 1. Create config file synced w/ 'tech_stack'. 2. Create simple README.md (title + brief ENGLISH description). 3. Generate short ENGLISH `repo_description`.\nGenerate JSON: {{ "repo_name": "configs", "repo_description": "Short ENGLISH repo description...", "files": [ {{...}}, {{ "file_name": "README.md", "file_content": "# configs\\n\\nBrief ENGLISH description..." }} ] }}""",
    "dotfiles_enthusiast": """Developer Context (Seed): {base_persona_json}\nTask: 1. Create dotfile synced w/ 'tech_stack'. 2. Create simple README.md (title + brief ENGLISH description). 3. Generate short ENGLISH `repo_description`.\nGenerate JSON: {{ "repo_name": "dotfiles", "repo_description": "Short ENGLISH repo description...", "files": [ {{...}}, {{ "file_name": "README.md", "file_content": "# Dotfiles\\n\\nBrief ENGLISH description..." }} ] }}""",
    "cloud_architect_aws": """Developer Context (Seed): {base_persona_json}\nTask: AWS Cloud Architect. 1. Create simple IaC snippet (Terraform default). 2. Create simple README.md (title + brief ENGLISH description). 3. Generate short ENGLISH `repo_description`.\nGenerate JSON: {{ "repo_name": "aws-iac-examples", "repo_description": "Short ENGLISH repo description...", "files": [ {{...}}, {{ "file_name": "README.md", "file_content": "# aws-iac-examples\\n\\nBrief ENGLISH description..." }} ] }}""",
    "database_admin": """Developer Context (Seed): {base_persona_json}\nTask: DB Admin. 1. Create simple SQL script snippet (PostgreSQL default). 2. Create simple README.md (title + brief ENGLISH description). 3. Generate short ENGLISH `repo_description`.\nGenerate JSON: {{ "repo_name": "db-scripts", "repo_description": "Short ENGLISH repo description...", "files": [ {{...}}, {{ "file_name": "README.md", "file_content": "# db-scripts\\n\\nBrief ENGLISH description..." }} ] }}""",
    "network_engineer": """Developer Context (Seed): {base_persona_json}\nTask: Network Engineer. 1. Create generic config snippet. 2. Create simple README.md (title + brief ENGLISH description). 3. Generate short ENGLISH `repo_description`.\nGenerate JSON: {{ "repo_name": "network-configs", "repo_description": "Short ENGLISH repo description...", "files": [ {{...}}, {{ "file_name": "README.md", "file_content": "# network-configs\\n\\nBrief ENGLISH description..." }} ] }}""",

    # --- Kategori Spesialis Kode & Script Lanjutan ---
    "polyglot_tool_builder": """Developer Context (Seed): {base_persona_json}\nTask: 1. Create TWO utility scripts in DIFFERENT languages from 'tech_stack' (or Py/Bash default). 2. Create simple README.md (title + brief ENGLISH description). 3. Generate short ENGLISH `repo_description`.\nGenerate JSON: {{ "repo_name": "poly-tools", "repo_description": "Short ENGLISH repo description...", "files": [ {{...}}, {{...}}, {{ "file_name": "README.md", "file_content": "# poly-tools\\n\\nBrief ENGLISH description..." }} ] }}""",
    "game_developer": """Developer Context (Seed): {base_persona_json}\nTask: Game Dev. 1. Create code snippet (C# default). 2. Create simple README.md (title + brief ENGLISH description). 3. Generate short ENGLISH `repo_description`.\nGenerate JSON: {{ "repo_name": "game-dev-snippets", "repo_description": "Short ENGLISH repo description...", "files": [ {{...}}, {{ "file_name": "README.md", "file_content": "# game-dev-snippets\\n\\nBrief ENGLISH description..." }} ] }}""",
    "embedded_systems_dev": """Developer Context (Seed): {base_persona_json}\nTask: Embedded Dev. 1. Create code snippet (C default). 2. Create simple README.md (title + brief ENGLISH description). 3. Generate short ENGLISH `repo_description`.\nGenerate JSON: {{ "repo_name": "embedded-snippets", "repo_description": "Short ENGLISH repo description...", "files": [ {{...}}, {{ "file_name": "README.md", "file_content": "# embedded-snippets\\n\\nBrief ENGLISH description..." }} ] }}""",
    "framework_maintainer": """Developer Context (Seed): {base_persona_json}\nTask: Framework Maintainer. 1. Create code example for framework internal/contribution. 2. Create simple README.md (title + brief ENGLISH description). 3. Generate short ENGLISH `repo_description`.\nGenerate JSON: {{ "repo_name": "framework-example", "repo_description": "Short ENGLISH repo description...", "files": [ {{...}}, {{ "file_name": "README.md", "file_content": "# framework-example\\n\\nBrief ENGLISH description..." }} ] }}""",
    "performance_optimizer": """Developer Context (Seed): {base_persona_json}\nTask: Performance Optimizer. 1. Create benchmarking script snippet (Python default). 2. Create simple README.md (title + brief ENGLISH description). 3. Generate short ENGLISH `repo_description`.\nGenerate JSON: {{ "repo_name": "perf-benchmarks", "repo_description": "Short ENGLISH repo description...", "files": [ {{...}}, {{ "file_name": "README.md", "file_content": "# perf-benchmarks\\n\\nBrief ENGLISH description..." }} ] }}""",
    "api_designer": """Developer Context (Seed): {base_persona_json}\nTask: API Designer. 1. Create API definition snippet (OpenAPI default). 2. Create simple README.md (title + brief ENGLISH description). 3. Generate short ENGLISH `repo_description`.\nGenerate JSON: {{ "repo_name": "api-design", "repo_description": "Short ENGLISH repo description...", "files": [ {{...}}, {{ "file_name": "README.md", "file_content": "# api-design\\n\\nBrief ENGLISH description..." }} ] }}""",

    # --- Kategori Pasif & Observasi ---
    # ghost, lurker, securer, code_collector, organization_member: No asset prompt needed

    # --- Kategori Lainnya ---
    "security_researcher": """Developer Context (Seed): {base_persona_json}\nTask: 1. Create simple security script synced w/ 'tech_stack'. 2. Create simple README.md (title + brief ENGLISH description + Disclaimer). 3. Generate short ENGLISH `repo_description`.\nGenerate JSON: {{ "repo_name": "sec-lab", "repo_description": "Short ENGLISH repo description...", "files": [ {{...}}, {{ "file_name": "README.md", "file_content": "# sec-lab\\n\\nBrief ENGLISH description...\\n**Disclaimer:** Use responsibly." }} ] }}""",
    # niche_guy: No asset prompt needed

} # <-- AKHIR DARI DICTIONARY ASSET_PROMPTS
