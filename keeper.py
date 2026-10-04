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
import threading
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog, filedialog

import pwgen
import browser_io
import watcher
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
            ("Заметка", "note"),
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
        if not self.vars["title"].get().strip():
            messagebox.showwarning(APP_NAME, "Укажите название записи.", parent=self)
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
        # слежение за браузером включено всегда (по умолчанию)
        self.watch_on = True
        self._watch_job = None
        self._last_site = None
        self.detected_site = None

        if not self._unlock():
            self.destroy()
            return

        self._build_ui()
        self._refresh()
        # сразу начинаем следить за браузером, если это возможно
        if watcher.available():
            self._watch_tick()

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
        toolbar = ttk.Frame(self, padding=(10, 8))
        toolbar.pack(fill="x")
        ttk.Button(toolbar, text="Добавить", command=self._add).pack(side="left")
        ttk.Button(toolbar, text="Изменить", command=self._edit).pack(side="left", padx=4)
        ttk.Button(toolbar, text="Удалить", command=self._delete).pack(side="left")
        ttk.Button(toolbar, text="Копировать пароль",
                   command=self._copy_pw).pack(side="left", padx=4)
        self._show_pw = False
        self._show_pw_btn = ttk.Button(toolbar, text="Показать пароли",
                                       command=self._toggle_show_pw)
        self._show_pw_btn.pack(side="left", padx=4)
        ttk.Button(toolbar, text="Импорт из браузера",
                   command=self._import_browser).pack(side="left")
        ttk.Button(toolbar, text="Экспорт для браузера",
                   command=self._export_browser).pack(side="left", padx=4)
        ttk.Button(toolbar, text="Сменить мастер-пароль",
                   command=self._change_master).pack(side="right")

        self.search_var = tk.StringVar()
        self.search_var.trace_add("write", lambda *_: self._refresh())
        sfrm = ttk.Frame(self, padding=(10, 0))
        sfrm.pack(fill="x")
        ttk.Label(sfrm, text="Поиск:").pack(side="left")
        ttk.Entry(sfrm, textvariable=self.search_var).pack(
            side="left", fill="x", expand=True, padx=(6, 0))

        cols = ("title", "login", "password", "url")
        self.tree = ttk.Treeview(self, columns=cols, show="headings", selectmode="browse")
        self.tree.heading("title", text="Название")
        self.tree.heading("login", text="Логин")
        self.tree.heading("password", text="Пароль")
        self.tree.heading("url", text="Сайт")
        self.tree.column("title", width=180)
        self.tree.column("login", width=160)
        self.tree.column("password", width=140)
        self.tree.column("url", width=200)
        self.tree.pack(fill="both", expand=True, padx=10, pady=10)
        self.tree.bind("<Double-1>", lambda _e: self._edit())

        self.status = ttk.Label(self, anchor="w", padding=(10, 4))
        self.status.pack(fill="x")

    def _pw_cell(self, pw):
        """Что показывать в столбце «Пароль»: точки или сам пароль."""
        if not pw:
            return ""
        return pw if self._show_pw else "\u2022" * 8

    def _toggle_show_pw(self):
        """Показать / скрыть пароли в таблице."""
        self._show_pw = not self._show_pw
        self._show_pw_btn.config(
            text="Скрыть пароли" if self._show_pw else "Показать пароли")
        if self.detected_site:
            self._show_matches(self.detected_site)
        else:
            self._refresh()

    def _refresh(self):
        query = (self.search_var.get() if hasattr(self, "search_var") else "").lower()
        self.tree.delete(*self.tree.get_children())
        self._index_map = {}
        for i, e in enumerate(self.vault.entries):
            hay = (e.get("title", "") + e.get("login", "") + e.get("url", "")).lower()
            if query and query not in hay:
                continue
            iid = self.tree.insert(
                "", "end",
                values=(e.get("title", ""), e.get("login", ""),
                        self._pw_cell(e.get("password", "")), e.get("url", "")))
            self._index_map[iid] = i
        self.status.config(text="Записей: %d" % len(self.vault.entries))

    def _selected_index(self):
        sel = self.tree.selection()
        if not sel:
            return None
        return self._index_map.get(sel[0])

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
        if idx is None:
            return
        title = self.vault.entries[idx].get("title", "")
        if messagebox.askyesno(APP_NAME, "Удалить запись «%s»?" % title):
            self.vault.delete(idx)
            self._refresh()

    def _copy_pw(self):
        idx = self._selected_index()
        if idx is None:
            return
        pw = self.vault.entries[idx].get("password", "")
        self.clipboard_clear()
        self.clipboard_append(pw)
        self.status.config(text="Пароль скопирован в буфер обмена.")

    def _import_browser(self):
        """Импорт паролей из браузеров (Chrome/Edge/Яндекс и др.)."""
        found = browser_io.list_browsers()
        if not found:
            messagebox.showinfo(
                APP_NAME,
                "Не найдено поддерживаемых браузеров (Chrome, Edge, Яндекс, Brave, Opera).")
            return
        if not messagebox.askyesno(
                APP_NAME,
                "Найдены браузеры:\n  %s\n\n"
                "Импортировать из них сохранённые пароли?\n"
                "(совет: закройте браузер перед импортом)" % "\n  ".join(found)):
            return
        try:
            imported = browser_io.import_passwords()
        except browser_io.BrowserError as e:
            messagebox.showerror(APP_NAME, str(e))
            return
        except Exception as e:
            messagebox.showerror(APP_NAME, "Ошибка импорта: %s" % e)
            return

        # пропускаем дубли по (сайт + логин + пароль)
        existing = {(e.get("url", ""), e.get("login", ""), e.get("password", ""))
                    for e in self.vault.entries}
        added = 0
        for e in imported:
            key = (e.get("url", ""), e.get("login", ""), e.get("password", ""))
            if key in existing:
                continue
            self.vault.entries.append(e)
            existing.add(key)
            added += 1
        if added:
            self.vault.save()
        self._refresh()
        messagebox.showinfo(
            APP_NAME,
            "Готово.\nНайдено в браузерах: %d\nДобавлено новых: %d\nПропущено дублей: %d"
            % (len(imported), added, len(imported) - added))

    def _export_browser(self):
        """Экспорт в CSV для импорта в браузер."""
        if not self.vault.entries:
            messagebox.showinfo(APP_NAME, "Нет записей для экспорта.")
            return
        path = filedialog.asksaveasfilename(
            parent=self,
            title="Сохранить пароли для браузера",
            defaultextension=".csv",
            initialfile="klyuchnica_passwords.csv",
            filetypes=[("CSV (для браузера)", "*.csv")])
        if not path:
            return
        try:
            n = browser_io.export_csv(self.vault.entries, path)
        except Exception as e:
            messagebox.showerror(APP_NAME, "Ошибка экспорта: %s" % e)
            return
        messagebox.showinfo(
            APP_NAME,
            "Экспортировано записей: %d\n\n"
            "Как загрузить в браузер (Chrome/Яндекс/Edge):\n"
            "1. Откройте настройки паролей браузера.\n"
            "2. «Импорт» → выберите этот CSV-файл.\n\n"
            "❗ Файл не зашифрован — удалите его после импорта!" % n)

    # ---------- слежение за браузером ----------
    def _watch_tick(self):
        """Один цикл проверки — в фоновом потоке, чтобы окно не подвисало."""
        if not self.watch_on:
            return

        def work():
            try:
                site = watcher.get_active_site()
            except Exception:
                site = None
            try:
                self.after(0, lambda: self._watch_result(site))
            except Exception:
                pass

        threading.Thread(target=work, daemon=True).start()

    def _watch_result(self, site):
        """Пришёл результат определения сайта — обновить список."""
        if not self.watch_on:
            return
        if site and site != self._last_site:
            self._last_site = site
            self.detected_site = site
            self._show_matches(site)
        # следующая проверка
        self._watch_job = self.after(1200, self._watch_tick)

    def _show_matches(self, site):
        """Показать только записи, подходящие к открытому сайту."""
        self.tree.delete(*self.tree.get_children())
        self._index_map = {}
        for i, e in enumerate(self.vault.entries):
            if watcher.same_site(site, e.get("url", "")):
                iid = self.tree.insert(
                    "", "end",
                    values=(e.get("title", ""), e.get("login", ""),
                            self._pw_cell(e.get("password", "")), e.get("url", "")))
                self._index_map[iid] = i
        matches = len(self._index_map)
        if matches:
            first = next(iter(self._index_map))
            self.tree.selection_set(first)
            self.tree.focus(first)
            self.status.config(
                text="Сайт: %s — паролей: %d. Нажмите «Копировать пароль»." % (site, matches))
        else:
            self.status.config(text="Сайт: %s — подходящих паролей нет." % site)

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
