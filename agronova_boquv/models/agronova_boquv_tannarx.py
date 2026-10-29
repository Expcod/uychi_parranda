# -*- coding: utf-8 -*-
"""Kunlik tannarx snapshot — dashboardning «bugungi va kechagi tannarx».

TZ 15-band: «1 dona tirik jo'ja tannarxi … **har kuni yangilanadi**».
TZ 20-band, dashboard: «Bugungi tannarx · Kechagi tannarx».

Compute maydon bir vaqtning o'zida faqat **hozirgi** qiymatni bera oladi —
kechagini bilish uchun tarix kerak. Shuning uchun har kecha cron barcha
faol partiya bo'yicha bitta satr yozadi: shu kundagi tirik son, jami
xarajat, tannarx, FCR, nobudgarchilik.

Bu jadval yana ikki narsani beradi:

* tannarx **dinamikasi grafigi** (partiya davomida qanday o'sgan);
* hisobotlar tez ishlaydi — analitik qatorlarni qayta yig'ish shart emas.

Yopilgan partiya uchun snapshot yozilmaydi — tannarx qotgan.
"""
import logging

from odoo import _, api, fields, models

_logger = logging.getLogger(__name__)


class AgroNovaBoquvTannarxKunlik(models.Model):
    _name = 'agronova.boquv.tannarx.kunlik'
    _description = "Boquv — kunlik tannarx"
    _order = 'sana desc, partiya_id'
    _rec_name = 'sana'

    sana = fields.Date("Sana", required=True, index=True)
    partiya_id = fields.Many2one(
        'agronova.boquv.partiya', string="Partiya", required=True,
        ondelete='cascade', index=True)
    bino_id = fields.Many2one(
        related='partiya_id.bino_id', string="Bino", store=True, readonly=True)
    filial_id = fields.Many2one(
        related='partiya_id.filial_id', string="Filial", store=True, readonly=True)
    company_id = fields.Many2one(
        related='partiya_id.company_id', string="Korxona",
        store=True, readonly=True)
    currency_id = fields.Many2one(
        related='company_id.currency_id', readonly=True)

    yosh_kun = fields.Integer("Yoshi (kun)")
    tirik_son = fields.Integer("Tirik bosh soni")
    nobud_son = fields.Integer("Nobud (jami)")
    nobud_foiz = fields.Float("Nobudgarchilik (%)", digits=(12, 2))
    ortacha_vazn = fields.Float("O'rtacha vazn (kg)", digits='Product Unit')
    jami_tirik_vazn = fields.Float("Jami tirik vazn (kg)", digits='Product Unit')
    yem_sarf_kg = fields.Float("Yem sarfi (kg)", digits='Product Unit')
    fcr = fields.Float("FCR", digits=(12, 3))
    epef = fields.Float("EPEF", digits=(12, 1))

    jami_xarajat = fields.Monetary("Jami xarajat")
    tannarx_1_bosh = fields.Monetary("1 bosh tannarxi")
    tannarx_1_kg = fields.Monetary("1 kg tirik vazn tannarxi")

    # --- kechagi bilan farq
    oldingi_1_bosh = fields.Monetary(
        "Kechagi 1 bosh tannarxi",
        help="Oldingi snapshot qiymati — o'sish dinamikasini ko'rish uchun.")
    ozgarish_1_bosh = fields.Monetary(
        "1 bosh o'zgarishi", compute='_compute_ozgarish', store=True)
    ozgarish_foiz = fields.Float(
        "O'zgarish (%)", compute='_compute_ozgarish', store=True, digits=(12, 2))

    _partiya_sana_uniq = models.Constraint(
        'UNIQUE(partiya_id, sana)',
        "Bu partiya uchun shu sanadagi tannarx snapshot allaqachon mavjud.")

    @api.depends('tannarx_1_bosh', 'oldingi_1_bosh')
    def _compute_ozgarish(self):
        for t in self:
            t.ozgarish_1_bosh = t.tannarx_1_bosh - t.oldingi_1_bosh
            t.ozgarish_foiz = (
                t.ozgarish_1_bosh / t.oldingi_1_bosh * 100.0
                if t.oldingi_1_bosh else 0.0)

    # ------------------------------------------------------------- yozish
    @api.model
    def _snapshot_yozish(self, sana=None, partiyalar=None):
        """Berilgan sana uchun snapshot yozadi (yoki yangilaydi).

        Cron kuniga bir marta chaqiradi. Qo'lda ham chaqirilishi mumkin —
        shuning uchun mavjud satr bo'lsa yangilanadi, dublikat yaratilmaydi.
        """
        sana = sana or fields.Date.context_today(self)
        if partiyalar is None:
            partiyalar = self.env['agronova.boquv.partiya'].search([
                ('holat', '=', 'active'),
            ])
        yozilgan = self.browse()
        for p in partiyalar:
            # Oldingi snapshot — «kechagi tannarx» uchun.
            oldingi = self.search([
                ('partiya_id', '=', p.id),
                ('sana', '<', sana),
            ], order='sana desc', limit=1)
            vals = {
                'sana': sana,
                'partiya_id': p.id,
                'yosh_kun': p.yosh_kun,
                'tirik_son': p.joriy_son,
                'nobud_son': p.nobud_son,
                'nobud_foiz': p.nobud_foiz,
                'ortacha_vazn': p.ortacha_vazn,
                'jami_tirik_vazn': p.jami_tirik_vazn,
                'yem_sarf_kg': p.yem_sarf_kg,
                'fcr': p.fcr,
                'epef': p.epef,
                'jami_xarajat': p.jami_xarajat,
                'tannarx_1_bosh': p.tannarx_1_bosh,
                'tannarx_1_kg': p.tannarx_1_kg,
                'oldingi_1_bosh': oldingi.tannarx_1_bosh if oldingi else 0.0,
            }
            mavjud = self.search([
                ('partiya_id', '=', p.id), ('sana', '=', sana),
            ], limit=1)
            if mavjud:
                mavjud.write(vals)
                yozilgan |= mavjud
            else:
                yozilgan |= self.create(vals)
        return yozilgan

    @api.model
    def _cron_kunlik_tannarx(self):
        """Kunlik cron — barcha faol partiya bo'yicha snapshot."""
        yozilgan = self._snapshot_yozish()
        _logger.info("Boquv: %s ta partiya uchun kunlik tannarx yozildi.",
                     len(yozilgan))
        return True

    @api.model
    def kechagi(self, partiya):
        """Partiyaning kechagi tannarx satri (dashboard uchun)."""
        bugun = fields.Date.context_today(self)
        return self.search([
            ('partiya_id', '=', partiya.id),
            ('sana', '<', bugun),
        ], order='sana desc', limit=1)
