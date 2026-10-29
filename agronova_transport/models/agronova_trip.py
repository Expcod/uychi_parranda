# -*- coding: utf-8 -*-
from odoo import _, api, fields, models
from odoo.exceptions import UserError


class SssTrip(models.Model):
    """Transport reysi.

    Odooda «reys» tushunchasi yo'q, shuning uchun alohida model. Har bir reysga
    avtomat analitik hisob (TZ da «lot / partiya») ochiladi — barcha xarajat va
    daromad shu yerga yig'iladi, foyda va haydovchi ulushi shundan hisoblanadi.
    """
    _name = 'agronova.trip'
    _description = 'Transport reysi'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date desc, id desc'

    name = fields.Char(
        "Reys raqami", default=lambda self: _("Yangi"),
        copy=False, readonly=True, index=True)
    date = fields.Date(
        "Sana", default=fields.Date.context_today, required=True, tracking=True)
    trip_type = fields.Selection(
        [('internal', "Ichki reys"), ('external', "Tashqi reys")],
        string="Reys turi", default='internal', required=True, tracking=True,
        help="Ichki reys — korxona bo'limlari orasidagi tashish, daromadi "
             "tasdiqlangan ichki tarif bo'yicha hisoblanadi.\n"
             "Tashqi reys — mijozga ko'rsatilgan xizmat.")
    company_id = fields.Many2one(
        'res.company', string="Korxona", required=True,
        default=lambda self: self.env.company)
    currency_id = fields.Many2one(
        'res.currency', related='company_id.currency_id', readonly=True)

    # --- Ijrochilar
    vehicle_id = fields.Many2one(
        'fleet.vehicle', string="Avtomobil", required=True, tracking=True)
    driver_id = fields.Many2one(
        'hr.employee', string="Haydovchi", tracking=True)
    partner_id = fields.Many2one(
        'res.partner', string="Mijoz",
        help="Tashqi reysda xizmat ko'rsatilgan mijoz.")

    # --- Yuk va yo'nalish
    origin = fields.Char("Qayerdan")
    destination = fields.Char("Qayerga")
    distance_km = fields.Float("Masofa (km)")
    cargo_type = fields.Char("Yuk turi")
    cargo_qty = fields.Float("Yuk miqdori (tonna)")

    # --- Ombor tranzaksiyasi (ichki reyslarda majburiy)
    picking_ids = fields.One2many(
        'stock.picking', 'trip_id', string="Ombor hujjatlari",
        help="Shu reysda tashilgan tovar harakati. Ichki reysda qaysi "
             "mahsulot, qayerdan qayerga va qancha ketgani shu yerdan ko'rinadi.")
    move_ids = fields.Many2many(
        'stock.move', string="Tashilgan mahsulotlar",
        compute='_compute_move_ids',
        help="Bog'langan ombor hujjatlaridagi barcha tovar harakati.")
    # Diqqat: saqlanadigan va saqlanmaydigan maydonlar alohida compute
    # metodlarida bo'lishi kerak, aks holda Odoo ogohlantiradi va
    # saqlanmaydigan maydonga murojaat saqlanadiganlarini qayta hisoblatadi.
    picking_count = fields.Integer(
        "Hujjatlar soni", compute='_compute_picking_count')
    cargo_weight_kg = fields.Float(
        "Yuk og'irligi (kg)", compute='_compute_cargo_weight', store=True,
        help="Bog'langan ombor hujjatlaridagi og'irlik birligidagi "
             "mahsulotlar yig'indisi.")
    cargo_weight_ton = fields.Float(
        "Yuk og'irligi (tonna)", compute='_compute_cargo_weight', store=True)

    # --- Lot (analitik hisob)
    analytic_account_id = fields.Many2one(
        'account.analytic.account', string="Lot / analitik hisob",
        readonly=True, copy=False, ondelete='restrict',
        help="Reys yaratilganda avtomat ochiladi. Barcha xarajat va daromad "
             "shu hisobga yig'iladi.")

    # --- Pul
    revenue = fields.Monetary(
        "Reys daromadi", tracking=True,
        help="Ichki reysda — tasdiqlangan ichki tarif, tashqi reysda — "
             "mijoz bilan kelishilgan summa.")
    expense_manual = fields.Monetary(
        "Qo'shimcha xarajat",
        help="Hujjat bilan rasmiylashtirilmagan, qo'lda kiritiladigan xarajat.")
    expense_ids = fields.One2many(
        'hr.expense', 'trip_id', string="Haydovchi xarajatlari")
    service_ids = fields.One2many(
        'fleet.vehicle.log.services', 'trip_id', string="Texnik xizmat va ta'mir")
    expense_total = fields.Monetary(
        "Jami xarajat", compute='_compute_amounts', store=True)
    profit = fields.Monetary(
        "Foyda / zarar", compute='_compute_amounts', store=True, tracking=True)

    # --- Haydovchi hisob-kitobi
    driver_share_pct = fields.Float(
        "Haydovchi ulushi (%)", default=30.0,
        help="TZ bo'yicha 30%. Ulush SOF FOYDADAN hisoblanadi, tushumdan emas.")
    driver_share = fields.Monetary(
        "Haydovchi ulushi", compute='_compute_amounts', store=True)
    collected = fields.Monetary(
        "Haydovchi olgan pul",
        help="Tashqi reysda haydovchi mijozdan naqd olgan summa.")
    handed_over = fields.Monetary("Korxonaga topshirgan")
    balance_due = fields.Monetary(
        "Topshirilishi kerak", compute='_compute_amounts', store=True,
        help="Olgan pul − topshirgan − xarajat − haydovchi ulushi.")

    # TZ 12-bo'limida 7 bosqich sanalgan; «Xarajatlar kiritilmoqda» va
    # «Hisob-kitob qilinmoqda» buyurtmachi bilan kelishilgan holda bitta
    # «Hisob-kitob» bosqichiga birlashtirildi (2026-08-11).
    departed_datetime = fields.Datetime(
        "Yo'lga chiqqan vaqt", readonly=True, copy=False)
    arrival_datetime = fields.Datetime(
        "Yetib kelgan vaqt", readonly=True, copy=False,
        help="Haydovchi Telegram botda «Yetib keldim» tugmasini bosgan vaqt "
             "yoki hujjatda qo'lda belgilangan vaqt.")
    trip_duration = fields.Float(
        "Yo'lda (soat)", compute='_compute_trip_duration', store=True)

    state = fields.Selection(
        [
            ('new', "Yangi"),
            ('planned', "Rejalashtirilgan"),
            ('departed', "Yo'lga chiqdi"),
            ('delivered', "Yetkazib berildi"),
            ('settling', "Hisob-kitob"),
            ('done', "Yakunlandi"),
        ],
        string="Holati", default='new', required=True, tracking=True, copy=False)
    note = fields.Text("Izoh")

    _driver_share_pct_range = models.Constraint(
        'CHECK (driver_share_pct >= 0 AND driver_share_pct <= 100)',
        "Haydovchi ulushi 0 dan 100 gacha bo'lishi kerak.",
    )

    # ------------------------------------------------------------- compute
    @api.depends('revenue', 'expense_manual', 'driver_share_pct',
                 'collected', 'handed_over',
                 'expense_ids.total_amount', 'expense_ids.state',
                 'service_ids.amount')
    def _compute_amounts(self):
        for trip in self:
            expenses = trip.expense_ids.filtered(lambda e: e.state != 'refused')
            total = (trip.expense_manual
                     + sum(expenses.mapped('total_amount'))
                     + sum(trip.service_ids.mapped('amount')))
            trip.expense_total = total
            trip.profit = trip.revenue - total
            # Zarar bo'lsa haydovchiga ulush hisoblanmaydi
            trip.driver_share = (trip.profit * trip.driver_share_pct / 100.0
                                 if trip.profit > 0 else 0.0)
            trip.balance_due = (trip.collected - trip.handed_over
                                - total - trip.driver_share)

    @api.depends('departed_datetime', 'arrival_datetime')
    def _compute_trip_duration(self):
        for trip in self:
            if trip.departed_datetime and trip.arrival_datetime:
                delta = trip.arrival_datetime - trip.departed_datetime
                trip.trip_duration = delta.total_seconds() / 3600.0
            else:
                trip.trip_duration = 0.0

    @api.depends('picking_ids.move_ids')
    def _compute_move_ids(self):
        for trip in self:
            trip.move_ids = trip.picking_ids.move_ids

    @api.depends('picking_ids')
    def _compute_picking_count(self):
        for trip in self:
            trip.picking_count = len(trip.picking_ids)

    @api.depends('picking_ids', 'picking_ids.move_ids.quantity',
                 'picking_ids.move_ids.product_uom')
    def _compute_cargo_weight(self):
        kg = self.env.ref('uom.product_uom_kgm', raise_if_not_found=False)
        for trip in self:
            weight = 0.0
            for move in trip.picking_ids.move_ids:
                uom = move.product_uom
                if kg and uom and uom._has_common_reference(kg):
                    # kg, gramm, tonna, qop — hammasi kg ga keltiriladi
                    weight += uom._compute_quantity(move.quantity, kg)
                else:
                    # dona, bosh, litr — mahsulot kartochkasidagi og'irlik bo'yicha
                    weight += move.quantity * (move.product_id.weight or 0.0)
            trip.cargo_weight_kg = weight
            trip.cargo_weight_ton = weight / 1000.0

    @api.onchange('vehicle_id')
    def _onchange_vehicle_id(self):
        """Mashinaga biriktirilgan haydovchini o'zi qo'yadi."""
        for trip in self:
            employee = trip.vehicle_id.agronova_driver_employee_id
            if employee and not trip.driver_id:
                trip.driver_id = employee

    @api.onchange('picking_ids')
    def _onchange_picking_ids(self):
        """Birinchi hujjatdan yo'nalishni va yuk turini to'ldiradi."""
        for trip in self:
            picking = trip.picking_ids[:1]
            if not picking:
                continue
            if not trip.origin:
                trip.origin = picking.location_id.display_name
            if not trip.destination:
                trip.destination = picking.location_dest_id.display_name
            if not trip.cargo_type:
                products = picking.move_ids.product_id
                trip.cargo_type = ", ".join(products[:3].mapped('name'))

    def action_attach_picking(self):
        """Mavjud ombor hujjatini reysga biriktirish oynasi."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _("«%s» reysiga hujjat biriktirish", self.name),
            'res_model': 'agronova.trip.attach.picking',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_trip_id': self.id},
        }

    def action_detach_picking(self):
        """Formadagi qatordan hujjatni ajratish (context orqali keladi)."""
        self.ensure_one()
        picking_id = self.env.context.get('picking_id')
        if picking_id:
            self.env['stock.picking'].browse(picking_id).trip_id = False
        return True

    def action_open_pickings(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _("«%s» reysi hujjatlari", self.name),
            'res_model': 'stock.picking',
            'view_mode': 'list,form',
            'domain': [('trip_id', '=', self.id)],
            'context': {'default_trip_id': self.id},
        }

    # ------------------------------------------------------------- create
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('name') or vals['name'] == _("Yangi"):
                vals['name'] = self.env['ir.sequence'].next_by_code('agronova.trip') or _("Yangi")
        trips = super().create(vals_list)
        trips._ensure_analytic_account()
        return trips

    def _ensure_analytic_account(self):
        """Har reysga o'z analitik hisobini (lot) ochadi."""
        plan = self.env.ref('agronova_transport.analytic_plan_trip', raise_if_not_found=False)
        if not plan:
            return
        for trip in self.filtered(lambda t: not t.analytic_account_id):
            trip.analytic_account_id = self.env['account.analytic.account'].create({
                'name': trip.name,
                'plan_id': plan.id,
                'company_id': trip.company_id.id,
            })

    # ------------------------------------------------------------- holatlar
    def action_plan(self):
        self.write({'state': 'planned'})

    def action_depart(self):
        for trip in self:
            if not trip.driver_id:
                raise UserError(_("Yo'lga chiqishdan oldin haydovchi tanlanishi kerak."))
        self.write({'state': 'departed',
                    'departed_datetime': fields.Datetime.now()})

    def action_deliver(self):
        """Yuk yetkazib berildi — vaqti qayd etiladi.

        Haydovchi botdan bosganda ham shu metod chaqiriladi, shuning uchun
        vaqt bir joyda yoziladi.
        """
        for trip in self:
            vals = {'state': 'delivered'}
            if not trip.arrival_datetime:
                vals['arrival_datetime'] = fields.Datetime.now()
            trip.write(vals)

    def action_settle(self):
        self.write({'state': 'settling'})

    def action_done(self):
        for trip in self:
            if trip.trip_type == 'internal' and not trip.picking_ids:
                raise UserError(_(
                    "«%s» ichki reysini yakunlab bo'lmaydi: ombor hujjati "
                    "biriktirilmagan. Ichki reysda qaysi mahsulot qayerdan "
                    "qayerga va qancha ketgani ko'rinishi kerak.", trip.name))
            if not trip.revenue:
                raise UserError(_(
                    "«%s» reysini yakunlab bo'lmaydi: daromad kiritilmagan. "
                    "Ichki reysda ham tasdiqlangan tarif bo'yicha summa "
                    "ko'rsatilishi kerak — busiz foyda va haydovchi ulushi "
                    "hisoblanmaydi.", trip.name))
        self.write({'state': 'done'})

    def action_reset(self):
        self.write({'state': 'new'})

    def action_open_expenses(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _("«%s» reysi xarajatlari", self.name),
            'res_model': 'hr.expense',
            'view_mode': 'list,form',
            'domain': [('trip_id', '=', self.id)],
            'context': {'default_trip_id': self.id,
                        'default_employee_id': self.driver_id.id},
        }
