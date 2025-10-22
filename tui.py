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
    from src.config import setup_logging # Panggil setup logging lebih awal
    # Panggil setup_logging SEBELUM import lain yg mungkin log
    setup_logging(is_controller=True)
    logger = logging.getLogger(__name__) # Setup logger setelah setup_logging
except ImportError as e:
    print(f"Fatal Error: Could not import from 'src'. Make sure structure is correct and files exist.")
    print(f"Import Error: {e}")
    sys.exit(1)
# ---------------------------------

try:
    from textual.app import App, ComposeResult
    from textual.widgets import Header, Footer, Static, Log, Button
    from textual.containers import Horizontal, Vertical
    from textual.reactive import reactive
except ImportError:
    logger.critical("Library 'textual' not found. Please install: pip install textual"); sys.exit(1)

# --- Variabel Global TUI (Tidak berubah) ---
bot_process: Optional[subprocess.Popen] = None
log_thread: Optional[threading.Thread] = None
log_thread_stop_event = threading.Event()

# --- Fungsi log_reader_thread (Tidak berubah) ---
def log_reader_thread(stdout_pipe, stop_event, app_instance):
    try:
        for line_bytes in iter(stdout_pipe.readline, b''):
            if stop_event.is_set(): break
            line = line_bytes.decode('utf-8', errors='replace').strip()
            if line: app_instance.call_from_thread(app_instance.add_log_line, line)
    except Exception as e:
        if not stop_event.is_set():
            error_line = f"[Log Thread Error] {e}"; app_instance.call_from_thread(app_instance.add_log_line, error_line)
    finally:
        try: stdout_pipe.close()
        except Exception: pass
        app_instance.call_from_thread(app_instance.add_log_line, "[TUI] Log reader thread stopped.")

# --- Class TuiApp (Subprocess path diubah) ---
class TuiApp(App):
    CSS = """
    Screen { layout: vertical; overflow: hidden; }
    Header { dock: top; } Footer { dock: bottom; }
    #main-container { layout: horizontal; height: 100%; }
    #menu-panel { width: 35; height: 100%; border-right: solid white; padding: 1; overflow-y: auto; }
    #log-panel { width: 1fr; height: 100%; } Log { height: 100%; width: 100%; }
    Button { width: 100%; margin: 1 0; }
    """
    BINDINGS = [("q", "quit_app", "Exit"), ("escape", "quit_app", "Exit"), ("c", "clear_log", "Clear Log"), ("down", "focus_next_button", "Next"), ("up", "focus_prev_button", "Prev")]
    is_running = reactive(False)
    def __init__(self): super().__init__(); self.status_widget = Static("STATUS: ❌ STOPPED\n\nPID: -"); self.log_widget = Log(max_lines=1000, id="log-widget")
    def compose(self) -> ComposeResult:
        yield Header(name="🤖 GitHub Asset Bot - TUI Controller")
        with Horizontal(id="main-container"):
            with Vertical(id="menu-panel"):
                yield Button("▶️ Start Server", id="btn_start_stop", variant="success")
                yield Button("🔄 Refresh Server", id="btn_refresh", variant="default")
                yield Button("🚪 Exit", id="btn_exit", variant="error")
                yield Static("\n" + ("-" * 25)); yield self.status_widget; yield Static("\nUse ⬆️ / ⬇️ + [Enter]"); yield Static("Press [C] to Clear Log"); yield Static("Press [Q] or [Esc] to Quit")
            with Vertical(id="log-panel"): yield self.log_widget
        yield Footer()
    def on_mount(self) -> None: self.add_log_line("[TUI] Controller loaded."); self.add_log_line("[TUI] Use Arrows + Enter."); self.query_one(Button).focus()
    def watch_is_running(self, running: bool) -> None:
        global bot_process; btn_start_stop = self.query_one("#btn_start_stop", Button)
        if running and bot_process: status = f"STATUS: ✅ RUNNING\n\nPID: {bot_process.pid}"; btn_start_stop.label = "🛑 Stop Server"; btn_start_stop.variant = "error"
        else: status = "STATUS: ❌ STOPPED\n\nPID: -"; btn_start_stop.label = "▶️ Start Server"; btn_start_stop.variant = "success"
        self.status_widget.update(status)
    def add_log_line(self, line: str) -> None:
        if "TUI Controller" not in line: self.log_widget.write_line(line)
    def action_clear_log(self) -> None: self.log_widget.clear(); self.add_log_line("[TUI] Log cleared.")
    def action_quit_app(self) -> None:
        if self.is_running: self.add_log_line("[TUI] Stopping server before exit..."); self.stop_bot()
        self.exit()
    def action_focus_next_button(self) -> None: self.screen.focus_next(Button)
    def action_focus_prev_button(self) -> None: self.screen.focus_previous(Button)
    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn_start_stop": self.action_start_stop()
        elif event.button.id == "btn_refresh": self.action_refresh()
        elif event.button.id == "btn_exit": self.action_quit_app()
    def action_start_stop(self) -> None:
        if self.is_running: self.stop_bot()
        else: self.start_bot()
    def action_refresh(self) -> None:
        self_copy = self;
        def refresh_task():
            self_copy.call_from_thread(self_copy.add_log_line, "[TUI] Refreshing server...")
            if self_copy.is_running: self_copy.stop_bot(); time.sleep(1)
            self_copy.start_bot(); self_copy.call_from_thread(self_copy.add_log_line, "[TUI] Refresh complete.")
        threading.Thread(target=refresh_task, daemon=True).start()
    def start_bot(self) -> None:
        global bot_process, log_thread, log_thread_stop_event
        if not self.is_running:
            self.add_log_line("[TUI] Starting worker process (src/bot.py)...")
            try:
                # --- PATH SUBPROCESS DIUBAH ---
                bot_script_path = os.path.join("src", "bot.py")
                if not os.path.exists(bot_script_path):
                     self.add_log_line(f"[TUI] ERROR: Cannot find bot script at {bot_script_path}")
                     logger.error(f"Bot script not found at {bot_script_path}")
                     return

                bot_process = subprocess.Popen(
                    [sys.executable, bot_script_path], # Panggil src/bot.py
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True, # Decode output automatically
                    encoding='utf-8', errors='replace' # Handle encoding errors
                )
                # -----------------------------
                log_thread_stop_event.clear()
                log_thread = threading.Thread(target=log_reader_thread, args=(bot_process.stdout, log_thread_stop_event, self), daemon=True)
                log_thread.start()
                self.add_log_line(f"[TUI] Worker started (PID: {bot_process.pid})")
                self.is_running = True
            except Exception as e:
                self.add_log_line(f"[TUI] Error starting bot process: {e}")
                logger.error(f"Failed to start bot process: {e}", exc_info=True)

    def stop_bot(self) -> None:
        global bot_process, log_thread, log_thread_stop_event
        if self.is_running and bot_process:
            self.add_log_line("[TUI] Stopping worker process...")
            log_thread_stop_event.set(); bot_process.terminate()
            try: bot_process.wait(timeout=5); self.add_log_line("[TUI] Worker stopped.")
            except subprocess.TimeoutExpired: bot_process.kill(); self.add_log_line("[TUI] Worker killed (force).")
            if log_thread is not None and log_thread.is_alive(): log_thread.join(timeout=2)
            bot_process = None; log_thread = None; self.is_running = False

if __name__ == "__main__":
    app = TuiApp()
    app.run()
