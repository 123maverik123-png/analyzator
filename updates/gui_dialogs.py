# gui_dialogs.py — модальные окна (выбор папки, ввод имени, активация)
import os
import sys
import string
import tkinter as tk
from tkinter import ttk, messagebox


class DirChooser(tk.Toplevel):
    DUMMY = "::dummy"

    def __init__(self, parent, initialdir=None):
        super().__init__(parent)
        self.title("Выбор папки с записями")
        self.geometry("560x540")
        self.transient(parent)
        self.result = None

        ttk.Label(self, text="Выберите папку с записями разговоров:",
                  padding=(12, 10)).pack(anchor=tk.W)

        wrap = ttk.Frame(self, padding=(12, 0))
        wrap.pack(fill=tk.BOTH, expand=True)
        self.tree = ttk.Treeview(wrap, show="tree", selectmode="browse")
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        sb = ttk.Scrollbar(wrap, orient=tk.VERTICAL, command=self.tree.yview)
        self.tree.configure(yscrollcommand=sb.set)
        sb.pack(side=tk.RIGHT, fill=tk.Y)
        self.tree.bind("<<TreeviewOpen>>", lambda e: self._expand(self.tree.focus()))
        self.tree.bind("<<TreeviewSelect>>", lambda e: self.path_var.set(self.tree.focus()))

        self.path_var = tk.StringVar()
        ttk.Entry(self, textvariable=self.path_var).pack(fill=tk.X, padx=12, pady=8)

        btns = ttk.Frame(self, padding=12)
        btns.pack(fill=tk.X)
        ttk.Button(btns, text="Отмена", command=self.destroy).pack(side=tk.RIGHT)
        ttk.Button(btns, text="Выбрать", command=self._ok).pack(side=tk.RIGHT, padx=8)

        for d in self._drives():
            self._add(_root="", path=d, text=d)
        if initialdir:
            try:
                self._reveal(os.path.normpath(initialdir))
            except Exception:
                pass

        self.lift()
        self.focus_force()
        self.grab_set()
        self.wait_window(self)

    def _drives(self):
        try:
            return list(os.listdrives())
        except Exception:
            return [f"{c}:\\" for c in string.ascii_uppercase if os.path.exists(f"{c}:\\")]

    def _add(self, _root, path, text):
        if self.tree.exists(path):
            return
        self.tree.insert(_root, tk.END, iid=path, text=" " + text, open=False)
        self.tree.insert(path, tk.END, iid=path + self.DUMMY, text="")

    def _expand(self, path):
        kids = self.tree.get_children(path)
        if not (kids and kids[0].endswith(self.DUMMY)):
            return
        self.tree.delete(*kids)
        try:
            subdirs = sorted((e for e in os.scandir(path) if e.is_dir()),
                             key=lambda e: e.name.lower())
        except (PermissionError, OSError):
            subdirs = []
        for e in subdirs:
            self._add(_root=path, path=e.path, text=e.name)

    def _reveal(self, path):
        chain, p = [], path
        while True:
            chain.append(p)
            parent = os.path.dirname(p)
            if parent == p:
                break
            p = parent
        for node in reversed(chain):
            if self.tree.exists(node):
                self.tree.item(node, open=True)
                self._expand(node)
        if self.tree.exists(path):
            self.tree.selection_set(path)
            self.tree.focus(path)
            self.tree.see(path)
            self.path_var.set(path)

    def _ok(self):
        sel = self.path_var.get().strip() or self.tree.focus()
        if sel and os.path.isdir(sel):
            self.result = sel
            self.destroy()
        else:
            messagebox.showwarning("Папка", "Выберите существующую папку.", parent=self)


class NameDialog(tk.Toplevel):
    def __init__(self, parent):
        super().__init__(parent)
        self.title("Вход")
        self.geometry("440x250")
        self.resizable(False, False)
        self.transient(parent)
        self.result = None

        frm = ttk.Frame(self, padding=22)
        frm.pack(fill=tk.BOTH, expand=True)
        ttk.Label(frm, text="Введите вашу фамилию и имя",
                  font=("Segoe UI", 12, "bold")).pack(anchor=tk.W)

        self.var = tk.StringVar()
        ent = ttk.Entry(frm, textvariable=self.var, font=("Segoe UI", 12))
        ent.pack(fill=tk.X, pady=12)
        ent.focus_set()
        ent.bind("<Return>", lambda e: self._ok())

        ttk.Label(frm,
                  text="⚠  Имя вводится только один раз.\nВнимательно перепроверьте данные перед сохранением.",
                  foreground="#e0a000", justify=tk.LEFT).pack(anchor=tk.W, pady=(0, 16))
        ttk.Button(frm, text="Сохранить", command=self._ok).pack(anchor=tk.E)

        self.lift()
        self.focus_force()
        self.grab_set()
        self.wait_window(self)

    def _ok(self):
        name = " ".join(self.var.get().split())
        if len(name.split()) < 2:
            messagebox.showwarning("Проверьте данные", "Укажите фамилию и имя.", parent=self)
            return
        if messagebox.askyesno(
                "Подтверждение",
                f"Сохранить «{name}»?\n\nИмя вводится один раз — изменить его потом будет нельзя.",
                parent=self):
            self.result = name
            self.destroy()


class ActivationDialog(tk.Toplevel):
    def __init__(self, parent, status, on_activate):
        super().__init__(parent)
        self.title("Активация подписки")
        self.geometry("420x300")
        self.transient(parent)
        self.grab_set()
        self.on_activate = on_activate
        self.result = None

        if status == "expired":
            msg = "Ваш демо-период истёк. Введите лицензионный ключ для продолжения работы."
        else:
            msg = "Сервер лицензирования недоступен. Проверьте соединение или введите ключ вручную."

        ttk.Label(self, text=msg, wraplength=380, justify=tk.CENTER).pack(pady=15)

        ttk.Label(self, text="Лицензионный ключ:").pack(pady=(10,0))
        self.key_var = tk.StringVar()
        ttk.Entry(self, textvariable=self.key_var, width=40).pack(pady=5)

        btn_frame = ttk.Frame(self)
        btn_frame.pack(pady=15)
        ttk.Button(btn_frame, text="Активировать", command=self._activate).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Выйти", command=self._quit).pack(side=tk.LEFT, padx=5)

        self.lift()
        self.focus_force()

    def _activate(self):
        key = self.key_var.get().strip()
        if not key:
            messagebox.showwarning("Ошибка", "Введите ключ активации.")
            return
        success, msg = self.on_activate(key)
        if success:
            messagebox.showinfo("Успех", msg)
            self.result = True
            self.destroy()
        else:
            messagebox.showerror("Ошибка", msg)

    def _quit(self):
        self.result = False
        self.destroy()
        sys.exit(0)