# -*- coding: utf-8 -*-
"""Kontragentlar bazasi (TZ 3-bo'lim).

Kirim hujjatida faqat shu bazadagi kontragent ishlatiladi — erkin matn yo'q.
Uch qattiq qoida:

1. Bir xil STIR bilan ikkinchi kontragent yaratilmaydi;
2. Yuridik shaxs va YATT STIRsiz saqlanmaydi;
3. Kontragent **o'chirilmaydi**, faqat bloklanadi — eski hujjatlar unga
   bog'langan bo'lishi mumkin (TZ 21.5).
"""
from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError

SHAXS_TURI = [
    ('yuridik', "Yuridik shaxs"),
    ('yatt', "YATT"),
    ('jismoniy', "Jismoniy shaxs"),
]
XARAJAT_TURI = [
    ('hom_ashyo', "Hom ashyo"),
    ('dori', "Dori-darmon"),
    ('vh', "Xo'jalik mollari (VH)"),
    ('uskuna', "Uskuna"),
    ('xizmat', "Xizmat"),
]


class ResPartner(models.Model):
    _inherit = 'res.partner'

    shaxs_turi = fields.Selection(
        SHAXS_TURI, string="Shaxs turi", tracking=True)
    stir = fields.Char(
        "STIR / INN", size=14, tracking=True, index='btree_not_null',
        help="Yuridik shaxs va YATT uchun majburiy. Takrorlanmaydi.")
    qqs_tolovchi = fields.Boolean("QQS to'lovchi", tracking=True)
    qqs_royxat_raqami = fields.Char("QQS ro'yxat raqami")
    xarajat_turi = fields.Selection(
        XARAJAT_TURI, string="Xarajat turi", tracking=True,
        help="Kontragent asosan qaysi turdagi tovar/xizmat yetkazadi.")
    bank_hisob_raqami = fields.Char("Bank hisob raqami", tracking=True)
    bank_mfo = fields.Char("Bank MFO", size=5, tracking=True)
    telegram_username = fields.Char(
        "Telegram username",
        help="Xabarnoma yuborish uchun. `agronova_telegram` xodimlar uchun alohida "
             "maydon yuritadi — bu esa kontragent uchun.")
    zakupka_holati = fields.Selection(
        [('faol', "Faol"), ('bloklangan', "Bloklangan")],
        string="Xarid holati", default='faol', required=True, tracking=True,
        help="Bloklangan kontragent yangi hujjatda tanlanmaydi, lekin eski "
             "hujjatlarda ko'rinishda qoladi.")
    bloklash_sababi = fields.Text("Bloklash sababi", tracking=True)

    _stir_uniq = models.Constraint(
        'UNIQUE(stir)',
        "Bu STIR bilan kontragent allaqachon mavjud — takroriy kontragent "
        "yaratilmaydi (TZ 3-bo'lim).",
    )

    @api.constrains('shaxs_turi', 'stir', 'bank_hisob_raqami', 'bank_mfo')
    def _check_zakupka_rekvizit(self):
        for p in self:
            if p.shaxs_turi in ('yuridik', 'yatt') and not p.stir:
                raise ValidationError(_(
                    "«%s» — yuridik shaxs va YATT STIRsiz saqlanmaydi.",
                    p.display_name))
            # Hisob raqami yolg'iz yetarli emas — MFO ham kerak, aks holda
            # to'lov topshiriqnomasi tuzilmaydi.
            if bool(p.bank_hisob_raqami) != bool(p.bank_mfo):
                raise ValidationError(_(
                    "«%s» — bank hisob raqami va MFO birga kiritiladi: "
                    "bittasi yolg'iz yetarli emas.", p.display_name))

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('stir') is not None:
                vals['stir'] = (vals.get('stir') or '').strip() or False
        return super().create(vals_list)

    def write(self, vals):
        if 'stir' in vals:
            vals['stir'] = (vals.get('stir') or '').strip() or False
        return super().write(vals)

    def action_zakupka_bloklash(self):
        for p in self:
            if not p.bloklash_sababi:
                raise UserError(_(
                    "«%s» ni bloklashdan oldin sababini yozing.", p.display_name))
            p.zakupka_holati = 'bloklangan'
        return True

    def action_zakupka_faollashtirish(self):
        self.write({'zakupka_holati': 'faol'})
        return True

    def unlink(self):
        """Xarid rekviziti kiritilgan kontragent o'chirilmaydi (TZ 21.5)."""
        himoyalangan = self.filtered(lambda p: p.stir or p.shaxs_turi)
        if himoyalangan and not self.env.context.get('agronova_force_unlink'):
            raise UserError(_(
                "Kontragent o'chirilmaydi — unga eski xarid hujjatlari "
                "bog'langan bo'lishi mumkin. «Bloklash» tugmasidan "
                "foydalaning: %s",
                ", ".join(himoyalangan.mapped('display_name'))))
        return super().unlink()
