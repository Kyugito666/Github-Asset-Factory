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
    project_root = os.path.dirname(os.path.abspath(__file__))
    src_path = os.path.join(project_root, 'src')
    if src_path not in sys.path: sys.path.insert(0, src_path)
    from config import setup_logging
    setup_logging(is_controller=True)
    logger = logging.getLogger(__name__)
except ImportError as e:
    print(f"Fatal Error: Could not import 'setup_logging' from 'src.config'.")
    print(f"Import Error: {e}"); sys.exit(1)
# ---------------------------------

try:
    from textual.app import App, ComposeResult
    from textual.widgets import Header, Footer, Static, Log, Button
    from textual.containers import Horizontal, Vertical
    from textual.reactive import reactive
except ImportError: logger.critical("Library 'textual' not found. Please install: pip install textual"); sys.exit(1)

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
        if not stop_event.is_set(): error_line = f"[Log Thread Error] {type(e).__name__}: {e}"; logger.error(error_line);
        try: app_instance.call_from_thread(app_instance.add_log_line, error_line)
        except Exception: pass
    finally:
        try: stdout_pipe.close()
        except Exception: pass
        try: app_instance.call_from_thread(app_instance.add_log_line, "[TUI] Log reader thread stopped.")
        except Exception: pass

# --- Class TuiApp (Subprocess call diubah) ---
class TuiApp(App):
    CSS = """ Screen { layout: vertical; overflow: hidden; } Header { dock: top; } Footer { dock: bottom; } #main-container { layout: horizontal; height: 100%; } #menu-panel { width: 35; height: 100%; border-right: solid white; padding: 1; overflow-y: auto; } #log-panel { width: 1fr; height: 100%; } Log { height: 100%; width: 100%; } Button { width: 100%; margin: 1 0; } """
    BINDINGS = [("q", "quit_app", "Exit"), ("escape", "quit_app", "Exit"), ("c", "clear_log", "Clear Log"), ("down", "focus_next_button", "Next"), ("up", "focus_prev_button", "Prev")]
    is_running = reactive(False)
    def __init__(self): super().__init__(); self.status_widget = Static("STATUS: ❌ STOPPED\n\nPID: -", id="status-widget"); self.log_widget = Log(max_lines=1000, id="log-widget", auto_scroll=True)
    def compose(self) -> ComposeResult:
        yield Header(name="🤖 GitHub Asset Bot - TUI Controller")
        with Horizontal(id="main-container"):
            with Vertical(id="menu-panel"): yield Button("▶️ Start Server", id="btn_start_stop", variant="success"); yield Button("🔄 Refresh Server", id="btn_refresh", variant="default"); yield Button("🚪 Exit", id="btn_exit", variant="error"); yield Static("\n" + ("-" * 25)); yield self.status_widget; yield Static("\nUse ⬆️ / ⬇️ + [Enter]"); yield Static("Press [C] to Clear Log"); yield Static("Press [Q] or [Esc] to Quit")
            with Vertical(id="log-panel"): yield self.log_widget
        yield Footer()
    def on_mount(self) -> None: self.add_log_line("[TUI] Controller loaded."); self.add_log_line("[TUI] Use Arrows + Enter."); self.query_one(Button).focus()
    def watch_is_running(self, running: bool) -> None:
        global bot_process; try: btn_start_stop = self.query_one("#btn_start_stop", Button)
        except Exception: return
        if running and bot_process: status = f"STATUS: ✅ RUNNING\n\nPID: {bot_process.pid}"; btn_start_stop.label = "🛑 Stop Server"; btn_start_stop.variant = "error"
        else: status = "STATUS: ❌ STOPPED\n\nPID: -"; btn_start_stop.label = "▶️ Start Server"; btn_start_stop.variant = "success"
        self.status_widget.update(status)
    def add_log_line(self, line: str) -> None:
        if not line.startswith("[TUI]"): self.log_widget.write_line(line)
    def action_clear_log(self) -> None: self.log_widget.clear(); self.add_log_line("[TUI] Log view cleared by user.")
    def action_quit_app(self) -> None:
        if self.is_running: self.add_log_line("[TUI] Stopping worker process before exiting TUI..."); logger.info("Stopping worker process before exiting TUI..."); self.stop_bot()
        logger.info("Exiting TUI application..."); self.exit()
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
        if not hasattr(self, "_refresh_lock"): self._refresh_lock = threading.Lock()
        if self._refresh_lock.acquire(blocking=False): self.add_log_line("[TUI] Starting refresh sequence..."); logger.info("Starting refresh sequence..."); refresh_thread = threading.Thread(target=self._run_refresh_sequence, daemon=True); refresh_thread.start()
        else: self.add_log_line("[TUI] Refresh already in progress."); logger.warning("Refresh action ignored: operation in progress.")
    def _run_refresh_sequence(self):
        try: self.call_from_thread(self.add_log_line, "[TUI] Refresh: Stopping worker..."); self.stop_bot(); time.sleep(1.5); self.call_from_thread(self.add_log_line, "[TUI] Refresh: Starting worker..."); self.start_bot(); self.call_from_thread(self.add_log_line, "[TUI] Refresh sequence complete."); logger.info("Refresh sequence complete.")
        except Exception as e: error_msg = f"[TUI] Error during refresh: {e}"; self.call_from_thread(self.add_log_line, error_msg); logger.error(f"Error during refresh sequence: {e}", exc_info=True)
        finally:
             if hasattr(self, "_refresh_lock"): self._refresh_lock.release()
    def start_bot(self) -> None:
        global bot_process, log_thread, log_thread_stop_event
        if bot_process is not None and bot_process.poll() is None: logger.warning("Start ignored: Bot already running."); self.is_running = True; return
        self.add_log_line("[TUI] Attempting to start worker process..."); logger.info("Attempting to start worker process...")
        try:
            # --- CARA MANGGIL SUBPROCESS DIUBAH ---
            python_executable = sys.executable
            # Gunakan '-m' untuk menjalankan sebagai module
            command = [
                python_executable, "-m", "src.bot"
            ]
            # Tentukan working directory ke parent dari src/ (root folder)
            # agar 'src.bot' bisa ditemukan
            project_root = os.path.dirname(os.path.abspath(__file__))

            bot_process = subprocess.Popen(
                command, # Pakai command baru
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=False, bufsize=1,
                cwd=project_root, # Set working directory
                # env=os.environ.copy() # Pastikan env var diteruskan jika perlu
            )
            # ------------------------------------

            log_thread_stop_event.clear()
            log_thread = threading.Thread(target=log_reader_thread, args=(bot_process.stdout, log_thread_stop_event, self), daemon=True)
            log_thread.start()
            time.sleep(1) # Tunggu proses start
            if bot_process.poll() is None: self.add_log_line(f"[TUI] Worker started (PID: {bot_process.pid})"); logger.info(f"Worker process started (PID: {bot_process.pid})."); self.is_running = True
            else: exit_code = bot_process.poll(); error_msg = f"[TUI] Worker failed to start (Code: {exit_code}). Check logs."; self.add_log_line(error_msg); logger.error(error_msg); bot_process = None; self.is_running = False
        except Exception as e: error_msg = f"[TUI] Error starting bot process: {e}"; self.add_log_line(error_msg); logger.error(f"Failed to start bot process: {e}", exc_info=True); bot_process = None; self.is_running = False
    def stop_bot(self) -> None:
        global bot_process, log_thread, log_thread_stop_event
        if bot_process is None or bot_process.poll() is not None: logger.warning("Stop ignored: Bot not running."); self.is_running = False; return
        self.add_log_line("[TUI] Attempting to stop worker process..."); logger.info("Attempting to stop worker process...")
        log_thread_stop_event.set(); logger.info(f"Sending SIGTERM to process {bot_process.pid}"); bot_process.terminate()
        try: bot_process.wait(timeout=10); logger.info(f"Worker process {bot_process.pid} terminated gracefully."); self.add_log_line("[TUI] Worker stopped gracefully.")
        except subprocess.TimeoutExpired: logger.warning(f"Worker {bot_process.pid} timed out. Sending SIGKILL."); bot_process.kill();
        try: bot_process.wait(timeout=5); logger.info(f"Worker process {bot_process.pid} killed."); self.add_log_line("[TUI] Worker killed (force).")
        except Exception as e: logger.error(f"Error waiting after killing {bot_process.pid}: {e}"); self.add_log_line("[TUI] Error confirming worker kill.")
        if log_thread is not None and log_thread.is_alive(): logger.debug("Waiting for log reader thread..."); log_thread.join(timeout=2);
        if log_thread is not None and log_thread.is_alive(): logger.warning("Log reader thread did not finish cleanly.")
        bot_process = None; log_thread = None; self.is_running = False; logger.info("Stop sequence complete.")

if __name__ == "__main__":
    app = TuiApp()
    app.run()
