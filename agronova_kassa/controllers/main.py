# -*- coding: utf-8 -*-
"""Chekni ochiq tekshirish sahifasi.

Chekdagi QR kod shu manzilga olib boradi. Mijoz telefonida ochib,
qo'lidagi qog'oz chek haqiqiy ekaniga ishonch hosil qiladi — bu TZ M04
dagi «QR + ochiq tekshirish sahifasi» talabi.

Sahifa **autentifikatsiyasiz** ochiladi, shuning uchun u faqat chekning
o'zida allaqachon bosilgan ma'lumotni ko'rsatadi: order raqami, sana,
summa va kassa nomi. Token — 32 belgili tasodifiy uuid, ya'ni raqamni
ketma-ket terib boshqa cheklarni ko'rib bo'lmaydi.
"""
from odoo import http
from odoo.http import request


class AgroNovaKassaChek(http.Controller):

    @http.route(['/kassa/chek/<string:token>'], type='http', auth='public',
                website=False, sitemap=False)
    def chek(self, token, **kwargs):
        harakat = request.env['agronova.kassa.harakat'].sudo().search(
            [('chek_token', '=', token)], limit=1)
        if not harakat:
            return request.render('agronova_kassa.chek_topilmadi', {}, status=404)
        return request.render('agronova_kassa.chek_sahifa', {
            'harakat': harakat,
            'kassa': harakat.kassa_id,
            'company': harakat.company_id,
        })
