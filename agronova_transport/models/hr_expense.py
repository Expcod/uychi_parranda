# -*- coding: utf-8 -*-
from odoo import api, fields, models


class HrExpense(models.Model):
    _inherit = 'hr.expense'

    trip_id = fields.Many2one(
        'agronova.trip', string="Reys", index='btree_not_null', ondelete='set null',
        help="Xarajat shu reysning lotiga (analitik hisobiga) yoziladi.")

    @api.onchange('trip_id')
    def _onchange_trip_id(self):
        """Reys tanlansa — analitik taqsimot reys lotiga yo'naltiriladi."""
        for expense in self:
            account = expense.trip_id.analytic_account_id
            if account:
                expense.analytic_distribution = {str(account.id): 100}

    @api.model_create_multi
    def create(self, vals_list):
        expenses = super().create(vals_list)
        for expense in expenses:
            account = expense.trip_id.analytic_account_id
            if account and not expense.analytic_distribution:
                expense.analytic_distribution = {str(account.id): 100}
        return expenses
