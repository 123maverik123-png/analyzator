# gui.py — основной GUI-файл (с лицензией и ссылкой продления внизу)
import os
import sys
import queue
import threading
import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox

import sv_ttk
import vlc
import settings
import storage
import achievements
import updater
import license

from gui_utils import fmt_time, extract_phone, extract_dt
from gui_bot import BotController
from gui_dialogs import DirChooser, NameDialog, ActivationDialog

storage.init_db()


class App:
    def __init__(self, root):
        self.root = root
        self.root.title("Анализатор разговоров")
        self.root.geometry("1060x720")
        self.root.minsize(900, 600)

        # Проверка лицензии
        self._check_license()

        self.cfg = settings.load()
        sv_ttk.set_theme(self.cfg.get("theme", "dark"))

        self.bot = BotController(self._on_bot_log)

        # Инициализация VLC
        self.vlc_instance = vlc.Instance()
        self.player = self.vlc_instance.media_player_new()
        self.current_media = None
        self.audio_duration = 0
        self.audio_position = 0
        self.is_playing = False
        self.is_paused = False
        self.is_seeking = False
        self.current_audio_path = None

        self._build_header()
        self._build_tabs()
        self._refresh_operator_label()

        self.ui_queue = queue.Queue()
        self._last_count = storage.count_calls()

        self.load_calls()
        self.refresh_achievements()

        self._tick()
        self._poll()

        # Копирайт и контакты (справа внизу)
        copyright_label = ttk.Label(
            self.root,
            text="© 2026 Все права защищены",
            foreground="#888",
            font=("Segoe UI", 8)
        )
        copyright_label.place(relx=1.0, rely=1.0, x=-10, y=-10, anchor="se")

        contact_label = ttk.Label(
            self.root,
            text="✉️ 123maverik123@gmail.com",
            foreground="#4a90e2",
            font=("Segoe UI", 8, "underline"),
            cursor="hand2"
        )
        contact_label.place(relx=1.0, rely=1.0, x=-10, y=-30, anchor="se")
        contact_label.bind("<Button-1>", lambda e: self._copy_email())

        # Информация о лицензии + ссылка "Продлить подписку" (слева внизу)
        bottom_left_frame = ttk.Frame(self.root)
        bottom_left_frame.place(relx=0.0, rely=1.0, x=10, y=-10, anchor="sw")

        self.license_label = ttk.Label(
            bottom_left_frame,
            text="",
            foreground="#888",
            font=("Segoe UI", 8)
        )
        self.license_label.pack(side=tk.LEFT)

        renew_link = ttk.Label(
            bottom_left_frame,
            text="Продлить подписку",
            foreground="#4a90e2",
            font=("Segoe UI", 8, "underline"),
            cursor="hand2"
        )
        renew_link.pack(side=tk.LEFT, padx=(10, 0))
        renew_link.bind("<Button-1>", lambda e: self.show_subscription())

        self._update_license_label()

        # Автообновление
        self.updater = updater.Updater(self.root, self.log_message)
        self.root.after(1000, lambda: self.updater.check_for_updates(silent=False))

        # При первом запуске, если оператор не задан, спросить
        if not (settings.get("operator_id") or os.getenv("OPERATOR_ID")):
            self.root.after(400, self._first_run_operator)

        root.protocol("WM_DELETE_WINDOW", self.on_close)

    def _update_license_label(self):
        """Обновляет отображение статуса лицензии."""
        status = license.get_license_status()
        if status == "trial":
            days_left = license.days_remaining()
            text = f"🔓 Демо-период: {days_left} дн."
        elif status == "active":
            days_left = license.days_remaining()
            text = f"✅ Подписка активна: {days_left} дн."
        elif status == "expired":
            text = "❌ Демо-период истёк"
        else:
            text = "⚠️ Статус лицензии неизвестен"
        self.license_label.config(text=text)

    def _check_license(self):
        status = license.get_license_status()
        if status == "expired":
            self._show_activation("expired")
            self._update_license_label()
        elif status == "error":
            self._show_activation("error")
            self._update_license_label()

    def _show_activation(self, status):
        def on_activate(key):
            return license.activate_license(key)

        dialog = ActivationDialog(self.root, status, on_activate)
        self.root.wait_window(dialog)
        if not dialog.result:
            sys.exit(0)

    def _build_header(self):
        bar = ttk.Frame(self.root, padding=(12, 10))
        bar.pack(fill=tk.X)

        ttk.Label(bar, text="🎧  Анализатор разговоров", font=("Segoe UI", 14, "bold")).pack(side=tk.LEFT)
        self.op_label = ttk.Label(bar, text="", foreground="#888")
        self.op_label.pack(side=tk.LEFT, padx=12)

        self.btn_theme = ttk.Button(bar, width=3, command=self.toggle_theme,
                                    text="☀" if self.cfg.get("theme") == "dark" else "☽")
        self.btn_theme.pack(side=tk.RIGHT, padx=4)
        ttk.Button(bar, text="⚙ Папка записей", command=self.choose_folder).pack(side=tk.RIGHT, padx=4)
        ttk.Button(bar, text="🔄 Проверить обновления", command=self.check_updates_manual).pack(side=tk.RIGHT, padx=4)

        self.status = ttk.Label(bar, text="● остановлен", foreground="#e05656")
        self.status.pack(side=tk.RIGHT, padx=16)
        self.btn_bot = ttk.Button(bar, text="▶ Запустить бота", command=self.toggle_bot)
        self.btn_bot.pack(side=tk.RIGHT)

    def _build_tabs(self):
        nb = ttk.Notebook(self.root)
        nb.pack(fill=tk.BOTH, expand=True, padx=12, pady=(0, 6))
        self._build_calls_tab(nb)
        self._build_ach_tab(nb)

        self.log_var = tk.StringVar(value="Готово.")
        ttk.Label(self.root, textvariable=self.log_var, padding=(14, 2),
                  foreground="#888").pack(fill=tk.X)

    def _build_calls_tab(self, nb):
        tab = ttk.Frame(nb, padding=8)
        nb.add(tab, text="  Мои разговоры  ")

        paned = ttk.PanedWindow(tab, orient=tk.HORIZONTAL)
        paned.pack(fill=tk.BOTH, expand=True)

        left = ttk.Frame(paned)
        paned.add(left, weight=3)

        search_row = ttk.Frame(left)
        search_row.pack(fill=tk.X, pady=(0, 6))
        ttk.Label(search_row, text="🔍").pack(side=tk.LEFT, padx=(0, 4))
        self.search_var = tk.StringVar()
        self.search_var.trace_add("write", lambda *_: self.load_calls())
        ttk.Entry(search_row, textvariable=self.search_var).pack(fill=tk.X, expand=True)

        cols = ("phone", "date", "category", "resolved")
        self.tree = ttk.Treeview(left, columns=cols, show="headings", selectmode="browse")
        for c, t, w in (("phone", "Телефон", 120), ("date", "Дата/время", 130),
                        ("category", "Категория", 130), ("resolved", "✓", 40)):
            self.tree.heading(c, text=t)
            self.tree.column(c, width=w, anchor=tk.W)
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        sb = ttk.Scrollbar(left, orient=tk.VERTICAL, command=self.tree.yview)
        self.tree.configure(yscrollcommand=sb.set)
        sb.pack(side=tk.RIGHT, fill=tk.Y)
        self.tree.bind("<<TreeviewSelect>>", lambda e: self.on_select())

        right = ttk.Frame(paned)
        paned.add(right, weight=2)

        self.detail_head = ttk.Label(right, text="Выберите разговор", font=("Segoe UI", 12, "bold"))
        self.detail_head.pack(anchor=tk.W)
        self.detail_meta = ttk.Label(right, text="", foreground="#888", wraplength=380, justify=tk.LEFT)
        self.detail_meta.pack(anchor=tk.W, pady=(2, 8))

        ttk.Label(right, text="Резюме", font=("Segoe UI", 9, "bold")).pack(anchor=tk.W)
        self.detail_summary = ttk.Label(right, text="—", wraplength=380, justify=tk.LEFT)
        self.detail_summary.pack(anchor=tk.W, pady=(0, 4))
        self.btn_copy = ttk.Button(right, text="📋 Копировать резюме",
                                   command=self.copy_summary, state=tk.DISABLED)
        self.btn_copy.pack(anchor=tk.W, pady=(0, 8))
        self.current_summary = ""

        self.detail_text_label = ttk.Label(right, text="Расшифровка", font=("Segoe UI", 9, "bold"))
        self.detail_text_label.pack(anchor=tk.W)
        self.detail_text = scrolledtext.ScrolledText(right, wrap=tk.WORD, height=10,
                                                     font=("Segoe UI", 10), relief=tk.FLAT)
        self.detail_text.pack(fill=tk.BOTH, expand=True, pady=(2, 8))

        self._build_player(tab)
        self.player_frame.pack_forget()

    def _build_player(self, parent):
        self.player_frame = ttk.Frame(parent, padding=(0, 8, 0, 0))
        bar = self.player_frame
        self.btn_back = ttk.Button(bar, text="⏪10", width=5, command=lambda: self.skip(-10), state=tk.DISABLED)
        self.btn_back.pack(side=tk.LEFT)
        self.btn_play = ttk.Button(bar, text="▶", width=4, command=self.toggle_play, state=tk.DISABLED)
        self.btn_play.pack(side=tk.LEFT, padx=4)
        self.btn_stop = ttk.Button(bar, text="⏹", width=4, command=self.stop_play, state=tk.DISABLED)
        self.btn_stop.pack(side=tk.LEFT)
        self.btn_fwd = ttk.Button(bar, text="10⏩", width=5, command=lambda: self.skip(10), state=tk.DISABLED)
        self.btn_fwd.pack(side=tk.LEFT, padx=4)
        self.player_btns = [self.btn_back, self.btn_play, self.btn_stop, self.btn_fwd]

        self.pos_var = tk.DoubleVar(value=0)
        self.scale = ttk.Scale(bar, from_=0, to=100, variable=self.pos_var)
        self.scale.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=10)
        self.scale.bind("<ButtonPress-1>", lambda e: setattr(self, "is_seeking", True))
        self.scale.bind("<ButtonRelease-1>", self._on_seek)
        self.scale.bind("<B1-Motion>", self._on_scale_drag)

        self.time_lbl = ttk.Label(bar, text="00:00 / 00:00", width=14)
        self.time_lbl.pack(side=tk.LEFT)
        self.file_lbl = ttk.Label(bar, text="", foreground="#888")
        self.file_lbl.pack(side=tk.LEFT, padx=10)

    def _build_ach_tab(self, nb):
        tab = ttk.Frame(nb, padding=16)
        nb.add(tab, text="  Достижения  ")

        top = ttk.Frame(tab)
        top.pack(fill=tk.X, pady=(0, 14))
        self.level_lbl = ttk.Label(top, text="Уровень 1", font=("Segoe UI", 16, "bold"))
        self.level_lbl.pack(side=tk.LEFT)
        self.xp_lbl = ttk.Label(top, text="", foreground="#888")
        self.xp_lbl.pack(side=tk.RIGHT)
        self.xp_bar = ttk.Progressbar(tab, maximum=1.0, value=0)
        self.xp_bar.pack(fill=tk.X, pady=(0, 18))

        self.ach_grid = ttk.Frame(tab)
        self.ach_grid.pack(fill=tk.BOTH, expand=True)
        for i in range(2):
            self.ach_grid.columnconfigure(i, weight=1, uniform="ach")

    def load_calls(self):
        q = self.search_var.get().lower().strip() if hasattr(self, "search_var") else ""
        sel = self.tree.selection()
        sel_id = self.tree.item(sel[0], "tags")[0] if sel else None

        self.tree.delete(*self.tree.get_children())
        for c in storage.get_all_calls():
            cid = c["call_id"]
            hay = f"{extract_phone(cid)} {c.get('category') or ''} {c.get('problem') or ''}".lower()
            if q and q not in hay:
                continue
            iid = self.tree.insert("", tk.END, tags=(cid,), values=(
                extract_phone(cid), extract_dt(cid), c.get("category") or "—",
                "✅" if c.get("is_resolved") else "❌"))
            if cid == sel_id:
                self.tree.selection_set(iid)

    def on_select(self):
        sel = self.tree.selection()
        if not sel:
            return
        cid = self.tree.item(sel[0], "tags")[0]
        call = storage.get_call(cid)
        if not call:
            return
        self.detail_head.config(text=extract_phone(cid))
        neg, neu, pos = call.get("sent_neg") or 0, call.get("sent_neu") or 0, call.get("sent_pos") or 0
        self.detail_meta.config(text=(
            f"{extract_dt(cid)}   ·   {call.get('category') or '—'}   ·   "
            f"{'решено' if call.get('is_resolved') else 'не решено'}\n"
            f"Тональность: 😟 {neg:.0%}  ·  😐 {neu:.0%}  ·  🙂 {pos:.0%}\n"
            f"Проблема: {call.get('problem') or '—'}\nДействие: {call.get('action') or '—'}"))
        self.current_summary = call.get("summary") or ""
        self.detail_summary.config(text=self.current_summary or "—")
        self.btn_copy.config(state=(tk.NORMAL if self.current_summary else tk.DISABLED))
        dialogue = call.get("dialogue_text")
        self.detail_text_label.config(
            text="Расшифровка (по голосам)" if dialogue else "Расшифровка")
        self.detail_text.config(state=tk.NORMAL)
        self.detail_text.delete("1.0", tk.END)
        self.detail_text.insert(tk.END, dialogue or call.get("full_text") or "—")
        self.detail_text.config(state=tk.DISABLED)
        self._load_audio(cid)

    def _load_audio(self, call_id):
        self.stop_play()
        self.current_audio_path = os.path.join(settings.get("recordings_folder"), call_id)
        if not os.path.exists(self.current_audio_path):
            self.file_lbl.config(text="файл записи не найден")
            self._set_player_state(tk.DISABLED)
            self.time_lbl.config(text="00:00 / 00:00")
            self.audio_duration = 0
            self.player_frame.pack_forget()
            return
        try:
            self.current_media = self.vlc_instance.media_new(self.current_audio_path)
            self.player.set_media(self.current_media)
            self.player.play()
            self.root.after(200, self._update_duration)
            self._set_player_state(tk.NORMAL)
            self.file_lbl.config(text=call_id)
            self.audio_duration = 0
            self.audio_position = 0
            self.is_playing = True
            self.is_paused = False
            self.btn_play.config(text="⏸")
            self.pos_var.set(0)
            self.time_lbl.config(text="00:00 / 00:00")
            self.player_frame.pack(fill=tk.X, pady=(8, 0))
        except Exception as e:
            self.file_lbl.config(text=f"ошибка аудио: {e}")
            self._set_player_state(tk.DISABLED)
            self.time_lbl.config(text="00:00 / 00:00")
            self.player_frame.pack_forget()

    def _update_duration(self):
        if self.player:
            dur = self.player.get_length() / 1000.0
            if dur > 0:
                self.audio_duration = dur
                self.scale.config(to=max(dur, 1))
                self.time_lbl.config(text=f"00:00 / {fmt_time(dur)}")
            else:
                self.root.after(1000, self._update_duration)

    def _set_player_state(self, state):
        for b in self.player_btns:
            b.config(state=state)
        self.btn_play.config(text="▶")

    def toggle_play(self):
        if not self.current_audio_path:
            return
        if self.is_playing:
            self.player.pause()
            self.is_playing = False
            self.is_paused = True
            self.btn_play.config(text="▶")
        elif self.is_paused:
            self.player.play()
            self.is_playing = True
            self.is_paused = False
            self.btn_play.config(text="⏸")
        else:
            self.player.play()
            self.is_playing = True
            self.is_paused = False
            self.btn_play.config(text="⏸")

    def _on_scale_drag(self, event):
        if self.audio_duration > 0:
            new_pos = self.pos_var.get()
            if new_pos < 0:
                new_pos = 0
            if new_pos > self.audio_duration:
                new_pos = self.audio_duration
            self.time_lbl.config(text=f"{fmt_time(new_pos)} / {fmt_time(self.audio_duration)}")

    def _on_seek(self, _event):
        if self.player and self.audio_duration > 0:
            new_pos = self.pos_var.get()
            if new_pos < 0:
                new_pos = 0
            if new_pos > self.audio_duration:
                new_pos = self.audio_duration
            self.player.set_time(int(new_pos * 1000))
            self.audio_position = new_pos
            self.time_lbl.config(text=f"{fmt_time(new_pos)} / {fmt_time(self.audio_duration)}")
        self.is_seeking = False

    def skip(self, delta):
        if not self.player or self.audio_duration == 0:
            return
        current = self.player.get_time() / 1000.0
        new_pos = max(0, min(current + delta, self.audio_duration - 0.2))
        self.player.set_time(int(new_pos * 1000))
        self.audio_position = new_pos
        self.pos_var.set(new_pos)
        self.time_lbl.config(text=f"{fmt_time(new_pos)} / {fmt_time(self.audio_duration)}")

    def stop_play(self):
        if self.player:
            self.player.stop()
        self.is_playing = False
        self.is_paused = False
        self.btn_play.config(text="▶")
        self.audio_position = 0
        self.pos_var.set(0)
        self.time_lbl.config(text=f"00:00 / {fmt_time(self.audio_duration)}")

    def _tick(self):
        if self.is_playing and not self.is_seeking and self.player:
            try:
                pos_ms = self.player.get_time()
                if pos_ms != -1 and self.audio_duration > 0:
                    self.audio_position = pos_ms / 1000.0
                    self.pos_var.set(self.audio_position)
                    self.time_lbl.config(text=f"{fmt_time(self.audio_position)} / {fmt_time(self.audio_duration)}")
            except Exception:
                pass
            state = self.player.get_state()
            if state == vlc.State.Ended or state == vlc.State.Stopped:
                if self.is_playing:
                    self.is_playing = False
                    self.is_paused = False
                    self.btn_play.config(text="▶")
                    self.audio_position = self.audio_duration
                    self.pos_var.set(self.audio_duration)
                    self.time_lbl.config(text=f"{fmt_time(self.audio_duration)} / {fmt_time(self.audio_duration)}")
        self.root.after(300, self._tick)

    def refresh_achievements(self):
        stats = storage.get_stats()
        newly = achievements.sync_unlocks(stats)
        xp = achievements.xp_for(stats)
        level, into, needed, frac = achievements.level_info(xp)
        self.level_lbl.config(text=f"Уровень {level}")
        self.xp_lbl.config(text=f"XP {xp}  ·  до след. уровня {needed - into}")
        self.xp_bar.config(value=frac)

        for w in self.ach_grid.winfo_children():
            w.destroy()
        for idx, a in enumerate(achievements.evaluate(stats)):
            self._ach_card(self.ach_grid, a, idx // 2, idx % 2)

        for a in newly:
            messagebox.showinfo("Новое достижение!", f"{a['icon']}  {a['title']}\n{a['desc']}")

    def _ach_card(self, parent, a, r, c):
        card = ttk.Frame(parent, padding=12, relief=tk.SOLID, borderwidth=1)
        card.grid(row=r, column=c, sticky="nsew", padx=6, pady=6)
        unlocked = a["unlocked"]
        head = ttk.Frame(card)
        head.pack(fill=tk.X)
        ttk.Label(head, text=a["icon"], font=("Segoe UI", 18)).pack(side=tk.LEFT, padx=(0, 8))
        title = ttk.Label(head, text=a["title"], font=("Segoe UI", 11, "bold"),
                          foreground=("" if unlocked else "#888"))
        title.pack(side=tk.LEFT)
        if unlocked:
            ttk.Label(head, text="✓", foreground="#3fb950",
                      font=("Segoe UI", 12, "bold")).pack(side=tk.RIGHT)
        ttk.Label(card, text=a["desc"], foreground="#888").pack(anchor=tk.W, pady=(4, 6))
        ttk.Progressbar(card, maximum=1.0, value=a["progress"]).pack(fill=tk.X)
        ttk.Label(card, text=f"{a['current']} / {a['target']}",
                  foreground="#888").pack(anchor=tk.E, pady=(2, 0))

    def toggle_bot(self):
        if self.bot.is_running():
            self.bot.stop()
            self.status.config(text="● остановлен", foreground="#e05656")
            self.btn_bot.config(text="▶ Запустить бота")
        else:
            self.bot.start()
            self.status.config(text="● работает", foreground="#3fb950")
            self.btn_bot.config(text="⏹ Остановить бота")

    def toggle_theme(self):
        new = "light" if sv_ttk.get_theme() == "dark" else "dark"
        sv_ttk.set_theme(new)
        settings.set("theme", new)
        self.btn_theme.config(text="☀" if new == "dark" else "☽")

    def _operator(self):
        return (settings.get("operator_id") or os.getenv("OPERATOR_ID")
                or os.getenv("COMPUTERNAME") or "не задан")

    def _refresh_operator_label(self):
        self.op_label.config(text=f"👤 {self._operator()}")

    def _first_run_operator(self):
        result = NameDialog(self.root).result
        if result:
            settings.set("operator_id", result)
            self._refresh_operator_label()

    def copy_summary(self):
        text = (self.current_summary or "").strip()
        if not text:
            return
        self.root.clipboard_clear()
        self.root.clipboard_append(text)
        self.root.update()
        self.log_var.set("✔ Резюме скопировано в буфер обмена")

    def _copy_email(self):
        email = "123maverik123@gmail.com"
        self.root.clipboard_clear()
        self.root.clipboard_append(email)
        self.root.update()
        self.log_var.set("✉️ Email скопирован в буфер обмена")

    def choose_folder(self):
        initial = settings.get("recordings_folder") or os.path.expanduser("~")
        if not os.path.isdir(initial):
            initial = os.path.expanduser("~")
        folder = DirChooser(self.root, initial).result
        if folder:
            settings.set("recordings_folder", folder)
            messagebox.showinfo("Папка изменена",
                                "Папка сохранена.\nЕсли бот запущен — перезапустите его, чтобы он следил за новой папкой.",
                                parent=self.root)

    def check_updates_manual(self):
        self.updater.check_for_updates(silent=False)

    def show_subscription(self):
        """Показывает окно активации для продления подписки."""
        def on_activate(key):
            return license.activate_license(key)
        dialog = ActivationDialog(self.root, "active", on_activate)
        self.root.wait_window(dialog)
        if dialog.result:
            messagebox.showinfo("Успех", "Подписка обновлена.")
            self._update_license_label()

    def log_message(self, msg):
        self.root.after(0, lambda: self.log_var.set(msg[:120]))

    def _on_bot_log(self, msg):
        self.ui_queue.put(msg)

    def _poll(self):
        try:
            while True:
                self.log_var.set(self.ui_queue.get_nowait()[:120])
        except queue.Empty:
            pass
        try:
            cur = storage.count_calls()
            if cur != self._last_count:
                self._last_count = cur
                self.load_calls()
                self.refresh_achievements()
        except Exception:
            pass
        self.root.after(1000, self._poll)

    def on_close(self):
        if self.player:
            self.player.stop()
        if self.bot.is_running():
            self.bot.stop()
        self.root.destroy()


if __name__ == "__main__":
    root = tk.Tk()
    App(root)
    root.mainloop()