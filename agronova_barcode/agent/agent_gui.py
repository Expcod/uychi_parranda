"""Odoo stiker agenti — sozlash oynasi.

Sexdagi kompyuterda ishlaydi. Ishchi bu yerda serverni bir marta sozlaydi,
keyin dastur o'zi fonda ishlab turadi va navbatdagi stikerlarni printerga
yuboradi.

Chop etish mantig'i `print_agent.py` da — bu fayl faqat oyna.

Ishga tushirish:
    python agent_gui.py

Exe qilish:
    pyinstaller agent.spec
"""
import logging
import os
import queue
import sys
import threading
import tkinter as tk
from tkinter import messagebox, ttk

import autostart
from tray import TrayIcon

from print_agent import (ConfigError, PrintAgent, load_config, read_config,
                         save_config, short_error)

APP_TITLE = "Odoo stiker agenti"
MAX_LOG_LINES = 300


def app_dir():
    """Sozlama va log yoziladigan papka.

    Exe ichida ishlaganda `__file__` vaqtinchalik papkaga ishora qiladi,
    shuning uchun exe turgan papkani olamiz — ishchi uni topa olsin.
    """
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


CONFIG_PATH = os.path.join(app_dir(), "agent.ini")
LOG_PATH = os.path.join(app_dir(), "agent.log")


def list_printers():
    """Windows'da o'rnatilgan printerlar nomi."""
    try:
        import win32print
    except ImportError:
        return []
    flags = win32print.PRINTER_ENUM_LOCAL | win32print.PRINTER_ENUM_CONNECTIONS
    try:
        return sorted(p[2] for p in win32print.EnumPrinters(flags, None, 1))
    except Exception:
        return []


class QueueLogHandler(logging.Handler):
    """Loglarni oynaga uzatadi.

    Agent alohida oqimda ishlaydi, tkinter esa faqat asosiy oqimdan
    yangilanadi — shuning uchun navbat orqali o'tkazamiz.
    """

    def __init__(self, log_queue):
        super().__init__()
        self.log_queue = log_queue

    def emit(self, record):
        try:
            self.log_queue.put_nowait(self.format(record))
        except Exception:
            pass


class AgentGUI:
    def __init__(self, root):
        self.root = root
        self.agent = None
        self.thread = None
        self.log_queue = queue.Queue()
        self.vars = {}
        self._shown_running = None      # oynada hozir ko'rinayotgan holat
        self._restart_pending = False   # sozlama o'zgardi, agent tiklanishi kerak
        self.tray = None

        root.title(APP_TITLE)
        root.geometry("620x640")
        root.minsize(560, 560)

        self._build()
        self._setup_logging()
        self._load()
        self._pump_logs()
        self._setup_tray()

        root.protocol("WM_DELETE_WINDOW", self.on_close)

        # Sozlama tayyor bo'lsa kutib turmaymiz — kompyuter yonganda ishchi
        # "Ishga tushirish" ni bosishi shart bo'lmasligi kerak.
        self.root.after(300, self._autostart_if_ready)

    # ------------------------------------------------------------------
    # Oyna
    # ------------------------------------------------------------------
    def _build(self):
        pad = {"padx": 10, "pady": 4}

        form = ttk.LabelFrame(self.root, text="Odoo serveri")
        form.pack(fill="x", **pad)
        form.columnconfigure(1, weight=1)

        self._row(form, 0, "url", "Server manzili", "https://filtruz.example.uz")
        self._row(form, 1, "db", "Baza nomi", "filtruz_prod")
        self._row(form, 2, "username", "Login", "print_agent@filtruz.uz")
        self._row(form, 3, "password", "Parol", "", secret=True)
        self._row(form, 4, "token", "Agent kaliti", "", secret=True)

        hint = ttk.Label(
            form, foreground="#666", font=("Segoe UI", 8),
            text="Kalitni Odoo'dan oling:  Ombor > Sozlamalar > Stiker printerlari",
        )
        hint.grid(row=5, column=1, sticky="w", padx=6, pady=(0, 6))

        # --- printer ---
        pframe = ttk.LabelFrame(self.root, text="Printer")
        pframe.pack(fill="x", **pad)
        pframe.columnconfigure(1, weight=1)

        ttk.Label(pframe, text="Printer").grid(row=0, column=0, sticky="w", padx=6, pady=4)
        self.vars["printer"] = tk.StringVar()
        self.printer_box = ttk.Combobox(
            pframe, textvariable=self.vars["printer"], values=list_printers())
        self.printer_box.grid(row=0, column=1, sticky="ew", padx=6, pady=4)
        ttk.Button(pframe, text="Yangilash", width=10,
                   command=self.refresh_printers).grid(row=0, column=2, padx=6)

        ttk.Label(
            pframe, foreground="#666", font=("Segoe UI", 8),
            text="Bo'sh qoldirilsa Odoo'dagi sozlamadagi printer ishlatiladi.",
        ).grid(row=1, column=1, sticky="w", padx=6, pady=(0, 6))

        self.vars["dry_run"] = tk.BooleanVar(value=False)
        ttk.Checkbutton(
            pframe, text="Sinov rejimi — printerga yuborilmaydi, faqat logga yoziladi",
            variable=self.vars["dry_run"],
        ).grid(row=2, column=0, columnspan=3, sticky="w", padx=6, pady=(0, 6))

        # --- avtomatik ishlash ---
        aframe = ttk.LabelFrame(self.root, text="Avtomatik ishlash")
        aframe.pack(fill="x", **pad)

        self.autostart_var = tk.BooleanVar(value=autostart.is_enabled())
        ttk.Checkbutton(
            aframe, text="Kompyuter yonganda avtomatik ishlasin",
            variable=self.autostart_var, command=self.on_autostart_toggle,
        ).pack(anchor="w", padx=6, pady=(6, 0))
        ttk.Label(
            aframe, foreground="#666", font=("Segoe UI", 8),
            text="Dastur o'zi ochilib navbatni kuzatadi va soat yonidagi "
                 "belgichaga yashirinadi.",
        ).pack(anchor="w", padx=26, pady=(0, 6))

        # --- tugmalar ---
        btns = ttk.Frame(self.root)
        btns.pack(fill="x", **pad)

        self.btn_start = ttk.Button(btns, text="Ishga tushirish", command=self.toggle)
        self.btn_start.pack(side="left")
        ttk.Button(btns, text="Saqlash", command=self.save).pack(side="left", padx=6)
        ttk.Button(btns, text="Ulanishni tekshirish",
                   command=self.test_connection).pack(side="left")
        ttk.Button(btns, text="Log papkasi",
                   command=lambda: os.startfile(app_dir())).pack(side="right")

        # --- holat ---
        self.status = ttk.Label(self.root, text="To'xtatilgan", foreground="#a33",
                                font=("Segoe UI", 10, "bold"))
        self.status.pack(anchor="w", padx=12, pady=(4, 0))

        # --- log ---
        lframe = ttk.LabelFrame(self.root, text="Hodisalar")
        lframe.pack(fill="both", expand=True, **pad)

        self.log = tk.Text(lframe, height=10, wrap="none", state="disabled",
                           background="#1e1e1e", foreground="#d4d4d4",
                           font=("Consolas", 9), borderwidth=0)
        scroll = ttk.Scrollbar(lframe, command=self.log.yview)
        self.log.configure(yscrollcommand=scroll.set)
        scroll.pack(side="right", fill="y")
        self.log.pack(side="left", fill="both", expand=True, padx=4, pady=4)

        self.log.tag_configure("ERROR", foreground="#f48771")
        self.log.tag_configure("WARNING", foreground="#dcdcaa")

    def _row(self, parent, row, key, label, placeholder="", secret=False):
        ttk.Label(parent, text=label).grid(row=row, column=0, sticky="w", padx=6, pady=4)
        var = tk.StringVar(value=placeholder if not secret else "")
        entry = ttk.Entry(parent, textvariable=var, show="•" if secret else "")
        entry.grid(row=row, column=1, columnspan=2, sticky="ew", padx=6, pady=4)
        self.vars[key] = var

    # ------------------------------------------------------------------
    def _setup_logging(self):
        handler = QueueLogHandler(self.log_queue)
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)-7s %(message)s",
                                               datefmt="%H:%M:%S"))
        root_log = logging.getLogger()
        root_log.setLevel(logging.INFO)
        root_log.addHandler(handler)

        # Fayl logi — xizmat rejimida oyna bo'lmaydi, muammoni shundan qaraladi
        try:
            fh = logging.FileHandler(LOG_PATH, encoding="utf-8")
            fh.setFormatter(logging.Formatter(
                "%(asctime)s %(levelname)-7s %(message)s"))
            root_log.addHandler(fh)
        except Exception:
            pass

    def _pump_logs(self):
        """Navbatdagi loglarni oynaga chiqaradi va holatni yangilaydi (har 200 ms).

        Agent alohida oqimda — holatni shu yerdan kuzatamiz, chunki oqim
        tugaganini o'zi xabar qilishi ishonchsiz.
        """
        try:
            while True:
                self._append_log(self.log_queue.get_nowait())
        except queue.Empty:
            pass

        running = self.running
        if running != self._shown_running:
            self._set_state(running)

        # Sozlama o'zgargani uchun to'xtatilgan bo'lsa — yangisi bilan tiklaymiz
        if self._restart_pending and not running:
            self._restart_pending = False
            self.start_agent()

        self.root.after(200, self._pump_logs)

    def _append_log(self, line):
        tag = "ERROR" if " ERROR " in line else ("WARNING" if " WARNING" in line else "")
        self.log.configure(state="normal")
        self.log.insert("end", line + "\n", tag)

        # Oyna kun bo'yi ochiq turadi — xotira o'smasligi uchun cheklaymiz
        total = int(self.log.index("end-1c").split(".")[0])
        if total > MAX_LOG_LINES:
            self.log.delete("1.0", "%d.0" % (total - MAX_LOG_LINES))

        self.log.see("end")
        self.log.configure(state="disabled")

    # ------------------------------------------------------------------
    # Sozlama
    # ------------------------------------------------------------------
    def _load(self):
        if not os.path.exists(CONFIG_PATH):
            logging.info("Sozlama hali yo'q — maydonlarni to'ldiring va Saqlang")
            return
        # Sozlama to'liq bo'lmasligi mumkin — borini oynaga chiqaramiz,
        # ishchi qolganini o'zi to'ldiradi.
        try:
            cfg = read_config(CONFIG_PATH)
        except ConfigError as exc:
            logging.error("%s", exc)
            messagebox.showwarning(
                APP_TITLE,
                "Saqlangan sozlamani o'qib bo'lmadi:\n\n%s\n\n"
                "Maydonlarni qaytadan to'ldirib, Saqlang." % exc)
            return

        for key in ("url", "db", "username", "password", "token", "printer"):
            if key in self.vars and cfg.get(key):
                self.vars[key].set(cfg[key])
        self.vars["dry_run"].set(str(cfg.get("dry_run", "")).lower() in ("1", "true", "yes"))
        logging.info("Sozlama o'qildi: %s", CONFIG_PATH)

    def _collect(self):
        cfg = {k: v.get().strip() for k, v in self.vars.items() if k != "dry_run"}
        cfg["dry_run"] = "1" if self.vars["dry_run"].get() else "0"
        cfg["poll_seconds"] = "3"
        return cfg

    def _validate(self, cfg):
        labels = {"url": "Server manzili", "db": "Baza nomi", "username": "Login",
                  "password": "Parol", "token": "Agent kaliti"}
        missing = [labels[k] for k in labels if not cfg.get(k)]
        if missing:
            messagebox.showwarning(
                APP_TITLE, "Quyidagilar to'ldirilmagan:\n\n  • " + "\n  • ".join(missing))
            return False
        if not cfg["url"].startswith(("http://", "https://")):
            messagebox.showwarning(
                APP_TITLE, "Server manzili http:// yoki https:// bilan boshlanishi kerak.")
            return False
        return True

    def save(self, restart_if_running=True):
        cfg = self._collect()
        if not self._validate(cfg):
            return False
        try:
            save_config(CONFIG_PATH, cfg)
        except Exception as exc:
            messagebox.showerror(APP_TITLE, "Saqlab bo'lmadi:\n\n%s" % exc)
            return False
        logging.info("Sozlama saqlandi")

        # Ishlab turgan agent eski sozlama bilan qolib ketmasin — masalan
        # sinov rejimi o'chirilsa-yu, stikerlar baribir printerga bormasa
        # ishchi sababni topa olmaydi.
        if restart_if_running and self.running:
            logging.info("Yangi sozlama qo'llanmoqda — agent qayta ishga tushmoqda")
            self._restart_pending = True
            self.agent.stop()
        return True

    def refresh_printers(self):
        printers = list_printers()
        self.printer_box["values"] = printers
        if not printers:
            messagebox.showinfo(
                APP_TITLE,
                "Printer topilmadi.\n\n"
                "Printer Windows'da o'rnatilganini va USB ulanganini tekshiring.")
        else:
            logging.info("%d ta printer topildi", len(printers))

    # ------------------------------------------------------------------
    # Ulanishni tekshirish
    # ------------------------------------------------------------------
    def test_connection(self):
        cfg = self._collect()
        if not self._validate(cfg):
            return

        def work():
            try:
                PrintAgent(cfg).test_connection()
            except Exception as exc:
                self.root.after(0, self._test_failed, exc)
            else:
                self.root.after(0, self._test_ok)

        logging.info("Ulanish tekshirilmoqda...")
        threading.Thread(target=work, daemon=True).start()

    def _test_ok(self):
        logging.info("Ulanish muvaffaqiyatli")
        messagebox.showinfo(
            APP_TITLE,
            "Ulanish muvaffaqiyatli.\n\n"
            "Endi 'Ishga tushirish' ni bosing va Odoo'da sinov stiker chiqaring.")

    def _test_failed(self, exc):
        error = short_error(exc)
        logging.error("Ulanish xatosi: %s", error)
        messagebox.showerror(APP_TITLE, "Ulanib bo'lmadi:\n\n%s\n\nEhtimoliy sabab:\n%s"
                             % (error, self._diagnose(exc)))

    @staticmethod
    def _diagnose(exc):
        """Xato matnidan eng ehtimolli sababni aytadi."""
        text = str(exc).lower()
        if "kirib bo'lmadi" in text or "access denied" in text and "login" in text:
            return "Login yoki parol xato. Odoo'da 2FA yoqilgan bo'lsa uni o'chiring."
        if "accessdenied" in text or "access denied" in text:
            return "Agent kaliti xato — Odoo'dagi printer formasidan qayta nusxalang."
        if "certificate" in text:
            return ("Kompyuter server sertifikatiga ishonmadi. Ko'pincha sabab "
                    "kompyuterdagi sana/vaqt xato yoki Windows yangilanmagan — "
                    "shularni tekshiring.")
        if "refused" in text or "timed out" in text or "getaddrinfo" in text:
            return "Serverga yetib bo'lmadi — manzilni va internetni tekshiring."
        if "database" in text or "does not exist" in text:
            return "Baza nomi xato. Aniq nomi: <server>/web/database/selector"
        return "Sozlamalarni tekshiring."

    # ------------------------------------------------------------------
    # Avtomatik ishlash
    # ------------------------------------------------------------------
    def on_autostart_toggle(self):
        wanted = self.autostart_var.get()
        try:
            autostart.set_enabled(wanted)
        except Exception as exc:
            self.autostart_var.set(not wanted)      # katakni orqaga qaytaramiz
            logging.error("Avtoyuklash sozlanmadi: %s", short_error(exc))
            messagebox.showerror(
                APP_TITLE, "Avtomatik ishlashni yoqib bo'lmadi:\n\n%s" % short_error(exc))
            return

        if wanted:
            messagebox.showinfo(
                APP_TITLE,
                "Tayyor.\n\nEndi kompyuter yonganda dastur o'zi ishga tushadi va "
                "navbatni kuzata boshlaydi.\n\n"
                "Oynani yopsangiz dastur to'xtamaydi — soat yonidagi belgichaga "
                "yashirinadi. Uni ochish uchun belgichani ikki marta bosing.")

    def _autostart_if_ready(self):
        """Sozlama to'liq bo'lsa agentni o'zi ishga tushiradi."""
        if self.running:
            return
        try:
            load_config(CONFIG_PATH)
        except ConfigError:
            return          # sozlama tayyor emas — ishchi to'ldirsin
        logging.info("Sozlama tayyor — avtomatik ishga tushirilmoqda")
        self.start_agent()

    def _setup_tray(self):
        """Trey belgichasini yaratadi. Ishlamasa dastur oddiy oyna bo'lib qoladi."""
        try:
            tray = TrayIcon(APP_TITLE, on_open=self._tray_open, on_exit=self._tray_exit)
            if tray.start():
                self.tray = tray
        except Exception:
            logging.debug("Trey belgichasi ishlamadi", exc_info=True)

    def _tray_open(self):
        self.root.after(0, self._show_window)

    def _show_window(self):
        self.root.deiconify()
        self.root.lift()
        self.root.focus_force()

    def _tray_exit(self):
        self.root.after(0, self._quit)

    # ------------------------------------------------------------------
    # Ishga tushirish / to'xtatish
    # ------------------------------------------------------------------
    @property
    def running(self):
        return self.thread is not None and self.thread.is_alive()

    def toggle(self):
        self.stop_agent() if self.running else self.start_agent()

    def start_agent(self):
        # Bu yerda qayta ishga tushirish so'ralmaydi — biz allaqachon shu ishni
        # qilyapmiz (aks holda o'zini cheksiz to'xtatib-yoqaverardi).
        if not self.save(restart_if_running=False):
            return
        try:
            cfg = load_config(CONFIG_PATH)
        except ConfigError as exc:
            messagebox.showerror(APP_TITLE, str(exc))
            return

        self.agent = PrintAgent(cfg)
        self.thread = threading.Thread(target=self._run_agent, daemon=True)
        self.thread.start()
        self._set_state(True)

    def _run_agent(self):
        try:
            self.agent.run()
        except Exception as exc:
            logging.error("Agent to'xtadi: %s", short_error(exc))
        # Holatni `_pump_logs` o'zi payqaydi — bu yerda oynaga tegmaymiz,
        # chunki oyna allaqachon yopilgan bo'lishi mumkin.

    def stop_agent(self):
        if self.agent:
            self.agent.stop()
        self.status.configure(text="To'xtatilmoqda...", foreground="#a60")

    def _set_state(self, running):
        self._shown_running = running
        if running:
            self.status.configure(text="● Ishlamoqda — navbat kuzatilmoqda",
                                  foreground="#2a7")
            self.btn_start.configure(text="To'xtatish")
        else:
            self.status.configure(text="To'xtatilgan", foreground="#a33")
            self.btn_start.configure(text="Ishga tushirish")

    # ------------------------------------------------------------------
    def on_close(self):
        """Oyna yopilganda dastur to'xtamaydi — treyga yashirinadi.

        Ishchi tasodifan yopib qo'ysa stikerlar chop etilmay qolmasligi kerak.
        Butunlay chiqish trey menyusidagi "Chiqish" orqali.
        """
        if self.running and self.tray:
            self.root.withdraw()
            self.tray.notify(
                APP_TITLE,
                "Dastur ishlashda davom etmoqda. Ochish uchun shu belgichani "
                "ikki marta bosing.")
            return

        if self.running:
            # Trey ishlamayapti — yashirinib qololmaymiz, shuning uchun so'raymiz
            if not messagebox.askyesno(
                APP_TITLE,
                "Agent ishlamoqda. Yopilsa stikerlar chop etilmay qoladi.\n\n"
                "Baribir yopilsinmi?",
            ):
                return
        self._quit()

    def _quit(self):
        """Dasturdan butunlay chiqish."""
        if self.agent:
            self.agent.stop()
        if self.tray:
            self.tray.stop()
        self.root.destroy()


def main():
    root = tk.Tk()
    try:
        ttk.Style().theme_use("vista")
    except tk.TclError:
        pass

    # Kutilmagan xato oynani ochilmay qoldirmasin — exe'da bunday holat
    # ishchiga tushunarsiz "Unhandled exception" oynasi bo'lib ko'rinadi.
    try:
        AgentGUI(root)
    except Exception as exc:
        logging.exception("Dastur ochilmadi")
        messagebox.showerror(
            APP_TITLE,
            "Dasturni ochib bo'lmadi:\n\n%s\n\n"
            "Sozlama fayli buzilgan bo'lishi mumkin. Uni o'chirib ko'ring:\n%s"
            % (short_error(exc), CONFIG_PATH))
        return 1

    root.mainloop()
    return 0


if __name__ == "__main__":
    sys.exit(main())
