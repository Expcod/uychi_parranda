# -*- coding: utf-8 -*-
"""Jo'ja o'stirish partiyasi (B02).

Jo'ja kelganidan tuxumga kirguncha bo'lgan davr. Partiya yopilganda
**1 bosh tannarxi qotadi** va shu qiymat tuxum partiyasiga meros bo'lib
o'tadi — bozor narxida ichki sotuv YO'Q (2-bo'lim qarori), ya'ni bu ikki
bosqich orasida alohida foyda-zarar yaratilmaydi.
"""
from odoo import _, api, fields, models
from odoo.exceptions import UserError


class AgroNovaOnaTovuqPartiyaOstirish(models.Model):
    _name = 'agronova.ona_tovuq.partiya.ostirish'
    _description = "Ona tovuq — jo'ja o'stirish partiyasi"
    _inherit = ['agronova.ona_tovuq.partiya.mixin']
    _agronova_tannarx_fields = ('tannarx_1_bosh',)

    kirim_sana = fields.Date(
        "Jo'ja kirim sanasi", required=True, tracking=True,
        default=fields.Date.context_today)
    yopilish_sana = fields.Date("Yopilgan sana", readonly=True, copy=False)
    yosh_kun = fields.Integer("Yoshi (kun)", compute='_compute_yosh')
    yosh_hafta = fields.Integer("Yoshi (hafta)", compute='_compute_yosh')

    holat = fields.Selection(
        [('draft', "Qoralama"),
         ('active', "Faol"),
         ('closed', "Yopilgan")],
        string="Holati", default='draft', required=True, tracking=True, copy=False)

    jurnal_ids = fields.One2many(
        'agronova.ona_tovuq.jurnal.ostirish', 'partiya_id', string="Kunlik jurnal")
    jurnal_count = fields.Integer("Jurnal kunlari", compute='_compute_jurnal_count')

    # TZ: tannarx maydoni HAR DOIM readonly — hech bir rol qo'lda kiritmaydi.
    tannarx_1_bosh = fields.Monetary(
        "1 bosh tannarxi", readonly=True, copy=False, tracking=True,
        help="Partiya yopilganda hisoblanadi va qotadi: jami xarajat / "
             "yakuniy bosh soni. Qo'lda kiritilmaydi.")
    tuxum_partiya_id = fields.Many2one(
        'agronova.ona_tovuq.partiya.tuxum', string="Ona tovuq partiyasi",
        readonly=True, copy=False,
        help="Partiya yopilganda avtomat ochiladi.")

    _boshlangich_musbat = models.Constraint(
        'CHECK (boshlangich_son >= 0)',
        "Boshlang'ich bosh soni manfiy bo'lmasin.")

    # ------------------------------------------------------------- compute
    @api.depends('boshlangich_son', 'chiqim_son',
                 'jurnal_ids.nobud_son', 'jurnal_ids.brak_son')
    def _compute_son(self):
        return super()._compute_son()

    @api.depends('kirim_sana', 'yopilish_sana')
    def _compute_yosh(self):
        bugun = fields.Date.context_today(self)
        for p in self:
            oxir = p.yopilish_sana or bugun
            kun = (oxir - p.kirim_sana).days if p.kirim_sana else 0
            p.yosh_kun = max(kun, 0)
            p.yosh_hafta = p.yosh_kun // 7

    @api.depends('jurnal_ids')
    def _compute_jurnal_count(self):
        for p in self:
            p.jurnal_count = len(p.jurnal_ids)

    # ------------------------------------------------------------- yaratish
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('name') or vals['name'] == _("Yangi"):
                vals['name'] = self.env['ir.sequence'].next_by_code(
                    'agronova.ona_tovuq.partiya.ostirish') or _("Yangi")
        return super().create(vals_list)

    # -------------------------------------------------------------- holatlar
    def action_faollashtirish(self):
        for p in self:
            if p.holat != 'draft':
                raise UserError(_("Faqat qoralama partiya faollashtiriladi."))
            if not p.boshlangich_son:
                raise UserError(_(
                    "«%s» partiyasida boshlang'ich bosh soni kiritilmagan.", p.name))
            band = self.search([
                ('sex_id', '=', p.sex_id.id),
                ('holat', '=', 'active'),
                ('id', '!=', p.id),
            ], limit=1)
            if band:
                raise UserError(_(
                    "«%(sex)s» sexida «%(band)s» o'stirish partiyasi hali faol. "
                    "Bir sexda bir vaqtda bitta aktiv o'stirish partiyasi bo'ladi.",
                    sex=p.sex_id.name, band=band.name))
            p.holat = 'active'
        return True

    def action_close(self):
        """Partiyani yopadi, tannarxni qotiradi va tuxum partiyasini ochadi.

        Tartib muhim: avval tannarx hisoblanadi (partiya hali ochiq, barcha
        xarajat kirgan), keyin holat `closed` ga o'tadi, keyin yangi tuxum
        partiyasi yaratiladi va unga meros qiymat yoziladi.
        """
        for p in self:
            if p.holat != 'active':
                raise UserError(_("Faqat faol partiya yopiladi."))
            if p.joriy_son <= 0:
                raise UserError(_(
                    "«%s» partiyasida bosh soni nolga teng — yopib bo'lmaydi. "
                    "Kunlik jurnal yozuvlarini tekshiring.", p.name))

            xarajat = p.jami_xarajat
            p._tannarx_yozish().tannarx_1_bosh = (
                xarajat / p.joriy_son if p.joriy_son else 0.0)
            p.yopilish_sana = fields.Date.context_today(p)
            joriy_son = p.joriy_son
            p.holat = 'closed'

            tuxum = self.env['agronova.ona_tovuq.partiya.tuxum']._tannarx_yozish().create({
                'ostirish_partiya_id': p.id,
                'sex_id': p.sex_id.id,
                'zot_id': p.zot_id.id,
                'company_id': p.company_id.id,
                'yem_product_id': p.yem_product_id.id,
                'ochilish_sana': p.yopilish_sana,
                'boshlangich_son': joriy_son,
                'boshlangich_tannarx': p.tannarx_1_bosh,
                'holat': 'active',
            })
            p.tuxum_partiya_id = tuxum

            # Meros qiymatni tuxum partiyasining analitik hisobiga xarajat
            # sifatida yozamiz — tuxum tannarxi shundan boshlanadi.
            meros = p.tannarx_1_bosh * joriy_son
            if meros:
                tuxum._agronova_post_analytic(
                    name=_("O'stirishdan meros tannarx (%s)", p.name),
                    amount=-abs(meros),
                    date=p.yopilish_sana,
                    unit_amount=joriy_son,
                )
            p.message_post(body=_(
                "Partiya yopildi. 1 bosh tannarxi: %(tannarx)s. "
                "«%(tuxum)s» tuxum partiyasi ochildi.",
                tannarx=p.tannarx_1_bosh, tuxum=tuxum.name))
        return True

    def action_open_tuxum_partiya(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'agronova.ona_tovuq.partiya.tuxum',
            'res_id': self.tuxum_partiya_id.id,
            'view_mode': 'form',
        }

    def write(self, vals):
        # Yopilgan partiyani tahrirlash taqiqlanadi (tannarx qotgan).
        qulf_tashqari = {'tuxum_partiya_id', 'message_follower_ids',
                         'message_ids', 'activity_ids'}
        if set(vals) - qulf_tashqari:
            for p in self:
                if p.holat == 'closed':
                    raise UserError(_(
                        "«%s» partiyasi yopilgan — tannarx qotgan, tahrirlash "
                        "taqiqlanadi.", p.name))
        return super().write(vals)

    def unlink(self):
        if any(p.holat != 'draft' for p in self):
            raise UserError(_("Faqat qoralama partiya o'chiriladi."))
        return super().unlink()
