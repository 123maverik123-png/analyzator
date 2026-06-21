# updater.py — автообновление через GitHub (raw-ссылки)
import os
import sys
import json
import hashlib
import tempfile
import zipfile
import subprocess
import requests
from threading import Thread
from config import VERSION, UPDATE_BASE_URL
from tkinter import messagebox

class Updater:
    def __init__(self, root, log_callback):
        self.root = root
        self.log = log_callback
        self.thread = None

    def check_for_updates(self, silent=False):
        if self.thread and self.thread.is_alive():
            return
        self.thread = Thread(target=self._check, args=(silent,), daemon=True)
        self.thread.start()

    def _check(self, silent):
        try:
            self.log("[Обновления] Проверка наличия обновлений...")
            version_url = f"{UPDATE_BASE_URL}/version.json"
            resp = requests.get(version_url, timeout=10)
            if resp.status_code != 200:
                self.log(f"[Обновления] Не удалось получить version.json (код {resp.status_code})")
                return

            data = resp.json()
            latest_version = data.get("version")
            if not latest_version:
                return

            if latest_version == VERSION:
                self.log(f"[Обновления] У вас актуальная версия {VERSION}.")
                return

            self.log(f"[Обновления] Доступна новая версия {latest_version} (текущая {VERSION}).")
            self.root.after(0, lambda: self._ask_update(data, latest_version))

        except Exception as e:
            self.log(f"[Обновления] Ошибка: {e}")

    def _ask_update(self, data, new_version):
        changelog = data.get("changelog", "Исправлены ошибки и улучшена производительность.")
        answer = messagebox.askyesno(
            "Обновление",
            f"Доступна новая версия {new_version}.\n\nИзменения:\n{changelog}\n\nОбновить сейчас?",
            parent=self.root
        )
        if answer:
            self._apply_update(data, new_version)

    def _apply_update(self, data, new_version):
        download_url = data.get("download_url")
        if not download_url:
            messagebox.showerror("Ошибка", "Не удалось получить ссылку для скачивания.")
            return

        temp_dir = tempfile.mkdtemp()
        zip_path = os.path.join(temp_dir, "update.zip")
        extract_path = os.path.join(temp_dir, "extracted")

        try:
            self.log("[Обновления] Скачивание обновления...")
            with requests.get(download_url, stream=True) as r:
                r.raise_for_status()
                with open(zip_path, "wb") as f:
                    for chunk in r.iter_content(chunk_size=8192):
                        f.write(chunk)

            sha256 = data.get("sha256")
            if sha256:
                self.log("[Обновления] Проверка целостности...")
                if not self._verify_sha256(zip_path, sha256):
                    messagebox.showerror("Ошибка", "Контрольная сумма не совпадает. Обновление отменено.")
                    return

            self.log("[Обновления] Распаковка...")
            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                zip_ref.extractall(extract_path)

            self.log("[Обновления] Применение обновления...")
            self._launch_updater_script(extract_path)

        except Exception as e:
            self.log(f"[Обновления] Ошибка: {e}")
            messagebox.showerror("Ошибка", f"Не удалось применить обновление: {e}")

    def _verify_sha256(self, file_path, expected):
        sha256_hash = hashlib.sha256()
        with open(file_path, "rb") as f:
            for byte_block in iter(lambda: f.read(4096), b""):
                sha256_hash.update(byte_block)
        return sha256_hash.hexdigest() == expected

    def _launch_updater_script(self, update_dir):
        bat_content = f"""@echo off
timeout /t 2 /nobreak >nul
xcopy /E /I /Y "{update_dir}\*" "%~dp0"
start "" "{sys.executable}" "gui.py"
exit
"""
        bat_path = os.path.join(os.path.dirname(__file__), "apply_update.bat")
        with open(bat_path, "w", encoding="utf-8") as f:
            f.write(bat_content)

        subprocess.Popen(bat_path, creationflags=subprocess.CREATE_NO_WINDOW)
        self.root.quit()