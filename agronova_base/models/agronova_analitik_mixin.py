# -*- coding: utf-8 -*-
"""Analitik hisob bilan ishlash uchun umumiy yordamchilar.

Loyihada xarajat va daromadning yagona manbasi — `account.analytic.line`.
Har bir obyekt (bino/seh, partiya, reys) o'z analitik hisobiga ega bo'ladi,
barcha pul harakati o'sha hisobga yoziladi. Bo'lim modullari tannarx va
foyda-zararni shu qatorlardan hisoblaydi, o'z jadvalidan emas — shunda
ikki xil manbadan ikki xil raqam chiqib qolmaydi.
"""
from odoo import _, api, fields, models
from odoo.exceptions import UserError


class AgroNovaAnalitikMixin(models.AbstractModel):
    """Obyektga avtomat analitik hisob ochadi va unga qator yozadi."""
    _name = 'agronova.analitik.mixin'
    _description = "AgroNova — analitik hisob mixin"

    analytic_account_id = fields.Many2one(
        'account.analytic.account', string="Analitik hisob",
        readonly=True, copy=False, ondelete='restrict', index=True,
        help="Yozuv yaratilganda avtomat ochiladi. Barcha xarajat va daromad "
             "shu hisobga yig'iladi.")

    # Meros oluvchi model shu ikkitasini belgilaydi
    _agronova_analytic_plan_xmlid = None   # masalan 'agronova_ona_tovuq.analytic_plan_ot_partiya'
    _agronova_analytic_plan_name = None    # xmlid topilmasa nom bo'yicha qidiriladi/yaratiladi

    # ------------------------------------------------------------------ plan
    @api.model
    def _agronova_get_plan(self, xmlid=None, name=None, parent_plan=None):
        """Analitik rejani xmlid yoki nom bo'yicha topadi, bo'lmasa yaratadi.

        Loyihadagi mavjud rejalar («Filial», «Bino (seh)», «Faoliyat
        yo'nalishi») qo'lda/skript orqali yaratilgan va xmlid'i yo'q —
        shuning uchun nom bo'yicha qidirish ham kerak.
        """
        Plan = self.env['account.analytic.plan'].sudo()
        if xmlid:
            plan = self.env.ref(xmlid, raise_if_not_found=False)
            if plan:
                return plan
        if not name:
            return Plan.browse()
        plan = Plan.search([('name', '=ilike', name)], limit=1)
        if not plan:
            vals = {'name': name, 'default_applicability': 'optional'}
            if parent_plan:
                vals['parent_id'] = parent_plan.id
            plan = Plan.create(vals)
        return plan

    def _agronova_analytic_plan(self):
        """Shu model uchun analitik reja."""
        return self._agronova_get_plan(
            xmlid=self._agronova_analytic_plan_xmlid,
            name=self._agronova_analytic_plan_name,
        )

    def _agronova_analytic_vals(self):
        """Analitik hisob yaratish uchun qiymatlar. Model qayta yozishi mumkin."""
        self.ensure_one()
        return {
            'name': self.display_name,
            'company_id': getattr(self, 'company_id', self.env.company).id,
        }

    def _ensure_analytic_account(self):
        """Analitik hisobi yo'q yozuvlarga hisob ochadi."""
        plan = self._agronova_analytic_plan()
        if not plan:
            return
        Analytic = self.env['account.analytic.account'].sudo()
        for rec in self.filtered(lambda r: not r.analytic_account_id):
            vals = rec._agronova_analytic_vals()
            vals['plan_id'] = plan.id
            rec.analytic_account_id = Analytic.create(vals)

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        records._ensure_analytic_account()
        return records

    # ------------------------------------------------------------- qatorlar
    def _agronova_post_analytic(self, name, amount, date=None, extra=None,
                             unit_amount=0.0, product=None, tannarxga=True):
        """Analitik qator yozadi.

        `amount` ishorasi Odoo konvensiyasi bo'yicha: **xarajat manfiy,
        daromad musbat**. Bu qatorlar tannarx va foyda-zararning yagona
        manbasi, shuning uchun har bir xarajat manbai (xarajat hujjati,
        ombordan sarf, ish haqi) shu metod orqali o'tadi.
        """
        self.ensure_one()
        if not self.analytic_account_id:
            raise UserError(_(
                "«%s» yozuvida analitik hisob yo'q — xarajat biriktirib "
                "bo'lmaydi.", self.display_name))
        plan = self.analytic_account_id.plan_id
        vals = {
            'name': name,
            'date': date or fields.Date.context_today(self),
            'amount': amount,
            'unit_amount': unit_amount,
            # Sotilgan mahsulotning tannarx chiqimi birlik tannarxini
            # oshirmasligi kerak — `tannarxga=False` bilan yoziladi.
            'agronova_tannarx_bazasi': tannarxga,
            plan._column_name(): self.analytic_account_id.id,
        }
        if product:
            vals['product_id'] = product.id
        if extra:
            vals.update(extra)
        return self.env['account.analytic.line'].sudo().create(vals)

    def _agronova_analytic_amount(self, date_from=None, date_to=None, sign=None,
                               faqat_tannarx=False):
        """Analitik hisobdagi summani qaytaradi.

        `sign='cost'` — faqat xarajat (manfiy qatorlar) mutlaq qiymatda,
        `sign='income'` — faqat daromad, aks holda sof qoldiq.

        `faqat_tannarx=True` — birlik tannarxini hisoblash uchun: sotilgan
        mahsulotning tannarx chiqimi qatorlari chiqarib tashlanadi, aks
        holda tannarx har sotuvda o'z-o'zidan oshib ketadi.
        """
        self.ensure_one()
        if not self.analytic_account_id:
            return 0.0
        plan = self.analytic_account_id.plan_id
        domain = [(plan._column_name(), '=', self.analytic_account_id.id)]
        if date_from:
            domain.append(('date', '>=', date_from))
        if date_to:
            domain.append(('date', '<=', date_to))
        # `faqat_tannarx` belgini toraytiradi, ishorani emas: ikkala shart
        # ham qo'llanadi. `elif` qilinsa daromad qatorlari ham bazaga
        # tushadi — ichki berish tushumi tannarxdan ayrilib, birlik
        # tannarxi manfiy chiqadi (QX: 370 so'm o'rniga -192,5 so'm).
        if faqat_tannarx:
            domain.append(('agronova_tannarx_bazasi', '=', True))
        if sign == 'cost':
            domain.append(('amount', '<', 0.0))
        elif sign == 'income':
            domain.append(('amount', '>', 0.0))
        lines = self.env['account.analytic.line'].sudo().search(domain)
        total = sum(lines.mapped('amount'))
        return -total if sign == 'cost' else total
