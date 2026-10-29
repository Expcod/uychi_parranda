# -*- coding: utf-8 -*-
"""Xarid sozlamalari.

TZ 20-bo'lim: quyidagi qiymatlar buyurtmachidan hali olinmagan. Har biri
`ir.config_parameter` orqali sozlanadi — kodga qattiq yozilmagan, admin
interfeysdan o'zgartiradi.
"""
from odoo import fields, models

# Sozlama kalitlari va ularning taxminiy (kelishilmagan) qiymatlari.
# TODO: buyurtmachi tasdiqlashi kerak — 20-bo'lim.
DEFAULTS = {
    'agronova_zakupka.bitta_tasdiq_chegara': '500000',      # TODO 20.1
    'agronova_zakupka.muddat_juda_muhim': '1.0',            # TODO 20.3 (6-bo'lim jadvali)
    'agronova_zakupka.muddat_orta': '1.5',
    'agronova_zakupka.muddat_zaxira': '3.0',
    'agronova_zakupka.eskalatsiya_oraliq': '30',            # TODO 20.3, daqiqa
    'agronova_zakupka.narx_eskirish_oy': '6',               # TODO 20.4
    'agronova_zakupka.ogish_umumiy': '10.0',                # TODO 20.5, %
    'agronova_zakupka.narx_tarixi_soni': '5',               # oxirgi necha xarid o'rtachasi
    'agronova_zakupka.birinchi_xarid_taklif': '3',          # 6-bo'lim: kamida 3 taklif
    'agronova_zakupka.tranzit_ogohlantirish_kun': '3',      # 7-bo'lim hisoboti
    'agronova_zakupka.didox_kutish_kun': '3',               # 9-bo'lim ogohlantirishi
    'agronova_zakupka.orqaga_sana_oyna': '24',              # 12-bo'lim, soat
}


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    # --- tasdiqlash va muddat
    agronova_zk_kalendar_id = fields.Many2one(
        'resource.calendar', string="Xarid ish vaqti kalendari",
        config_parameter='agronova_zakupka.kalendar_id',
        help="TZ 21.7 — barcha muddat hisoblari (javob, tasdiq, eskalatsiya) "
             "shu bitta kalendardan olinadi. Bo'sh bo'lsa korxona kalendari.")
    agronova_zk_bitta_tasdiq_chegara = fields.Float(
        "Bitta tasdiq chegarasi (so'm)",
        config_parameter='agronova_zakupka.bitta_tasdiq_chegara',
        help="Shu summadan past ruxsat so'rovi bitta tasdiq bilan yopiladi "
             "(sifat va narx nazorati bosqichi o'tkazib yuboriladi). "
             "TODO: aniq raqam buyurtmachidan.")
    agronova_zk_muddat_juda_muhim = fields.Float(
        "1 — juda muhim: javob muddati (soat)",
        config_parameter='agronova_zakupka.muddat_juda_muhim')
    agronova_zk_muddat_orta = fields.Float(
        "2 — o'rta muhim: javob muddati (soat)",
        config_parameter='agronova_zakupka.muddat_orta')
    agronova_zk_muddat_zaxira = fields.Float(
        "3 — zaxira uchun: javob muddati (soat)",
        config_parameter='agronova_zakupka.muddat_zaxira')
    agronova_zk_eskalatsiya_oraliq = fields.Integer(
        "Eskalatsiya oralig'i (daqiqa)",
        config_parameter='agronova_zakupka.eskalatsiya_oraliq',
        help="Muddat o'tgach shu oraliqda o'rinbosarga, keyingisida yuqori "
             "rahbarga xabar boradi. TODO: aniq qiymat buyurtmachidan.")

    # --- narx nazorati
    agronova_zk_narx_tarixi_soni = fields.Integer(
        "Norma narx uchun oxirgi xaridlar soni",
        config_parameter='agronova_zakupka.narx_tarixi_soni',
        help="1-qatlam: shu songa teng oxirgi xaridning o'rtacha narxi "
             "norma narx sifatida olinadi (TZ 6-bo'lim: 3-5).")
    agronova_zk_narx_eskirish_oy = fields.Integer(
        "Narx eskirish chegarasi (oy)",
        config_parameter='agronova_zakupka.narx_eskirish_oy',
        help="Norma narx shu muddatdan eski bo'lsa ogohlantiriladi. "
             "TODO: aniq muddat buyurtmachidan.")
    agronova_zk_ogish_umumiy = fields.Float(
        "Umumiy og'ish chegarasi (%)",
        config_parameter='agronova_zakupka.ogish_umumiy',
        help="Tovarda ham, kategoriyada ham chegara ko'rsatilmagan bo'lsa "
             "shu qiymat ishlatiladi. TODO: aniq raqam buyurtmachidan.")
    agronova_zk_birinchi_xarid_taklif = fields.Integer(
        "«Birinchi xarid» uchun minimal taklif soni",
        config_parameter='agronova_zakupka.birinchi_xarid_taklif')

    # --- tranzit va Didox
    agronova_zk_tranzit_kun = fields.Integer(
        "Tranzitda ogohlantirish (kun)",
        config_parameter='agronova_zakupka.tranzit_ogohlantirish_kun',
        help="Tovar zakupchik tranzitida shu kundan ortiq tursa hisobotga "
             "tushadi va zakupchikka eslatma yuboriladi.")
    agronova_zk_didox_kutish_kun = fields.Integer(
        "Faktura kutish chegarasi (kun)",
        config_parameter='agronova_zakupka.didox_kutish_kun',
        help="Tovar keldi, Didox fakturasi shu kundan ortiq kelmasa "
             "buxgalterga xabar boradi.")
    agronova_zk_didox_url = fields.Char(
        "Didox API manzili", config_parameter='agronova_zakupka.didox_url')
    agronova_zk_didox_login = fields.Char(
        "Didox login", config_parameter='agronova_zakupka.didox_login')
    agronova_zk_didox_token = fields.Char(
        "Didox token", config_parameter='agronova_zakupka.didox_token')

    # --- kiritish intizomi (12-bo'lim)
    agronova_zk_orqaga_sana_oyna = fields.Integer(
        "Orqaga sana oynasi (soat)",
        config_parameter='agronova_zakupka.orqaga_sana_oyna',
        help="Shu oyna ichida orqaga sana bilan kiritish mumkin — hujjat "
             "«kechikib kiritilgan» deb belgilanadi. Oynadan tashqarida "
             "bosh buxgalter ruxsati kerak, oy yopilgandan keyin mutlaqo "
             "taqiqlanadi.")
