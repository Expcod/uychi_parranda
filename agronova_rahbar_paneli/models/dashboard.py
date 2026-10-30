# -*- coding: utf-8 -*-
from odoo import _, api, models
from odoo.exceptions import AccessError, UserError


class FeedManagerDashboard(models.TransientModel):
    _inherit = 'agronova.executive.dashboard'

    def _check_feed_manager_access(self):
        self._check_dashboard_access()
        if not self.env.user.has_group('agronova_dashboard.group_agronova_dashboard_manager'):
            raise AccessError(_("Rahbar paneliga kirish huquqingiz yo'q."))

    @api.model
    def get_feed_manager_meta(self):
        self._check_feed_manager_access()
        return self.get_dashboard_meta()

    @api.model
    def get_feed_manager_data(self, section='overview', period='month', date_from=None, date_to=None):
        self._check_feed_manager_access()
        allowed = {'overview', 'production', 'stock', 'quality', 'dispatch', 'energy'}
        if section not in allowed:
            raise UserError(_("Noma'lum bo'lim."))
        data = self.get_dashboard_data('yem_zavodi', period, date_from, date_to)
        if not data.get('available'):
            return data
        ctx = self._make_ctx(period, date_from, date_to)
        a = self._yem_asos(ctx)
        k, panels = data['kpis'], data['panels']
        company = [('company_id', 'in', ctx['companies'])]
        dates = [('sana', '>=', ctx['d_from_s']), ('sana', '<=', ctx['d_to_s'])] + company
        energy = self.env['agronova.yem.energiya'].sudo().search(dates, order='sana desc, id desc')
        # Xarajatlar oylik yozuvlar: tanlangan oraliqqa tegishli barcha oylar olinadi.
        costs = self.env['agronova.yem.xarajat'].sudo().search([
            ('oy', '>=', ctx['d_from'].replace(day=1)), ('oy', '<=', ctx['d_to'].replace(day=1)),
        ] + company, order='oy desc, id desc')
        def action(name, model, domain):
            return {'name': name, 'res_model': model, 'domain': domain}
        def card(label, value, unit, icon, color, key=None, hint='', act=None):
            return self._kpi(label, value, unit, icon, color, hint=hint,
                             detail=self._det(key) if key else None, action=act)
        energy_action = action(_("Energiya yozuvlari"), 'agronova.yem.energiya', dates)
        cost_action = action(_("Oylik xarajatlar"), 'agronova.yem.xarajat', [
            ('oy', '>=', ctx['d_from'].replace(day=1).isoformat()),
            ('oy', '<=', ctx['d_to'].replace(day=1).isoformat())] + company)
        extras = {
            'open': card(_("Ochiq buyurtmalar"), len(a['ochiq']), 'int', 'fa-cogs', 'blue',
                         act=action(_("Ochiq yem buyurtmalari"), 'mrp.production', [
                             ('agronova_yem', '=', True), ('state', 'in', ['confirmed', 'progress', 'to_close'])] + company),
                         hint=_("Joriy holat, davrga bog'liq emas")),
            'raw': card(_("Xomashyo qoldig'i"), a['xomashyo_kg']/1000, 'ton', 'fa-database', 'blue', 'yem_zaxira', hint=_("Joriy qoldiq")),
            'finished': card(_("Tayyor yem qoldig'i"), a['tayyor_kg']/1000, 'ton', 'fa-cubes', 'green', hint=_("Joriy ombor qoldig'i")),
            'incoming': card(_("Tarozi kirimi"), a['kirim_t_kg']/1000, 'ton', 'fa-balance-scale', 'indigo', 'yem_tortish'),
            'input': card(_("Ishlab chiqarishga sarf"), a['kirim_kg']/1000, 'ton', 'fa-sliders', 'blue', 'yem_sarf'),
            'loss': card(_("Me'yordan ortiq yo'qotish"), a['ortiq_kg'], 'kg', 'fa-exclamation-triangle', 'red', 'yem_yoqotish'),
            'bags': card(_("Qoplar soni"), a['qop'], 'int', 'fa-archive', 'teal', 'yem_qadoqlash'),
            'sales': card(_("Jo'natma sotuv summasi"), a['sotuv_summa'], 'money', 'fa-money', 'green', 'yem_jonatma', hint=_("Sotuv turidagi jo'natmalar")),
            'electric': card(_("Elektr sarfi"), a['kwh'], 'qty', 'fa-bolt', 'orange', hint=_("kVt·soat"), act=energy_action),
            'gas': card(_("Gaz sarfi"), sum(energy.mapped('gaz_m3')), 'qty', 'fa-fire', 'orange', hint=_("m³"), act=energy_action),
            'energycost': card(_("Energiya summasi"), sum(energy.mapped('summa')), 'money', 'fa-bolt', 'purple', act=energy_action),
            'totalcost': card(_("Ishlab chiqarish tannarxi"), a['tannarx'], 'money', 'fa-money', 'purple', 'mrp_orders', hint=_("Yopilgan buyurtmalar bo'yicha")),
            'overhead': card(_("Oylik xarajatlar"), sum(costs.mapped('jami')), 'money', 'fa-calculator', 'indigo', hint=_("Tanlangan oraliqqa tegishli to'liq oylar"), act=cost_action),
        }
        def cell(text, right=False):
            return {'text': text, 'align': 'right' if right else 'left'}
        def grid(title, icon, headers, rows):
            panel = self._grid_panel(title, icon, [{'label': h} for h in headers], rows)
            panel['rows'] = rows
            return panel
        energy_rows = [{'open': {'res_model': 'agronova.yem.energiya', 'res_id': e.id}, 'cells': [
            cell(str(e.sana or '')), cell(e.liniya_id.display_name),
            cell(self._fmt(e.elektr_kwh, 'qty'), True), cell(self._fmt(e.gaz_m3, 'qty'), True),
            cell(self._fmt(e.kwh_t, 'qty'), True), cell(self._fmt(e.summa, 'money'), True)]} for e in energy]
        cost_rows = [{'open': {'res_model': 'agronova.yem.xarajat', 'res_id': x.id}, 'cells': [
            cell(str(x.oy or '')), cell(dict(x._fields['state'].selection).get(x.state, x.state)),
            cell(self._fmt(x.jami, 'money'), True), cell(self._fmt(x.ishlab_chiqarilgan_kg, 'kg'), True),
            cell(self._fmt(x.ustama_1_kg, 'money'), True)]} for x in costs]
        stock_rows = []
        for z in a['zaxira'].sorted(lambda r: (r.holat_tartib, r.yetadi_kun)):
            stock_rows.append({'open': {'res_model': 'agronova.yem.zaxira', 'res_id': z.id}, 'cells': [
                cell(z.product_id.display_name), cell(self._fmt(z.qoldiq_kg, 'kg'), True),
                cell(self._fmt(z.min_kg, 'kg'), True),
                cell(self._fmt(z.yetadi_kun, 'days') if z.yetadi_kun < 999 else '—', True),
                cell(dict(z._fields['holat'].selection).get(z.holat, ''))]})
        stock_grid = grid(_("Barcha xomashyo zaxiralari — joriy holat"), 'fa-database',
                          [_('Mahsulot'), _('Qoldiq'), _('Minimum'), _('Yetadi'), _('Holat')], stock_rows)
        energy_grid = grid(_("Energiya yozuvlari"), 'fa-bolt',
                           [_('Sana'), _('Liniya'), _('Elektr, kVt·soat'), _('Gaz, m³'), _('kVt·soat/t'), _('Summa')], energy_rows)
        cost_grid = grid(_("Oylik xarajatlar taqsimoti"), 'fa-calculator',
                         [_('Oy'), _('Holat'), _('Jami'), _('Ishlab chiqarildi'), _('1 kg ustama')], cost_rows)
        sections = {
            'overview': (k + [extras['open'], extras['raw'], extras['finished']], [panels[0], panels[1], panels[2]]),
            'production': ([k[0], k[1], extras['open'], extras['input']], [panels[1], panels[3], panels[5]]),
            'stock': ([extras['raw'], extras['finished'], extras['incoming'], k[6], k[8]], [stock_grid]),
            'quality': ([k[2], extras['loss'], k[7], k[8]], [panels[2], panels[6], panels[5]]),
            'dispatch': ([k[4], extras['bags'], k[5], extras['sales'], extras['finished']], [panels[4]]),
            'energy': ([k[3], extras['totalcost'], extras['electric'], extras['gas'], extras['energycost'], extras['overhead']],
                       [panels[2], energy_grid, cost_grid]),
        }
        data['kpis'], data['panels'] = sections[section]
        data['section'] = section
        return data
