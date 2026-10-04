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
from tkinter import ttk, messagebox, simpledialog, filedialog

import datetime

import vault as vaultmod
from vault import Vault, WrongPassword, BadFile

APP_NAME = "Ключница"


def resource_path(name: str) -> str:
    """Путь к ресурсу рядом с программой (работает и в .exe PyInstaller)."""
    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, name)


def vault_path() -> str:
    """Путь к файлу хранилища в %APPDATA%\\MAMONOV\\Klyuchnica."""
    base = os.environ.get("APPDATA") or os.path.expanduser("~")
    folder = os.path.join(base, "MAMONOV", "Klyuchnica")
    os.makedirs(folder, exist_ok=True)
    return os.path.join(folder, "vault.dat")


class App(tk.Tk):
    """Главное окно менеджера паролей."""

    def __init__(self):
        super().__init__()
        self.title(APP_NAME)
        self.geometry("620x380")
        self.minsize(540, 320)
        # Окно поверх всех приложений (не прячется за браузером и т.п.)
        self.attributes("-topmost", True)
        # значок окна и панели задач
        try:
            self.iconbitmap(resource_path("keeper.ico"))
        except Exception:
            pass
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
            self._master = pw1
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
                self._master = pw
                self.deiconify()
                return True
            except WrongPassword:
                messagebox.showerror(APP_NAME, "Неверный мастер-пароль. Попробуйте ещё раз.")
            except BadFile as e:
                messagebox.showerror(APP_NAME, str(e))
                return False
        return False

    # ---------- тёмная тема ----------
    def _enable_clipboard_hotkeys(self):
        """Заставить Ctrl+C/V/X/A работать даже при русской раскладке.

        При русской раскладке Tk не понимает Ctrl+V (видит кириллицу),
        поэтому ловим нажатие по коду клавиши.
        """
        self.bind_all("<Control-KeyPress>", self._clipboard_hotkey)

    def _clipboard_hotkey(self, event):
        if not (event.state & 0x0004):   # должен быть зажат Ctrl
            return
        ks = (event.keysym or "").lower()
        # латинскую раскладку Tk обработает сам — не дублируем
        if ks in ("v", "c", "x", "a"):
            return
        w = event.widget
        kc = event.keycode
        try:
            if kc == 86:        # V — вставить
                w.event_generate("<<Paste>>")
                return "break"
            if kc == 67:        # C — копировать
                w.event_generate("<<Copy>>")
                return "break"
            if kc == 88:        # X — вырезать
                w.event_generate("<<Cut>>")
                return "break"
            if kc == 65:        # A — выделить всё
                if isinstance(w, tk.Text):
                    w.tag_add("sel", "1.0", "end-1c")
                elif hasattr(w, "select_range"):
                    w.select_range(0, "end")
                return "break"
        except tk.TclError:
            pass

    # ---------- тёмная тема ----------
    def _apply_dark_theme(self):
        BG = "#000000"       # фон окна (чёрный)
        PANEL = "#000000"    # поля/таблица
        FG = "#ffffff"       # текст (белый)
        SEL = "#3a5a8c"      # выделение
        BTN = "#1a1a1a"
        BTN_ACT = "#333333"
        self.configure(bg=BG)
        style = ttk.Style(self)
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass
        style.configure("TFrame", background=BG)
        style.configure("TLabel", background=BG, foreground=FG)
        style.configure("TButton", background=BTN, foreground=FG, borderwidth=0)
        style.map("TButton",
                  background=[("active", BTN_ACT), ("pressed", BTN_ACT)])
        style.configure("TEntry", fieldbackground=PANEL, foreground=FG,
                        insertcolor=FG, bordercolor=BTN)
        style.configure("Treeview", background=PANEL, foreground=FG,
                        fieldbackground=PANEL, bordercolor=BG, borderwidth=0)
        style.map("Treeview",
                  background=[("selected", SEL)],
                  foreground=[("selected", "#ffffff")])
        style.configure("Treeview.Heading", background=BTN, foreground=FG,
                        borderwidth=0)
        style.map("Treeview.Heading", background=[("active", BTN_ACT)])

    # ---------- интерфейс ----------
    def _build_ui(self):
        self._apply_dark_theme()
        self._enable_clipboard_hotkeys()
        # Строка поиска сверху
        self.search_var = tk.StringVar()
        self.search_var.trace_add("write", lambda *_: self._refresh())
        sfrm = ttk.Frame(self, padding=(10, 8))
        sfrm.pack(fill="x")
        ttk.Label(sfrm, text="Поиск:").pack(side="left")
        ttk.Entry(sfrm, textvariable=self.search_var).pack(
            side="left", fill="x", expand=True, padx=(6, 0))

        # Таблица записей. Последние столбцы — копировать строку и корзина.
        cols = ("note", "login", "password", "copy", "del")
        self.tree = ttk.Treeview(self, columns=cols, show="headings", selectmode="browse")
        self.tree.heading("note", text="Примечание")
        self.tree.heading("login", text="Логин")
        self.tree.heading("password", text="Пароль")
        self.tree.heading("copy", text="")
        self.tree.heading("del", text="")
        self.tree.column("note", width=190)
        self.tree.column("login", width=160)
        self.tree.column("password", width=120)
        self.tree.column("copy", width=40, anchor="center", stretch=False)
        self.tree.column("del", width=40, anchor="center", stretch=False)
        self.tree.pack(fill="both", expand=True, padx=10, pady=(8, 4))
        # чередующиеся строки на чёрном фоне, белый текст
        self.tree.tag_configure("odd", background="#000000", foreground="#ffffff")
        self.tree.tag_configure("even", background="#141414", foreground="#ffffff")
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

        # Панель архива: сохранить на Рабочий стол и загрузить из файла
        arc = ttk.Frame(self, padding=(10, 2))
        arc.pack(fill="x")
        ttk.Button(arc, text="Сохранить копию", command=self._save_backup).pack(side="left")
        ttk.Label(arc, text="Копия:").pack(side="left", padx=(14, 0))
        self.backup_var = tk.StringVar()
        bk_entry = ttk.Entry(arc, textvariable=self.backup_var, width=18)
        bk_entry.pack(side="left", padx=(4, 0))
        bk_entry.bind("<Return>", lambda e: self._load_backup(self.backup_var.get().strip()))
        ttk.Button(arc, text="\u2026", width=3, command=self._browse_backup).pack(side="left", padx=(4, 0))
        ttk.Button(arc, text="Загрузить",
                   command=lambda: self._load_backup(self.backup_var.get().strip())).pack(
                       side="left", padx=(4, 0))

        self._editor = None  # поле для редактирования прямо в таблице

        self.status = ttk.Label(self, anchor="w", padding=(10, 4))
        self.status.pack(fill="x")
        self.status.config(
            text="Клик по ячейке — скопировать. Двойной клик — изменить. Клик по 🗑 — удалить.")

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
                        self._pw_cell(e.get("password", "")), "\U0001f4cb", "\U0001f5d1"),
                tags=("even" if len(self._index_map) % 2 else "odd",))
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
        if col == "#5":            # корзина — удалить
            self._delete_index(idx)
            return
        if col == "#4":            # копировать всю строку
            self._copy_row(idx)
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

    def _copy_row(self, idx):
        """Скопировать всю строку (логин, пароль, примечание) в буфер."""
        e = self.vault.entries[idx]
        parts = []
        for key, label in (("login", "Логин"), ("password", "Пароль"),
                           ("note", "Примечание")):
            val = e.get(key, "")
            if val:
                parts.append("%s: %s" % (label, val))
        if not parts:
            self.status.config(text="Строка пустая.")
            return
        self.clipboard_clear()
        self.clipboard_append("\n".join(parts))
        self.status.config(text="Скопирована вся строка.")

    def _on_double_click(self, event):
        """Двойной клик по ячейке (не по корзине) — редактировать прямо в таблице."""
        if self.tree.identify("region", event.x, event.y) != "cell":
            return
        row = self.tree.identify_row(event.y)
        col = self.tree.identify_column(event.x)
        if not row or col == "#4":
            return
        if col == "#5":
            return
        self._begin_edit(row, col)

    # ---------- редактирование прямо в таблице ----------
    _COL_FIELD = {"#1": "note", "#2": "login", "#3": "password"}

    def _add(self):
        """«+»: добавить пустую строку и сразу дать ввести в неё данные."""
        self._close_editor()
        self.search_var.set("")  # чтобы новая строка точно была видна
        self.vault.add({"title": "", "login": "", "password": "", "url": "", "note": ""})
        self._refresh()
        new_idx = len(self.vault.entries) - 1
        iid = None
        for k, v in self._index_map.items():
            if v == new_idx:
                iid = k
                break
        if iid is None:
            return
        self.tree.selection_set(iid)
        self.tree.see(iid)
        # начать ввод с первого столбца (Примечание)
        self.after(50, lambda: self._begin_edit(iid, "#1"))

    def _begin_edit(self, iid, col):
        """Показать поле ввода поверх ячейки."""
        key = self._COL_FIELD.get(col)
        if key is None:
            return
        idx = self._index_map.get(iid)
        if idx is None:
            return
        self._close_editor()
        self.tree.see(iid)
        bbox = self.tree.bbox(iid, col)
        if not bbox:
            return
        x, y, w, h = bbox
        value = self.vault.entries[idx].get(key, "")
        if key == "password":
            # Ключ/пароль может быть длинным и многострочным (например, SSH-ключ).
            # Показываем повышенное поле, чтобы удобно вставлять целиком;
            # в таблице же всё равно останется одна строка (точки).
            ed = tk.Text(self.tree, wrap="word", height=6,
                         bg="#000000", fg="#ffffff", insertbackground="#ffffff",
                         relief="solid", borderwidth=1)
            ed.insert("1.0", value)
            ed.place(x=x, y=y, width=max(w, 300), height=max(h * 6, 110))
            ed.focus_set()
            ed.bind("<Escape>", lambda e: self._close_editor())
            ed.bind("<FocusOut>", lambda e: self._commit_edit())
            self._editor_is_text = True
            self.status.config(
                text="Вставьте ключ/пароль (можно многострочный). Клик вне поля — сохранить, Esc — отмена.")
        else:
            ed = ttk.Entry(self.tree)
            ed.insert(0, value)
            ed.select_range(0, "end")
            ed.place(x=x, y=y, width=w, height=h)
            ed.focus_set()
            ed.bind("<Return>", lambda e: self._commit_edit())
            ed.bind("<Escape>", lambda e: self._close_editor())
            ed.bind("<FocusOut>", lambda e: self._commit_edit())
            self._editor_is_text = False
        self._editor = ed
        self._edit_iid = iid
        self._edit_idx = idx
        self._edit_key = key

    def _commit_edit(self):
        """Сохранить введённое значение."""
        if self._editor is None:
            return
        if getattr(self, "_editor_is_text", False):
            value = self._editor.get("1.0", "end-1c").strip()
        else:
            value = self._editor.get().strip()
        idx = self._edit_idx
        key = self._edit_key
        self._close_editor()
        if 0 <= idx < len(self.vault.entries):
            self.vault.entries[idx][key] = value
            self.vault.save()
            self._refresh()

    def _close_editor(self):
        """Убрать поле ввода без сохранения."""
        if self._editor is not None:
            ed = self._editor
            self._editor = None  # сначала обнулить, чтобы FocusOut не зациклился
            ed.destroy()

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
        self._master = p1
        messagebox.showinfo(APP_NAME, "Мастер-пароль изменён.")

    # ---------- архив (сохранить / загрузить) ----------
    def _desktop_dir(self):
        """Найти папку Рабочего стола (с учётом OneDrive)."""
        home = os.path.expanduser("~")
        candidates = [
            os.path.join(home, "Desktop"),
            os.path.join(home, "Рабочий стол"),
            os.path.join(home, "OneDrive", "Desktop"),
            os.path.join(home, "OneDrive", "Рабочий стол"),
        ]
        for c in candidates:
            if os.path.isdir(c):
                return c
        return home

    def _save_backup(self):
        """Сохранить закрытый архив со всеми записями на Рабочий стол."""
        self._close_editor()
        stamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M")
        name = "Klyuchnica-backup-%s.klch" % stamp
        dest = os.path.join(self._desktop_dir(), name)
        try:
            self.vault.export_backup(dest)
        except Exception as ex:
            messagebox.showerror(APP_NAME, "Не удалось сохранить архив:\n%s" % ex)
            return
        messagebox.showinfo(
            APP_NAME,
            "Резервная копия сохранена на Рабочий стол:\n%s\n\n"
            "Она зашифрована вашим мастер-паролем." % name)
        self.status.config(text="Резервная копия сохранена: %s" % name)

    def _browse_backup(self):
        """Выбрать файл-архив и загрузить его."""
        path = filedialog.askopenfilename(
            parent=self, title="Выберите архив «Ключницы»",
            initialdir=self._desktop_dir(),
            filetypes=[("Архив Ключницы", "*.klch"), ("Все файлы", "*.*")])
        if not path:
            return
        self.backup_var.set(path)
        self._load_backup(path)

    def _entry_key(self, e):
        return (e.get("title", ""), e.get("login", ""), e.get("password", ""),
                e.get("url", ""), e.get("note", ""))

    def _load_backup(self, path):
        """Загрузить записи из архива и добавить к имеющимся."""
        self._close_editor()
        if not path:
            messagebox.showwarning(APP_NAME, "Сначала укажите файл-архив (кнопка «…»).", parent=self)
            return
        if not os.path.isfile(path):
            messagebox.showerror(APP_NAME, "Файл не найден:\n%s" % path, parent=self)
            return
        entries = None
        # 1) пробуем текущим мастер-паролем
        try:
            entries = vaultmod.read_vault_file(path, self._master)
        except BadFile as ex:
            messagebox.showerror(APP_NAME, str(ex), parent=self)
            return
        except OSError as ex:
            messagebox.showerror(APP_NAME, "Не удалось открыть файл:\n%s" % ex, parent=self)
            return
        except WrongPassword:
            # 2) мастер-пароли не совпали — переспрашиваем пароль архива
            while True:
                pw = simpledialog.askstring(
                    APP_NAME,
                    "Мастер-пароль архива не совпадает с текущим.\n"
                    "Введите мастер-пароль этого архива:",
                    show="\u2022", parent=self)
                if pw is None:
                    return
                try:
                    entries = vaultmod.read_vault_file(path, pw)
                    break
                except WrongPassword:
                    messagebox.showerror(APP_NAME, "Неверный пароль архива. Попробуйте ещё раз.", parent=self)
        if not isinstance(entries, list):
            messagebox.showerror(APP_NAME, "Архив повреждён или пуст.", parent=self)
            return
        # добавляем к имеющимся, пропуская дубликаты
        existing = {self._entry_key(e) for e in self.vault.entries}
        added = 0
        for e in entries:
            if not isinstance(e, dict):
                continue
            k = self._entry_key(e)
            if k in existing:
                continue
            self.vault.entries.append(e)
            existing.add(k)
            added += 1
        self.vault.save()
        self._refresh()
        self.backup_var.set("")
        messagebox.showinfo(
            APP_NAME,
            "Загружено новых записей: %d\nПропущено дубликатов: %d"
            % (added, len(entries) - added), parent=self)


# держим handle mutex живым на всё время работы программы
_SINGLE_INSTANCE_HANDLE = None


def ensure_single_instance() -> bool:
    """Разрешает только одно окно «Ключницы».

    Если программа уже запущена — поднимает старое окно на
    передний план и возвращает False (второе окно не открывать).
    На не-Windows всегда разрешает (для разработки).
    """
    global _SINGLE_INSTANCE_HANDLE
    try:
        import ctypes
        from ctypes import wintypes
    except Exception:
        return True
    if not hasattr(ctypes, "windll"):
        return True

    MUTEX_NAME = "Global\\MAMONOV_Klyuchnica_SingleInstance"
    ERROR_ALREADY_EXISTS = 183
    kernel32 = ctypes.windll.kernel32

    handle = kernel32.CreateMutexW(None, False, MUTEX_NAME)
    last_err = kernel32.GetLastError()
    _SINGLE_INSTANCE_HANDLE = handle

    if last_err == ERROR_ALREADY_EXISTS:
        # Уже запущена — попробуем поднять старое окно
        try:
            user32 = ctypes.windll.user32
            hwnd = user32.FindWindowW(None, APP_NAME)
            if hwnd:
                SW_RESTORE = 9
                user32.ShowWindow(hwnd, SW_RESTORE)
                user32.SetForegroundWindow(hwnd)
        except Exception:
            pass
        return False
    return True


def main():
    if not ensure_single_instance():
        return  # «Ключница» уже открыта — второе окно не открываем
    app = App()
    try:
        app.mainloop()
    except tk.TclError:
        pass


if __name__ == "__main__":
    main()
