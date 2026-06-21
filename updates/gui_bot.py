# gui_bot.py — управление фоновым процессом main.py
import os
import sys
import subprocess
import threading


class BotController:
    def __init__(self, log_callback):
        self.process = None
        self.log_callback = log_callback
        self.reader_thread = None

    def start(self):
        if self.is_running():
            return
        flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
        self.process = subprocess.Popen(
            [sys.executable, "main.py"],
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, encoding="utf-8", errors="replace", bufsize=1,
            cwd=os.path.dirname(os.path.abspath(__file__)), creationflags=flags,
        )
        self.reader_thread = threading.Thread(target=self._read, daemon=True)
        self.reader_thread.start()

    def _read(self):
        while self.process and self.process.stdout:
            line = self.process.stdout.readline()
            if not line:
                break
            self.log_callback(line.strip())

    def stop(self):
        if not self.is_running():
            return
        try:
            self.process.terminate()
            self.process.wait(timeout=5)
        except Exception:
            self.process.kill()
        finally:
            self.process = None

    def is_running(self):
        return self.process is not None and self.process.poll() is None