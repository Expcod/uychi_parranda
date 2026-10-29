# -*- coding: utf-8 -*-
from odoo import _, api, fields, models

# Xodim kartochkasida vaqt mintaqasi ko'rsatilmagan yoki UTC bo'lsa shu
# ishlatiladi — haydovchiga UTC vaqtni ko'rsatish chalkashtiradi.
DEFAULT_TZ = 'Asia/Tashkent'


class SssTrip(models.Model):
    _inherit = 'agronova.trip'

    def _tg_local_time(self, dt, employee):
        """Datetime ni haydovchi ko'radigan mahalliy vaqtga o'giradi."""
        tz = employee.tz
        if not tz or tz == 'UTC':
            tz = self.env.user.tz if self.env.user.tz not in (False, 'UTC') else DEFAULT_TZ
        moment = fields.Datetime.context_timestamp(self.with_context(tz=tz), dt)
        return moment.strftime('%d.%m.%Y %H:%M')

    @api.model
    def tg_open_trips(self, chat_id, limit=10):
        """Bot: haydovchining yakunlanmagan reyslari."""
        employee = self.env['hr.employee']._tg_find(chat_id)
        if not employee:
            return self.env['hr.employee']._tg_not_linked(chat_id)
        trips = self.sudo().search([
            ('driver_id', '=', employee.id),
            ('state', 'not in', ('done',)),
        ], limit=limit, order='date desc')
        return {'ok': True, 'trips': [{
            'id': trip.id,
            'name': trip.name,
            'date': trip.date and trip.date.strftime('%d.%m.%Y') or '',
            'route': "%s → %s" % (trip.origin or '?', trip.destination or '?'),
            'vehicle': trip.vehicle_id.license_plate or trip.vehicle_id.display_name,
            'state': dict(self._fields['state'].selection).get(trip.state, ''),
            'expense_total': trip.expense_total,
        } for trip in trips]}

    @api.model
    def tg_trip_summary(self, chat_id, trip_id):
        """Bot: bitta reysning hisob-kitobi."""
        employee = self.env['hr.employee']._tg_find(chat_id)
        if not employee:
            return self.env['hr.employee']._tg_not_linked(chat_id)
        trip = self.sudo().browse(int(trip_id))
        if not trip.exists() or trip.driver_id != employee:
            return {'ok': False, 'error': "Reys topilmadi."}
        return {
            'ok': True,
            'name': trip.name,
            'route': "%s → %s" % (trip.origin or '?', trip.destination or '?'),
            'revenue': trip.revenue,
            'expense_total': trip.expense_total,
            'profit': trip.profit,
            'driver_share_pct': trip.driver_share_pct,
            'driver_share': trip.driver_share,
            'collected': trip.collected,
            'handed_over': trip.handed_over,
            'balance_due': trip.balance_due,
            'cargo_weight_ton': trip.cargo_weight_ton,
        }

    @api.model
    def tg_arrivable_trips(self, chat_id, limit=10):
        """Bot: «Yetib keldim» bosish mumkin bo'lgan reyslar.

        Hali yetkazilmagan — ya'ni rejalashtirilgan yoki yo'lga chiqqanlari.
        """
        employee = self.env['hr.employee']._tg_find(chat_id)
        if not employee:
            return self.env['hr.employee']._tg_not_linked(chat_id)
        trips = self.sudo().search([
            ('driver_id', '=', employee.id),
            ('state', 'in', ('new', 'planned', 'departed')),
        ], limit=limit, order='date desc')
        return {'ok': True, 'trips': [{
            'id': trip.id,
            'name': trip.name,
            'route': "%s → %s" % (trip.origin or '?', trip.destination or '?'),
            'state': dict(self._fields['state'].selection).get(trip.state, ''),
        } for trip in trips]}

    @api.model
    def tg_mark_delivered(self, chat_id, trip_id):
        """Bot: haydovchi «Yetib keldim» dedi — holat va vaqt qayd etiladi."""
        employee = self.env['hr.employee']._tg_find(chat_id)
        if not employee:
            return self.env['hr.employee']._tg_not_linked(chat_id)
        trip = self.sudo().browse(int(trip_id))
        if not trip.exists() or trip.driver_id != employee:
            return {'ok': False, 'error': "Reys topilmadi."}
        if trip.state == 'delivered':
            return {'ok': False, 'error': "Bu reys allaqachon yetkazib berilgan deb belgilangan."}
        if trip.state in ('settling', 'done'):
            return {'ok': False, 'error': "Reys hisob-kitob bosqichiga o'tgan."}

        trip.action_deliver()
        moment = trip._tg_local_time(trip.arrival_datetime, employee)
        trip.message_post(
            body=_("Haydovchi Telegram bot orqali «Yetib keldim» deb belgiladi. "
                   "Vaqt: %s", moment))
        self.env['agronova.telegram.log'].tg_log(
            "Yetib keldim", chat_id=chat_id, employee_id=employee.id,
            trip_id=trip.id, payload=trip.arrival_datetime)
        return {'ok': True, 'name': trip.name,
                'route': "%s → %s" % (trip.origin or '?', trip.destination or '?'),
                'time': moment,
                'state': dict(self._fields['state'].selection).get(trip.state, '')}

    @api.model
    def tg_driver_balance(self, chat_id):
        """Bot: haydovchining umumiy hisob-kitobi (yakunlanmagan reyslar bo'yicha)."""
        employee = self.env['hr.employee']._tg_find(chat_id)
        if not employee:
            return self.env['hr.employee']._tg_not_linked(chat_id)
        trips = self.sudo().search([
            ('driver_id', '=', employee.id),
            ('state', '!=', 'done'),
        ])
        return {
            'ok': True,
            'name': employee.name,
            'trip_count': len(trips),
            'driver_share': sum(trips.mapped('driver_share')),
            'balance_due': sum(trips.mapped('balance_due')),
            'expense_total': sum(trips.mapped('expense_total')),
        }
