# -*- coding: utf-8 -*-
"""Ishlab chiqarish tannarxi (Yem zavodi TZ 7 va 13-band).

Odoo 19 da `mrp.production` da tannarx yig'indisi maydonlari yo'q — faqat
`extra_cost` (qo'lda kiritiladigan qo'shimcha). Qiymatlar `stock.move.value`
da yotadi, lekin ular hujjatda ko'rinmaydi va hisobotga tushmaydi.

TZ talab qiladi: **1 kg va 1 tonna yem tannarxi**, xomashyo qiymatining
tannarxga ta'siri, ishlab chiqarish xarajatlari, **rejalashtirilgan va
haqiqiy tannarx** taqqoslamasi. Shu maydonlar shu yerda hisoblanadi.

Tonnaga o'girish o'lchov birligi orqali qilinadi — mahsulot kilogrammda
bo'lsa ham, tonnada bo'lsa ham to'g'ri chiqadi.
"""
from odoo import _, api, fields, models


class MrpProduction(models.Model):
    _inherit = 'mrp.production'

    currency_id = fields.Many2one(
        'res.currency', related='company_id.currency_id', readonly=True)

    # Ishlab chiqariladigan mahsulot ro'yxati: faqat **retsepti bor** va
    # retsepti shu korxonaga tegishli mahsulotlar. Standart holda Odoo barcha
    # `consu` mahsulotlarni ko'rsatadi — yem zavodi operatori ro'yxatdan
    # vitamin, o'g'it, dori va boshqa bo'limlarning mahsulotini ham ko'radi
    # va adashadi. Retseptsiz mahsulotni ishlab chiqarib bo'lmaydi.
    product_id = fields.Many2one(
        domain="[('type', '=', 'consu'),"
               " ('bom_ids', '!=', False),"
               " ('bom_ids.company_id', 'in', [False, company_id])]")

    agronova_miqdor_kg = fields.Float(
        "Ishlab chiqarilgan (kg)", compute='_compute_agronova_tannarx',
        store=True, digits='Product Unit',
        help="Mahsulot o'lchov birligidan kilogrammga o'girilgan miqdor.")
    agronova_xomashyo_qiymat = fields.Monetary(
        "Xomashyo qiymati", compute='_compute_agronova_tannarx', store=True,
        help="Sarflangan xomashyoning FIFO bo'yicha haqiqiy qiymati.")
    agronova_ustama_qiymat = fields.Monetary(
        "Ishlab chiqarish xarajati", compute='_compute_agronova_tannarx',
        store=True,
        help="Ish markazi orqali kirgan xarajat: elektr, gaz, ish haqi, "
             "amortizatsiya. Tayyor mahsulot qiymati minus xomashyo.")
    agronova_jami_tannarx = fields.Monetary(
        "Jami tannarx", compute='_compute_agronova_tannarx', store=True)
    agronova_tannarx_1_kg = fields.Monetary(
        "1 kg tannarxi", compute='_compute_agronova_tannarx', store=True)
    agronova_tannarx_1_tonna = fields.Monetary(
        "1 tonna tannarxi", compute='_compute_agronova_tannarx', store=True)
    agronova_xomashyo_ulush = fields.Float(
        "Xomashyo ulushi (%)", compute='_compute_agronova_tannarx', store=True,
        help="Xomashyo qiymati tannarxning necha foizini tashkil qiladi.")

    # Reja hisoblanadigan maydon EMAS: u buyurtma tasdiqlangan paytda
    # qotadi. Aks holda xomashyo narxi keyin o'zgarsa, o'tgan oylarning
    # reja-fakt taqqoslamasi ham siljib ketardi va tarix yolg'on ko'rsatardi.
    agronova_reja_tannarx_1_kg = fields.Monetary(
        "Reja: 1 kg tannarxi", readonly=True, copy=False,
        help="Buyurtma tasdiqlangan paytdagi retsept bo'yicha nazariy "
             "tannarx: komponentlarning standart narxi + operatsiya vaqti × "
             "ish markazi tarifi. Keyin o'zgarmaydi.")
    # Saqlanadi — saqlanmagan maydon bo'yicha filtr va guruhlash ishlamaydi
    # (hisobotda «rejadan qimmat/arzon» filtrlari shunga tayanadi).
    agronova_chetlanish = fields.Float(
        "Rejadan chetlanish (%)", compute='_compute_agronova_chetlanish',
        store=True,
        help="Fakt rejadan qancha foizga farq qildi. Musbat — qimmatga "
             "tushgan.")

    # ------------------------------------------------------------- yordamchi
    def _agronova_kg(self, qty, uom):
        """Miqdorni kilogrammga o'giradi; o'girib bo'lmasa 0 qaytaradi."""
        kg = self.env.ref('uom.product_uom_kgm', raise_if_not_found=False)
        if not kg or not uom or not qty:
            return 0.0
        if uom == kg:
            return qty
        try:
            return uom._compute_quantity(qty, kg, raise_if_failure=False) or 0.0
        except Exception:
            # Og'irlik bo'lmagan birlik (dona, litr) — tonnaga o'girilmaydi.
            return 0.0

    # -------------------------------------------------------------- compute
    @api.depends('state', 'qty_produced', 'product_uom_id',
                 'move_raw_ids.value', 'move_raw_ids.state',
                 'move_finished_ids.value', 'move_finished_ids.state',
                 'move_finished_ids.quantity')
    def _compute_agronova_tannarx(self):
        for mo in self:
            xom = sum(abs(m.value or 0.0)
                      for m in mo.move_raw_ids if m.state == 'done')
            tayyor = mo.move_finished_ids.filtered(
                lambda m: m.state == 'done' and m.product_id == mo.product_id)
            jami = sum(abs(m.value or 0.0) for m in tayyor)
            miqdor = sum(m.quantity for m in tayyor)

            # Tayyor mahsulot qiymati hisoblanmagan bo'lsa (masalan standart
            # baholashda narx qo'yilmagan) — kamida xomashyoni ko'rsatamiz.
            if not jami and xom:
                jami = xom

            mo.agronova_xomashyo_qiymat = xom
            mo.agronova_ustama_qiymat = max(jami - xom, 0.0)
            mo.agronova_jami_tannarx = jami
            mo.agronova_xomashyo_ulush = (xom / jami * 100.0) if jami else 0.0

            kg = mo._agronova_kg(miqdor, tayyor[:1].product_uom or mo.product_uom_id)
            mo.agronova_miqdor_kg = kg
            mo.agronova_tannarx_1_kg = (jami / kg) if kg else 0.0
            mo.agronova_tannarx_1_tonna = mo.agronova_tannarx_1_kg * 1000.0

    @api.depends('agronova_tannarx_1_kg', 'agronova_reja_tannarx_1_kg')
    def _compute_agronova_chetlanish(self):
        for mo in self:
            reja = mo.agronova_reja_tannarx_1_kg
            mo.agronova_chetlanish = (
                (mo.agronova_tannarx_1_kg - reja) / reja * 100.0
                if reja and mo.agronova_tannarx_1_kg else 0.0)

    # ------------------------------------------------------------ reja qotish
    def _agronova_reja_hisobla(self):
        """Retsept bo'yicha 1 kg nazariy tannarx (shu paytdagi narxlarda)."""
        self.ensure_one()
        bom = self.bom_id
        if not bom or not bom.product_qty:
            return 0.0
        xom = sum(line.product_id.standard_price * line.product_qty
                  for line in bom.bom_line_ids)
        ustama = sum(
            (op.time_cycle_manual / 60.0) * op.workcenter_id.costs_hour
            for op in bom.operation_ids)
        kg = self._agronova_kg(bom.product_qty, bom.product_uom_id)
        return ((xom + ustama) / kg) if kg else 0.0

    def action_confirm(self):
        res = super().action_confirm()
        for mo in self:
            if not mo.agronova_reja_tannarx_1_kg:
                mo.agronova_reja_tannarx_1_kg = mo._agronova_reja_hisobla()
        return res

    def button_mark_done(self):
        # Modul o'rnatilishidan oldin tasdiqlangan buyurtmalarda reja bo'sh
        # qolgan bo'lishi mumkin — yopishdan oldin to'ldiramiz.
        for mo in self:
            if not mo.agronova_reja_tannarx_1_kg:
                mo.agronova_reja_tannarx_1_kg = mo._agronova_reja_hisobla()
        return super().button_mark_done()
