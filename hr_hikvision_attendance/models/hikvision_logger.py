# -*- coding: utf-8 -*-
"""
Hikvision logging yordamchilari.

Odoo'ning standart logging tizimidan foydalanadi - loglar Odoo
server logiga tushadi va odatdagi log sozlamalari bilan boshqariladi.

O'ZGARISH TARIXI:
  Ilgari bu modul addon papkasi ichiga (logs/hikvision.log) o'z faylini
  yozardi va har daqiqada log qatorlarini Telegram guruhga yuborardi.
  Ikkalasi ham olib tashlandi:
    - Addon papkasiga yozish: konteynerda/read-only o'rnatishda ishlamaydi,
      manba daraxtini ifloslaydi va 19 MB ga yetgan edi.
    - Telegram: bot tokeni kodda ochiq turardi va xodim ismlari bilan
      davomat vaqtlari nazoratsiz kanalga chiqib ketardi.
"""
import logging

_logger = logging.getLogger(__name__)


def log_info(message):
    _logger.info(message)


def log_error(message):
    _logger.error(message)


def log_warning(message):
    _logger.warning(message)


def log_debug(message):
    _logger.debug(message)


def log_cron(cron_name, message):
    """Cron job hodisasi."""
    _logger.info("[CRON: %s] %s", cron_name, message)


def log_sync(action, employee_name, status, device_name=None):
    """Xodim sinxronizatsiyasi hodisasi."""
    target = f" -> {device_name}" if device_name else ""
    _logger.info("[SYNC: %s] %s%s: %s", action, employee_name, target, status)


def log_api(method, endpoint, status, error=None):
    """Qurilma API chaqiruvi."""
    if error:
        _logger.warning("[API] %s %s -> %s: %s", method, endpoint, status, error)
    else:
        _logger.debug("[API] %s %s -> %s", method, endpoint, status)
