#!/usr/bin/env python3
"""
GitHub Asset Bot - TUI Controller (Textual Version)
Ini adalah main entry point untuk menjalankan aplikasi.
"""

import sys
import os
import time
import subprocess
import threading
import logging
from collections import deque
from typing import Optional

try:
    # Import ini untuk TUI-nya sendiri, BUKAN subprocess
    from src.config import setup_logging
except ImportError:
    print("Error: config.py tidak ditemukan. Pastikan file ada di src/config.py")
    sys.exit(1)

# Import Textual
try:
    from textual.app import App, ComposeResult
    from textual.widgets import Header, Footer, Static, Log, Button
    from textual.containers import Horizontal, Vertical
    from textual.reactive import reactive
except ImportError:
    print("Error: Library 'textual' tidak ditemukan.")
    print("Silakan install: pip install textual")
    sys.exit(1)


# Setup logging HANYA untuk TUI (console)
setup_logging(is_controller=True)
logger = logging.getLogger(__name__)

# --- Variabel Global untuk TUI ---
bot_process: Optional[subprocess.Popen] = None
log_thread: Optional[threading.Thread] = None
log_thread_stop_event = threading.Event()
# --- Akhir Variabel Global ---

def log_reader_thread(stdout_pipe, stop_event, app_instance):
    """
    Thread target: Membaca output dari pipe subprocess
    dan mengirimkannya ke App Textual (thread-safe).
    """
    try:
        for line_bytes in iter(stdout_pipe.readline, b''):
            if stop_event.is_set():
                break
            
            line = line_bytes.decode('utf-8', errors='replace').strip()
            
            if line:
                app_instance.call_from_thread(app_instance.add_log_line, line)
        
    except Exception as e:
        if not stop_event.is_set():
            error_line = f"[Log Thread Error] {e}"
            app_instance.call_from_thread(app_instance.add_log_line, error_line)
    finally:
        try:
            stdout_pipe.close()
        except Exception:
            pass
        app_instance.call_from_thread(app_instance.add_log_line, "[TUI] Log reader thread stopped.")


# === FUNGSI BARU UNTUK GIT PULL ===
def git_pull_thread(app_instance):
    """Thread target: Menjalankan git pull dan log output."""
    app_instance.call_from_thread(app_instance.add_log_line, "[TUI] Starting 'git pull'...")
    try:
        # Menjalankan git pull sebagai subprocess
        process = subprocess.Popen(
            ["git", "pull"],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            # Pastikan CWD adalah root folder (tempat .git berada)
            cwd=os.path.dirname(os.path.abspath(__file__))
        )
        
        # Baca output line by line
        for line_bytes in iter(process.stdout.readline, b''):
            line = line_bytes.decode('utf-8', errors='replace').strip()
            if line:
                app_instance.call_from_thread(app_instance.add_log_line, f"[GIT] {line}")
        
        process.stdout.close()
        return_code = process.wait()
        
        if return_code == 0:
            app_instance.call_from_thread(app_instance.add_log_line, "[TUI] 'git pull' completed successfully.")
            app_instance.call_from_thread(app_instance.add_log_line, "[TUI] Server WAJIB di-Refresh untuk menerapkan update.")
        else:
            app_instance.call_from_thread(app_instance.add_log_line, f"[TUI] 'git pull' failed (Code: {return_code}). Check log.")

    except FileNotFoundError:
        app_instance.call_from_thread(app_instance.add_log_line, "[TUI] ERROR: 'git' command not found. Pastikan Git sudah terinstall.")
    except Exception as e:
        app_instance.call_from_thread(app_instance.add_log_line, f"[TUI] 'git pull' exception: {e}")
# === AKHIR FUNGSI BARU ===


class TuiApp(App):
    """Aplikasi TUI untuk Bot Controller"""
    
    CSS = """
    Screen {
        layout: vertical;
        overflow: hidden;
    }
    Header {
        dock: top;
    }
    Footer {
        dock: bottom;
    }
    #main-container {
        layout: horizontal;
        height: 100%;
    }
    #menu-panel {
        width: 35; 
        height: 100%;
        border-right: solid white;
        padding: 1;
        overflow-y: auto; 
    }
    #log-panel {
        width: 1fr; 
        height: 100%;
    }
    Log {
        height: 100%;
        width: 100%;
    }
    Button {
        width: 100%;
        margin: 1 0;
    }
    """
    
    BINDINGS = [
        ("q", "quit_app", "Exit"),
        ("escape", "quit_app", "Exit"),
        ("c", "clear_log", "Clear Log"),
        ("down", "focus_next_button", "Next"),
        ("up", "focus_prev_button", "Prev"),
    ]
    
    is_running = reactive(False)
    
    def __init__(self):
        super().__init__()
        self.status_widget = Static("STATUS: ❌ STOPPED\n\nPID: -")
        self.log_widget = Log(max_lines=1000, id="log-widget")

    def compose(self) -> ComposeResult:
        """Buat layout widget"""
        yield Header(name="🤖 GitHub Asset Bot - TUI Controller")
        with Horizontal(id="main-container"):
            with Vertical(id="menu-panel"):
                yield Button("▶️ Start Server", id="btn_start_stop", variant="success")
                yield Button("🔄 Refresh Server", id="btn_refresh", variant="default")
                # === TOMBOL BARU ===
                yield Button("⬇️ Git Pull", id="btn_git_pull", variant="primary")
                # === AKHIR TOMBOL BARU ===
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
        self.add_log_line("[TUI] Controller TUI berhasil dimuat.")
        self.add_log_line("[TUI] Gunakan ⬆️ / ⬇️ dan [Enter] untuk navigasi.")
        self.query_one(Button).focus()

    # --- Watchers (Auto-update UI) ---
    
    def watch_is_running(self, running: bool) -> None:
        """Update status widget DAN label tombol saat 'self.is_running' berubah"""
        global bot_process
        
        btn_start_stop = self.query_one("#btn_start_stop", Button)
        
        if running and bot_process:
            status = f"STATUS: ✅ RUNNING\n\nPID: {bot_process.pid}"
            btn_start_stop.label = "🛑 Stop Server"
            btn_start_stop.variant = "error"
        else:
            status = "STATUS: ❌ STOPPED\n\nPID: -"
            btn_start_stop.label = "▶️ Start Server"
            btn_start_stop.variant = "success"
            
        self.status_widget.update(status)

    # --- Log Management ---
    
    def add_log_line(self, line: str) -> None:
        """Fungsi thread-safe untuk menambah log ke widget"""
        if "TUI Controller" not in line and "RECENT BOT LOGS" not in line:
            self.log_widget.write_line(line)

    # --- Actions (dari Key Bindings) ---

    def action_clear_log(self) -> None:
        """Kosongkan log viewer"""
        self.log_widget.clear()
        self.add_log_line("[TUI] Log TUI dikosongkan.")

    def action_quit_app(self) -> None:
        """Keluar dari aplikasi"""
        if self.is_running:
            self.add_log_line("[TUI] Mematikan server sebelum keluar...")
            self.stop_bot()
        self.exit()

    def action_focus_next_button(self) -> None:
        """Pindahkan fokus ke tombol berikutnya."""
        self.screen.focus_next(Button)
        
    def action_focus_prev_button(self) -> None:
        """Pindahkan fokus ke tombol sebelumnya."""
        self.screen.focus_previous(Button)

    # --- Handler untuk Button Press (Enter) ---
    
    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Dipanggil saat Tombol [Enter] ditekan."""
        
        if event.button.id == "btn_start_stop":
            self.action_start_stop()
        
        elif event.button.id == "btn_refresh":
            self.action_refresh()
            
        # === HANDLER BARU ===
        elif event.button.id == "btn_git_pull":
            self.action_git_pull()
        # === AKHIR HANDLER BARU ===
            
        elif event.button.id == "btn_exit":
            self.action_quit_app()

    # --- Actions (Logika inti) ---
    
    def action_start_stop(self) -> None:
        """Toggle start/stop server"""
        if self.is_running:
            self.stop_bot()
        else:
            self.start_bot()

    # === FUNGSI REFRESH DIPERBAIKI ===
    def action_refresh(self) -> None:
        """Refresh server (dijalankan di thread)"""
        self_copy = self 
        
        def refresh_task():
            self_copy.call_from_thread(self_copy.add_log_line, "[TUI] Refreshing server...")
            if self_copy.is_running:
                # Panggil stop_bot lewat main thread (thread-safe)
                self_copy.call_from_thread(self_copy.stop_bot)
                time.sleep(1) # Sleep aman di background thread
            
            # Panggil start_bot lewat main thread (thread-safe)
            self_copy.call_from_thread(self_copy.start_bot)
            self_copy.call_from_thread(self_copy.add_log_line, "[TUI] Refresh complete.")
        
        threading.Thread(target=refresh_task, daemon=True).start()
    # === AKHIR FUNGSI REFRESH ===

    # === AKSI BARU ===
    def action_git_pull(self) -> None:
        """Menjalankan git pull di thread terpisah."""
        self.add_log_line("[TUI] Memulai 'git pull' di background thread...")
        threading.Thread(target=git_pull_thread, args=(self,), daemon=True).start()
    # === AKHIR AKSI BARU ===

    # --- Subprocess Logic (Tidak berubah dari fix sebelumnya) ---
    
    def start_bot(self) -> None:
        global bot_process, log_thread, log_thread_stop_event
        
        if not self.is_running:
            self.add_log_line("[TUI] Starting worker process (src.bot)...")
            
            # FIX (PAKAI -m UNTUK EKSEKUSI SEBAGAI MODUL)
            bot_process = subprocess.Popen(
                [sys.executable, "-m", "src.bot"],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                # Pastikan CWD adalah root folder agar 'src.bot' ditemukan
                cwd=os.path.dirname(os.path.abspath(__file__)) 
            )
            
            log_thread_stop_event.clear()
            log_thread = threading.Thread(
                target=log_reader_thread,
                args=(bot_process.stdout, log_thread_stop_event, self),
                daemon=True
            )
            log_thread.start()
            
            self.add_log_line(f"[TUI] Worker started (PID: {bot_process.pid})")
            self.is_running = True

    def stop_bot(self) -> None:
        global bot_process, log_thread, log_thread_stop_event
        
        if self.is_running and bot_process:
            self.add_log_line("[TUI] Stopping worker process...")
            
            log_thread_stop_event.set()
            bot_process.terminate()
            
            try:
                bot_process.wait(timeout=5)
                self.add_log_line("[TUI] Worker stopped.")
            except subprocess.TimeoutExpired:
                bot_process.kill()
                self.add_log_line("[TUI] Worker killed (force).")
            
            if log_thread is not None and log_thread.is_alive():
                log_thread.join(timeout=2)
                
            bot_process = None
            log_thread = None
            self.is_running = False


if __name__ == "__main__":
    # Jalankan aplikasi Textual
    app = TuiApp()
    app.run()
