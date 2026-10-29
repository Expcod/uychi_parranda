# -*- coding: utf-8 -*-
"""Tarozi agenti shu yerga vazn yuboradi.

POST /agronova/tarozi/vazn  (JSON)
    {"kod": "AVTO-1", "kalit": "<agent kaliti>", "vazn": 24180, "barqaror": true}

Kalit tarozi kartasida (faqat administrator ko'radi). Kalit noto'g'ri
bo'lsa javob bir xil — qaysi kod mavjudligini tashqaridan bilib bo'lmasin.
"""
import hmac
import logging

from odoo import http
from odoo.http import request

_logger = logging.getLogger(__name__)


class AgroNovaTaroziController(http.Controller):

    @http.route('/agronova/tarozi/vazn', type='jsonrpc', auth='none',
                methods=['POST'], csrf=False)
    def vazn(self, kod=None, kalit=None, vazn=None, barqaror=True, **kw):
        if not kod or not kalit or vazn is None:
            return {'ok': False, 'error': 'kod, kalit va vazn majburiy'}
        Tarozi = request.env['agronova.tarozi'].sudo()
        tarozi = Tarozi.search([('kod', '=', kod), ('active', '=', True)], limit=1)
        if not tarozi or not tarozi.token or \
                not hmac.compare_digest(str(tarozi.token), str(kalit)):
            _logger.warning("Tarozi: noto'g'ri kod yoki kalit (%s)", kod)
            return {'ok': False, 'error': 'ruxsat yo\'q'}
        try:
            tarozi.vazn_qabul(vazn, barqaror=bool(barqaror))
        except Exception as e:  # noqa: BLE001 — agentga matnli javob
            return {'ok': False, 'error': str(e)}
        return {'ok': True}
