"""Odoo stiker chop etish agenti.

Sexdagi kompyuterda ishlaydi. Odoo'dagi navbatni kuzatib turadi va
kelgan ishlarni USB printerga yuboradi. Server uzoqda (VPS) bo'lsa ham
ishlaydi — agent o'zi murojaat qiladi, serverga printerga yo'l kerak emas.

Ishga tushirish:
    python print_agent.py --config agent.ini

Windows xizmati sifatida (NSSM bilan):
    nssm install OdooPrintAgent "C:\\Python\\python.exe" "C:\\agent\\print_agent.py --config C:\\agent\\agent.ini"
    nssm start OdooPrintAgent
"""
import argparse
import configparser
import logging
import os
import signal
import ssl
import sys
import time
import xmlrpc.client

LOG = logging.getLogger("print_agent")

DEFAULT_POLL = 3          # soniya
MAX_BACKOFF = 60          # xato bo'lganda kutish chegarasi
BATCH = 10                # bir martada olinadigan ish soni


def short_error(exc):
    """Xatoni bir qatorga siqadi.

    XML-RPC Fault serverning butun traceback'ini matn qilib qaytaradi —
    log oynasida o'nlab qator bo'lib oqadi va ishchi hech narsa tushunmaydi.
    Bizga faqat oxirgi — mazmunli — qatori kerak.
    """
    if isinstance(exc, xmlrpc.client.Fault):
        text = (exc.faultString or "").strip()
        lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
        if lines:
            # Traceback'ning oxirgi qatori — asl xato turi va matni.
            # "odoo.exceptions.AccessDenied: Access Denied" ko'rinishidan
            # ishchiga faqat o'ng tomoni kerak.
            text = lines[-1]
            head, sep, tail = text.partition(": ")
            if sep and " " not in head:      # head xato sinfi nomi bo'lsa
                text = tail.strip() or head
        return (text or "Serverdan xato qaytdi")[:200]

    text = " ".join(str(exc).split())
    return (text or exc.__class__.__name__)[:200]


def build_ssl_context():
    """HTTPS uchun ishonch omborini tayyorlaydi.

    Python o'zicha ildiz sertifikatlarni `C:\\Program Files\\Common Files\\SSL\\
    cert.pem` dan qidiradi — Windows'da bu fayl yo'q, exe ichida ham
    certifi bundle yo'q. Natijada har qanday HTTPS "unable to get local
    issuer certificate" beradi.

    Shuning uchun ildizlarni Windows'ning o'z omboridan yuklaymiz: u
    tizim yangilanishi bilan o'zi to'ldirilib turadi, ishchi hech narsa
    qilishi shart emas.
    """
    ctx = ssl.create_default_context()

    if sys.platform != "win32":
        return ctx

    loaded = 0
    for store in ("ROOT", "CA"):
        try:
            certs = ssl.enum_certificates(store)
        except Exception as exc:
            LOG.debug("Windows '%s' ombori o'qilmadi: %s", store, exc)
            continue
        for cert, encoding, trust in certs:
            # trust=True — "har qanday maqsad uchun", aks holda ro'yxat
            if encoding != "x509_asn" or trust is False:
                continue
            try:
                ctx.load_verify_locations(cadata=ssl.DER_cert_to_PEM_cert(cert))
                loaded += 1
            except ssl.SSLError:
                # Buzuq yoki eskirgan yozuv — qolganini yuklashda davom etamiz
                pass

    if loaded:
        LOG.debug("Windows omboridan %d ta ildiz sertifikat yuklandi", loaded)
    else:
        LOG.warning("Windows ishonch omboridan sertifikat yuklanmadi — "
                    "HTTPS ulanishda muammo bo'lishi mumkin")
    return ctx


class PrintAgent:
    def __init__(self, cfg):
        self.url = cfg["url"].rstrip("/")
        self.db = cfg["db"]
        self.username = cfg["username"]
        self.password = cfg["password"]
        self.token = cfg["token"]
        self.poll = int(cfg.get("poll_seconds", DEFAULT_POLL))
        self.printer_override = cfg.get("printer") or None
        self.dry_run = str(cfg.get("dry_run", "")).lower() in ("1", "true", "yes")

        self.uid = None
        self.models = None
        self._running = True
        self._backoff = 0
        # Kontekstni bir marta yasaymiz — har ulanishda omborni qayta
        # o'qish qimmat, sertifikatlar esa dastur ishlab turganda o'zgarmaydi.
        self._ssl_context = build_ssl_context() if self.url.startswith("https://") else None

    # ------------------------------------------------------------------
    def _proxy(self, endpoint):
        return xmlrpc.client.ServerProxy(
            "%s/xmlrpc/2/%s" % (self.url, endpoint), context=self._ssl_context)

    def connect(self):
        common = self._proxy("common")
        self.uid = common.authenticate(self.db, self.username, self.password, {})
        if not self.uid:
            raise RuntimeError("Odoo'ga kirib bo'lmadi — login yoki parol xato")
        self.models = self._proxy("object")
        LOG.info("Odoo'ga ulandi: %s (db=%s, uid=%s)", self.url, self.db, self.uid)

    def _call(self, method, *args):
        return self.models.execute_kw(
            self.db, self.uid, self.password,
            "agronova.label.print.job", method, list(args),
        )

    # ------------------------------------------------------------------
    def fetch(self):
        return self._call("agent_fetch", self.token, BATCH)

    def report(self, results):
        if results:
            self._call("agent_report", self.token, results)

    # ------------------------------------------------------------------
    def send_to_printer(self, printer_name, payload, encoding="cp1251"):
        """RAW rejimda printerga yuboradi.

        Kodlash Odoo'dagi printer sozlamasidan keladi. Kirill matn UTF-8 da
        yuborilsa printerning ichki shrifti uni buzib chiqaradi.
        """
        try:
            data = payload.encode(encoding, errors="replace")
        except LookupError:
            LOG.warning("Noma'lum kodlash '%s' — cp1251 ishlatildi", encoding)
            data = payload.encode("cp1251", errors="replace")

        if self.dry_run:
            LOG.warning("SINOV REJIMI — printerga YUBORILMADI. Haqiqiy chop etish "
                        "uchun 'Sinov rejimi' katagini o'chiring (%s, %d bayt)",
                        printer_name, len(data))
            return

        import win32print
        handle = win32print.OpenPrinter(printer_name)
        try:
            win32print.StartDocPrinter(handle, 1, ("Odoo stiker", None, "RAW"))
            win32print.StartPagePrinter(handle)
            win32print.WritePrinter(handle, data)
            win32print.EndPagePrinter(handle)
            win32print.EndDocPrinter(handle)
        finally:
            win32print.ClosePrinter(handle)

    def process(self, jobs):
        results = []
        for job in jobs:
            printer = self.printer_override or job.get("printer")
            try:
                self.send_to_printer(
                    printer, job["payload"], job.get("encoding") or "cp1251")
            except Exception as exc:
                error = short_error(exc)
                LOG.error("Job %s chop etilmadi: %s", job["id"], error)
                results.append({"id": job["id"], "ok": False, "error": error})
            else:
                LOG.info("Job %s chop etildi (%s)", job["id"], printer)
                results.append({"id": job["id"], "ok": True})
        return results

    # ------------------------------------------------------------------
    def run(self):
        """Navbatni to'xtovsiz kuzatadi.

        Birinchi ulanish ham tsikl ichida — kompyuter yonganda internet hali
        ko'tarilmagan bo'lishi mumkin, bunda agent o'lmasdan qayta urinadi.
        """
        while self._running:
            try:
                if self.models is None:
                    self.connect()
                    LOG.info("Navbat kuzatilmoqda (har %d soniyada)...", self.poll)
                    if self.dry_run:
                        LOG.warning("DIQQAT: sinov rejimi yoqilgan — stikerlar "
                                    "printerga chiqmaydi")

                jobs = self.fetch()
                if jobs:
                    LOG.info("%d ta ish olindi", len(jobs))
                    self.report(self.process(jobs))
                self._backoff = 0
                self._sleep(self.poll)

            except KeyboardInterrupt:
                break
            except Exception as exc:
                # Tarmoq uzilishi yoki server o'chishi — qayta urinamiz.
                # `models` ni tozalaymiz: keyingi aylanish qaytadan ulanadi.
                self.models = None
                self._backoff = min(MAX_BACKOFF, max(self.poll, self._backoff * 2 or self.poll))
                LOG.warning("Ulanmadi: %s — %d soniyadan keyin qayta urinaman",
                            short_error(exc), self._backoff)
                self._sleep(self._backoff)

        LOG.info("Agent to'xtadi")

    def _sleep(self, seconds):
        """To'xtatish signalini kutib turadigan uyqu."""
        end = time.time() + seconds
        while self._running and time.time() < end:
            time.sleep(min(0.5, max(0, end - time.time())))

    def stop(self, *args):
        LOG.info("To'xtatish signali keldi")
        self._running = False

    # ------------------------------------------------------------------
    def test_connection(self):
        """Sozlama to'g'riligini tekshiradi. Xato bo'lsa Exception ko'taradi.

        GUI shu metodni "Ulanishni tekshirish" tugmasida ishlatadi.
        """
        self.connect()
        self.fetch()   # token noto'g'ri bo'lsa shu yerda AccessDenied chiqadi
        return True


# ----------------------------------------------------------------------
REQUIRED_KEYS = ("url", "db", "username", "password", "token")


class ConfigError(Exception):
    """Sozlama xatosi — GUI uni oynada ko'rsatadi, konsol esa chiqib ketadi."""


def read_config(path):
    """Faylni o'qiydi, bo'limlarni lug'at qilib qaytaradi (tekshiruvsiz).

    `utf-8-sig` — Notepad va PowerShell fayl boshiga BOM qo'yib yuboradi,
    oddiy `utf-8` da esa u `[agent]` ga yopishib "File contains no section
    headers" xatosini beradi. BOM bo'lmasa ham shu kodlash to'g'ri ishlaydi.
    """
    parser = configparser.ConfigParser()
    try:
        parser.read(path, encoding="utf-8-sig")
    except configparser.Error as exc:
        # configparser xatosi bir necha qator — ishchiga birinchisi yetarli
        first = str(exc).splitlines()[0]
        raise ConfigError("Sozlama fayli buzilgan: %s" % first)
    return dict(parser["agent"]) if "agent" in parser else {}


def load_config(path):
    if not os.path.exists(path):
        raise ConfigError("Sozlama fayli topilmadi: %s" % path)

    cfg = read_config(path)
    if not cfg:
        raise ConfigError("Sozlama faylida [agent] bo'limi yo'q")

    for key in REQUIRED_KEYS:
        if not cfg.get(key):
            raise ConfigError("Sozlamada '%s' ko'rsatilmagan" % key)
    return cfg


def save_config(path, cfg):
    """Sozlamani agent.ini ga yozadi (GUI ishlatadi)."""
    parser = configparser.ConfigParser()
    parser["agent"] = {k: str(v if v is not None else "") for k, v in cfg.items()}
    with open(path, "w", encoding="utf-8") as fh:
        parser.write(fh)


def main():
    ap = argparse.ArgumentParser(description="Odoo stiker chop etish agenti")
    ap.add_argument("--config", default="agent.ini", help="sozlama fayli")
    ap.add_argument("--log", help="log fayli (ko'rsatilmasa ekranga chiqadi)")
    ap.add_argument("--verbose", action="store_true")
    args = ap.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)-7s %(message)s",
        filename=args.log,
        encoding="utf-8",
    )

    try:
        agent = PrintAgent(load_config(args.config))
    except ConfigError as exc:
        raise SystemExit(str(exc))

    signal.signal(signal.SIGINT, agent.stop)
    signal.signal(signal.SIGTERM, agent.stop)

    try:
        agent.run()
    except Exception:
        LOG.exception("Agent to'xtadi (kutilmagan xato)")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
