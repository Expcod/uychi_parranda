"""Kompyuter yonganda avtomatik ishga tushish.

Windows'ning "Автозагрузка" papkasiga yorliq qo'yadi. Xizmat (NSSM) dan
farqli o'laroq Administrator huquqi kerak emas va oyna ish stolida ochiladi —
bizga aynan shu kerak, chunki dastur oynali.
"""
import logging
import os
import sys

LOG = logging.getLogger("print_agent.autostart")

SHORTCUT_NAME = "Odoo stiker agenti.lnk"


def target_path():
    """Yorliq ishga tushiradigan fayl.

    Exe bo'lsa — o'zi. Python skript bo'lsa — pythonw.exe + skript
    (pythonw konsol oynasini ochmaydi).
    """
    if getattr(sys, "frozen", False):
        return sys.executable, ""

    pythonw = os.path.join(os.path.dirname(sys.executable), "pythonw.exe")
    runner = pythonw if os.path.exists(pythonw) else sys.executable
    script = os.path.abspath(sys.argv[0])
    return runner, '"%s"' % script


def startup_dir():
    """Windows'ning avtoyuklash papkasi."""
    return os.path.join(
        os.environ.get("APPDATA", ""),
        "Microsoft", "Windows", "Start Menu", "Programs", "Startup",
    )


def shortcut_path():
    return os.path.join(startup_dir(), SHORTCUT_NAME)


def is_enabled():
    return os.path.exists(shortcut_path())


def enable():
    """Yorliq yaratadi. Xato bo'lsa Exception ko'taradi."""
    import win32com.client

    folder = startup_dir()
    if not os.path.isdir(folder):
        raise RuntimeError("Avtoyuklash papkasi topilmadi: %s" % folder)

    exe, args = target_path()
    shell = win32com.client.Dispatch("WScript.Shell")
    link = shell.CreateShortCut(shortcut_path())
    link.TargetPath = exe
    link.Arguments = args
    # Ish papkasi muhim — agent.ini shu yerdan o'qiladi
    link.WorkingDirectory = os.path.dirname(exe if getattr(sys, "frozen", False)
                                            else os.path.abspath(sys.argv[0]))
    link.Description = "Odoo stiker chop etish agenti"
    link.save()
    LOG.info("Avtoyuklashga qo'shildi: %s", shortcut_path())


def disable():
    path = shortcut_path()
    if os.path.exists(path):
        os.remove(path)
        LOG.info("Avtoyuklashdan olib tashlandi")


def set_enabled(enabled):
    enable() if enabled else disable()
