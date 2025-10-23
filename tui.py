#!/usr/bin/env python3
"""
GitHub Asset Bot - TUI Controller (Entry Point)
Refactored with improved structure and git pull support
"""
import sys
import os
import time
import subprocess
import threading
import logging
from typing import Optional

try:
    project_root = os.path.dirname(os.path.abspath(__file__))
    src_path = os.path.join(project_root, 'src')
    if src_path not in sys.path:
        sys.path.insert(0, src_path)
    
    from config import setup_logging
    setup_logging(is_controller=True)
    logger = logging.getLogger(__name__)
except ImportError as e:
    print(f"Fatal Error: Could not import 'setup_logging' from 'src.config'.")
    print(f"Import Error: {e}")
    sys.exit(1)

try:
    from textual.app import App, ComposeResult
    from textual.widgets import Header, Footer, Static, Log, Button
    from textual.containers import Horizontal, Vertical
    from textual.reactive import reactive
except ImportError:
    logger.critical("Library 'textual' not found. Install: pip install textual")
    sys.exit(1)

# ============================================================
# GLOBAL VARIABLES
# ============================================================

bot_process: Optional[subprocess.Popen] = None
log_thread: Optional[threading.Thread] = None
log_thread_stop_event = threading.Event()

# ============================================================
# LOG READER THREAD
# ============================================================

def log_reader_thread(stdout_pipe, stop_event, app_instance):
    """Read subprocess stdout and forward to TUI log widget."""
    try:
        for line_bytes in iter(stdout_pipe.readline, b''):
            if stop_event.is_set():
                break
            line = line_bytes.decode('utf-8', errors='replace').strip()
            if line:
                app_instance.call_from_thread(app_instance.add_log_line, line)
    except Exception as e:
        if not stop_event.is_set():
            error_line = f"[Log Thread Error] {type(e).__name__}: {e}"
            logger.error(error_line)
            try:
                app_instance.call_from_thread(app_instance.add_log_line, error_line)
            except Exception:
                pass
    finally:
        try:
            stdout_pipe.close()
        except Exception:
            pass
        try:
            app_instance.call_from_thread(app_instance.add_log_line, "[TUI] Log reader thread stopped.")
        except Exception:
            pass

# ============================================================
# UTILITY FUNCTIONS
# ============================================================

def run_git_pull(cwd: str) -> tuple[bool, str]:
    """Execute git pull in the project directory."""
    try:
        result = subprocess.run(
            ['git', 'pull'],
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=30
        )
        success = result.returncode == 0
        output = result.stdout + result.stderr
        return success, output.strip()
    except subprocess.TimeoutExpired:
        return False, "Git pull timed out after 30s"
    except FileNotFoundError:
        return False, "Git command not found. Is git installed?"
    except Exception as e:
        return False, f"Git pull error: {type(e).__name__}: {e}"

# ============================================================
# TUI APPLICATION
# ============================================================

class TuiApp(App):
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
    #status-widget {
        margin-top: 1;
        padding: 1;
        border: solid white;
    }
    """
    
    BINDINGS = [
        ("q", "quit_app", "Exit"),
        ("escape", "quit_app", "Exit"),
        ("c", "clear_log", "Clear Log"),
        ("down", "focus_next_button", "Next"),
        ("up", "focus_prev_button", "Prev")
    ]
    
    is_running = reactive(False)
    
    def __init__(self):
        super().__init__()
        self.status_widget = Static("STATUS: ❌ STOPPED\n\nPID: -", id="status-widget")
        self.log_widget = Log(max_lines=1000, id="log-widget", auto_scroll=True)
        self._refresh_lock = threading.Lock()
    
    def compose(self) -> ComposeResult:
        yield Header(name="🤖 GitHub Asset Bot - TUI Controller")
        with Horizontal(id="main-container"):
            with Vertical(id="menu-panel"):
                yield Button("▶️ Start Server", id="btn_start_stop", variant="success")
                yield Button("🔄 Refresh Server", id="btn_refresh", variant="default")
                yield Button("🔃 Git Pull", id="btn_git_pull", variant="primary")
                yield Button("🚪 Exit", id="btn_exit", variant="error")
                yield Static("\n" + ("-" * 25))
                yield self.status_widget
                yield Static("\n📌 Keybindings:")
                yield Static("• ⬆️/⬇️ + Enter: Navigate")
                yield Static("• [C]: Clear Log")
                yield Static("• [Q]/[Esc]: Quit")
            with Vertical(id="log-panel"):
                yield self.log_widget
        yield Footer()
    
    def on_mount(self) -> None:
        self.add_log_line("[TUI] Controller loaded.")
        self.add_log_line("[TUI] Use Arrow keys + Enter to navigate.")
        self.query_one(Button).focus()
    
    def watch_is_running(self, running: bool) -> None:
        """Update status widget and button label when is_running changes."""
        global bot_process
        try:
            btn_start_stop = self.query_one("#btn_start_stop", Button)
        except Exception:
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
        """Add line to log widget (filter TUI internal messages)."""
        if not line.startswith("[TUI]"):
            self.log_widget.write_line(line)
    
    # ============================================================
    # ACTIONS
    # ============================================================
    
    def action_clear_log(self) -> None:
        self.log_widget.clear()
        self.add_log_line("[TUI] Log view cleared by user.")
    
    def action_quit_app(self) -> None:
        if self.is_running:
            self.add_log_line("[TUI] Stopping worker process before exiting...")
            logger.info("Stopping worker process before exiting TUI...")
            self.stop_bot()
        logger.info("Exiting TUI application...")
        self.exit()
    
    def action_focus_next_button(self) -> None:
        self.screen.focus_next(Button)
    
    def action_focus_prev_button(self) -> None:
        self.screen.focus_previous(Button)
    
    # ============================================================
    # BUTTON HANDLERS
    # ============================================================
    
    def on_button_pressed(self, event: Button.Pressed) -> None:
        button_id = event.button.id
        if button_id == "btn_start_stop":
            self.action_start_stop()
        elif button_id == "btn_refresh":
            self.action_refresh()
        elif button_id == "btn_git_pull":
            self.action_git_pull()
        elif button_id == "btn_exit":
            self.action_quit_app()
    
    def action_start_stop(self) -> None:
        if self.is_running:
            self.stop_bot()
        else:
            self.start_bot()
    
    def action_refresh(self) -> None:
        """Refresh: Git Pull -> Stop -> Start."""
        if not self._refresh_lock.acquire(blocking=False):
            self.add_log_line("[TUI] Refresh already in progress.")
            logger.warning("Refresh action ignored: operation in progress.")
            return
        
        self.add_log_line("[TUI] Starting refresh sequence...")
        logger.info("Starting refresh sequence...")
        refresh_thread = threading.Thread(target=self._run_refresh_sequence, daemon=True)
        refresh_thread.start()
    
    def action_git_pull(self) -> None:
        """Execute git pull only."""
        if not self._refresh_lock.acquire(blocking=False):
            self.add_log_line("[TUI] Git pull already in progress.")
            return
        
        self.add_log_line("[TUI] Starting git pull...")
        logger.info("Starting git pull...")
        git_thread = threading.Thread(target=self._run_git_pull_only, daemon=True)
        git_thread.start()
    
    # ============================================================
    # THREADED OPERATIONS
    # ============================================================
    
    def _run_refresh_sequence(self):
        """Refresh sequence: Git Pull -> Stop -> Start."""
        try:
            # Step 1: Git Pull
            self.call_from_thread(self.add_log_line, "[TUI] Refresh Step 1/3: Git Pull")
            project_root = os.path.dirname(os.path.abspath(__file__))
            success, output = run_git_pull(project_root)
            
            if success:
                self.call_from_thread(self.add_log_line, f"[TUI] ✅ Git Pull: {output}")
                logger.info(f"Git pull successful: {output}")
            else:
                self.call_from_thread(self.add_log_line, f"[TUI] ⚠️ Git Pull failed: {output}")
                logger.warning(f"Git pull failed: {output}")
            
            # Step 2: Stop
            self.call_from_thread(self.add_log_line, "[TUI] Refresh Step 2/3: Stopping worker")
            self.stop_bot()
            time.sleep(1.5)
            
            # Step 3: Start
            self.call_from_thread(self.add_log_line, "[TUI] Refresh Step 3/3: Starting worker")
            self.start_bot()
            
            self.call_from_thread(self.add_log_line, "[TUI] ✅ Refresh sequence complete.")
            logger.info("Refresh sequence complete.")
        
        except Exception as e:
            error_msg = f"[TUI] ❌ Error during refresh: {e}"
            self.call_from_thread(self.add_log_line, error_msg)
            logger.error(f"Error during refresh sequence: {e}", exc_info=True)
        
        finally:
            self._refresh_lock.release()
    
    def _run_git_pull_only(self):
        """Execute git pull without restart."""
        try:
            project_root = os.path.dirname(os.path.abspath(__file__))
            success, output = run_git_pull(project_root)
            
            if success:
                self.call_from_thread(self.add_log_line, f"[TUI] ✅ Git Pull: {output}")
                logger.info(f"Git pull successful: {output}")
            else:
                self.call_from_thread(self.add_log_line, f"[TUI] ⚠️ Git Pull failed: {output}")
                logger.warning(f"Git pull failed: {output}")
        
        except Exception as e:
            error_msg = f"[TUI] ❌ Git pull error: {e}"
            self.call_from_thread(self.add_log_line, error_msg)
            logger.error(f"Git pull error: {e}", exc_info=True)
        
        finally:
            self._refresh_lock.release()
    
    # ============================================================
    # BOT PROCESS MANAGEMENT
    # ============================================================
    
    def start_bot(self) -> None:
        """Start the bot worker process."""
        global bot_process, log_thread, log_thread_stop_event
        
        if bot_process is not None and bot_process.poll() is None:
            logger.warning("Start ignored: Bot already running.")
            self.is_running = True
            return
        
        self.add_log_line("[TUI] Attempting to start worker process...")
        logger.info("Attempting to start worker process...")
        
        try:
            python_executable = sys.executable
            command = [python_executable, "-m", "src.bot"]
            project_root = os.path.dirname(os.path.abspath(__file__))
            
            bot_process = subprocess.Popen(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=False,
                bufsize=1,
                cwd=project_root
            )
            
            log_thread_stop_event.clear()
            log_thread = threading.Thread(
                target=log_reader_thread,
                args=(bot_process.stdout, log_thread_stop_event, self),
                daemon=True
            )
            log_thread.start()
            
            time.sleep(1)
            
            if bot_process.poll() is None:
                self.add_log_line(f"[TUI] ✅ Worker started (PID: {bot_process.pid})")
                logger.info(f"Worker process started (PID: {bot_process.pid}).")
                self.is_running = True
            else:
                exit_code = bot_process.poll()
                error_msg = f"[TUI] ❌ Worker failed to start (Exit Code: {exit_code}). Check logs."
                self.add_log_line(error_msg)
                logger.error(error_msg)
                bot_process = None
                self.is_running = False
        
        except Exception as e:
            error_msg = f"[TUI] ❌ Error starting bot process: {e}"
            self.add_log_line(error_msg)
            logger.error(f"Failed to start bot process: {e}", exc_info=True)
            bot_process = None
            self.is_running = False
    
    def stop_bot(self) -> None:
        """Stop the bot worker process gracefully."""
        global bot_process, log_thread, log_thread_stop_event
        
        if bot_process is None or bot_process.poll() is not None:
            logger.warning("Stop ignored: Bot not running.")
            self.is_running = False
            return
        
        self.add_log_line("[TUI] Attempting to stop worker process...")
        logger.info("Attempting to stop worker process...")
        
        log_thread_stop_event.set()
        logger.info(f"Sending SIGTERM to process {bot_process.pid}")
        bot_process.terminate()
        
        try:
            bot_process.wait(timeout=10)
            logger.info(f"Worker process {bot_process.pid} terminated gracefully.")
            self.add_log_line("[TUI] ✅ Worker stopped gracefully.")
        except subprocess.TimeoutExpired:
            logger.warning(f"Worker {bot_process.pid} timed out. Sending SIGKILL.")
            bot_process.kill()
            try:
                bot_process.wait(timeout=5)
                logger.info(f"Worker process {bot_process.pid} killed.")
                self.add_log_line("[TUI] ⚠️ Worker killed (force).")
            except Exception as e:
                logger.error(f"Error waiting after killing {bot_process.pid}: {e}")
                self.add_log_line("[TUI] ❌ Error confirming worker kill.")
        
        if log_thread is not None and log_thread.is_alive():
            logger.debug("Waiting for log reader thread...")
            log_thread.join(timeout=2)
            if log_thread.is_alive():
                logger.warning("Log reader thread did not finish cleanly.")
        
        bot_process = None
        log_thread = None
        self.is_running = False
        logger.info("Stop sequence complete.")

# ============================================================
# ENTRY POINT
# ============================================================

if __name__ == "__main__":
    app = TuiApp()
    app.run()
