# -*- coding: utf-8 -*-
"""Tortish varaqasi — ikki marta tortish tamoyili (TZ 4.1 va 4.3).

Kirim: mashina yuk bilan keladi (1-tortish = brutto), bo'shatib qaytadi
(2-tortish = tara). Chiqim: bo'sh keladi (tara), yuklab ketadi (brutto).
Shuning uchun brutto doim kattasi, tara kichigi — yo'nalishdan qat'i
nazar `Netto = Brutto − Tara`.

Tafovut: hujjatdagi netto (nakladnoy yoki ombor hujjati) bilan haqiqiy
netto farqi. Farq **yo'qotish deb yozilmaydi**: varaqa sabab va mas'ul
tasdig'i bilan yopiladi, qaror keyin alohida hujjat bilan hisobga olinadi.
"""
from odoo import _, api, fields, models
from odoo.exceptions import UserError

TAFOVUT = [
    ('yoq', "Hujjat yo'q"),
    ('normal', "Me'yorda"),
    ('ogohlantirish', "Ogohlantirish"),
    ('tasdiq', "Tasdiq kerak"),
    ('kritik', "Kritik"),
]
DARAJA = {k: i for i, (k, _n) in enumerate(TAFOVUT)}

# Sozlamalar bo'sh bo'lsa ishlatiladigan chegaralar: (kg, %)
DEFAULT_CHEGARA = {
    'normal': (40.0, 0.2),
    'ogohlantirish': (100.0, 0.5),
    'tasdiq': (300.0, 1.0),
}


class AgroNovaTaroziTortish(models.Model):
    _name = 'agronova.tarozi.tortish'
    _description = "Tortish varaqasi"
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'sana desc, id desc'

    name = fields.Char("Raqam", required=True, copy=False, readonly=True,
                       default=lambda s: _("Yangi"))
    company_id = fields.Many2one('res.company', "Korxona", required=True,
                                 default=lambda s: s.env.company)
    sana = fields.Datetime("Sana", required=True, default=fields.Datetime.now,
                           tracking=True)
    yonalish = fields.Selection([
        ('kirim', "Kirim (xomashyo)"),
        ('chiqim', "Chiqim (jo'natma)"),
        ('ichki', "Ichki ko'chirish"),
    ], "Yo'nalish", required=True, default='kirim', tracking=True)
    tarozi_id = fields.Many2one('agronova.tarozi', "Tarozi", required=True,
                                domain="[('company_id', '=', company_id)]",
                                default=lambda s: s._default_tarozi(), tracking=True)
    state = fields.Selection([
        ('draft', "Yangi"),
        ('vazn1', "1-tortish qilindi"),
        ('done', "Yakunlandi"),
        ('cancel', "Bekor qilindi"),
    ], "Holat", default='draft', required=True, tracking=True, copy=False)

    # --- transport
    avto_raqam = fields.Char("Avtomobil raqami", tracking=True)
    haydovchi = fields.Char("Haydovchi")
    partner_id = fields.Many2one('res.partner', "Kontragent", tracking=True,
                                 help="Yetkazib beruvchi yoki qabul qiluvchi.")
    product_id = fields.Many2one('product.product', "Tovar / xomashyo", tracking=True)
    picking_id = fields.Many2one('stock.picking', "Ombor hujjati", copy=False,
                                 tracking=True, index='btree_not_null')
    purchase_id = fields.Many2one('purchase.order', "Xarid buyurtmasi",
                                  compute='_compute_buyurtma', store=True)
    sale_id = fields.Many2one('sale.order', "Sotuv buyurtmasi",
                              compute='_compute_buyurtma', store=True)
    operator_id = fields.Many2one('res.users', "Operator", default=lambda s: s.env.user,
                                  readonly=True)

    # --- vaznlar
    vazn1 = fields.Float("1-tortish (kg)", digits=(16, 1), tracking=True, copy=False)
    vazn1_vaqt = fields.Datetime("1-tortish vaqti", readonly=True, copy=False)
    vazn1_manba = fields.Selection([('tarozi', "Tarozidan"), ('qolda', "Qo'lda")],
                                   "1-tortish manbasi", readonly=True, copy=False)
    vazn2 = fields.Float("2-tortish (kg)", digits=(16, 1), tracking=True, copy=False)
    vazn2_vaqt = fields.Datetime("2-tortish vaqti", readonly=True, copy=False)
    vazn2_manba = fields.Selection([('tarozi', "Tarozidan"), ('qolda', "Qo'lda")],
                                   "2-tortish manbasi", readonly=True, copy=False)
    brutto = fields.Float("Brutto (kg)", compute='_compute_netto', store=True, digits=(16, 1))
    tara = fields.Float("Tara (kg)", compute='_compute_netto', store=True, digits=(16, 1))
    netto = fields.Float("Netto (kg)", compute='_compute_netto', store=True, digits=(16, 1))
    netto_t = fields.Float("Netto (t)", compute='_compute_netto', store=True, digits=(16, 3))

    # --- tafovut
    hujjat_netto = fields.Float("Hujjat bo'yicha netto (kg)", digits=(16, 1), tracking=True,
                                help="Nakladnoy yoki ombor hujjatidagi miqdor.")
    farq_kg = fields.Float("Farq (kg)", compute='_compute_farq', store=True, digits=(16, 1))
    farq_pct = fields.Float("Farq (%)", compute='_compute_farq', store=True, digits=(16, 2))
    tafovut = fields.Selection(TAFOVUT, "Tafovut", compute='_compute_farq', store=True,
                               tracking=True)
    tafovut_sabab = fields.Text("Tafovut sababi", tracking=True)
    tasdiqlagan_id = fields.Many2one('res.users', "Tafovutni tasdiqlagan", readonly=True,
                                     copy=False, tracking=True)
    tasdiq_vaqt = fields.Datetime("Tasdiq vaqti", readonly=True, copy=False)
    izoh = fields.Text("Izoh")

    _netto_musbat = models.Constraint('CHECK(vazn1 >= 0 AND vazn2 >= 0)',
                                      "Vazn manfiy bo'lishi mumkin emas.")

    # ------------------------------------------------------------- defaults
    @api.model
    def _default_tarozi(self):
        return self.env['agronova.tarozi'].search(
            [('turi', '=', 'avto'), ('company_id', '=', self.env.company.id)], limit=1)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', _("Yangi")) == _("Yangi"):
                vals['name'] = self.env['ir.sequence'].next_by_code(
                    'agronova.tarozi.tortish') or _("Yangi")
        return super().create(vals_list)

    # -------------------------------------------------------------- compute
    @api.depends('picking_id')
    def _compute_buyurtma(self):
        for t in self:
            p = t.picking_id
            t.purchase_id = p.purchase_id if p and 'purchase_id' in p._fields else False
            t.sale_id = p.sale_id if p and 'sale_id' in p._fields else False

    @api.depends('vazn1', 'vazn2')
    def _compute_netto(self):
        for t in self:
            if t.vazn1 and t.vazn2:
                t.brutto = max(t.vazn1, t.vazn2)
                t.tara = min(t.vazn1, t.vazn2)
            else:
                t.brutto = t.vazn1 or 0.0
                t.tara = 0.0
            t.netto = (t.brutto - t.tara) if (t.vazn1 and t.vazn2) else 0.0
            t.netto_t = t.netto / 1000.0

    @api.model
    def _chegaralar(self):
        icp = self.env['ir.config_parameter'].sudo()
        natija = {}
        for daraja, (kg, pct) in DEFAULT_CHEGARA.items():
            natija[daraja] = (
                float(icp.get_param('agronova_tarozi.%s_kg' % daraja, kg) or kg),
                float(icp.get_param('agronova_tarozi.%s_pct' % daraja, pct) or pct),
            )
        return natija

    @api.model
    def tafovut_darajasi(self, farq_kg, asos_kg):
        """Farqni darajaga ajratadi.

        Farq kg chegarasi YOKI % chegarasi ichida bo'lsa — shu daraja:
        kichik yukda kg hal qiladi (1 t da 30 kg = 3%, lekin tarozi aniqligi
        doirasida), katta yukda % (60 t da 100 kg = 0,17% — me'yorda).
        """
        if not asos_kg:
            return 'yoq'
        farq = abs(farq_kg)
        pct = farq / asos_kg * 100.0
        ch = self._chegaralar()
        for daraja in ('normal', 'ogohlantirish', 'tasdiq'):
            kg, p = ch[daraja]
            if farq <= kg or pct <= p:
                return daraja
        return 'kritik'

    @api.depends('netto', 'hujjat_netto', 'vazn2')
    def _compute_farq(self):
        for t in self:
            if t.hujjat_netto and t.netto:
                t.farq_kg = t.netto - t.hujjat_netto
                t.farq_pct = t.farq_kg / t.hujjat_netto * 100.0
                t.tafovut = self.tafovut_darajasi(t.farq_kg, t.hujjat_netto)
            else:
                t.farq_kg = 0.0
                t.farq_pct = 0.0
                t.tafovut = 'yoq'

    # ------------------------------------------------------ qo'lda o'zgartirish
    def write(self, vals):
        # Tarozidan olingan vaznni qo'lda o'zgartirish — faqat «tuzatish»
        # huquqi bilan va izi qoladi (TZ 4.1: favqulodda tuzatish auditi).
        qolda = {'vazn1', 'vazn2'} & set(vals)
        if qolda and not self.env.context.get('agronova_tarozi_manba'):
            for t in self:
                if t.state == 'done':
                    raise UserError(_("Yakunlangan varaqadagi vaznni o'zgartirib bo'lmaydi."))
                for f in qolda:
                    manba = t['%s_manba' % f]
                    if manba == 'tarozi' and not self.env.user.has_group(
                            'agronova_tarozi.group_tarozi_tuzatish'):
                        raise UserError(_(
                            "Vazn tarozidan olingan — uni qo'lda o'zgartirish uchun "
                            "«Tarozi — vaznni tuzatish» huquqi kerak."))
                    if t.tarozi_id.protokol != 'qolda' and not self.env.user.has_group(
                            'agronova_tarozi.group_tarozi_tuzatish'):
                        raise UserError(_(
                            "«%s» tarozisi integratsiyalangan — vazn «Tarozidan olish» "
                            "tugmasi bilan olinadi.", t.tarozi_id.name))
                    eski = t[f]
                    if eski != vals[f]:
                        t.message_post(body=_(
                            "%(f)s qo'lda o'zgartirildi: %(eski)s → %(yangi)s kg (%(kim)s)",
                            f=t._fields[f].string, eski=eski, yangi=vals[f],
                            kim=self.env.user.name))
            now = fields.Datetime.now()
            for f in qolda:
                vals.setdefault('%s_manba' % f, 'qolda')
                vals.setdefault('%s_vaqt' % f, now)
        res = super().write(vals)
        if qolda:
            for t in self.filtered(lambda r: r.state == 'draft' and r.vazn1):
                super(AgroNovaTaroziTortish, t).write({'state': 'vazn1'})
        return res

    # --------------------------------------------------------------- tugmalar
    def _tarozidan(self, maydon):
        for t in self:
            if t.state in ('done', 'cancel'):
                raise UserError(_("Varaqa yopilgan."))
            vazn = t.tarozi_id.joriy_vazn()
            t.with_context(agronova_tarozi_manba=True).write({
                maydon: vazn,
                '%s_manba' % maydon: 'tarozi',
                '%s_vaqt' % maydon: fields.Datetime.now(),
            })
            if maydon == 'vazn1' and t.state == 'draft':
                t.state = 'vazn1'
        return True

    def action_vazn1(self):
        return self._tarozidan('vazn1')

    def action_vazn2(self):
        if any(not t.vazn1 for t in self):
            raise UserError(_("Avval 1-tortishni bajaring."))
        return self._tarozidan('vazn2')

    def action_tafovut_tasdiq(self):
        if not self.env.user.has_group('agronova_tarozi.group_tarozi_masul'):
            raise UserError(_("Tafovutni faqat mas'ul shaxs tasdiqlaydi."))
        for t in self:
            if not (t.tafovut_sabab or '').strip():
                raise UserError(_("Tafovut sababini yozing — tasdiq sababsiz berilmaydi."))
            t.write({'tasdiqlagan_id': self.env.user.id,
                     'tasdiq_vaqt': fields.Datetime.now()})
            t.message_post(body=_("Tafovut tasdiqlandi: %(farq)s kg (%(pct)s%%). Sabab: %(s)s",
                                  farq=round(t.farq_kg, 1), pct=round(t.farq_pct, 2),
                                  s=t.tafovut_sabab))
        return True

    def action_yakunlash(self):
        for t in self:
            if t.state == 'done':
                continue
            if not (t.vazn1 and t.vazn2):
                raise UserError(_("Ikkala tortish ham bajarilishi kerak."))
            if t.netto <= 0:
                raise UserError(_("Netto nolga teng — tortishlarni tekshiring."))
            if t.tafovut in ('tasdiq', 'kritik') and not t.tasdiqlagan_id:
                raise UserError(_(
                    "Tafovut %(farq)s kg (%(pct)s%%) — «%(d)s». Varaqani yopish uchun "
                    "mas'ul shaxs sababni ko'rib, tasdiqlashi kerak.",
                    farq=round(t.farq_kg, 1), pct=round(t.farq_pct, 2),
                    d=dict(TAFOVUT)[t.tafovut]))
            t.state = 'done'
            t._hujjatga_yoz()
            if t.tafovut in ('ogohlantirish', 'tasdiq', 'kritik'):
                t._tafovut_xabari()
        return True

    def action_bekor(self):
        for t in self:
            if t.state == 'done' and not self.env.user.has_group(
                    'agronova_tarozi.group_tarozi_masul'):
                raise UserError(_("Yakunlangan varaqani faqat mas'ul bekor qiladi."))
            t.state = 'cancel'
        return True

    def action_qayta_ochish(self):
        if not self.env.user.has_group('agronova_tarozi.group_tarozi_masul'):
            raise UserError(_("Varaqani faqat mas'ul qayta ochadi."))
        self.write({'state': 'vazn1'})
        return True

    # ------------------------------------------------------ hujjat bilan bog'lanish
    def _hujjatga_yoz(self):
        """Kirim hujjatining miqdorini haqiqiy nettoga moslaydi.

        Faqat **kirimda**: korxona haqiqatda qancha qabul qilgan bo'lsa,
        omborga shuncha kiradi. Chiqimda hujjatdagi miqdor qoladi — farq
        alohida tasdiqlanadi va avtomatik yo'qotish deb yozilmaydi (TZ 4.3).
        Hujjatda shu tovarning bitta og'irlik birligidagi qatori bo'lishi
        kerak — aks holda qaysi qatorga qancha yozishni omborchi hal qiladi.
        """
        self.ensure_one()
        p = self.picking_id
        if self.yonalish != 'kirim' or not p or p.state in ('done', 'cancel'):
            return
        kg = self.env.ref('uom.product_uom_kgm')
        moves = p.move_ids.filtered(lambda m: m.state not in ('done', 'cancel'))
        if self.product_id:
            moves = moves.filtered(lambda m: m.product_id == self.product_id)
        if len(moves) != 1:
            return
        move = moves
        if not move.product_uom._has_common_reference(kg):
            return
        miqdor = kg._compute_quantity(self.netto, move.product_uom)
        move.quantity = miqdor
        move.picked = True
        p.message_post(body=_("Tarozi varaqasi %(n)s: haqiqiy netto %(kg)s kg yozildi.",
                              n=self.name, kg=round(self.netto, 1)))

    def _tafovut_xabari(self):
        """Tafovut haqida mas'ullarga vazifa (Telegram ogohlantirishi
        `agronova_yem_zavodi` va bot modulida shu vazifadan oladi)."""
        guruh = self.env.ref('agronova_tarozi.group_tarozi_masul', raise_if_not_found=False)
        users = guruh.user_ids if guruh else self.env['res.users']
        for u in users[:5]:
            self.activity_schedule(
                'mail.mail_activity_data_todo', user_id=u.id,
                summary=_("Tarozi tafovuti: %s kg", round(self.farq_kg, 1)),
                note=_("%(n)s — %(p)s, farq %(pct)s%%", n=self.name,
                       p=self.product_id.display_name or '', pct=round(self.farq_pct, 2)))

    def action_picking(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window', 'res_model': 'stock.picking',
            'res_id': self.picking_id.id, 'view_mode': 'form',
        }
