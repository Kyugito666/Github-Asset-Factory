# 🤖 GitHub Asset Factory

[![Python Version](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://python.org)
[![Status](https://img.shields.io/badge/status-production-success.svg)]()
[![License](https://img.shields.io/badge/license-MIT-green.svg)]()
[![Architecture](https://img.shields.io/badge/architecture-modular-orange.svg)]()

> **AI-Powered GitHub Profile & Asset Generator** dengan kontrol penuh via Telegram Bot. Menghasilkan persona developer realistis, README profesional, code snippets, dan konfigurasi file menggunakan berbagai model AI (Gemini, Groq, Cohere, OpenRouter, dll.) dengan **manual fallback** untuk uptime maksimal.

---

## 📋 Daftar Isi

- [Fitur Utama](#-fitur-utama)
- [Arsitektur Sistem](#-arsitektur-sistem)
- [Prerequisites](#-prerequisites)
- [Instalasi](#-instalasi)
- [Konfigurasi](#-konfigurasi)
  - [Environment Variables](#environment-variables)
  - [Proxy Configuration](#proxy-configuration)
  - [API Keys Setup](#api-keys-setup)
- [Penggunaan](#-penggunaan)
  - [Mode Lokal (TUI)](#1-mode-lokal-tui)
  - [Mode Production (systemd)](#2-mode-production-systemd)
  - [Interaksi via Telegram](#3-interaksi-via-telegram)
- [Struktur Proyek](#-struktur-proyek)
- [Komponen Utama](#-komponen-utama)
- [Troubleshooting](#-troubleshooting)
- [Best Practices](#-best-practices)
- [Changelog](#-changelog)

---

## 🚀 Fitur Utama

### 🎭 **Generasi Persona AI**
- **32+ Tipe Persona**: Explorer, Professional, FullStack Dev, AI Engineer, Security Researcher, dll.
- **Data Profil Realistis**: Username, nama, bio profesional (Bahasa Inggris), lokasi, company, website, social links
- **Global Diversity**: Generator secara otomatis menghasilkan identitas dari berbagai region (Asia, Europe, Americas, Africa)
- **Deduplication System**: Tracking otomatis untuk menghindari duplikasi username/nama
- **Pronoun-Aware**: Mendukung pronoun modern (he/him, she/her, they/them, ask me)

### 📦 **Generasi Aset Pendukung**
- **Profile README.md**: Personal branding dengan struktur profesional
- **Project README.md**: Dokumentasi proyek dengan deskripsi lengkap
- **Code Snippets**: Python, JavaScript, Go, Rust, TypeScript, dll.
- **Config Files**: Docker, Nginx, Terraform, Ansible, dll.
- **Dotfiles**: Shell configs, vim/neovim, git configs

### 🤖 **AI Multi-Provider System**
- **7 Provider Didukung**: Gemini, Groq, Cohere, OpenRouter, Replicate, HuggingFace, Mistral
- **Manual Fallback**: Jika satu model/API key gagal, sistem otomatis mencoba kombinasi lain secara acak
- **40+ Model AI**: Rotasi otomatis untuk optimasi biaya dan uptime
- **Proxy Rotation**: Mendukung proxy pool dengan cooldown mechanism (5 menit)
- **Rate Limit Handling**: Auto-retry dengan exponential backoff

### 📧 **Gmail Dot Trick Generator**
- Generate variasi alamat Gmail unik dengan menambahkan titik (`.`) acak
- History tracking untuk menghindari duplikasi variasi
- Batch processing dari file `data/gmail.txt`
- Format output terstruktur dan mudah di-copy

### 🔄 **Auto Proxy Sync**
- **Background Scheduler**: Auto-sync proxy list setiap minggu (APScheduler)
- **Manual Sync Command**: `/sync_proxies` via Telegram
- **Health Check**: Tes koneksi ke multiple endpoints (ipify.org, httpbin.org)
- **Concurrent Testing**: Multi-threaded proxy validation (10 workers)
- **Backup System**: Auto-backup proxy list sebelum update

### 🖥️ **Dual Interface**
- **TUI Controller** (Textual): Development/debugging dengan real-time log viewer
- **Systemd Service**: Production deployment untuk 24/7 uptime dengan auto-restart

---

## 🏗️ Arsitektur Sistem

```
┌─────────────────────────────────────────────────────────────┐
│                    TELEGRAM BOT INTERFACE                   │
│         (Commands: /start, /sync_proxies, Buttons)          │
└────────────────────────┬────────────────────────────────────┘
                         │
         ┌───────────────┴───────────────┐
         │                               │
         ▼                               ▼
┌─────────────────┐            ┌──────────────────┐
│  PERSONA ENGINE │            │  GMAIL DOT TRICK │
│  (AI Chaining)  │            │    GENERATOR     │
└────────┬────────┘            └──────────────────┘
         │
         ▼
┌─────────────────────────────────────────────────────────────┐
│               LiteLLM MANUAL FALLBACK SYSTEM                │
│  ┌──────────┬──────────┬──────────┬──────────┬──────────┐  │
│  │  Gemini  │   Groq   │  Cohere  │OpenRouter│ Replicate│  │
│  │ (7 models)│(6 models)│(4 models)│(20 models)│(7 models)│  │
│  └──────────┴──────────┴──────────┴──────────┴──────────┘  │
│        ↓ Random Shuffle + Sequential Fallback ↓            │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
         ┌───────────────────────────────┐
         │   PROXY POOL (with Cooldown)  │
         │  • Rotation: Round-robin      │
         │  • Health: 5min cooldown      │
         │  • Backup: Auto-save history  │
         └───────────────┬───────────────┘
                         │
         ┌───────────────┴───────────────┐
         │                               │
         ▼                               ▼
┌─────────────────┐            ┌──────────────────┐
│ HISTORY TRACKER │            │  ASSET GENERATOR │
│  • Persona JSON │            │  • README Files  │
│  • Dot Trick    │            │  • Code Snippets │
└─────────────────┘            └──────────────────┘
```

### **Design Principles**
1. **Separation of Concerns**: Modules, services, prompts terpisah
2. **Fail-Safe Operations**: Graceful degradation pada setiap layer
3. **Thread-Safety**: Async operations untuk TUI dan Telegram
4. **Configuration-Driven**: Semua settings di `.env` dan JSON files
5. **Logging Excellence**: Structured logging dengan level yang tepat

---

## 📦 Prerequisites

### **Sistem Operasi**
- **Linux** (Ubuntu 20.04+, Debian 11+, CentOS 8+) - **Recommended untuk Production**
- **macOS** (12.0+) - Development OK
- **Windows** (10/11 dengan WSL2) - Development dengan batasan

### **Software Requirements**
```bash
# Python 3.10+ (MANDATORY)
python3 --version  # Harus >= 3.10.0

# Git (untuk git pull feature di TUI)
git --version

# Pip & Venv
python3 -m pip --version
python3 -m venv --help
```

### **API Keys** (Minimal 1 Required)
- **Gemini API** - [Google AI Studio](https://makersuite.google.com/app/apikey)
- **Cohere API** - [Cohere Dashboard](https://dashboard.cohere.ai/)
- **OpenRouter API** - [OpenRouter Keys](https://openrouter.ai/keys)
- **Groq API** - [Groq Console](https://console.groq.com/) (Optional, sering suspended)
- **Replicate API** - [Replicate Tokens](https://replicate.com/account/api-tokens)
- **HuggingFace Token** - [HF Settings](https://huggingface.co/settings/tokens)
- **Mistral API** - [Mistral Platform](https://console.mistral.ai/)

### **Telegram Setup**
- **Bot Token**: Buat bot baru via [@BotFather](https://t.me/BotFather)
- **Chat ID**: Dapatkan dari [@userinfobot](https://t.me/userinfobot)

---

## 🔧 Instalasi

### **1. Clone Repository**
```bash
git clone https://github.com/Kyugito666/Github-Asset-Factory.git
cd Github-Asset-Factory
```

### **2. Setup Virtual Environment**
```bash
# Buat venv
python3 -m venv venv

# Aktivasi (Linux/macOS)
source venv/bin/activate

# Aktivasi (Windows - CMD)
venv\Scripts\activate.bat

# Aktivasi (Windows - PowerShell)
venv\Scripts\Activate.ps1
```

### **3. Install Dependencies**
```bash
pip install --upgrade pip
pip install -r requirements.txt
```

**Expected Output:**
```
Successfully installed:
- litellm
- python-telegram-bot
- apscheduler
- textual
- requests
- python-dotenv
- (dan dependencies lainnya)
```

### **4. Verify Installation**
```bash
python -c "import litellm, telegram, textual; print('✅ All imports OK')"
```

---

## ⚙️ Konfigurasi

### **Environment Variables**

Buat file `.env` di root folder proyek:

```bash
# Copy template
cp .env.example .env  # Jika ada, atau buat manual

# Edit dengan editor favorit
nano .env
# atau
vim .env
```

#### **Struktur `.env` Lengkap**
```dotenv
# ============================================================
# AI API KEYS (Minimal 1 Provider WAJIB)
# ============================================================

# Gemini (Google AI) - Multiple keys supported
GEMINI_API_KEY="AIzaSyA...key1,AIzaSyB...key2,AIzaSyC...key3"

# Cohere - Multiple keys supported
COHERE_API_KEY="co_...key1,co_...key2"

# OpenRouter (Free tier available)
OPENROUTER_API_KEY="sk-or-v1-...key1"

# Groq (Optional - sering rate limit)
GROQ_API_KEY="gsk_...key1"

# Replicate
REPLICATE_API_KEY="r8_...key1"

# HuggingFace (Free tier)
HF_API_TOKEN="hf_...token1"

# Mistral AI
MISTRAL_API_KEY="mis_...key1"

# ============================================================
# TELEGRAM CONFIGURATION (WAJIB)
# ============================================================
TELEGRAM_BOT_TOKEN="7426856123:AAH..."
TELEGRAM_CHAT_ID="722XXXXXX"

# ============================================================
# OPTIONAL SETTINGS
# ============================================================
# LOG_FILE="app.log"  # Custom log filename
```

#### **Multi-Key Format**
Untuk provider yang support multiple keys, gunakan format:
```dotenv
# Format 1: Comma-separated (Recommended)
GEMINI_API_KEY="key1,key2,key3"

# Format 2: Numbered suffix
GEMINI_API_KEY="key1"
GEMINI_API_KEY_1="key2"
GEMINI_API_KEY_2="key3"
```

### **Proxy Configuration**

#### **Setup `data/proxy.txt`**
```bash
# Buat file
mkdir -p data
nano data/proxy.txt
```

**Format Proxy:**
```text
# Format 1: Dengan Authentication (Recommended)
http://username:password@proxy.server.com:8080
http://user123:pass456@123.45.67.89:3128

# Format 2: Tanpa Authentication
http://proxy.server.com:8080
http://123.45.67.89:3128

# Format 3: HTTPS Proxy
https://username:password@secure-proxy.com:443

# Komentar (diabaikan)
# Proxy dari provider X
http://user:pass@provider-x.com:8080
```

**❗ PENTING:**
- Satu proxy per baris
- Format `IP:PORT@USER:PASS` dan `USER:PASS@IP:PORT` otomatis di-convert
- Proxy yang gagal akan masuk cooldown 5 menit
- Backup otomatis disimpan di `history/proxy_backup.txt`

#### **Setup API List untuk Auto-Sync** (Opsional)
```bash
nano data/apilist.txt
```

**Format API List:**
```text
# URL API yang return plain text proxy list
https://api.proxyscrape.com/v2/?request=getproxies&protocol=http
https://www.proxy-list.download/api/v1/get?type=http
https://raw.githubusercontent.com/clarketm/proxy-list/master/proxy-list-raw.txt

# API dengan format custom (akan di-parse otomatis)
https://your-custom-proxy-api.com/list.txt
```

### **API Keys Setup**

#### **1. Gemini (Google AI) - RECOMMENDED**
```bash
# Cara Mendapatkan:
# 1. Buka https://makersuite.google.com/app/apikey
# 2. Klik "Create API Key"
# 3. Copy key (format: AIzaSy...)
# 4. Paste ke .env

# Kelebihan:
✅ Free tier generous (1500 req/day)
✅ Model terbaru (Gemini 2.5 Pro/Flash)
✅ Response quality tinggi
✅ Stable uptime
```

#### **2. Cohere - GOOD BALANCE**
```bash
# Cara Mendapatkan:
# 1. Sign up di https://dashboard.cohere.ai/
# 2. Navigate ke API Keys
# 3. Generate Production Key
# 4. Copy key (format: co_...)

# Kelebihan:
✅ Free trial credits
✅ Model multilingual (Aya Expanse)
✅ Good for text generation
```

#### **3. OpenRouter - BEST FREE FALLBACK**
```bash
# Cara Mendapatkan:
# 1. Sign up di https://openrouter.ai/
# 2. Go to Keys section
# 3. Create new key
# 4. Copy (format: sk-or-v1-...)

# Kelebihan:
✅ 20+ free models
✅ Aggregator (akses banyak provider)
✅ Rate limit reasonable
✅ Good uptime
```

---

## 🎮 Penggunaan

### **1. Mode Lokal (TUI)**

**Cocok untuk:**
- Development & debugging
- Testing konfigurasi baru
- Monitoring real-time logs
- Git operations (pull updates)

#### **Menjalankan TUI**
```bash
# Pastikan venv aktif
source venv/bin/activate

# Jalankan TUI
python tui.py
```

#### **TUI Controls**
```
┌─────────────────────────────────────────────────────────┐
│ 🤖 GitHub Asset Bot - TUI Controller                    │
├─────────────────────────────────────────────────────────┤
│ ▶️  Start Server    - Mulai bot worker                  │
│ 🔄 Refresh Server   - Restart (stop + start)            │
│ ⬇️  Git Pull         - Update kode dari GitHub          │
│ 🚪 Exit            - Keluar (auto-stop bot)            │
├─────────────────────────────────────────────────────────┤
│ Keyboard Shortcuts:                                      │
│   ⬆️ / ⬇️  : Navigate buttons                            │
│   [Enter]: Activate button                               │
│   [C]    : Clear log window                              │
│   [Q/Esc]: Quit application                              │
└─────────────────────────────────────────────────────────┘
```

#### **TUI Workflow**
```bash
1. Jalankan: python tui.py
2. Tekan [Enter] pada "▶️ Start Server"
3. Monitor logs di panel kanan
4. Interaksi via Telegram bot
5. Jika butuh update: "⬇️ Git Pull" → "🔄 Refresh Server"
6. Stop: "🚪 Exit" atau [Q]
```

**⚠️ Catatan TUI:**
- TUI hanya untuk lokal, TIDAK cocok untuk VPS headless
- Logs hanya tampil di TUI, tidak tersimpan ke file
- Jika koneksi SSH terputus, bot akan mati

---

### **2. Mode Production (systemd)**

**Cocok untuk:**
- VPS/Cloud deployment (AWS, DigitalOcean, Vultr, dll.)
- 24/7 uptime requirement
- Auto-restart on crash
- Background operation

#### **Setup Systemd Service**

**Step 1: Buat Service File**
```bash
sudo nano /etc/systemd/system/github-asset-bot.service
```

**Step 2: Isi dengan Konfigurasi Ini**
```ini
[Unit]
Description=GitHub Asset Factory Bot Worker (Production)
After=network.target
Wants=network-online.target

[Service]
Type=simple
User=ubuntu
Group=ubuntu
WorkingDirectory=/home/ubuntu/Github-Asset-Factory

# Path ke python di virtual environment
ExecStart=/home/ubuntu/Github-Asset-Factory/venv/bin/python -m src.bot

# Auto-restart policy
Restart=on-failure
RestartSec=10
StartLimitInterval=5min
StartLimitBurst=3

# Environment
Environment="PYTHONUNBUFFERED=1"
Environment="PATH=/home/ubuntu/Github-Asset-Factory/venv/bin:/usr/local/bin:/usr/bin:/bin"

# Security (Optional - Recommended)
NoNewPrivileges=true
PrivateTmp=true

# Logging
StandardOutput=journal
StandardError=journal
SyslogIdentifier=github-asset-bot

[Install]
WantedBy=multi-user.target
```

**📝 PENTING - Sesuaikan Path:**
```bash
# Ganti semua instance dari:
/home/ubuntu/Github-Asset-Factory

# Dengan path absolut folder proyek Anda:
# - Cek dengan: pwd
# - Contoh hasil: /home/youruser/projects/Github-Asset-Factory
```

**Step 3: Reload & Enable Service**
```bash
# Reload systemd
sudo systemctl daemon-reload

# Enable auto-start saat boot
sudo systemctl enable github-asset-bot.service

# Start service
sudo systemctl start github-asset-bot.service
```

#### **Systemd Commands**
```bash
# Cek status
sudo systemctl status github-asset-bot.service

# Lihat logs real-time
sudo journalctl -u github-asset-bot.service -f

# Lihat logs terakhir (50 baris)
sudo journalctl -u github-asset-bot.service -n 50

# Restart service
sudo systemctl restart github-asset-bot.service

# Stop service
sudo systemctl stop github-asset-bot.service

# Disable auto-start
sudo systemctl disable github-asset-bot.service
```

#### **Troubleshooting Systemd**
```bash
# Jika service gagal start
sudo journalctl -u github-asset-bot.service -n 100 --no-pager

# Cek permission issues
ls -la /home/ubuntu/Github-Asset-Factory/venv/bin/python

# Cek .env file readable
ls -la /home/ubuntu/Github-Asset-Factory/.env

# Test manual (debugging)
cd /home/ubuntu/Github-Asset-Factory
source venv/bin/activate
python -m src.bot
```

---

### **3. Interaksi via Telegram**

#### **Command List**
```
/start        - Menampilkan menu keyboard
/info         - Informasi tentang bot
/stats        - Status konfigurasi AI & statistik
/sync_proxies - Update proxy list secara manual (NOW)
```

#### **Keyboard Buttons**
```
┌─────────────────────────────────────────┐
│  🎲 Random       📋 List Persona        │
│  📧 Dot Trick    ℹ️ Info                │
│  📊 Stats                               │
└─────────────────────────────────────────┘
```

#### **Workflow: Generate Persona**
```
1. Buka chat dengan bot Telegram Anda
2. Tekan /start
3. Pilih metode:
   
   A. Random Generation:
      • Tekan "🎲 Random"
      • Bot akan generate persona acak
      • Tunggu 30-60 detik
      • Terima hasil (Profil + Assets)
   
   B. Specific Persona:
      • Tekan "📋 List Persona"
      • Pilih tipe (misal: "Backend Dev")
      • Tunggu processing
      • Terima hasil
```

#### **Workflow: Gmail Dot Trick**
```
1. Siapkan file data/gmail.txt dengan list email
2. Tekan "📧 Dot Trick"
3. Pilih email dari list
4. Bot generate 1 variasi baru
5. Hasil dikirim dalam format:
   
   ✅ Variasi Gmail Baru
   📧 original.email@gmail.com
   🆕 o.riginal.email@gmail.com
```

#### **Workflow: Sync Proxies**
```
1. Siapkan file data/apilist.txt (URL API proxy)
2. Kirim command: /sync_proxies
3. Bot akan:
   • Download dari semua API
   • Convert format
   • Test koneksi (concurrent)
   • Backup proxy lama
   • Update proxy.txt dengan proxy yang working
4. Terima notifikasi hasil:
   ✅ Sync proxy manual OK (45.3s) & pool di-reload!
```

#### **Expected Response Time**
- **Persona Generation**: 30-90 detik (tergantung kompleksitas)
- **Dot Trick**: 2-5 detik
- **Proxy Sync**: 30-120 detik (tergantung jumlah proxy)
- **Stats**: Instant

---

## 📁 Struktur Proyek

```
Github-Asset-Factory/
│
├── 📄 .env                     # Environment variables (SECRET!)
├── 📄 .gitignore               # Git ignore rules
├── 📄 README.md                # Dokumentasi ini
├── 📄 requirements.txt         # Python dependencies
├── 📄 tui.py                   # TUI Controller (Textual)
│
├── 📁 data/                    # Data files
│   ├── gmail.txt               # Gmail list untuk dot trick
│   ├── proxy.txt               # Working proxy list (updated by sync)
│   └── apilist.txt             # API URLs untuk auto proxy download
│
├── 📁 history/                 # History tracking (auto-created)
│   ├── persona_history.json   # Persona yang sudah di-generate
│   ├── dot_trick_history.json # Variasi Gmail yang sudah dibuat
│   ├── proxy_backup.txt       # Backup proxy sebelum sync
│   └── fail_proxy.txt         # Proxy yang gagal saat testing
│
├── 📁 src/                     # Source code utama
│   ├── __init__.py
│   ├── bot.py                 # Main bot worker (entry point)
│   ├── config.py              # Configuration & proxy pool
│   │
│   ├── 📁 modules/            # Business logic modules
│   │   ├── __init__.py
│   │   ├── gmail.py           # Gmail dot trick logic
│   │   ├── persona.py         # Persona history management
│   │   └── proxy.py           # Proxy sync & testing logic
│   │
│   ├── 📁 services/           # External service integrations
│   │   ├── __init__.py
│   │   ├── llm.py             # LiteLLM manual fallback
│   │   ├── models.json        # AI model definitions
│   │   └── telegram.py        # Telegram API wrapper
│   │
│   └── 📁 prompts/            # AI prompt templates
│       ├── __init__.py
│       ├── persona.json       # Base persona prompt
│       └── assets.json        # Asset generation prompts
│
└── 📁 venv/                    # Virtual environment (not in git)
```

---

## 🔍 Komponen Utama

### **1. LiteLLM Manual Fallback (`src/services/llm.py`)**

**Cara Kerja:**
```python
# Pseudocode
llm_call_options = [
    {"provider": "Gemini", "model": "gemini-2.5-pro", "api_key": "key1"},
    {"provider": "Gemini", "model": "gemini-2.5-flash", "api_key": "key2"},
    {"provider": "Cohere", "model": "command-r", "api_key": "key3"},
    # ... 40+ total options
]

def call_llm(prompt):
    # RANDOM SHUFFLE setiap call (distribusi beban)
    shuffled_options = random.sample(llm_call_options, len(llm_call_options))
    
    for option in shuffled_options:
        try:
            response = litellm.completion(**option, messages=[prompt])
            return response  # SUCCESS
        except RateLimitError:
            continue  # Try next
        except AuthError:
            continue  # Try next
        except TimeoutError:
            mark_proxy_failed()
            continue
    
    return None  # All failed
```

**Kelebihan:**
- ✅ High availability (40+ fallback options)
- ✅ Load distribution otomatis (random shuffle)
- ✅ Fail-fast untuk error permanent (auth, bad request)
- ✅ Retry untuk error sementara (rate limit, timeout)

### **2. Proxy Pool dengan Cooldown (`src/config.py`)**

**Fitur:**
```python
class ProxyPool:
    def __init__(self, proxies: List[str]):
        self.proxies = proxies
        self.failed_proxies = {}  # {proxy_url: fail_timestamp}
        self.cooldown_period = 300  # 5 menit
    
    def get_next_proxy(self):
        # Round-robin dengan skip proxy yang masih cooldown
        for proxy in self.proxies:
            if proxy not in self.failed_proxies:
                return proxy
            
            # Cek apakah sudah melewati cooldown
            if time.now() - self.failed_proxies[proxy] > 300:
                del self.failed_proxies[proxy]
                return proxy
        
        # Fallback: Return proxy yang paling lama gagal
        return oldest_failed_proxy
```

**Alur:**
1. Request pertama: Ambil proxy dari pool (round-robin)
2. Jika request gagal: `mark_failed(proxy)` → Masuk cooldown 5 menit
3. Request kedua: Skip proxy yang masih cooldown
4. Setelah 5 menit: Proxy kembali eligible untuk dicoba

### **3. Proxy Sync System (`src/modules/proxy.py`)**

**Pipeline:**
```
┌─────────────┐
│ Download    │ → Dari multiple API URLs
│ from APIs   │   (concurrent downloads)
└──────┬──────┘
       │
       ▼
┌─────────────┐
│ Convert     │ → IP:PORT@USER:PASS → http://USER:PASS@IP:PORT
│ to HTTP     │   Support multiple formats
└──────┬──────┘
       │
       ▼
┌─────────────┐
│ Deduplicate │ → Remove duplicate entries
└──────┬──────┘
       │
       ▼
┌─────────────┐
│ Backup Old  │ → Save current proxy.txt to history/
└──────┬──────┘
       │
       ▼
┌─────────────┐
│ Test Proxy  │ → Concurrent testing (10 workers)
│ (Concurrent)│   Test against ipify.org, httpbin.org
└──────┬──────┘
       │
       ▼
┌─────────────┐
│ Save Working│ → Overwrite proxy.txt with only working proxies
│ Proxies     │   Shuffle order untuk distribusi
└─────────────┘
```

**Konfigurasi Testing:**
```python
PROXY_TIMEOUT = 15      # Detik (per URL check)
MAX_WORKERS = 10        # Concurrent tests
CHECK_URLS = [
    "https://api.ipify.org",
    "http://httpbin.org/ip"
]
```

### **4. APScheduler untuk Auto-Sync (`src/bot.py`)**

**Setup:**
```python
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

scheduler = AsyncIOScheduler(timezone="Asia/Jakarta")

async def scheduled_proxy_sync_task():
    success = await asyncio.to_thread(sync_proxies)
    if success:
        await asyncio.to_thread(reload_proxy_pool)

# Add job di post_init (setelah bot siap)
def setup_bot_commands(app: Application):
    scheduler.add_job(
        scheduled_proxy_sync_task,
        trigger=IntervalTrigger(weeks=1),
        id="weekly_proxy_sync",
        next_run_time=datetime.now()  # Run immediately on start
    )
    scheduler.start()
```

**Keuntungan:**
- ✅ Zero maintenance (auto-update proxy setiap minggu)
- ✅ Non-blocking (async task)
- ✅ Timezone-aware (Asia/Jakarta)
- ✅ Immediate first run (proxy fresh saat bot start)

### **5. Persona History & Deduplication (`src/modules/persona.py`)**

**Data Structure:**
```json
// history/persona_history.json
[
  {
    "username": "jane-dev",
    "name": "Jane Doe"
  },
  {
    "username": "kenji-codes",
    "name": "Kenji Tanaka"
  }
]
```

**Deduplication Logic:**
```python
def generate_persona_data(persona_type: str):
    used_usernames, used_names = load_used_data()  # Set for O(1) lookup
    
    MAX_RETRIES = 3
    for attempt in range(MAX_RETRIES):
        data = call_llm(prompt)
        username = data['username']
        name = data['name']
        
        # Check duplicate
        if username in used_usernames:
            logger.warning(f"Duplicate username: {username}")
            # Inject recent history ke prompt untuk avoid
            recent = load_history_data()[-10:]
            retry_prompt = f"CRITICAL: DO NOT use {username}. Recent: {recent}"
            continue
        
        if name in used_names:
            logger.warning(f"Duplicate name: {name}")
            continue
        
        # Success - save to history
        add_to_history(username, name)
        return data
    
    return None  # Failed after retries
```

### **6. AI Chaining untuk Persona + Assets (`src/services/llm.py`)**

**Two-Step Process:**
```
┌──────────────────────────────────────────────────────────┐
│ STEP 1: Base Persona Generation                         │
│                                                          │
│ Input:  persona_type (e.g., "backend_dev")              │
│ Prompt: persona.json template                           │
│ Output: {                                               │
│   username: "alex-backend",                             │
│   name: "Alex Rodriguez",                               │
│   bio: "Backend engineer specializing in...",           │
│   tech_stack: ["Python", "Go", "PostgreSQL"],          │
│   ...                                                   │
│ }                                                       │
└────────────────────┬─────────────────────────────────────┘
                     │
                     ▼
┌──────────────────────────────────────────────────────────┐
│ STEP 2: Asset Generation (Conditional)                  │
│                                                          │
│ Input:  base_persona_json + persona_type                │
│ Prompt: assets.json[persona_type] template              │
│ Context: Inject base persona sebagai seed               │
│ Output: {                                               │
│   repo_name: "api-toolkit",                             │
│   repo_description: "REST API utilities...",            │
│   files: [                                              │
│     {file_name: "main.py", file_content: "..."},        │
│     {file_name: "README.md", file_content: "..."}       │
│   ]                                                     │
│ }                                                       │
└──────────────────────────────────────────────────────────┘
```

**Kelebihan Chaining:**
- ✅ Consistency (assets synced dengan persona tech_stack)
- ✅ Flexibility (profile-only persona tidak generate assets)
- ✅ Context preservation (base persona jadi seed untuk step 2)

---

## 🐛 Troubleshooting

### **Problem: Bot tidak start di systemd**

**Symptom:**
```bash
sudo systemctl status github-asset-bot
● github-asset-bot.service - GitHub Asset Factory Bot Worker
   Loaded: loaded
   Active: failed (Result: exit-code)
```

**Diagnosis:**
```bash
# Lihat error detail
sudo journalctl -u github-asset-bot.service -n 50

# Common errors:
# 1. "No module named 'src'"
# 2. "Permission denied: .env"
# 3. "TELEGRAM_BOT_TOKEN not found"
```

**Solutions:**

**Error 1: Module not found**
```bash
# Cek WorkingDirectory di service file
sudo nano /etc/systemd/system/github-asset-bot.service

# Harus mengarah ke root folder proyek (tempat src/ berada)
WorkingDirectory=/home/ubuntu/Github-Asset-Factory

# Test manual
cd /home/ubuntu/Github-Asset-Factory
source venv/bin/activate
python -m src.bot  # Harus jalan tanpa error
```

**Error 2: Permission denied**
```bash
# Cek ownership file
ls -la /home/ubuntu/Github-Asset-Factory/.env

# Harus dimiliki oleh user yang run service (ubuntu)
sudo chown ubuntu:ubuntu /home/ubuntu/Github-Asset-Factory/.env
sudo chmod 600 /home/ubuntu/Github-Asset-Factory/.env
```

**Error 3: Config missing**
```bash
# Cek apakah .env exist
ls -la /home/ubuntu/Github-Asset-Factory/.env

# Cek isi minimal
cat /home/ubuntu/Github-Asset-Factory/.env | grep TELEGRAM_BOT_TOKEN

# Jika kosong/tidak ada, buat sesuai panduan Konfigurasi
```

---

### **Problem: Semua LLM call gagal**

**Symptom:**
```
❌ All LLM call options failed.
ERROR: No valid response after 40+ attempts
```

**Diagnosis Checklist:**
```bash
# 1. Cek API keys valid
cat .env | grep API_KEY

# 2. Test API key manual (contoh Gemini)
curl -X POST \
  https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key=YOUR_KEY \
  -H 'Content-Type: application/json' \
  -d '{"contents":[{"parts":[{"text":"Hello"}]}]}'

# 3. Cek proxy (jika digunakan)
cat data/proxy.txt | wc -l  # Harus ada proxy

# 4. Test proxy manual
curl -x http://user:pass@proxy:port https://api.ipify.org
```

**Solutions:**

**Jika API Key Invalid:**
```bash
# Re-generate key dari provider dashboard
# Update .env dengan key baru
nano .env

# Restart bot
sudo systemctl restart github-asset-bot  # systemd
# atau tekan Refresh di TUI
```

**Jika Rate Limit:**
```bash
# Tambah lebih banyak API keys
GEMINI_API_KEY="key1,key2,key3,key4,key5"

# Atau tambah provider baru
COHERE_API_KEY="your_cohere_key"
OPENROUTER_API_KEY="your_openrouter_key"
```

**Jika Proxy Issue:**
```bash
# Sync proxy baru
# Via Telegram: /sync_proxies
# Atau manual:
cd /home/ubuntu/Github-Asset-Factory
source venv/bin/activate
python -c "from src.modules.proxy import sync_proxies; sync_proxies()"
```

---

### **Problem: Proxy sync selalu gagal**

**Symptom:**
```
❌ Sync proxy manual Gagal (120.5s). Cek log.
No working proxies found after testing.
```

**Diagnosis:**
```bash
# Cek data/apilist.txt
cat data/apilist.txt

# Cek apakah API return data
curl -s "https://api.proxyscrape.com/v2/?request=getproxies&protocol=http" | head -n 5

# Cek file hasil download
cat data/proxylist_downloaded.txt | head -n 10
```

**Solutions:**

**Jika API List kosong:**
```bash
nano data/apilist.txt

# Tambahkan URL API reliable:
https://api.proxyscrape.com/v2/?request=getproxies&protocol=http&timeout=10000&country=all&ssl=all&anonymity=all
https://www.proxy-list.download/api/v1/get?type=http
https://raw.githubusercontent.com/clarketm/proxy-list/master/proxy-list-raw.txt
```

**Jika Proxy Quality buruk:**
```bash
# Adjust testing parameters di src/modules/proxy.py
PROXY_TIMEOUT = 20      # Naikkan timeout (dari 15 ke 20)
MAX_WORKERS = 5         # Kurangi concurrency (dari 10 ke 5)
```

**Jika Testing terlalu ketat:**
```bash
# Edit CHECK_URLS di src/modules/proxy.py
CHECK_URLS = [
    "http://httpbin.org/ip",  # Lebih tolerant
    # "https://api.ipify.org"  # Comment yang strict
]
```

---

### **Problem: Gmail Dot Trick tidak generate variasi**

**Symptom:**
```
⚠️ Gagal Generate
📧 user.email@gmail.com
❌ Error/Pendek.
```

**Diagnosis:**
```bash
# Cek panjang username
echo "user.email@gmail.com" | cut -d'@' -f1 | tr -d '.' | wc -c
# Harus >= 2 karakter
```

**Solutions:**

**Jika username terlalu pendek:**
```bash
# Edit data/gmail.txt
# Hapus email dengan username pendek (misal: a@gmail.com)
nano data/gmail.txt

# Valid examples:
john.doe@gmail.com      # ✅ OK (7 chars tanpa dot)
jane@gmail.com          # ✅ OK (4 chars)
ab@gmail.com            # ✅ OK (2 chars - minimal)
a@gmail.com             # ❌ TOO SHORT (1 char)
```

**Jika semua variasi sudah tergenerate:**
```bash
# Cek history
cat history/dot_trick_history.json | jq '.["user.email@gmail.com"]'

# Output: ["u.ser.email@...", "us.er.email@...", ...]
# Jika array panjang (>10), mungkin sudah exhausted

# Solution: Hapus history untuk re-generate
rm history/dot_trick_history.json
# Atau edit manual, hapus entry email tersebut
```

---

### **Problem: TUI tidak menampilkan logs**

**Symptom:**
```
TUI terbuka, tapi panel log tetap kosong setelah start server
```

**Diagnosis:**
```bash
# Cek apakah bot process jalan
ps aux | grep "python -m src.bot"

# Cek manual run (tanpa TUI)
cd /home/ubuntu/Github-Asset-Factory
source venv/bin/activate
python -m src.bot
# Harus tampil logs di terminal
```

**Solutions:**

**Jika bot error tapi silent:**
```bash
# Edit tui.py, tambah stderr redirect
# Baris ~160-an (di start_bot function)

bot_process = subprocess.Popen(
    [sys.executable, "-m", "src.bot"],
    stdout=subprocess.PIPE,
    stderr=subprocess.STDOUT,  # <-- Ini penting, merge stderr ke stdout
    cwd=os.path.dirname(os.path.abspath(__file__))
)
```

**Jika encoding issue:**
```bash
# Jika di Windows/Mac dengan encoding non-UTF8
# Edit tui.py, tambah encoding parameter di log_reader_thread

line = line_bytes.decode('utf-8', errors='replace')  # <-- 'replace' mode
```

---

## 💡 Best Practices

### **1. API Key Management**

**DO ✅:**
```bash
# Multiple keys per provider
GEMINI_API_KEY="key1,key2,key3"  # Load balancing otomatis

# Mix free & paid tiers
GEMINI_API_KEY="free_key1,free_key2"
OPENROUTER_API_KEY="paid_key_with_higher_limit"

# Rotate keys berkala
# Buat script untuk auto-rotate expired keys
```

**DON'T ❌:**
```bash
# Single key (single point of failure)
GEMINI_API_KEY="only_one_key"

# Commit ke Git
git add .env  # NEVER DO THIS!

# Share keys di public channel
# Use secret management (AWS Secrets Manager, etc.) untuk production
```

---

### **2. Proxy Management**

**DO ✅:**
```bash
# Mix proxy types
# - Residential (high success, mahal)
# - Datacenter (fast, cheaper)
# - Free (backup only)

# Auto-sync schedule
# Weekly sync (default) cukup untuk most cases
# Manual sync jika tiba-tiba banyak failure

# Monitor fail_proxy.txt
# Jika >50% proxy gagal, cari provider baru
```

**DON'T ❌:**
```bash
# Pakai free public proxy untuk production
# Quality rendah, sering blacklisted

# Terlalu banyak workers saat testing
MAX_WORKERS = 50  # Overkill, bisa banned oleh test endpoints

# Skip backup
# Selalu backup sebelum sync
```

---

### **3. Bot Deployment**

**DO ✅:**
```bash
# Gunakan systemd untuk production
# Auto-restart on failure
# Log management via journald

# Setup monitoring
# - Uptime checker (UptimeRobot, etc.)
# - Alerting via Telegram/Email jika down

# Regular updates
# Git pull via TUI (development)
# Blue-green deployment untuk production
```

**DON'T ❌:**
```bash
# Run dengan screen/tmux untuk production
# Tidak ada auto-restart, log management sulit

# Expose .env file
# Check permission: chmod 600 .env

# Run as root user
# Gunakan dedicated user dengan limited privileges
```

---

### **4. Cost Optimization**

**Strategy:**
```bash
# 1. Prioritas Free Tier
GEMINI_API_KEY="..."      # 1500 req/day gratis
OPENROUTER_API_KEY="..."  # 20+ free models
HF_API_TOKEN="..."        # Inference API gratis

# 2. Fallback ke Paid hanya jika perlu
# Urutkan di models.json: free models dulu

# 3. Monitor usage
# Check dashboard provider setiap minggu
# Set alert jika mendekati limit

# 4. Cache responses (future enhancement)
# Save hasil generate untuk query serupa
```

**Cost Estimate (Free Tier):**
```
Gemini Free: 1500 requests/day
  → ~45,000 requests/month
  → Cukup untuk ~750 persona/bulan (2 calls per persona)

OpenRouter Free: Rate limit vary per model
  → Backup unlimited (throttled)

Total: $0/month untuk personal use
```

---

### **5. Security Hardening**

**Checklist:**
```bash
# 1. File Permissions
chmod 600 .env                    # Only owner can read
chmod 700 venv/                   # Executable by owner only
chmod 755 src/ data/ history/     # Standard directory permissions

# 2. Git Security
# Verify .gitignore
cat .gitignore | grep .env        # Harus ada

# Check git status sebelum commit
git status | grep .env            # Tidak boleh muncul

# 3. Systemd Security (tambahkan ke service file)
[Service]
NoNewPrivileges=true              # Disable privilege escalation
PrivateTmp=true                   # Isolated /tmp
ReadOnlyPaths=/usr /boot /etc     # Read-only system dirs

# 4. Network Security (jika di VPS)
# Firewall: Only allow SSH + Telegram webhook (optional)
sudo ufw allow 22/tcp
sudo ufw enable

# 5. Secrets Rotation
# Rotate Telegram Bot Token setiap 6 bulan
# Rotate API keys setiap 3 bulan (free tier)
```

---

## 📝 Changelog

### **v19.3 (Current) - Manual Fallback + ProxySync**
**Release Date:** 2025-01-XX

**🎉 New Features:**
- ✨ Manual fallback system (40+ model kombinasi)
- ✨ Proxy pool dengan cooldown mechanism (5 menit)
- ✨ Auto proxy sync (weekly scheduler via APScheduler)
- ✨ Manual proxy sync command (`/sync_proxies`)
- ✨ Git pull feature di TUI
- ✨ Pronoun field di persona generation
- ✨ Global diversity enforcement (non-Indonesian by default)

**🔧 Improvements:**
- ⚡ Random shuffle untuk load distribution
- ⚡ Thread-safe operations di TUI
- ⚡ Better error handling (specific exception types)
- ⚡ Structured logging dengan proper levels
- ⚡ History deduplication dengan O(1) lookup

**🐛 Bug Fixes:**
- 🔥 Fix scheduler RuntimeError (moved to post_init)
- 🔥 Fix proxy pool reload mechanism
- 🔥 Fix social_links formatting di Telegram
- 🔥 Fix username generation (no underscore, no persona type in name)

**📚 Documentation:**
- 📖 Comprehensive README dengan troubleshooting
- 📖 Systemd deployment guide
- 📖 Architecture diagram
- 📖 Best practices section

---

### **v18.x - Router Deprecation**
**Deprecated:** LiteLLM Router (too complex, high maintenance)
**Reason:** Manual fallback lebih flexible & debuggable

---

## 🤝 Contributing

Proyek ini open untuk improvement! Area yang bisa dikembangkan:

**Priority High:**
- [ ] Response caching untuk reduce API calls
- [ ] Webhook mode untuk Telegram (replace polling)
- [ ] Multi-language support untuk persona bio
- [ ] Docker container untuk easier deployment

**Priority Medium:**
- [ ] Web dashboard untuk monitoring
- [ ] Database integration (SQLite/PostgreSQL)
- [ ] Batch generation (multiple persona sekaligus)
- [ ] Export persona ke JSON/CSV

**Priority Low:**
- [ ] Custom persona templates
- [ ] GitHub API integration (auto create repo)
- [ ] Analytics & reporting

**How to Contribute:**
```bash
1. Fork repository
2. Create feature branch: git checkout -b feature/amazing-feature
3. Commit changes: git commit -m 'Add amazing feature'
4. Push to branch: git push origin feature/amazing-feature
5. Open Pull Request
```

---

## 📄 License

MIT License - Free to use, modify, and distribute.

---

## 🙏 Acknowledgments

**Libraries & Tools:**
- [LiteLLM](https://github.com/BerriAI/litellm) - Multi-provider AI abstraction
- [python-telegram-bot](https://github.com/python-telegram-bot/python-telegram-bot) - Telegram Bot API wrapper
- [Textual](https://github.com/Textualize/textual) - Modern TUI framework
- [APScheduler](https://github.com/agronholm/apscheduler) - Advanced scheduler

**AI Providers:**
- Google (Gemini)
- Cohere
- OpenRouter
- Groq
- Replicate
- HuggingFace
- Mistral AI

---

## 📞 Support

**Butuh bantuan?**

1. **Baca Troubleshooting section** di atas terlebih dahulu
2. **Check logs**:
   ```bash
   # Systemd
   sudo journalctl -u github-asset-bot.service -n 100
   
   # TUI
   # Logs di panel kanan
   ```
3. **Create GitHub Issue** dengan info:
   - Python version
   - OS & version
   - Error logs (censor API keys!)
   - Steps to reproduce

**Common Questions:**
- Q: "Bisa pakai Windows?"
  - A: Ya, tapi dengan WSL2. Native Windows support experimental.
  
- Q: "Gratis atau bayar?"
  - A: Bot 100% gratis. API keys provider ada free tier generous.
  
- Q: "Bisa deploy di Heroku/Railway?"
  - A: Theoretically yes, tapi belum tested. Recommended: VPS (AWS EC2, DigitalOcean).

- Q: "Berapa RAM yang dibutuhkan?"
  - A: Minimal 512MB. Recommended 1GB untuk comfortable operation.

---

**Built with ❤️ by Developer Community**

_Last Updated: 2025-01-XX_
