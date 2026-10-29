# -*- coding: utf-8 -*-
"""Nomenklatura kengaytmasi (TZ 4.11, 8-bo'lim).

Ikki narsa qo'shiladi:

* **narx nazorati kalitlari** — og'ish foizi va kategoriya limit narxi.
  Og'ish foizi uch darajada: tovar (1-o'rin) → kategoriya (2-o'rin) →
  umumiy sozlama (3-o'rin). Eng aniqrog'i ustunlik qiladi.
* **seriya/yaroqlilik majburiyati** — dori-darmon va oziq-ovqatda tovar
  kategoriyasi darajasida yoqiladi va mahsulotlarga tarqatiladi. TZ 21.2:
  «keyin yoqish katta muammo», shuning uchun kategoriya belgilanishi bilan
  mahsulotdagi `tracking` va `use_expiration_date` avtomat yoqiladi.
"""
from odoo import _, api, fields, models

from .res_partner import XARAJAT_TURI


class ProductCategory(models.Model):
    _inherit = 'product.category'

    narx_ogish_foizi = fields.Float(
        "Narx og'ish chegarasi (%)",
        help="Haqiqiy narx norma narxdan shu foizdan ko'p oshsa kirim "
             "hujjati saqlanmaydi. Bo'sh (0) bo'lsa ota kategoriyadan, "
             "u ham bo'lmasa umumiy sozlamadan olinadi.")
    kategoriya_limit_narx = fields.Float(
        "Kategoriya limit narxi",
        help="Norma narxning 2-qatlami: xarid tarixi bo'lmaganda shu narx "
             "chegara sifatida ishlatiladi.")
    kuzatuv_majburiy = fields.Selection(
        [('yoq', "Kerak emas"),
         ('seriya', "Seriya raqami"),
         ('lot_muddat', "Lot + yaroqlilik muddati")],
        string="Kuzatuv majburiyati", default='yoq', required=True,
        help="Dori-darmon va oziq-ovqatda «Lot + yaroqlilik muddati», "
             "uskunada «Seriya raqami» (TZ 8-bo'lim).")

    def _agronova_ogish_foizi(self):
        """Kategoriya zanjiri bo'ylab yuqoriga yurib chegara topadi."""
        kat = self
        while kat:
            if kat.narx_ogish_foizi:
                return kat.narx_ogish_foizi
            kat = kat.parent_id
        return 0.0

    def _agronova_limit_narx(self):
        kat = self
        while kat:
            if kat.kategoriya_limit_narx:
                return kat.kategoriya_limit_narx
            kat = kat.parent_id
        return 0.0

    def _agronova_kuzatuv(self):
        kat = self
        while kat:
            if kat.kuzatuv_majburiy and kat.kuzatuv_majburiy != 'yoq':
                return kat.kuzatuv_majburiy
            kat = kat.parent_id
        return 'yoq'

    def write(self, vals):
        res = super().write(vals)
        if 'kuzatuv_majburiy' in vals:
            self.env['product.template'].search(
                [('categ_id', 'child_of', self.ids)])._agronova_kuzatuv_qollash()
        return res


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    xarajat_turi = fields.Selection(
        XARAJAT_TURI, string="Xarajat turi", tracking=True,
        help="Hom ashyo / dori-darmon / VH / uskuna / xizmat.")
    narx_ogish_foizi = fields.Float(
        "Narx og'ish chegarasi (%)",
        help="Faqat shu tovar uchun. Kategoriya va umumiy chegaradan "
             "ustun turadi (1-o'rin).")
    norma_narx = fields.Float(
        "Norma narx", compute='_compute_norma_narx',
        help="Uch qatlamli mexanizm natijasi: xarid tarixi → kategoriya "
             "limiti → «birinchi xarid». Qo'lda kiritilmaydi.")
    norma_narx_manba = fields.Char(
        "Norma narx manbai", compute='_compute_norma_narx')
    norma_narx_sana = fields.Date(
        "Norma narx sanasi", compute='_compute_norma_narx')
    norma_narx_eski = fields.Boolean(
        "Norma narx eskirgan", compute='_compute_norma_narx',
        help="Sozlamadagi muddatdan (masalan 6 oy) eski.")
    seriya_kuzatuv_shart = fields.Boolean(
        "Kuzatuv majburiy", compute='_compute_seriya_kuzatuv_shart', store=True,
        help="Kategoriya talabidan kelib chiqadi — dori va oziq-ovqatda "
             "lot/muddat, uskunada seriya.")

    @api.depends('categ_id', 'categ_id.kuzatuv_majburiy')
    def _compute_seriya_kuzatuv_shart(self):
        for tmpl in self:
            tmpl.seriya_kuzatuv_shart = tmpl.categ_id._agronova_kuzatuv() != 'yoq'

    def _compute_norma_narx(self):
        Normativ = self.env['agronova.narx.normasi']
        for tmpl in self:
            natija = Normativ._agronova_norma(tmpl.product_variant_id or tmpl)
            tmpl.norma_narx = natija['narx']
            tmpl.norma_narx_manba = natija['manba_nomi']
            tmpl.norma_narx_sana = natija['sana']
            tmpl.norma_narx_eski = natija['eski']

    def _agronova_kuzatuv_qollash(self):
        """Kategoriya talabini mahsulotga tarqatadi (TZ 21.2)."""
        for tmpl in self:
            talab = tmpl.categ_id._agronova_kuzatuv()
            vals = {}
            if talab == 'seriya' and tmpl.tracking != 'serial':
                vals['tracking'] = 'serial'
            elif talab == 'lot_muddat':
                if tmpl.tracking == 'none':
                    vals['tracking'] = 'lot'
                if not tmpl.use_expiration_date:
                    vals['use_expiration_date'] = True
            if vals:
                tmpl.write(vals)
        return True

    @api.model_create_multi
    def create(self, vals_list):
        tmpls = super().create(vals_list)
        tmpls._agronova_kuzatuv_qollash()
        return tmpls

    def write(self, vals):
        res = super().write(vals)
        if 'categ_id' in vals:
            self._agronova_kuzatuv_qollash()
        return res

    def _agronova_ogish_chegara(self):
        """Shu tovar uchun amaldagi og'ish chegarasi (%) va uning manbai."""
        self.ensure_one()
        if self.narx_ogish_foizi:
            return self.narx_ogish_foizi, _("tovar darajasi")
        kat = self.categ_id._agronova_ogish_foizi()
        if kat:
            return kat, _("kategoriya darajasi")
        umumiy = float(self.env['ir.config_parameter'].sudo().get_param(
            'agronova_zakupka.ogish_umumiy', 10.0) or 10.0)
        return umumiy, _("umumiy sozlama")


class ProductProduct(models.Model):
    _inherit = 'product.product'

    def _agronova_ogish_chegara(self):
        return self.product_tmpl_id._agronova_ogish_chegara()
