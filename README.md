# GitHub Persona Generator Bot

[![Python Version](https://img.shields.io/badge/Python-3.9+-blue.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

## Overview

This project contains a Telegram bot that generates realistic GitHub developer personas and associated assets (like profile data, activity suggestions, code snippets, and README files) using multiple AI models via LiteLLM Router. It features a Textual TUI for managing the bot process on a server.

## Features

* **Multi-Persona Generation:** Supports various developer archetypes (40+ personas defined).
* **AI Chaining:** Uses a 2-step process (Profile -> Assets) for coherence.
* **Multi-Provider AI:** Leverages `litellm.Router` to select the fastest AI provider (Gemini, Cohere, Mistral, OpenRouter, Fireworks, Hugging Face, Replicate) based on latency.
* **Duplicate Prevention:** Tracks generated names/usernames to avoid repetition.
* **Proxy Support:** Rotates through a list of proxies from `proxy.txt` for AI and Telegram API calls.
* **Telegram Bot Interface:** Interact with the generator via Telegram commands and inline buttons.
* **Gmail Dot Trick:** Includes a utility to generate random Gmail dot trick variations.
* **TUI Controller:** Uses `textual` for a terminal-based UI to start, stop, and refresh the bot worker process, including a live log view.
* **Structured Code:** Refactored into `src/` directory with modules, services, and prompts separated.

## Setup & Usage

1.  **Clone:** `git clone <your-repo-url>`
2.  **Navigate:** `cd <your-repo-name>`
3.  **Create `.env`:** Copy `.env.example` (if provided) or create `.env` and fill in your API keys (Gemini, Cohere, etc.) and Telegram Bot Token/Chat ID.
4.  **Create `data/proxy.txt`:** Add your proxies (format: `http://user:pass@host:port`), one per line.
5.  **Create `data/gmail.txt`:** Add target Gmail addresses for dot trick, one per line.
6.  **Setup Virtual Environment:**
    ```bash
    python3 -m venv venv
    source venv/bin/activate # or venv\Scripts\activate on Windows
    ```
7.  **Install Dependencies:** `pip install -r requirements.txt`
8.  **Run TUI Controller:** `python tui.py`
9.  Inside the TUI, press `1` to start the bot worker.
10. Interact with your bot on Telegram.

## File Structure

autoprofile/ ├── .env # API Keys & Secrets (Not committed) ├── .gitignore # Files ignored by Git ├── README.md # This file ├── data/ │ ├── gmail.txt # Input Gmail list (Not committed) │ └── proxy.txt # Input Proxy list (Not committed) ├── history/ # Generated history (Not committed) │ ├── dot_trick_history.json │ └── persona_history.json ├── logs/ # Log files (Not committed) │ └── app.log ├── requirements.txt # Python dependencies ├── src/ # Source code │ ├── init.py │ ├── bot.py # Telegram bot worker logic │ ├── config.py # Config loading, logging, proxy pool │ ├── modules/ # Specific features │ │ ├── init.py │ │ ├── gmail_trick.py │ │ └── persona_history.py │ ├── prompts/ # AI Prompts │ │ ├── init.py │ │ └── prompts.py │ └── services/ # External service interactions │ ├── init.py │ ├── llm_service.py # AI Router logic │ └── telegram_service.py # Telegram API logic └── tui.py # Main TUI controller entry point


## License

This project is licensed under the MIT License - see the LICENSE file for details (You might want to add a LICENSE file).
