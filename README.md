[![Python Version](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://python.org)
[![Status](https://img.shields.io/badge/status-active-success.svg)]()

AI-Powered GitHub Profile & Asset Generator controlled via Telegram Bot.

## Deskripsi

Project ini bertujuan untuk men-generate data profil developer GitHub yang realistis beserta aset-aset pendukungnya (seperti file README profil/proyek, *code snippets*, *config files*) menggunakan berbagai model AI (*Large Language Models*). Interaksi utama dilakukan melalui bot Telegram, memudahkan *request* pembuatan aset kapan saja.

Fitur utama termasuk *fallback* manual antar berbagai *provider* AI (Gemini, Groq, Cohere, OpenRouter, dll.) untuk memastikan *uptime* dan *chaining prompt* untuk menghasilkan data profil dan aset yang koheren.

## Fitur Utama

* **Generasi Persona AI:** Membuat data profil developer (nama, username unik, bio profesional dalam Bahasa Inggris, info opsional seperti perusahaan, lokasi, *website*, *social links*, *tech stack*).
* **Generasi Aset Terkait:** Secara opsional membuat aset seperti:
    * README.md untuk profil pengguna.
    * README.md untuk proyek baru.
    * *Code snippets* atau *script* dasar (Python, JS, Shell, dll.).
    * File konfigurasi (Docker, Nginx, dll.).
    * Dotfiles.
* **Dukungan Multi-Provider AI:** Menggunakan LiteLLM untuk mengakses berbagai API LLM (Gemini, Groq, Cohere, OpenRouter, Replicate, HuggingFace, Mistral).
* **Fallback Manual:** Jika satu model/API key gagal, sistem akan otomatis mencoba kombinasi model/key lain secara acak hingga berhasil.
* **Interface Bot Telegram:** Kontrol mudah via Telegram:
    * `/start`: Menampilkan menu utama.
    * **🎲 Random:** Generate persona acak.
    * **📋 List Persona:** Pilih tipe persona spesifik dari daftar.
    * **📧 Dot Trick:** Generate variasi alamat Gmail acak (membutuhkan `data/gmail.txt`).
    * **📊 Stats:** Melihat status konfigurasi AI dan statistik Dot Trick.
    * **ℹ️ Info:** Informasi dasar tentang bot.
* **Gmail Dot Trick Generator:** Membuat variasi alamat Gmail unik dengan menambahkan titik (`.`) secara acak.
* **History Tracking:** Menyimpan *history* persona dan variasi dot trick yang sudah di-generate (di folder `history/`) untuk menghindari duplikasi.
* **Konfigurasi Fleksibel:** Pengaturan API Key, Token Bot, dan ID Chat melalui file `.env`.
* **(Opsional) TUI Controller:** Interface `textual` untuk menjalankan dan memonitor bot secara lokal (kurang cocok untuk *deployment* VPS).

## Arsitektur & Teknologi

* **Bahasa:** Python 3.10+
* **AI Abstraction:** LiteLLM
* **Telegram Bot Framework:** `python-telegram-bot`
* **Konfigurasi:** `python-dotenv`
* **HTTP Requests:** `requests`
* **(Opsional) TUI:** `textual`
* **Deployment (Rekomendasi):** `systemd` di Linux (misal Ubuntu di AWS).

## Instalasi

1.  **Clone Repository:**
    ```bash
    git clone [https://github.com/Kyugito666/Github-Asset-Factory.git](https://github.com/Kyugito666/Github-Asset-Factory.git)
    cd Github-Asset-Factory
    ```

2.  **Buat & Aktifkan Virtual Environment:**
    ```bash
    python3 -m venv venv
    source venv/bin/activate 
    # (Di Windows pakai: venv\Scripts\activate)
    ```

3.  **Install Dependencies:**
    ```bash
    pip install -r requirements.txt
    ```

## Konfigurasi

1.  **Buat File `.env`:**
    Di *root* folder proyek (`Github-Asset-Factory`), buat file bernama `.env`. Isi dengan API key dan token Anda. Contoh format:
    ```dotenv
    # --- AI Keys (Wajib ada minimal 1 provider) ---
    GEMINI_API_KEY="AIza...,AIza..." # Bisa multiple, pisahkan koma
    GROQ_API_KEY="gsk_..."
    COHERE_API_KEY="..."
    REPLICATE_API_KEY="r8_..."
    HF_API_TOKEN="hf_..."
    OPENROUTER_API_KEY="sk-or-v1-..."
    MISTRAL_API_KEY="..."
    # FIREWORKS_API_KEY="..." # (Jika ingin ditambahkan kembali)

    # --- Telegram (Wajib) ---
    TELEGRAM_BOT_TOKEN="YOUR_BOT_TOKEN"
    TELEGRAM_CHAT_ID="YOUR_CHAT_ID" # ID User/Grup target pengiriman
    ```
    **PENTING:** Jangan pernah *commit* file `.env` ke Git! Pastikan ada di `.gitignore`.

2.  **Siapkan Folder `data/`:**
    * Buat folder `data` di *root* proyek: `mkdir data`
    * (Opsional) Buat file `data/gmail.txt`. Isi dengan daftar alamat Gmail (satu per baris) yang ingin dibuat variasinya.
    * (Opsional) Buat file `data/proxy.txt`. Isi dengan daftar proxy HTTP/HTTPS (satu per baris, format `http://user:pass@host:port` atau `http://host:port`) jika ingin menggunakan proxy untuk request ke API AI dan Telegram.

3.  **Folder `history/`:** Folder ini akan dibuat otomatis saat pertama kali ada data persona atau dot trick di-generate.

## Penggunaan

### 1. Lokal (Menggunakan TUI)

Cara ini cocok untuk *development* atau *debugging*.

```bash
# Pastikan venv aktif
source venv/bin/activate

# Jalankan TUI Controller
python tui.py 
````

Gunakan tombol di TUI untuk Start/Stop/Refresh server bot atau melakukan Git Pull. Log dari bot akan muncul di panel log TUI.

### 2\. VPS / Background Service (Menggunakan `systemd`) - Rekomendasi

Cara ini membuat bot berjalan 24/7 di *background*, otomatis start saat boot, dan otomatis restart jika *crash*.

1.  **Buat File Service Unit:**

    ```bash
    sudo nano /etc/systemd/system/github-asset-bot.service
    ```

2.  **Isi File Service:**
    Ganti `/path/to/your/Github-Asset-Factory` dengan *path* absolut folder proyek Anda.

    ```ini
    [Unit]
    Description=GitHub Asset Factory Bot Worker (Direct)
    After=network.target

    [Service]
    User=ubuntu # Ganti jika username VPS Anda berbeda
    Group=ubuntu # Ganti jika group VPS Anda berbeda
    WorkingDirectory=/path/to/your/Github-Asset-Factory 
    # Pastikan path ke python di venv benar
    ExecStart=/path/to/your/Github-Asset-Factory/venv/bin/python -m src.bot 
    Restart=on-failure
    Environment="PYTHONUNBUFFERED=1"

    [Install]
    WantedBy=multi-user.target
    ```

3.  **Simpan & Keluar** (`Ctrl+X`, `Y`, `Enter`).

4.  **Reload, Enable, Start:**

    ```bash
    sudo systemctl daemon-reload
    sudo systemctl enable github-asset-bot.service
    sudo systemctl start github-asset-bot.service
    ```

5.  **Cek Status & Log:**

    ```bash
    sudo systemctl status github-asset-bot.service 
    sudo journalctl -u github-asset-bot.service -f # Lihat log real-time (Ctrl+C untuk keluar)
    ```

    Bot akan berjalan di *background*. Interaksi hanya melalui Telegram.

### 3\. Interaksi via Telegram Bot

Setelah bot berjalan (baik via TUI atau `systemd`), buka chat dengan bot Anda di Telegram dan gunakan perintah atau tombol yang tersedia:

  * `/start`: Menampilkan menu keyboard.
  * **Tombol Keyboard:** Gunakan tombol `🎲 Random`, `📋 List Persona`, `📧 Dot Trick`, `📊 Stats`, `ℹ️ Info`.

## Lisensi

(Tambahkan info lisensi jika ada, misal: MIT License)

-----

```
```
