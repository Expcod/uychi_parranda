# -*- coding: utf-8 -*-
from odoo import api, models


class HrExpense(models.Model):
    _inherit = 'hr.expense'

    @api.model
    def tg_expense_products(self):
        """Bot: xarajat hujjatida tanlanadigan mahsulotlar."""
        products = self.env['product.product'].sudo().search(
            [('can_be_expensed', '=', True)], order='name')
        return [{'id': p.id, 'name': p.name, 'uom': p.uom_id.name} for p in products]

    @api.model
    def tg_create_expense(self, chat_id, trip_id, product_id, amount,
                          note=None, photo_b64=None, photo_name=None):
        """Bot: haydovchi yuborgan xarajatni yaratadi.

        TZ talabi: chek rasmi majburiy — fotosiz xarajat qabul qilinmaydi.
        """
        employee = self.env['hr.employee']._tg_find(chat_id)
        if not employee:
            return self.env['hr.employee']._tg_not_linked(chat_id)
        if not photo_b64:
            return {'ok': False, 'error': "Chek rasmi majburiy."}
        try:
            amount = float(str(amount).replace(' ', '').replace(',', '.'))
        except (TypeError, ValueError):
            return {'ok': False, 'error': "Summa noto'g'ri."}
        if amount <= 0:
            return {'ok': False, 'error': "Summa noldan katta bo'lishi kerak."}

        trip = self.env['agronova.trip'].sudo().browse(int(trip_id))
        if not trip.exists() or trip.driver_id != employee:
            return {'ok': False, 'error': "Reys topilmadi."}
        product = self.env['product.product'].sudo().browse(int(product_id))
        if not product.exists():
            return {'ok': False, 'error': "Xarajat turi topilmadi."}

        expense = self.sudo().create({
            'name': note or product.name,
            'employee_id': employee.id,
            'product_id': product.id,
            'total_amount_currency': amount,
            'trip_id': trip.id,
            'company_id': trip.company_id.id,
        })
        self.env['ir.attachment'].sudo().create({
            'name': photo_name or 'chek.jpg',
            'datas': photo_b64,
            'res_model': 'hr.expense',
            'res_id': expense.id,
            'mimetype': 'image/jpeg',
        })
        trip.invalidate_recordset(['expense_total', 'profit', 'driver_share'])
        return {
            'ok': True,
            'expense_id': expense.id,
            'trip_name': trip.name,
            'amount': amount,
            'expense_total': trip.expense_total,
            'profit': trip.profit,
        }
