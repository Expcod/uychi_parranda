from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    feed_manager_company_id = fields.Many2one(
        'res.company', string="Yem zavodi korxonasi",
        config_parameter='agronova_rahbar_paneli.company_id',
        help="Faqat yem zavodiga tegishli alohida korxonani tanlang. Barcha panel bo'limlari shu korxona bilan chegaralanadi.")
