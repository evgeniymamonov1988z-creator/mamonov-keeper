# -*- coding: utf-8 -*-
"""
Ключница — простой локальный менеджер паролей для Windows.

Все пароли хранятся в одном зашифрованном файле на вашем
компьютере. Ничего в интернет не отправляется. Открыть
хранилище можно только мастер-паролем.

© Evgeniy Mamonov — evgeniymamonov.com
"""

import os
import sys
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog

import pwgen
from vault import Vault, WrongPassword, BadFile

APP_NAME = "Ключница"


def vault_path() -> str:
    """Путь к файлу хранилища в %APPDATA%\\MAMONOV\\Klyuchnica."""
    base = os.environ.get("APPDATA") or os.path.expanduser("~")
    folder = os.path.join(base, "MAMONOV", "Klyuchnica")
    os.makedirs(folder, exist_ok=True)
    return os.path.join(folder, "vault.dat")


class EntryDialog(tk.Toplevel):
    """Окно добавления / редактирования записи."""

    def __init__(self, master, title, entry=None):
        super().__init__(master)
        self.title(title)
        self.resizable(False, False)
        self.result = None
        entry = entry or {}

        self._show_pw = tk.BooleanVar(value=False)
        self.vars = {
            "title": tk.StringVar(value=entry.get("title", "")),
            "login": tk.StringVar(value=entry.get("login", "")),
            "password": tk.StringVar(value=entry.get("password", "")),
            "url": tk.StringVar(value=entry.get("url", "")),
            "note": tk.StringVar(value=entry.get("note", "")),
        }

        frm = ttk.Frame(self, padding=16)
        frm.grid(sticky="nsew")
        rows = [
            ("Название", "title"),
            ("Логин", "login"),
            ("Пароль", "password"),
            ("Сайт", "url"),
            ("Примечание", "note"),
        ]
        for i, (label, key) in enumerate(rows):
            ttk.Label(frm, text=label + ":").grid(row=i, column=0, sticky="e", padx=(0, 8), pady=4)
            if key == "password":
                self._pw_entry = ttk.Entry(frm, textvariable=self.vars[key], width=34, show="\u2022")
                self._pw_entry.grid(row=i, column=1, sticky="we", pady=4)
                btns = ttk.Frame(frm)
                btns.grid(row=i, column=2, padx=(8, 0))
                ttk.Button(btns, text="👁", width=3, command=self._toggle).pack(side="left")
                ttk.Button(btns, text="Создать", command=self._generate).pack(side="left", padx=(4, 0))
            else:
                ttk.Entry(frm, textvariable=self.vars[key], width=34).grid(
                    row=i, column=1, columnspan=2, sticky="we", pady=4)

        bar = ttk.Frame(frm)
        bar.grid(row=len(rows), column=0, columnspan=3, pady=(14, 0), sticky="e")
        ttk.Button(bar, text="Отмена", command=self.destroy).pack(side="right")
        ttk.Button(bar, text="Сохранить", command=self._ok).pack(side="right", padx=(0, 8))

        self.transient(master)
        self.attributes("-topmost", True)
        self.grab_set()
        self.wait_window()

    def _toggle(self):
        self._show_pw.set(not self._show_pw.get())
        self._pw_entry.config(show="" if self._show_pw.get() else "\u2022")

    def _generate(self):
        pw = pwgen.generate(16)
        self.vars["password"].set(pw)
        self._pw_entry.config(show="")
        self._show_pw.set(True)

    def _ok(self):
        has_any = any(self.vars[k].get().strip() for k in ("login", "password", "note"))
        if not has_any:
            messagebox.showwarning(
                APP_NAME, "Заполните хотя бы логин, пароль или примечание.", parent=self)
            return
        self.result = {k: v.get().strip() for k, v in self.vars.items()}
        self.destroy()


class App(tk.Tk):
    """Главное окно менеджера паролей."""

    def __init__(self):
        super().__init__()
        self.title(APP_NAME)
        self.geometry("760x440")
        self.minsize(640, 380)
        # Окно поверх всех приложений (не прячется за браузером и т.п.)
        self.attributes("-topmost", True)
        self.vault = Vault(vault_path())

        if not self._unlock():
            self.destroy()
            return

        self._build_ui()
        self._refresh()

    # ---------- разблокировка ----------
    def _unlock(self) -> bool:
        """Создать мастер-пароль (первый запуск) или открыть хранилище."""
        self.withdraw()
        if not self.vault.exists():
            pw1 = simpledialog.askstring(
                APP_NAME,
                "Это первый запуск.\nПридумайте мастер-пароль (запомните его!):",
                show="\u2022", parent=self)
            if not pw1:
                return False
            pw2 = simpledialog.askstring(
                APP_NAME, "Повторите мастер-пароль:", show="\u2022", parent=self)
            if pw1 != pw2:
                messagebox.showerror(APP_NAME, "Пароли не совпадают.")
                return False
            self.vault.create(pw1)
            messagebox.showinfo(
                APP_NAME,
                "Хранилище создано.\n\nВАЖНО: если забыть мастер-пароль, "
                "восстановить пароли будет невозможно.")
            self.deiconify()
            return True

        for _ in range(3):
            pw = simpledialog.askstring(
                APP_NAME, "Введите мастер-пароль:", show="\u2022", parent=self)
            if pw is None:
                return False
            try:
                self.vault.open(pw)
                self.deiconify()
                return True
            except WrongPassword:
                messagebox.showerror(APP_NAME, "Неверный мастер-пароль. Попробуйте ещё раз.")
            except BadFile as e:
                messagebox.showerror(APP_NAME, str(e))
                return False
        return False

    # ---------- интерфейс ----------
    def _build_ui(self):
        # Строка поиска сверху
        self.search_var = tk.StringVar()
        self.search_var.trace_add("write", lambda *_: self._refresh())
        sfrm = ttk.Frame(self, padding=(10, 8))
        sfrm.pack(fill="x")
        ttk.Label(sfrm, text="Поиск:").pack(side="left")
        ttk.Entry(sfrm, textvariable=self.search_var).pack(
            side="left", fill="x", expand=True, padx=(6, 0))

        # Таблица записей. Последний столбец — корзина для удаления.
        cols = ("note", "login", "password", "del")
        self.tree = ttk.Treeview(self, columns=cols, show="headings", selectmode="browse")
        self.tree.heading("note", text="Примечание")
        self.tree.heading("login", text="Логин")
        self.tree.heading("password", text="Пароль")
        self.tree.heading("del", text="")
        self.tree.column("note", width=230)
        self.tree.column("login", width=200)
        self.tree.column("password", width=160)
        self.tree.column("del", width=40, anchor="center", stretch=False)
        self.tree.pack(fill="both", expand=True, padx=10, pady=(8, 4))
        # клик по ячейке — копировать; клик по корзине — удалить
        self.tree.bind("<Button-1>", self._on_click)
        # двойной клик — редактировать запись
        self.tree.bind("<Double-1>", self._on_double_click)

        # Нижняя панель: «+» для добавления под списком
        bottom = ttk.Frame(self, padding=(10, 2))
        bottom.pack(fill="x")
        ttk.Button(bottom, text="\u2795  Добавить", command=self._add).pack(side="left")
        ttk.Button(bottom, text="Сменить мастер-пароль",
                   command=self._change_master).pack(side="right")

        self.status = ttk.Label(self, anchor="w", padding=(10, 4))
        self.status.pack(fill="x")
        self.status.config(
            text="Клик по ячейке — скопировать. Клик по 🗑 — удалить. Двойной клик — изменить.")

    def _pw_cell(self, pw):
        """В столбце «Пароль» всегда точки (сам пароль — кликом копируется)."""
        return "\u2022" * 8 if pw else ""

    def _refresh(self):
        query = (self.search_var.get() if hasattr(self, "search_var") else "").lower()
        self.tree.delete(*self.tree.get_children())
        self._index_map = {}
        for i, e in enumerate(self.vault.entries):
            hay = (e.get("title", "") + e.get("login", "") + e.get("url", "")
                   + e.get("note", "")).lower()
            if query and query not in hay:
                continue
            iid = self.tree.insert(
                "", "end",
                values=(e.get("note", ""), e.get("login", ""),
                        self._pw_cell(e.get("password", "")), "\U0001f5d1"))
            self._index_map[iid] = i
        self.status.config(text="Записей: %d" % len(self.vault.entries))

    def _selected_index(self):
        sel = self.tree.selection()
        if not sel:
            return None
        return self._index_map.get(sel[0])

    # ---------- клики по таблице ----------
    def _on_click(self, event):
        """Клик по ячейке: копировать значение; клик по корзине: удалить."""
        if self.tree.identify("region", event.x, event.y) != "cell":
            return
        row = self.tree.identify_row(event.y)
        if not row:
            return
        idx = self._index_map.get(row)
        if idx is None:
            return
        col = self.tree.identify_column(event.x)
        if col == "#4":            # корзина
            self._delete_index(idx)
            return
        e = self.vault.entries[idx]
        fields = {
            "#1": ("note", "Примечание"),
            "#2": ("login", "Логин"),
            "#3": ("password", "Пароль"),
        }
        if col not in fields:
            return
        key, label = fields[col]
        value = e.get(key, "")
        if not value:
            self.status.config(text="Это поле пустое.")
            return
        self.clipboard_clear()
        self.clipboard_append(value)
        self.status.config(text="Скопировано: %s" % label)

    def _on_double_click(self, event):
        """Двойной клик по строке (не по корзине) — изменить запись."""
        if self.tree.identify("region", event.x, event.y) != "cell":
            return
        if self.tree.identify_column(event.x) == "#4":
            return
        self._edit()

    # ---------- действия ----------
    def _add(self):
        dlg = EntryDialog(self, "Новая запись")
        if dlg.result:
            self.vault.add(dlg.result)
            self._refresh()

    def _edit(self):
        idx = self._selected_index()
        if idx is None:
            return
        dlg = EntryDialog(self, "Изменить запись", self.vault.entries[idx])
        if dlg.result:
            self.vault.update(idx, dlg.result)
            self._refresh()

    def _delete(self):
        idx = self._selected_index()
        self._delete_index(idx)

    def _delete_index(self, idx):
        """Удалить запись по номеру (с подтверждением)."""
        if idx is None:
            return
        e = self.vault.entries[idx]
        label = e.get("note") or e.get("login") or e.get("title") or "эту запись"
        if messagebox.askyesno(APP_NAME, "Удалить «%s»?" % label, parent=self):
            self.vault.delete(idx)
            self._refresh()

    def _change_master(self):
        p1 = simpledialog.askstring(APP_NAME, "Новый мастер-пароль:", show="\u2022", parent=self)
        if not p1:
            return
        p2 = simpledialog.askstring(APP_NAME, "Повторите новый пароль:", show="\u2022", parent=self)
        if p1 != p2:
            messagebox.showerror(APP_NAME, "Пароли не совпадают.")
            return
        self.vault.change_master_password(p1)
        messagebox.showinfo(APP_NAME, "Мастер-пароль изменён.")


def main():
    app = App()
    try:
        app.mainloop()
    except tk.TclError:
        pass


if __name__ == "__main__":
    main()
