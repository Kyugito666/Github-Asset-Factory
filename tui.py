#!/usr/bin/env python3
"""
GitHub Asset Bot - TUI Controller (Entry Point)
"""
import sys
import os
import time
import subprocess
import threading
import logging
from collections import deque
from typing import Optional

# --- IMPORT DARI 'src' SEKARANG ---
try:
    # Panggil setup logging lebih awal dari config di src
    # Ini penting agar logger siap sebelum import lain
    # (Asumsikan struktur folder sudah benar)
    project_root = os.path.dirname(os.path.abspath(__file__))
    src_path = os.path.join(project_root, 'src')
    if src_path not in sys.path:
        sys.path.insert(0, src_path)

    from config import setup_logging
    setup_logging(is_controller=True) # TUI adalah controller
    logger = logging.getLogger(__name__) # Setup logger setelah setup_logging
except ImportError as e:
    print(f"Fatal Error: Could not import 'setup_logging' from 'src.config'.")
    print(f"Ensure the directory structure is correct (tui.py in root, src/ folder exists with config.py).")
    print(f"Import Error: {e}")
    sys.exit(1)
# ---------------------------------

try:
    from textual.app import App, ComposeResult
    from textual.widgets import Header, Footer, Static, Log, Button
    from textual.containers import Horizontal, Vertical
    from textual.reactive import reactive
except ImportError:
    # Gunakan logger yang sudah di-setup
    logger.critical("Library 'textual' not found. Please install: pip install textual")
    sys.exit(1)

# --- Variabel Global TUI (Tidak berubah) ---
bot_process: Optional[subprocess.Popen] = None
log_thread: Optional[threading.Thread] = None
log_thread_stop_event = threading.Event()

# --- Fungsi log_reader_thread (Tidak berubah) ---
def log_reader_thread(stdout_pipe, stop_event, app_instance):
    """Membaca output subprocess dan mengirim ke TUI."""
    try:
        # iter(readline, b'') lebih aman daripada loop biasa
        for line_bytes in iter(stdout_pipe.readline, b''):
            if stop_event.is_set():
                break # Stop jika diminta

            # Decode dengan error handling
            line = line_bytes.decode('utf-8', errors='replace').strip()

            if line:
                # Kirim ke TUI via method thread-safe
                app_instance.call_from_thread(app_instance.add_log_line, line)

    except Exception as e:
        # Log error jika terjadi saat membaca pipe
        if not stop_event.is_set(): # Jangan log error jika memang sengaja di-stop
            error_line = f"[Log Thread Error] {type(e).__name__}: {e}"
            # Gunakan logger TUI dan kirim ke TUI juga
            logger.error(error_line)
            try:
                # Coba kirim error ke TUI, mungkin gagal jika TUI sudah exit
                app_instance.call_from_thread(app_instance.add_log_line, error_line)
            except Exception:
                pass # Abaikan jika TUI sudah tidak ada
    finally:
        # Pastikan pipe ditutup saat thread selesai
        try:
            stdout_pipe.close()
        except Exception:
            pass # Abaikan error saat menutup pipe yang mungkin sudah ditutup
        try:
            # Beri tahu TUI bahwa thread log sudah berhenti
            app_instance.call_from_thread(app_instance.add_log_line, "[TUI] Log reader thread stopped.")
        except Exception:
            pass # Abaikan jika TUI sudah tidak ada


# --- Class TuiApp (Subprocess path diubah) ---
class TuiApp(App):
    """Aplikasi TUI untuk Bot Controller"""

    CSS = """
    Screen { layout: vertical; overflow: hidden; }
    Header { dock: top; } Footer { dock: bottom; }
    #main-container { layout: horizontal; height: 100%; }
    #menu-panel { width: 35; height: 100%; border-right: solid white; padding: 1; overflow-y: auto; }
    #log-panel { width: 1fr; height: 100%; } Log { height: 100%; width: 100%; }
    Button { width: 100%; margin: 1 0; }
    """
    BINDINGS = [
        ("q", "quit_app", "Exit"),
        ("escape", "quit_app", "Exit"),
        ("c", "clear_log", "Clear Log"),
        ("down", "focus_next_button", "Next"),
        ("up", "focus_prev_button", "Prev"),
    ]

    is_running = reactive(False) # Status bot worker

    def __init__(self):
        super().__init__()
        self.status_widget = Static("STATUS: ❌ STOPPED\n\nPID: -", id="status-widget")
        self.log_widget = Log(max_lines=1000, id="log-widget", auto_scroll=True)

    def compose(self) -> ComposeResult:
        """Buat layout widget"""
        yield Header(name="🤖 GitHub Asset Bot - TUI Controller")
        with Horizontal(id="main-container"):
            with Vertical(id="menu-panel"):
                yield Button("▶️ Start Server", id="btn_start_stop", variant="success")
                yield Button("🔄 Refresh Server", id="btn_refresh", variant="default")
                yield Button("🚪 Exit", id="btn_exit", variant="error")
                yield Static("\n" + ("-" * 25))
                yield self.status_widget
                yield Static("\nUse ⬆️ / ⬇️ + [Enter]")
                yield Static("Press [C] to Clear Log")
                yield Static("Press [Q] or [Esc] to Quit")
            with Vertical(id="log-panel"):
                yield self.log_widget
        yield Footer()

    def on_mount(self) -> None:
        """Dipanggil saat app pertama kali running"""
        self.add_log_line("[TUI] Controller TUI loaded.")
        self.add_log_line("[TUI] Use Arrow keys + Enter to navigate buttons.")
        self.query_one(Button).focus() # Fokus ke tombol pertama

    def watch_is_running(self, running: bool) -> None:
        """Update status widget DAN label tombol saat 'self.is_running' berubah"""
        global bot_process
        try:
            btn_start_stop = self.query_one("#btn_start_stop", Button)
        except Exception: # Widget mungkin belum siap saat awal
             return

        if running and bot_process:
            status = f"STATUS: ✅ RUNNING\n\nPID: {bot_process.pid}"
            btn_start_stop.label = "🛑 Stop Server"
            btn_start_stop.variant = "error"
        else:
            status = "STATUS: ❌ STOPPED\n\nPID: -"
            btn_start_stop.label = "▶️ Start Server"
            btn_start_stop.variant = "success"
        self.status_widget.update(status)

    def add_log_line(self, line: str) -> None:
        """Fungsi thread-safe untuk menambah log ke widget"""
        # Filter log TUI itu sendiri agar tidak double
        if not line.startswith("[TUI]"):
            self.log_widget.write_line(line)

    def action_clear_log(self) -> None:
        """Kosongkan log viewer"""
        self.log_widget.clear()
        self.add_log_line("[TUI] Log view cleared by user.") # Kirim konfirmasi ke TUI

    def action_quit_app(self) -> None:
        """Keluar dari aplikasi TUI"""
        if self.is_running:
            self.add_log_line("[TUI] Stopping worker process before exiting TUI...")
            logger.info("Stopping worker process before exiting TUI...")
            self.stop_bot()
        logger.info("Exiting TUI application...")
        self.exit() # Keluar dari aplikasi Textual

    def action_focus_next_button(self) -> None:
        """Pindahkan fokus ke tombol berikutnya."""
        self.screen.focus_next(Button)

    def action_focus_prev_button(self) -> None:
        """Pindahkan fokus ke tombol sebelumnya."""
        self.screen.focus_previous(Button)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Dipanggil saat Tombol [Enter] ditekan."""
        if event.button.id == "btn_start_stop":
            self.action_start_stop()
        elif event.button.id == "btn_refresh":
            self.action_refresh()
        elif event.button.id == "btn_exit":
            self.action_quit_app()

    def action_start_stop(self) -> None:
        """Toggle start/stop server"""
        if self.is_running:
            self.stop_bot()
        else:
            self.start_bot()

    def action_refresh(self) -> None:
        """Refresh server (dijalankan di thread agar tidak block TUI)"""
        # Pastikan refresh tidak dijalankan jika sedang proses start/stop lain
        if not hasattr(self, "_refresh_lock"):
             self._refresh_lock = threading.Lock()

        if self._refresh_lock.acquire(blocking=False):
            self.add_log_line("[TUI] Starting refresh sequence...")
            logger.info("Starting refresh sequence...")
            # Buat instance thread baru setiap kali refresh
            refresh_thread = threading.Thread(target=self._run_refresh_sequence, daemon=True)
            refresh_thread.start()
        else:
            self.add_log_line("[TUI] Refresh already in progress.")
            logger.warning("Refresh action ignored: another operation in progress.")

    def _run_refresh_sequence(self):
        """Logika refresh yang dijalankan di thread terpisah."""
        try:
            self.call_from_thread(self.add_log_line, "[TUI] Refresh: Stopping worker...")
            self.stop_bot() # Ini akan block sampai worker berhenti
            time.sleep(1.5) # Beri jeda sedikit
            self.call_from_thread(self.add_log_line, "[TUI] Refresh: Starting worker...")
            self.start_bot() # Ini akan block sebentar saat memulai
            self.call_from_thread(self.add_log_line, "[TUI] Refresh sequence complete.")
            logger.info("Refresh sequence complete.")
        except Exception as e:
            error_msg = f"[TUI] Error during refresh: {e}"
            self.call_from_thread(self.add_log_line, error_msg)
            logger.error(f"Error during refresh sequence: {e}", exc_info=True)
        finally:
            # Pastikan lock dilepas walaupun error
             if hasattr(self, "_refresh_lock"):
                 self._refresh_lock.release()


    def start_bot(self) -> None:
        """Memulai bot worker sebagai subprocess."""
        global bot_process, log_thread, log_thread_stop_event

        # Cek ulang status sebelum memulai
        if bot_process is not None and bot_process.poll() is None:
             logger.warning("Start command ignored: Bot process seems to be already running.")
             self.is_running = True # Sinkronkan state
             return

        self.add_log_line("[TUI] Attempting to start worker process (src/bot.py)...")
        logger.info("Attempting to start worker process...")
        try:
            # --- PATH SUBPROCESS DIUBAH ---
            # Dapatkan path absolut ke direktori tempat tui.py berada
            current_dir = os.path.dirname(os.path.abspath(__file__))
            bot_script_path = os.path.join(current_dir, "src", "bot.py")
            # -----------------------------

            if not os.path.exists(bot_script_path):
                 error_msg = f"[TUI] ERROR: Cannot find bot script at {bot_script_path}"
                 self.add_log_line(error_msg)
                 logger.error(f"Bot script not found at {bot_script_path}")
                 self.is_running = False # Pastikan status false jika gagal start
                 return

            # Gunakan sys.executable untuk memastikan pakai interpreter python yang sama
            python_executable = sys.executable

            bot_process = subprocess.Popen(
                [python_executable, bot_script_path], # Panggil src/bot.py
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=False, # Baca sebagai bytes untuk kontrol decoding
                bufsize=1, # Line-buffered
                # Pastikan variabel environment (seperti dari .env) diteruskan jika perlu
                # env=os.environ.copy() # Uncomment jika subprocess butuh env vars
            )
            # -----------------------------

            # Mulai thread log reader HANYA jika proses berhasil dibuat
            log_thread_stop_event.clear()
            log_thread = threading.Thread(
                target=log_reader_thread,
                args=(bot_process.stdout, log_thread_stop_event, self), # Kirim self (App)
                daemon=True # Set daemon True agar thread otomatis mati jika TUI mati
            )
            log_thread.start()

            # Beri sedikit waktu untuk proses start
            time.sleep(1)
            # Cek apakah proses masih running setelah start
            if bot_process.poll() is None:
                 self.add_log_line(f"[TUI] Worker started successfully (PID: {bot_process.pid})")
                 logger.info(f"Worker process started (PID: {bot_process.pid}).")
                 self.is_running = True # Update status HANYA jika berhasil
            else:
                 exit_code = bot_process.poll()
                 error_msg = f"[TUI] Worker process failed to start or exited immediately (Code: {exit_code}). Check logs."
                 self.add_log_line(error_msg)
                 logger.error(f"Worker process failed to start or exited immediately (Code: {exit_code}).")
                 bot_process = None # Reset process
                 self.is_running = False

        except Exception as e:
            error_msg = f"[TUI] Error starting bot process: {e}"
            self.add_log_line(error_msg)
            logger.error(f"Failed to start bot process: {e}", exc_info=True)
            bot_process = None # Pastikan reset jika error
            self.is_running = False # Pastikan status false jika error

    def stop_bot(self) -> None:
        """Menghentikan bot worker."""
        global bot_process, log_thread, log_thread_stop_event

        # Cek ulang status sebelum menghentikan
        if bot_process is None or bot_process.poll() is not None:
             logger.warning("Stop command ignored: Bot process is not running.")
             self.is_running = False # Sinkronkan state
             return

        self.add_log_line("[TUI] Attempting to stop worker process...")
        logger.info("Attempting to stop worker process...")

        # 1. Signal thread log untuk berhenti
        log_thread_stop_event.set()

        # 2. Kirim sinyal terminate ke proses
        logger.info(f"Sending SIGTERM to process {bot_process.pid}")
        bot_process.terminate()

        # 3. Tunggu proses berhenti (dengan timeout)
        try:
            bot_process.wait(timeout=10) # Beri waktu 10 detik untuk graceful shutdown
            logger.info(f"Worker process {bot_process.pid} terminated gracefully.")
            self.add_log_line("[TUI] Worker stopped gracefully.")
        except subprocess.TimeoutExpired:
            # Jika timeout, paksa kill
            logger.warning(f"Worker process {bot_process.pid} did not terminate gracefully. Sending SIGKILL.")
            bot_process.kill()
            try:
                bot_process.wait(timeout=5) # Tunggu sebentar setelah kill
                logger.info(f"Worker process {bot_process.pid} killed.")
                self.add_log_line("[TUI] Worker killed (force).")
            except Exception as e:
                logger.error(f"Error waiting after killing process {bot_process.pid}: {e}")
                self.add_log_line("[TUI] Error confirming worker kill.")

        # 4. Tunggu thread log selesai (sebentar saja)
        if log_thread is not None and log_thread.is_alive():
            logger.debug("Waiting for log reader thread to finish...")
            log_thread.join(timeout=2)
            if log_thread.is_alive():
                 logger.warning("Log reader thread did not finish cleanly.")

        # 5. Reset variabel global dan status
        bot_process = None
        log_thread = None
        self.is_running = False
        logger.info("Stop sequence complete.")


if __name__ == "__main__":
    app = TuiApp()
    app.run()
