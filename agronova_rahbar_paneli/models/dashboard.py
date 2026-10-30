# -*- coding: utf-8 -*-
import math

from odoo import _, api, models
from odoo.exceptions import AccessError, UserError
from odoo.tools.misc import formatLang


class FeedManagerDashboard(models.TransientModel):
    _inherit = 'agronova.executive.dashboard'

    def _check_feed_manager_access(self):
        self._check_dashboard_access()
        if not self.env.user.has_group('agronova_dashboard.group_agronova_dashboard_manager'):
            raise AccessError(_("Rahbar paneliga kirish huquqingiz yo'q."))

    def _feed_company(self):
        raw = self.env['ir.config_parameter'].sudo().get_param('agronova_rahbar_paneli.company_id')
        # Sozlama bo'sh bo'lsa — asosiy korxona (Uychi Paranda) yem zavodi hisoblanadi.
        company = self.env['res.company'].browse(int(raw)) if raw and raw.isdigit() \
            else self.env.ref('base.main_company', raise_if_not_found=False) or self.env['res.company']
        company = company.exists()
        if company and company.id not in self.env.user.company_ids.ids:
            raise AccessError(_("Yem zavodi korxonasiga kirish huquqingiz yo'q."))
        return company

    def _feed_scoped(self):
        company = self._feed_company()
        if not company:
            raise UserError(_("Sozlamalar → Rahbar paneli bo'limida yem zavodi korxonasini tanlang."))
        return self.with_context(allowed_company_ids=[company.id], feed_manager_scope=True)

    def _company_domain(self, model):
        if self.env.context.get('feed_manager_scope') and model is not None and model._name == 'hr.attendance':
            return [('employee_id.company_id', 'in', self.env.companies.ids)]
        return super()._company_domain(model)

    @api.model
    def get_feed_manager_meta(self):
        self._check_feed_manager_access()
        company = self._feed_company()
        if not company:
            return {'company': '', 'user': self.env.user.name, 'feed_company_id': False}
        meta = self._feed_scoped().get_dashboard_meta()
        meta['feed_company_id'] = company.id
        return meta

    @api.model
    def get_feed_manager_detail(self, key, period='month', date_from=None, date_to=None, ref=None):
        self._check_feed_manager_access()
        return self._feed_scoped().get_detail(key, period, date_from, date_to, ref)

    @api.model
    def get_feed_manager_data(self, section='overview', period='month', date_from=None, date_to=None):
        self._check_feed_manager_access()
        allowed = {'overview', 'production', 'stock', 'quality', 'dispatch', 'energy',
                   'moliya', 'qarzdorlar', 'ombor', 'zakupka', 'transport', 'ish_haqi', 'davomat'}
        if section not in allowed:
            raise UserError(_("Noma'lum bo'lim."))
        if not self._feed_company():
            return {'available': False, 'message': _("Sozlamalar → Rahbar paneli bo'limida yem zavodi korxonasini tanlang. Bu korxona faqat yem zavodiga tegishli bo'lishi kerak."), 'kpis': [], 'panels': [], 'alerts': []}
        self = self._feed_scoped()
        if section in {'moliya', 'qarzdorlar', 'ombor', 'zakupka', 'transport', 'ish_haqi', 'davomat'}:
            return self.get_dashboard_data(section, period, date_from, date_to)
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

    def _yem_scene(self, a):
        """Zavod ichidagi zanjir 3D da: kirim tarozisidan jo'natmagacha.

        Har bino — bitta bosqich, bosilsa o'sha bosqichning tafsiloti ochiladi.
        Rang — muammo bor-yo'qligi: kritik zaxira, me'yordan ortiq yo'qotish,
        to'xtab turgan liniya, kritik tarozi tafovuti.
        """
        lin = self.env["agronova.yem.liniya"].sudo().search([("company_id", "in", self.env.companies.ids)], limit=2)
        nodes = [
            {"id": "tarozi", "label": _("Tarozi (kirim)"), "shape": "truck", "pos": [-10, 0],
             "value": a["kirim_t_kg"], "display": self._fmt(a["kirim_t_kg"] / 1000.0, "ton"),
             "metric": _("Qabul qilingan xomashyo, tafovutli tortish: %s", len(a["tt_tafovut"])),
             "status": "bad" if (a["tt_ochiq"] and len(a["tt_kritik"]) > len(a["tt"]) * 0.05)
             or len(a["tt_kritik"]) > len(a["tt"]) * 0.05 else ("ok" if a["kirim_t_kg"] else "idle"),
             "detail": self._det("yem_tortish")},
            {"id": "xomashyo", "label": _("Xomashyo ombori"), "shape": "crates", "pos": [-6, -2.6],
             "value": a["xomashyo_kg"], "display": self._fmt(a["xomashyo_kg"] / 1000.0, "ton"),
             "metric": _("Qoldiq; minimumdan past: %s", len(a["zaxira_kritik"])),
             "status": "bad" if a["zaxira_kritik"] else "ok", "detail": self._det("yem_zaxira")},
            {"id": "silos", "label": _("Dozalash"), "shape": "silo", "pos": [-6, 2.6],
             "value": a["kirim_kg"], "display": self._fmt(a["kirim_kg"] / 1000.0, "ton"),
             "metric": _("Berilgan xomashyo; me'yordan tashqari sarf: %s", len(a["ogish"])),
             "status": "bad" if len(a["ogish"]) > len(a["mos"]) * 0.1 else ("ok" if a["kirim_kg"] else "idle"),
             "detail": self._det("yem_sarf")},
        ]
        for i, l in enumerate(lin):
            l_mos = a["mos"].filtered(lambda m: m.agronova_liniya_id == l)
            kg = sum(l_mos.mapped("agronova_miqdor_kg"))
            ortiq = sum(l_mos.mapped("agronova_ortiqcha_yoqotish_kg"))
            toxtagan = a["tox_hozir"].filtered(lambda t: t.liniya_id == l)
            nodes.append({
                "id": "liniya%s" % l.id, "label": l.name, "shape": "factory",
                "pos": [-1.5, -2.8 if i == 0 else 2.8], "value": kg,
                "display": self._fmt(kg / 1000.0, "ton"),
                "metric": _("To'xtab turibdi") if toxtagan else _("Me'yordan ortiq yo'qotish: %s",
                                                                  self._fmt(ortiq, "kg")),
                "status": "bad" if (toxtagan or ortiq > 0.005 * (kg or 1)) else ("ok" if kg else "idle"),
                "detail": self._det("yem_smena", l.id),
            })
        nodes += [
            {"id": "qadoq", "label": _("Qadoqlash"), "shape": "dome", "pos": [2.8, 0],
             "value": a["qadoq_kg"], "display": _("%s qop", formatLang(self.env, a["qop"], digits=0)),
             "metric": _("To'ldirishda tafovut: %s", len(a["qd_tafovut"])),
             "status": "bad" if len(a["qd_tafovut"]) > max(3, len(a["qd"]) * 0.1) else
             ("ok" if a["qadoq_kg"] else "idle"), "detail": self._det("yem_qadoqlash")},
            {"id": "tayyor", "label": _("Tayyor mahsulot"), "shape": "crates", "pos": [6.5, -2.6],
             "value": a["tayyor_kg"], "display": self._fmt(a["tayyor_kg"] / 1000.0, "ton"),
             "metric": _("Ombordagi qoldiq"), "status": "ok" if a["tayyor_kg"] else "idle",
             "detail": self._det("yem_jonatma")},
            {"id": "jonatma", "label": _("Jo'natma"), "shape": "truck", "pos": [10, 0],
             "value": a["jon_kg"], "display": self._fmt(a["jon_kg"] / 1000.0, "ton"),
             "metric": _("Sotuv va ichki xo'jaliklar"), "status": "ok" if a["jon_kg"] else "idle",
             "detail": self._det("yem_jonatma")},
            {"id": "sotuv", "label": _("Sotuv tushumi"), "shape": "bank", "pos": [6.5, 2.6],
             "value": a["sotuv_summa"], "display": self._fmt_compact(a["sotuv_summa"]),
             "metric": _("Tashqi mijozlarga sotuv"), "status": "ok" if a["sotuv_summa"] else "idle",
             "detail": self._det("yem_jonatma", "sotuv")},
        ]
        logs = {n["id"]: math.log10(abs(n["value"]) + 1) for n in nodes}
        top = max(logs.values(), default=0.0) or 1.0
        for n in nodes:
            n["h"] = round(0.35 + 0.65 * (logs[n["id"]] / top), 3)
        lid = ["liniya%s" % l.id for l in lin]
        links = [["tarozi", "xomashyo"], ["xomashyo", "silos"]] + [["silos", x] for x in lid] \
            + [[x, "qadoq"] for x in lid] + [["qadoq", "tayyor"], ["tayyor", "jonatma"], ["jonatma", "sotuv"]]
        return {
            "type": "scene3d", "mode": "chain", "title": _("Yem zavodi — 3D jarayon xaritasi"),
            "icon": "fa-cube", "nodes": nodes, "links": links,
            "hint": _("Kirim tarozisidan jo'natmagacha. Binoni bosing — o'sha bosqichning hujjatlari ochiladi."),
            "legend": [{"label": _("Normada"), "color": "green"},
                       {"label": _("Muammo bor"), "color": "red"},
                       {"label": _("Davrda faoliyat yo'q"), "color": "gray"}],
        }

