# -*- coding: utf-8 -*-
from odoo import api, fields, models


class FleetVehicle(models.Model):
    """Haydovchini kontakt emas, xodim ro'yxatidan tanlash.

    Odoo standartida `driver_id` — `res.partner` (kontakt). Bizda haydovchilar
    xodimlar ro'yxatida yuritiladi, shuning uchun tanlash xodimdan boradi.
    Standart `driver_id` orqaga moslik uchun avtomat to'ldiriladi (xodimning
    ish kontakti) — `fleet` ning hisobotlari va shartnomalari shunga tayanadi.
    """
    _inherit = 'fleet.vehicle'

    agronova_driver_employee_id = fields.Many2one(
        'hr.employee', string="Haydovchi (xodim)", tracking=True,
        domain="['|', ('company_id', '=', False), ('company_id', '=', company_id)]",
        help="Xodimlar ro'yxatidan tanlanadi. Standart «Driver» kontakti "
             "shunga qarab avtomat to'ldiriladi.")

    def _agronova_sync_driver_partner(self):
        """Xodim tanlansa — uning ish kontaktini `driver_id` ga qo'yadi."""
        for vehicle in self:
            employee = vehicle.agronova_driver_employee_id
            if not employee:
                continue
            if not employee.work_contact_id:
                employee.sudo()._create_work_contacts()
            vehicle.driver_id = employee.work_contact_id

    @api.model_create_multi
    def create(self, vals_list):
        vehicles = super().create(vals_list)
        vehicles._agronova_sync_driver_partner()
        return vehicles

    def write(self, vals):
        res = super().write(vals)
        if 'agronova_driver_employee_id' in vals:
            self._agronova_sync_driver_partner()
        return res
