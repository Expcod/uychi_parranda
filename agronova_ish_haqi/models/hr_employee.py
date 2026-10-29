# -*- coding: utf-8 -*-
"""Xodim kartochkasiga tarif va balans qo'shiladi.

Brigadir yoki xodimning o'zi «menga qancha qolgan?» degan savolga javobni
shu yerdan oladi — hisobvaraqlarni varaqlab chiqishi shart emas.
"""
from dateutil.relativedelta import relativedelta

from odoo import _, fields, models

from .agronova_ish_haqi_tarif import TUR as TARIF_TUR


class HrEmployee(models.Model):
    _inherit = 'hr.employee'

    agronova_tarif_ids = fields.One2many(
        'agronova.ish_haqi.tarif', 'employee_id', string="Ish haqi tariflari")
    agronova_tarif_id = fields.Many2one(
        'agronova.ish_haqi.tarif', string="Amaldagi tarif",
        compute='_compute_agronova_tarif')
    # `related=` ishlatilmaydi: `agronova_tarif_id` hisoblanadigan va
    # qidiruvsiz maydon, u orqali related qo'ysak Odoo qaysi yozuvni qayta
    # hisoblashni aniqlay olmaydi va registr ogohlantirish beradi.
    agronova_tarif_turi = fields.Selection(
        TARIF_TUR, string="Tarif turi", compute='_compute_agronova_tarif')
    agronova_stavka = fields.Monetary(
        "Stavka", compute='_compute_agronova_tarif',
        currency_field='agronova_currency_id')
    agronova_currency_id = fields.Many2one(
        'res.currency', related='company_id.currency_id', readonly=True)

    agronova_harakat_ids = fields.One2many(
        'agronova.ish_haqi.harakat', 'employee_id', string="Hisob-kitob harakati")
    agronova_hisoblandi = fields.Monetary(
        "Jami hisoblandi", compute='_compute_agronova_balans',
        currency_field='agronova_currency_id')
    agronova_berildi = fields.Monetary(
        "Jami berildi", compute='_compute_agronova_balans',
        currency_field='agronova_currency_id')
    agronova_balans = fields.Monetary(
        "Qoldiq (xodimga qarz)", compute='_compute_agronova_balans',
        currency_field='agronova_currency_id',
        help="Hisoblangan va bonus minus avans, jarima va berilgan pul. "
             "Musbat bo'lsa — korxona xodimga qarzdor.")

    # Char, Integer emas: Integer maydon interfeysda mingliklar ajratgichi
    # bilan «2 026» bo'lib chiqadi — yil uchun bu noto'g'ri ko'rinish.
    agronova_oylik_yili = fields.Char(
        "Yil", default=lambda s: str(fields.Date.context_today(s).year),
        help="Oyma-oy jadval qaysi yil bo'yicha ko'rsatilsin.")
    agronova_oylik_html = fields.Html(
        "Oyma-oy balans", compute='_compute_agronova_oylik_html', sanitize=False)

    # Joriy oy kesimi — xodimlar ro'yxatida «shu oy nima bo'ldi» ko'rinsin
    # (umumiy qoldiq bir yillik tarixni yig'ib beradi, o'zi yetarli emas).
    agronova_oy_hisoblandi = fields.Monetary(
        "Shu oy hisoblandi", compute='_compute_agronova_balans',
        currency_field='agronova_currency_id')
    agronova_oy_berildi = fields.Monetary(
        "Shu oy berildi", compute='_compute_agronova_balans',
        currency_field='agronova_currency_id')
    agronova_oy_balans = fields.Monetary(
        "Shu oy balansi", compute='_compute_agronova_balans',
        currency_field='agronova_currency_id')

    def _compute_agronova_tarif(self):
        Tarif = self.env['agronova.ish_haqi.tarif']
        for emp in self:
            tarif = Tarif.amaldagi(emp)
            emp.agronova_tarif_id = tarif
            emp.agronova_tarif_turi = tarif.tur or False
            emp.agronova_stavka = tarif.stavka or 0.0

    def _compute_agronova_balans(self):
        Harakat = self.env['agronova.ish_haqi.harakat'].sudo()
        for emp in self:
            qatorlar = Harakat.search([('employee_id', '=', emp.id)])
            emp.agronova_hisoblandi = sum(
                qatorlar.filtered(lambda h: h.tur in ('hisoblandi', 'bonus'))
                .mapped('summa'))
            emp.agronova_berildi = sum(
                qatorlar.filtered(lambda h: h.tur == 'berildi').mapped('summa'))
            emp.agronova_balans = sum(qatorlar.mapped('balans_summa'))

            bugun = fields.Date.context_today(emp)
            oy_boshi = bugun.replace(day=1)
            oyniki = qatorlar.filtered(lambda h: h.sana >= oy_boshi)
            emp.agronova_oy_hisoblandi = sum(
                oyniki.filtered(lambda h: h.tur in ('hisoblandi', 'bonus'))
                .mapped('summa'))
            emp.agronova_oy_berildi = sum(
                oyniki.filtered(lambda h: h.tur == 'berildi').mapped('summa'))
            emp.agronova_oy_balans = sum(oyniki.mapped('balans_summa'))

    def action_agronova_harakat(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _("«%s» bilan hisob-kitob", self.name),
            'res_model': 'agronova.ish_haqi.harakat',
            'view_mode': 'list,form',
            'domain': [('employee_id', '=', self.id)],
            'context': {'default_employee_id': self.id},
        }

    # ------------------------------------------------------------------
    # Oyma-oy balans jadvali
    #
    # Bitta umumiy qoldiq raqami «qachondan beri qarz?» degan savolga
    # javob bermaydi. Shuning uchun xodim kartochkasida har oy alohida
    # qator bo'lib chiqadi: nima hisoblandi, nima ushlandi, qancha
    # berildi va oy oxiriga qancha qoldi.
    # ------------------------------------------------------------------
    OYLAR = ("Yanvar", "Fevral", "Mart", "Aprel", "May", "Iyun", "Iyul",
             "Avgust", "Sentabr", "Oktabr", "Noyabr", "Dekabr")

    def _compute_agronova_oylik_html(self):
        Harakat = self.env['agronova.ish_haqi.harakat'].sudo()
        for emp in self:
            try:
                yil = int(emp.agronova_oylik_yili)
            except (TypeError, ValueError):
                yil = fields.Date.context_today(emp).year
            valyuta = emp.agronova_currency_id
            boshi = fields.Date.to_date('%s-01-01' % yil)
            oxiri = boshi + relativedelta(years=1, days=-1)
            # Yil boshigacha to'plangan qoldiq — jadval shundan boshlanadi.
            oldingi = sum(Harakat.search([
                ('employee_id', '=', emp.id),
                ('sana', '<', boshi)]).mapped('balans_summa'))
            qatorlar = Harakat.search([
                ('employee_id', '=', emp.id),
                ('sana', '>=', boshi), ('sana', '<=', oxiri)])

            def fmt(x):
                return valyuta.format(x) if valyuta else '%.0f' % x

            jami = oldingi
            html = ["<table class='table table-sm o_list_table'><thead><tr>"
                    "<th>Oy</th><th class='text-end'>Hisoblandi</th>"
                    "<th class='text-end'>Bonus</th>"
                    "<th class='text-end'>Avans</th>"
                    "<th class='text-end'>Jarima</th>"
                    "<th class='text-end'>Berildi</th>"
                    "<th class='text-end'>Oy balansi</th>"
                    "<th class='text-end'>Qoldiq</th></tr></thead><tbody>"]
            if oldingi:
                html.append(
                    "<tr class='text-muted'><td colspan='7'>%s yilgacha "
                    "qoldiq</td><td class='text-end'>%s</td></tr>"
                    % (yil, fmt(oldingi)))
            for oy in range(1, 13):
                oyniki = qatorlar.filtered(lambda h, o=oy: h.sana.month == o)

                def yig(turlar, rec=oyniki):
                    return sum(rec.filtered(
                        lambda h: h.tur in turlar).mapped('summa'))

                oy_balans = sum(oyniki.mapped('balans_summa'))
                jami += oy_balans
                if not oyniki:
                    # Bo'sh oy — qatori turadi, lekin ko'zni charchatmasin.
                    html.append(
                        "<tr class='text-muted'><td>%s</td>"
                        "<td colspan='6' class='text-end'>—</td>"
                        "<td class='text-end'>%s</td></tr>"
                        % (self.OYLAR[oy - 1], fmt(jami)))
                    continue
                html.append(
                    "<tr><td>%s</td><td class='text-end'>%s</td>"
                    "<td class='text-end'>%s</td><td class='text-end'>%s</td>"
                    "<td class='text-end'>%s</td><td class='text-end'>%s</td>"
                    "<td class='text-end'>%s</td>"
                    "<td class='text-end fw-bold'>%s</td></tr>"
                    % (self.OYLAR[oy - 1], fmt(yig(('hisoblandi',))),
                       fmt(yig(('bonus',))), fmt(yig(('avans',))),
                       fmt(yig(('jarima',))), fmt(yig(('berildi',))),
                       fmt(oy_balans), fmt(jami)))
            html.append("</tbody></table>")
            emp.agronova_oylik_html = "".join(html)

    def _agronova_yil_surish(self, qadam):
        self.ensure_one()
        try:
            yil = int(self.agronova_oylik_yili)
        except (TypeError, ValueError):
            yil = fields.Date.context_today(self).year
        self.agronova_oylik_yili = str(yil + qadam)
        return True

    def action_agronova_yil_oldingi(self):
        return self._agronova_yil_surish(-1)

    def action_agronova_yil_keyingi(self):
        return self._agronova_yil_surish(1)

    def action_agronova_oylik_ber(self):
        """Kassadan oylik berish orderini ochadi.

        Balans yozuvi alohida kiritilmaydi — kassa orderi tasdiqlansa,
        `agronova_kassa_harakat.py` ko'prigi xodim balansidan o'zi chiqaradi.
        """
        self.ensure_one()
        modda = self.env['agronova.kassa.modda'].search(
            [('direction', '=', 'out'),
             ('account_id.code', '=like', '6710%')], limit=1)
        return {
            'type': 'ir.actions.act_window',
            'name': _("«%s» ga oylik berish", self.name),
            'res_model': 'agronova.kassa.harakat',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_direction': 'out',
                'default_employee_id': self.id,
                'default_modda_id': modda.id or False,
                'default_partner_id': self.work_contact_id.id or False,
            },
        }
