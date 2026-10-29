"""Soat yonidagi trey ikonkasi.

Oyna yopilganda dastur butunlay chiqmasdan treyga yashirinadi — ishchi
tasodifan yopib qo'ysa ham stikerlar chop etilaveradi.

Faqat win32 bilan ishlaydi (pystray kabi qo'shimcha kutubxona kerak emas).
"""
import logging
import threading

LOG = logging.getLogger("print_agent.tray")

WM_TRAYICON = 0x0400 + 20      # o'zimizniki (WM_USER + 20)
ID_OPEN = 1001
ID_EXIT = 1002


class TrayIcon:
    """Trey ikonkasi. Alohida oqimda o'z xabar tsiklini yuritadi.

    :param on_open: ikonkaga bosilganda chaqiriladi (oynani ko'rsatish)
    :param on_exit: menyudan "Chiqish" tanlanganda
    """

    def __init__(self, title, on_open, on_exit):
        self.title = title
        self.on_open = on_open
        self.on_exit = on_exit
        self.hwnd = None
        self._thread = None
        self._ready = threading.Event()

    # ------------------------------------------------------------------
    def start(self):
        """Ikonkani ko'rsatadi. Muvaffaqiyatsiz bo'lsa False qaytaradi."""
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
        self._ready.wait(timeout=5)
        return self.hwnd is not None

    def _run(self):
        try:
            self._create()
        except Exception:
            LOG.exception("Trey ikonkasini yaratib bo'lmadi")
            self._ready.set()
            return

        import win32gui
        self._ready.set()
        win32gui.PumpMessages()

    def _create(self):
        import win32api
        import win32con
        import win32gui

        message_map = {
            WM_TRAYICON: self._on_tray,
            win32con.WM_COMMAND: self._on_command,
            # stop() shu xabarni yuboradi — oynani o'z oqimida yopamiz.
            # Har bir ishlov beruvchi son qaytarishi shart (LRESULT).
            win32con.WM_CLOSE: self._on_close,
            win32con.WM_DESTROY: self._on_destroy,
        }

        wc = win32gui.WNDCLASS()
        wc.hInstance = win32api.GetModuleHandle(None)
        wc.lpszClassName = "OdooPrintAgentTray"
        wc.lpfnWndProc = message_map
        class_atom = win32gui.RegisterClass(wc)

        # Ko'rinmas oyna — trey xabarlarini qabul qilish uchun kerak
        self.hwnd = win32gui.CreateWindow(
            class_atom, self.title, win32con.WS_OVERLAPPED,
            0, 0, win32con.CW_USEDEFAULT, win32con.CW_USEDEFAULT,
            0, 0, wc.hInstance, None,
        )
        win32gui.UpdateWindow(self.hwnd)

        hicon = win32gui.LoadIcon(0, win32con.IDI_APPLICATION)
        win32gui.Shell_NotifyIcon(win32gui.NIM_ADD, (
            self.hwnd, 0,
            win32gui.NIF_ICON | win32gui.NIF_MESSAGE | win32gui.NIF_TIP,
            WM_TRAYICON, hicon, self.title,
        ))

    # ------------------------------------------------------------------
    # Xabar ishlov beruvchilari — hammasi son qaytaradi (LRESULT)
    # ------------------------------------------------------------------
    def _on_close(self, hwnd, msg, wparam, lparam):
        import win32gui
        win32gui.DestroyWindow(hwnd)
        return 0

    def _on_destroy(self, hwnd, msg, wparam, lparam):
        import win32gui
        win32gui.PostQuitMessage(0)
        return 0

    def _on_tray(self, hwnd, msg, wparam, lparam):
        import win32con
        if lparam == win32con.WM_LBUTTONDBLCLK:
            self._safe(self.on_open)
        elif lparam == win32con.WM_RBUTTONUP:
            self._show_menu()
        return 0

    def _show_menu(self):
        import win32gui

        menu = win32gui.CreatePopupMenu()
        win32gui.AppendMenu(menu, 0, ID_OPEN, "Oynani ochish")
        win32gui.AppendMenu(menu, 0, ID_EXIT, "Chiqish")

        pos = win32gui.GetCursorPos()
        # Menyu tashqariga bosilganda yopilishi uchun oynani old planga olamiz
        win32gui.SetForegroundWindow(self.hwnd)
        win32gui.TrackPopupMenu(menu, 0x0002, pos[0], pos[1], 0, self.hwnd, None)
        win32gui.DestroyMenu(menu)

    def _on_command(self, hwnd, msg, wparam, lparam):
        import win32api
        cmd = win32api.LOWORD(wparam)
        if cmd == ID_OPEN:
            self._safe(self.on_open)
        elif cmd == ID_EXIT:
            self._safe(self.on_exit)
        return 0

    @staticmethod
    def _safe(callback):
        try:
            callback()
        except Exception:
            LOG.exception("Trey menyusi xatosi")

    # ------------------------------------------------------------------
    def notify(self, title, text):
        """Trey ustida qalqib chiquvchi xabar (masalan xato haqida)."""
        if not self.hwnd:
            return
        try:
            import win32gui
            win32gui.Shell_NotifyIcon(win32gui.NIM_MODIFY, (
                self.hwnd, 0, win32gui.NIF_INFO, WM_TRAYICON, 0,
                self.title, text, 200, title, win32gui.NIIF_INFO,
            ))
        except Exception:
            LOG.debug("Trey xabarini ko'rsatib bo'lmadi", exc_info=True)

    def stop(self):
        if not self.hwnd:
            return
        try:
            import win32con
            import win32gui
            win32gui.Shell_NotifyIcon(win32gui.NIM_DELETE, (self.hwnd, 0))
            # Oynani faqat uni yaratgan oqim o'chira oladi, shuning uchun
            # to'g'ridan-to'g'ri DestroyWindow emas — xabar yuboramiz.
            win32gui.PostMessage(self.hwnd, win32con.WM_CLOSE, 0, 0)
        except Exception:
            LOG.debug("Trey belgichasini o'chirib bo'lmadi", exc_info=True)
        self.hwnd = None
