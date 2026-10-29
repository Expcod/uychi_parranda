# -*- coding: utf-8 -*-
"""Rahbar paneli — tafsilot oynasi (drill-down).

Panelda deyarli har bir element (KPI kartochka, reyting qatori, donut bo'lagi,
grafik ustuni, 3D bino) ``{"key", "ref"}`` juftligini olib yuradi. Bosilganda
mijoz :meth:`get_detail` ni chaqiradi va o'ngdan ochiladigan oynada:

* qisqa ko'rsatkichlar (stats),
* ixtiyoriy grafik,
* yozuvlar jadvali (qatorni bosib — yana chuqurroq yoki Odoo formasi),
* «Odoo'da ochish» tugmasi

ko'rsatiladi. Mijoz ixtiyoriy model/domen yubora olmaydi — faqat shu fayldagi
``_detail_<key>`` metodlaridan biri tanlanadi, shuning uchun ``sudo`` xavfsiz.
"""
import re
from collections import defaultdict
from datetime import datetime, time

from dateutil.relativedelta import relativedelta

from odoo import _, api, fields, models
from odoo.exceptions import UserError
from odoo.tools.misc import format_date, format_datetime

from .agronova_executive_dashboard import MAX_ROWS, POS_DONE_STATES

_KEY_RE = re.compile(r"^[a-z][a-z0-9_]{1,40}$")


class AgroNovaExecutiveDashboardDetail(models.TransientModel):
    _inherit = 'agronova.executive.dashboard'

    # ==================================================================
    # Kirish nuqtasi
    # ==================================================================
    @api.model
    def get_detail(self, key, period="month", date_from=None, date_to=None, ref=None):
        self._check_dashboard_access()
        if not isinstance(key, str) or not _KEY_RE.match(key):
            raise UserError(_("Noto'g'ri so'rov."))
        method = getattr(self, "_detail_%s" % key, None)
        if not method:
            raise UserError(_("Bu element uchun tafsilot mavjud emas."))
        ctx = self._make_ctx(period, date_from, date_to)
        # Grafik ustuni bosilganda — faqat o'sha oraliq.
        if isinstance(ref, dict) and ref.get("from") and ref.get("to"):
            ctx = self._ctx_for(fields.Date.to_date(ref["from"]), fields.Date.to_date(ref["to"]))
            ref = ref.get("ref")
        payload = method(ctx, ref)
        payload.setdefault("stats", [])
        payload.setdefault("columns", [])
        payload.setdefault("rows", [])
        payload.setdefault("footer", [])
        payload.setdefault("message", _("Ma'lumot topilmadi."))
        payload["key"] = key
        payload["ref"] = ref
        payload["period_label"] = "%s — %s" % (format_date(self.env, ctx["d_from"]),
                                                format_date(self.env, ctx["d_to"]))
        return payload

    # ==================================================================
    # Yordamchilar
    # ==================================================================
    @staticmethod
    def _ref_id(ref):
        try:
            return int(ref) if ref not in (None, False, "") else False
        except (TypeError, ValueError):
            return False

    def _stat(self, label, value, kind="money", tone="", hint=""):
        return {"label": label, "display": self._fmt(value, kind) if kind else value,
                "tone": tone, "hint": hint}

    def _cell_value(self, rec, path, kind):
        """``partner_id.name`` kabi yo'l bo'yicha qiymatni formatlab qaytaradi."""
        value = rec
        field = None
        for part in path.split("."):
            if not value:
                return "—"
            field = value._fields.get(part)
            value = value[0][part] if len(value) > 1 else value[part]
        if kind in ("text", "m2o"):
            if isinstance(value, models.BaseModel):
                return value.display_name or "—"
            return value or "—"
        if kind == "sel":
            sel = dict(field._description_selection(self.env)) if field else {}
            return str(sel.get(value, value or "—"))
        if kind == "date":
            return format_date(self.env, value) if value else "—"
        if kind == "datetime":
            return format_datetime(self.env, value, dt_format="short") if value else "—"
        if kind == "bool":
            return _("Ha") if value else _("Yo'q")
        return self._fmt(value or 0.0, kind)

    def _rows_table(self, records, cols, row_detail=None, open_record=True, tone=None):
        """Yozuvlarni jadval qatorlariga aylantiradi.

        ``cols`` = [(yo'l, sarlavha, tur)]; son turlari o'ngga tekislanadi.
        ``row_detail(rec)`` — qator bosilganda ochiladigan keyingi tafsilot.
        ``tone(rec, path)`` — katakcha rangi ("danger" | "ok" | "strong" | ...).
        """
        textual = ("text", "m2o", "sel", "date", "datetime", "bool")
        columns = [{"label": label, "align": "left" if kind in textual else "right"}
                   for _path, label, kind in cols]
        rows = []
        for rec in records[:MAX_ROWS]:
            cells = []
            for path, _label, kind in cols:
                cells.append({
                    "text": self._cell_value(rec, path, kind),
                    "align": "left" if kind in textual else "right",
                    "tone": tone(rec, path) if tone else "",
                })
            row = {"cells": cells}
            if row_detail:
                row["detail"] = row_detail(rec)
            if open_record:
                row["open"] = {"res_model": rec._name, "res_id": rec.id}
            rows.append(row)
        return columns, rows

    def _detail(self, title, icon="fa-list", color="blue", subtitle="", stats=None,
                columns=None, rows=None, footer=None, chart=None, split=None, action=None,
                message="", total=None):
        out = {
            "title": title, "icon": icon, "color": color, "subtitle": subtitle,
            "stats": stats or [], "columns": columns or [], "rows": rows or [],
            "footer": footer or [], "chart": chart, "split": split, "action": action,
            "message": message or _("Ma'lumot topilmadi."),
        }
        if total is not None and total > MAX_ROWS:
            out["truncated"] = _("Birinchi %s ta yozuv ko'rsatildi (jami %s). To'liq ro'yxat "
                                 "uchun «Odoo'da ochish» tugmasini bosing.", MAX_ROWS, total)
        return out

    # ==================================================================
    # MOLIYA
    # ==================================================================
    def _invoices_detail(self, ctx, move_type, title, icon, color):
        Move = self.env["account.move"].sudo()
        domain = self._move_domain(ctx, move_type)
        moves = Move.search(domain, order="invoice_date desc, id desc", limit=MAX_ROWS)
        total = Move.search_count(domain)
        jami = abs(self._sum_moves(domain, "amount_total_signed"))
        qoldiq = abs(self._sum_moves(domain, "amount_residual_signed"))
        series = self._move_series(ctx, move_type)
        cols = [("name", _("Hujjat"), "text"), ("invoice_date", _("Sana"), "date"),
                ("partner_id", _("Kontragent"), "m2o"),
                ("amount_total_signed", _("Summa"), "money"),
                ("amount_residual_signed", _("Qoldiq"), "money"),
                ("payment_state", _("To'lov holati"), "sel")]
        columns, rows = self._rows_table(
            moves, cols,
            tone=lambda r, p: ("danger" if p == "amount_residual_signed" and r.amount_residual
                               else "strong" if p == "amount_total_signed" else ""))
        partners = defaultdict(float)
        for partner, amount in Move._read_group(domain, ["partner_id"],
                                                ["amount_total_signed:sum"]):
            partners[partner.display_name or str(_("Noma'lum"))] += abs(amount or 0.0)
        top = sorted(partners.items(), key=lambda x: x[1], reverse=True)
        return self._detail(
            title, icon, color,
            stats=[
                self._stat(_("Hujjatlar"), total, "int"),
                self._stat(_("Jami summa"), jami),
                self._stat(_("To'langan"), jami - qoldiq, tone="ok"),
                self._stat(_("To'lanmagan qoldiq"), qoldiq, tone="bad" if qoldiq else ""),
                self._stat(_("Kontragentlar"), len(partners), "int"),
                self._stat(_("O'rtacha hujjat"), (jami / total) if total else 0.0),
            ],
            chart=self._trend_panel(_("Kunlar kesimida"), "fa-bar-chart", ctx, series,
                                    label_a=title),
            split=self._split_panel(_("Asosiy kontragentlar"), "fa-pie-chart", [
                {"label": k, "value": v, "color": c}
                for (k, v), c in zip(top[:6], ("blue", "green", "orange", "purple", "teal",
                                               "indigo"))]) if top else None,
            columns=columns, rows=rows, total=total,
            action=self._act("account.move", domain, title))

    def _detail_sotuv(self, ctx, ref):
        return self._invoices_detail(ctx, "out_invoice", _("Sotuv hujjatlari"),
                                     "fa-shopping-cart", "blue")

    def _detail_xarid(self, ctx, ref):
        return self._invoices_detail(ctx, "in_invoice", _("Xarid hujjatlari"),
                                     "fa-shopping-basket", "orange")

    def _debt_detail(self, ctx, move_type, title, icon, color):
        Move = self.env["account.move"].sudo()
        domain = self._unpaid_domain(move_type, ctx["companies"])
        moves = Move.search(domain, order="invoice_date_due asc, id", limit=MAX_ROWS)
        total = Move.search_count(domain)
        today = fields.Date.context_today(self)
        jami = abs(self._sum_moves(domain, "amount_residual_signed"))
        muddati_otgan = abs(self._sum_moves(domain + [("invoice_date_due", "<", today)],
                                            "amount_residual_signed"))
        cols = [("name", _("Hujjat"), "text"), ("partner_id", _("Kontragent"), "m2o"),
                ("invoice_date", _("Sana"), "date"),
                ("invoice_date_due", _("To'lov muddati"), "date"),
                ("amount_total_signed", _("Summa"), "money"),
                ("amount_residual_signed", _("Qoldiq"), "money")]
        columns, rows = self._rows_table(
            moves, cols,
            row_detail=lambda r: self._det("partner", r.partner_id.id) if r.partner_id else None,
            tone=lambda r, p: ("danger" if p == "invoice_date_due" and r.invoice_date_due
                               and r.invoice_date_due < today else
                               "strong" if p == "amount_residual_signed" else ""))
        return self._detail(
            title, icon, color,
            subtitle=_("Davrdan qat'i nazar — barcha ochiq hujjatlar"),
            stats=[
                self._stat(_("Ochiq hujjatlar"), total, "int"),
                self._stat(_("Jami qoldiq"), jami, tone="bad" if jami else ""),
                self._stat(_("Muddati o'tgan"), muddati_otgan,
                           tone="bad" if muddati_otgan else "ok"),
                self._stat(_("Muddati o'tmagan"), max(jami - muddati_otgan, 0.0)),
            ],
            columns=columns, rows=rows, total=total,
            action=self._act("account.move", domain, title))

    def _detail_debitor(self, ctx, ref):
        return self._debt_detail(ctx, "out_invoice", _("Mijozlar qarzi (debitorlik)"),
                                 "fa-user-times", "red")

    def _detail_kreditor(self, ctx, ref):
        return self._debt_detail(ctx, "in_invoice", _("Ta'minotchilarga qarz (kreditorlik)"),
                                 "fa-truck", "indigo")

    def _detail_partner(self, ctx, ref):
        partner = self.env["res.partner"].sudo().browse(self._ref_id(ref)).exists()
        if not partner:
            return self._detail(_("Kontragent topilmadi"), "fa-user")
        Move = self.env["account.move"].sudo()
        base = [("partner_id", "child_of", partner.commercial_partner_id.id),
                ("state", "=", "posted"), ("company_id", "in", ctx["companies"]),
                ("move_type", "in", ["out_invoice", "in_invoice", "out_refund", "in_refund"])]
        ochiq = base + [("payment_state", "in", ["not_paid", "partial"])]
        davr = base + [("invoice_date", ">=", ctx["d_from_s"]), ("invoice_date", "<=", ctx["d_to_s"])]
        # Ochiq hujjatlar YOKI davr ichidagilar.
        moves = Move.search(base + [
            "|", ("payment_state", "in", ["not_paid", "partial"]),
            "&", ("invoice_date", ">=", ctx["d_from_s"]), ("invoice_date", "<=", ctx["d_to_s"]),
        ], order="invoice_date desc", limit=MAX_ROWS)
        sotuv = abs(self._sum_moves(davr + [("move_type", "=", "out_invoice")],
                                    "amount_total_signed"))
        xarid = abs(self._sum_moves(davr + [("move_type", "=", "in_invoice")],
                                    "amount_total_signed"))
        debitor = self._sum_moves(ochiq + [("move_type", "=", "out_invoice")],
                                  "amount_residual_signed")
        kreditor = abs(self._sum_moves(ochiq + [("move_type", "=", "in_invoice")],
                                       "amount_residual_signed"))
        cols = [("name", _("Hujjat"), "text"), ("move_type", _("Turi"), "sel"),
                ("invoice_date", _("Sana"), "date"),
                ("invoice_date_due", _("Muddat"), "date"),
                ("amount_total_signed", _("Summa"), "money"),
                ("amount_residual_signed", _("Qoldiq"), "money"),
                ("payment_state", _("Holat"), "sel")]
        columns, rows = self._rows_table(moves, cols)
        stats = [
            self._stat(_("Davr sotuvi"), sotuv),
            self._stat(_("Davr xaridi"), xarid),
            self._stat(_("Bizga qarzi"), debitor, tone="bad" if debitor else "ok"),
            self._stat(_("Bizning qarzimiz"), kreditor),
        ]
        if partner.phone:
            stats.append(self._stat(_("Telefon"), partner.phone, kind=None))
        if "credit_limit" in partner._fields and partner.credit_limit:
            stats.append(self._stat(_("Kredit limiti"), partner.credit_limit))
        return self._detail(
            partner.display_name, "fa-user", "blue",
            subtitle=_("Ochiq va davrdagi hujjatlar"), stats=stats,
            columns=columns, rows=rows,
            action={"res_model": "res.partner", "res_id": partner.id,
                    "name": partner.display_name})

    def _detail_kassalar(self, ctx, ref):
        Kassa = self._model("agronova.kassa")
        if Kassa is None:
            return self._detail(_("Kassalar"), "fa-archive")
        kassalar = Kassa.search([("active", "=", True)] + self._company_domain(Kassa))
        cols = [("name", _("Kassa"), "text"), ("turi", _("Turi"), "sel"),
                ("currency_id", _("Valyuta"), "m2o"), ("balance", _("Qoldiq"), "money")]
        columns, rows = self._rows_table(
            kassalar.sorted(lambda k: -abs(k.balance or 0.0)), cols,
            row_detail=lambda k: self._det("kassa", k.id),
            tone=lambda k, p: "danger" if p == "balance" and (k.balance or 0) < 0 else
            ("strong" if p == "balance" else ""))
        pul = self._kassa_qoldiqlari()
        kirim_s, chiqim_s = self._kassa_series(ctx)
        return self._detail(
            _("Kassalar"), "fa-archive", "green",
            stats=[self._stat(_("Kassalar soni"), len(kassalar), "int"),
                   self._stat(_("Jami (milliy valyuta)"), pul["kassa_uzs"]),
                   self._stat(_("Jami (chet el valyutasi)"), pul["kassa_usd"], "usd"),
                   self._stat(_("Davr kirimi"), sum(kirim_s.values()), tone="ok"),
                   self._stat(_("Davr chiqimi"), sum(chiqim_s.values()), tone="bad")],
            chart=self._trend_panel(_("Kirim va chiqim"), "fa-exchange", ctx, kirim_s, chiqim_s,
                                    label_a=_("Kirim"), label_b=_("Chiqim")),
            columns=columns, rows=rows,
            action=self._act("agronova.kassa", [("active", "=", True)], _("Kassalar")))

    def _harakat_detail(self, ctx, domain, title, extra_stats=None, action_name=None):
        Harakat = self._model("agronova.kassa.harakat")
        if Harakat is None:
            return self._detail(title, "fa-exchange")
        domain = [("state", "=", "posted"), ("date_day", ">=", ctx["d_from_s"]),
                  ("date_day", "<=", ctx["d_to_s"])] + self._company_domain(Harakat) + domain
        recs = Harakat.search(domain, order="date desc, id desc")
        kirim = sum(recs.filtered(lambda h: h.direction == "in").mapped("amount"))
        chiqim = sum(recs.filtered(lambda h: h.direction == "out").mapped("amount"))
        ks, cs = defaultdict(float), defaultdict(float)
        modda = defaultdict(float)
        for h in recs:
            if h.date_day:
                (ks if h.direction == "in" else cs)[h.date_day] += h.amount or 0.0
            if h.direction == "out":
                modda[h.modda_id.display_name or str(_("Moddasiz"))] += h.amount or 0.0
        cols = [("date", _("Vaqt"), "datetime"), ("name", _("Hujjat"), "text"),
                ("kassa_id", _("Kassa"), "m2o"), ("direction", _("Yo'nalish"), "sel"),
                ("modda_id", _("Modda"), "m2o"), ("partner_id", _("Kontragent"), "m2o"),
                ("amount", _("Summa"), "money")]
        columns, rows = self._rows_table(
            recs, cols,
            tone=lambda h, p: ("ok" if h.direction == "in" else "danger") if p == "amount" else "")
        top = sorted(modda.items(), key=lambda x: x[1], reverse=True)[:6]
        return self._detail(
            title, "fa-exchange", "teal",
            stats=(extra_stats or []) + [
                self._stat(_("Kirim"), kirim, tone="ok"),
                self._stat(_("Chiqim"), chiqim, tone="bad"),
                self._stat(_("Sof oqim"), kirim - chiqim, tone="ok" if kirim >= chiqim else "bad"),
                self._stat(_("Operatsiyalar"), len(recs), "int"),
            ],
            chart=self._trend_panel(_("Kunlar kesimida"), "fa-bar-chart", ctx, ks, cs,
                                    label_a=_("Kirim"), label_b=_("Chiqim")),
            split=self._split_panel(_("Chiqim moddalari"), "fa-tags", [
                {"label": k, "value": v, "color": c}
                for (k, v), c in zip(top, ("orange", "red", "purple", "blue", "teal", "gray"))
            ]) if top else None,
            columns=columns, rows=rows, total=len(recs),
            action=self._act("agronova.kassa.harakat", domain, action_name or title))

    def _detail_kassa(self, ctx, ref):
        Kassa = self._model("agronova.kassa")
        kassa = Kassa.browse(self._ref_id(ref)).exists() if Kassa is not None else None
        if not kassa:
            return self._detail(_("Kassa topilmadi"), "fa-archive")
        return self._harakat_detail(
            ctx, [("kassa_id", "=", kassa.id)], kassa.display_name,
            extra_stats=[self._stat(_("Joriy qoldiq"), kassa.balance or 0.0,
                                    "usd" if kassa.currency_id and kassa.currency_id != self.env.company.currency_id
                                    else "money",
                                    tone="strong")])

    def _detail_kassa_harakat(self, ctx, ref):
        domain = [("direction", "=", ref)] if ref in ("in", "out") else []
        return self._harakat_detail(ctx, domain, _("Kassa harakatlari"))

    def _detail_depozitlar(self, ctx, ref):
        Depozit = self._model("agronova.depozit")
        if Depozit is None:
            return self._detail(_("Depozitlar"), "fa-briefcase")
        recs = Depozit.search([("active", "=", True)] + self._company_domain(Depozit),
                              order="balans desc")
        cols = [("name", _("Depozit"), "text"), ("egasi_id", _("Egasi"), "m2o"),
                ("currency_id", _("Valyuta"), "m2o"), ("kirim", _("Jami kirim"), "money"),
                ("chiqim", _("Jami chiqim"), "money"), ("balans", _("Qoldiq"), "money"),
                ("limit", _("Limit"), "money")]
        columns, rows = self._rows_table(
            recs, cols,
            tone=lambda d, p: "danger" if p == "balans" and d.limit and d.balans > d.limit else
            ("strong" if p == "balans" else ""))
        oshgan = recs.filtered(lambda d: d.limit and d.balans > d.limit)
        return self._detail(
            _("Depozitlar (mas'ul shaxslar qo'lidagi naqd)"), "fa-briefcase", "orange",
            stats=[self._stat(_("Depozitlar"), len(recs), "int"),
                   self._stat(_("Jami qoldiq"), sum(recs.mapped("balans"))),
                   self._stat(_("Limitdan oshgan"), len(oshgan), "int",
                              tone="bad" if oshgan else "ok")],
            columns=columns, rows=rows,
            action=self._act("agronova.depozit", [("active", "=", True)], _("Depozitlar")))

    def _detail_aging(self, ctx, ref):
        Aging = self.env["agronova.debt.aging.report"].sudo()
        domain = [("company_id", "in", ctx["companies"])]
        if ref in ("yaxshi", "ogohlantirish", "xavfli"):
            domain.append(("xavf_darajasi", "=", ref))
        recs = Aging.search(domain, order="jami_qarz desc")
        cols = [("partner_id", _("Mijoz"), "m2o"), ("masul_sotuvchi_id", _("Mas'ul"), "m2o"),
                ("jami_qarz", _("Jami qarz"), "money"), ("qarz_0_30", _("0–30"), "money"),
                ("qarz_31_60", _("31–60"), "money"), ("qarz_60_plus", _("60+"), "money"),
                ("kechikish_kun_soni", _("Kechikish, kun"), "int")]
        columns, rows = self._rows_table(
            recs, cols, open_record=False,
            row_detail=lambda r: self._det("partner", r.partner_id.id),
            tone=lambda r, p: "danger" if p == "qarz_60_plus" and r.qarz_60_plus else
            ("strong" if p == "jami_qarz" else ""))
        titles = {"yaxshi": _("Joriy qarzlar (0–30 kun)"),
                  "ogohlantirish": _("Kechikkan qarzlar (31–60 kun)"),
                  "xavfli": _("Xavfli qarzlar (60+ kun)")}
        return self._detail(
            titles.get(ref, _("Debitorlik muddatlari")), "fa-credit-card", "red",
            stats=[self._stat(_("Mijozlar"), len(recs), "int"),
                   self._stat(_("Jami qarz"), sum(recs.mapped("jami_qarz"))),
                   self._stat(_("60+ kun"), sum(recs.mapped("qarz_60_plus")), tone="bad"),
                   self._stat(_("O'rtacha kechikish"),
                              self._ortacha(recs.mapped("kechikish_kun_soni")), "days")],
            columns=columns, rows=rows,
            action=self._act("agronova.debt.aging.report", domain, _("Qarzdorlik (Aging)")))

    # ==================================================================
    # BOQUV
    # ==================================================================
    def _partiya_table(self, partiyalar, title, subtitle="", color="green"):
        norm_fcr, norm_nobud = self._norm("fcr"), self._norm("nobud")
        cols = [("name", _("Partiya"), "text"), ("filial_id", _("Filial"), "m2o"),
                ("bino_id", _("Bino"), "m2o"), ("yosh_kun", _("Yosh, kun"), "int"),
                ("joriy_son", _("Tirik"), "int"), ("nobud_foiz", _("Nobud"), "pct"),
                ("fcr", _("FCR"), "coef"), ("ortacha_vazn", _("O'rt. vazn"), "qty"),
                ("epef", _("EPEF"), "qty"), ("tannarx_1_kg", _("1 kg tannarx"), "money")]
        columns, rows = self._rows_table(
            partiyalar, cols, row_detail=lambda p: self._det("boquv_partiya", p.id),
            tone=lambda p, f: ("danger" if (f == "fcr" and (p.fcr or 0) > norm_fcr)
                               or (f == "nobud_foiz" and (p.nobud_foiz or 0) > norm_nobud)
                               else "strong" if f == "joriy_son" else ""))
        tirik = sum(partiyalar.mapped("joriy_son"))
        return self._detail(
            title, "fa-home", color, subtitle=subtitle,
            stats=[self._stat(_("Partiyalar"), len(partiyalar), "int"),
                   self._stat(_("Tirik bosh"), tirik, "int"),
                   self._stat(_("Tirik vazn"), sum(partiyalar.mapped("jami_tirik_vazn")), "kg"),
                   self._stat(_("O'rtacha FCR"),
                              self._weighted(partiyalar, "fcr", "joriy_son"), "coef"),
                   self._stat(_("Nobud (bosh)"), sum(partiyalar.mapped("nobud_son")), "int")],
            columns=columns, rows=rows,
            action=self._act("agronova.boquv.partiya", [("id", "in", partiyalar.ids)], title))

    def _detail_boquv_partiyalar(self, ctx, ref):
        partiyalar = self._boquv_partiyalar()
        if partiyalar is None:
            return self._detail(_("Boquv"), "fa-home")
        fid = self._ref_id(ref)
        title = _("Faol boquv partiyalari")
        if fid:
            partiyalar = partiyalar.filtered(lambda p: p.filial_id.id == fid)
            if partiyalar:
                title = _("%s — faol partiyalar", partiyalar[0].filial_id.display_name)
        return self._partiya_table(partiyalar, title)

    def _detail_boquv_ogish(self, ctx, ref):
        partiyalar = self._boquv_partiyalar() or self.env["agronova.boquv.partiya"].browse()
        nf, nn = self._norm("fcr"), self._norm("nobud")
        yomon = partiyalar.filtered(lambda p: (p.fcr or 0) > nf or (p.nobud_foiz or 0) > nn
                                    or p.ogish_bormi)
        return self._partiya_table(yomon.sorted(lambda p: -(p.fcr or 0)),
                                   _("Normativdan og'gan partiyalar"),
                                   _("FCR > %s yoki nobud > %s%%", nf, nn), "red")

    def _detail_boquv_nobud(self, ctx, ref):
        partiyalar = self._boquv_partiyalar() or self.env["agronova.boquv.partiya"].browse()
        return self._partiya_table(partiyalar.sorted(lambda p: -(p.nobud_foiz or 0)),
                                   _("Nobudgarchilik bo'yicha partiyalar"), color="red")

    def _detail_boquv_partiya(self, ctx, ref):
        Partiya = self._model("agronova.boquv.partiya")
        p = Partiya.browse(self._ref_id(ref)).exists() if Partiya is not None else None
        if not p:
            return self._detail(_("Partiya topilmadi"), "fa-home")
        nf, nn, nv = self._norm("fcr"), self._norm("nobud"), self._norm("vazn")
        # Partiyaning butun hayoti — davrdan qat'i nazar.
        start = p.joja_sana or p.ochilish_sana or ctx["d_from"]
        end = p.yopilish_sana or fields.Date.context_today(self)
        life = self._ctx_for(min(start, end), end)
        jurnallar = self.env["agronova.boquv.jurnal"].sudo().search(
            [("partiya_id", "=", p.id)], order="sana desc")
        nobud_s, yem_s = defaultdict(float), defaultdict(float)
        for j in jurnallar:
            nobud_s[j.sana] += j.nobud_son or 0
            yem_s[j.sana] += j.yem_kg or 0.0
        cols = [("sana", _("Sana"), "date"), ("kun_boshi_son", _("Kun boshi"), "int"),
                ("nobud_son", _("Nobud"), "int"), ("kun_oxiri_son", _("Kun oxiri"), "int"),
                ("yem_kg", _("Yem, kg"), "kg"), ("suv_litr", _("Suv, l"), "qty"),
                ("harorat", _("Harorat °C"), "qty"), ("mas_ul_id", _("Mas'ul"), "m2o")]
        columns, rows = self._rows_table(
            jurnallar, cols, tone=lambda j, f: "danger" if f == "nobud_son" and j.nobud_son else "")
        stats = [
            self._stat(_("Filial / bino"), "%s / %s" % (p.filial_id.name or "—",
                                                        p.bino_id.name or "—"), None),
            self._stat(_("Yoshi"), _("%s / %s kun", p.yosh_kun or 0, p.reja_kun or 0), None),
            self._stat(_("Boshlang'ich"), p.boshlangich_son, "int"),
            self._stat(_("Tirik"), p.joriy_son, "int", tone="strong"),
            self._stat(_("Nobud"), p.nobud_foiz, "pct",
                       tone="bad" if (p.nobud_foiz or 0) > nn else "ok",
                       hint=_("%s bosh · norma %s%%", p.nobud_son or 0, nn)),
            self._stat(_("FCR"), p.fcr, "coef", tone="bad" if (p.fcr or 0) > nf else "ok",
                       hint=_("norma %s", nf)),
            self._stat(_("O'rtacha vazn"), p.ortacha_vazn, "kg",
                       tone="ok" if (p.ortacha_vazn or 0) >= nv else "",
                       hint=_("norma %s kg", nv)),
            self._stat(_("Kunlik o'sish"), _("%s g", round(p.kunlik_osish_gr or 0, 1)), None),
            self._stat(_("EPEF"), p.epef, "qty"),
            self._stat(_("Yem sarfi"), p.yem_sarf_kg, "kg"),
            self._stat(_("Jami xarajat"), p.jami_xarajat),
            self._stat(_("1 kg tannarx"), p.tannarx_1_kg),
            self._stat(_("Foyda / zarar"), p.foyda, tone="ok" if (p.foyda or 0) >= 0 else "bad"),
        ]
        return self._detail(
            _("Partiya %s", p.name), "fa-home", "green",
            subtitle=_("Brigadir: %s", p.brigadir_id.display_name or "—"),
            stats=stats,
            # Nobud va yem birliklari har xil — alohida grafiklar.
            chart=self._trend_panel(_("Kunlik nobud (bosh)"), "fa-heartbeat", life,
                                    nobud_s, label_a=_("Nobud"), value_fmt="int"),
            split=None,
            columns=columns, rows=rows,
            message=_("Bu partiya bo'yicha kunlik jurnal hali kiritilmagan."),
            action={"res_model": "agronova.boquv.partiya", "res_id": p.id, "name": p.name})

    # ==================================================================
    # ONA TOVUQ / INKUBATORIYA / SO'YISH / YEM / QX / TRANSPORT
    # ==================================================================
    def _detail_ona_jurnal(self, ctx, ref):
        Jurnal = self._model("agronova.ona_tovuq.jurnal.tuxum")
        domain = [("date", ">=", ctx["d_from_s"]), ("date", "<=", ctx["d_to_s"])] \
            + self._company_domain(Jurnal)
        sid = self._ref_id(ref)
        if sid:
            domain.append(("sex_id", "=", sid))
        recs = Jurnal.search(domain, order="date desc")
        norm = self._norm("tuxum_berish")
        kunlik = defaultdict(float)
        for j in recs:
            kunlik[j.date] += j.jami_tuxum or 0
        cols = [("date", _("Sana"), "date"), ("partiya_id", _("Partiya"), "m2o"),
                ("sex_id", _("Sex"), "m2o"), ("tovuq_son", _("Tovuq"), "int"),
                ("jami_tuxum", _("Tuxum"), "int"), ("sifatli_tuxum", _("Sifatli"), "int"),
                ("brak_tuxum", _("Brak"), "int"),
                ("inkubatsiyaga_yarokli", _("Inkubatsiyaga"), "int"),
                ("tuxum_berish_foiz", _("Berish %"), "pct")]
        columns, rows = self._rows_table(
            recs, cols,
            tone=lambda j, f: "danger" if f == "tuxum_berish_foiz" and
            (j.tuxum_berish_foiz or 0) < norm else ("strong" if f == "jami_tuxum" else ""))
        jami = sum(recs.mapped("jami_tuxum"))
        return self._detail(
            _("Tuxum jurnali"), "fa-circle", "orange",
            subtitle=recs[:1].sex_id.display_name if sid and recs else "",
            stats=[self._stat(_("Jurnal kunlari"), len(recs), "int"),
                   self._stat(_("Jami tuxum"), jami, "int"),
                   self._stat(_("Sifatli"), sum(recs.mapped("sifatli_tuxum")), "int", tone="ok"),
                   self._stat(_("Brak"), sum(recs.mapped("brak_tuxum")), "int", tone="bad"),
                   self._stat(_("O'rtacha berish"),
                              self._ortacha(recs.mapped("tuxum_berish_foiz")), "pct",
                              hint=_("norma %s%%", norm))],
            chart=self._trend_panel(_("Kunlik tuxum"), "fa-bar-chart", ctx, kunlik,
                                    label_a=_("Tuxum"), value_fmt="int"),
            columns=columns, rows=rows,
            action=self._act(Jurnal._name, domain, _("Tuxum jurnali")))

    def _detail_ona_partiyalar(self, ctx, ref):
        Partiya = self._model("agronova.ona_tovuq.partiya.tuxum")
        if Partiya is None:
            return self._detail(_("Ona tovuq partiyalari"), "fa-folder-open")
        domain = [("holat", "=", "active")] + self._company_domain(Partiya)
        recs = Partiya.search(domain)
        cols = [("display_name", _("Partiya"), "text"), ("ochilish_sana", _("Ochilgan"), "date"),
                ("yosh_hafta", _("Yosh, hafta"), "int"), ("tovuq_son", _("Tovuq"), "int"),
                ("xoroz_son", _("Xo'roz"), "int"), ("jami_tuxum", _("Jami tuxum"), "int"),
                ("inkubatsiyaga_yarokli", _("Inkubatsiyaga"), "int")]
        columns, rows = self._rows_table(recs, cols)
        return self._detail(
            _("Faol ona tovuq partiyalari"), "fa-folder-open", "blue",
            stats=[self._stat(_("Partiyalar"), len(recs), "int"),
                   self._stat(_("Tovuq"), sum(recs.mapped("tovuq_son")), "int"),
                   self._stat(_("Xo'roz"), sum(recs.mapped("xoroz_son")), "int"),
                   self._stat(_("Jami tuxum"), sum(recs.mapped("jami_tuxum")), "int")],
            columns=columns, rows=rows, action=self._act(Partiya._name, domain, _("Partiyalar")))

    def _detail_ink_ochilish(self, ctx, ref):
        Ochilish = self._model("agronova.ink.ochilish")
        domain = [("holat", "=", "done"), ("sana", ">=", ctx["d_from_s"]),
                  ("sana", "<=", ctx["d_to_s"])] + self._company_domain(Ochilish)
        pid = self._ref_id(ref)
        if pid:
            domain.append(("partiya_id", "=", pid))
        recs = Ochilish.search(domain, order="sana desc")
        joja = sum(recs.mapped("ochilgan_joja"))
        qoy = joja + sum(recs.mapped("ochilmagan_tuxum"))
        kunlik = defaultdict(float)
        for o in recs:
            kunlik[o.sana] += o.ochilgan_joja or 0
        cols = [("name", _("Hujjat"), "text"), ("sana", _("Sana"), "date"),
                ("partiya_id", _("Partiya"), "m2o"), ("ochilgan_joja", _("Ochilgan"), "int"),
                ("ochilmagan_tuxum", _("Ochilmagan"), "int"), ("nobud_son", _("Nobud"), "int"),
                ("brak_son", _("Brak"), "int"), ("sof_joja", _("Yaroqli"), "int")]
        columns, rows = self._rows_table(recs, cols)
        return self._detail(
            _("Jo'ja ochilishi"), "fa-child", "green",
            stats=[self._stat(_("Hujjatlar"), len(recs), "int"),
                   self._stat(_("Ochilgan"), joja, "int"),
                   self._stat(_("Ochilish %"), (joja / qoy * 100) if qoy else 0.0, "pct",
                              hint=_("norma %s%%", self._norm("ochilish"))),
                   self._stat(_("Yaroqli"), sum(recs.mapped("sof_joja")), "int", tone="ok"),
                   self._stat(_("Nobud + brak"),
                              sum(recs.mapped("nobud_son")) + sum(recs.mapped("brak_son")),
                              "int", tone="bad")],
            chart=self._trend_panel(_("Kunlik ochilish"), "fa-bar-chart", ctx, kunlik,
                                    label_a=_("Jo'ja"), value_fmt="int"),
            columns=columns, rows=rows, action=self._act(Ochilish._name, domain, _("Ochilishlar")))

    def _detail_ink_partiyalar(self, ctx, ref):
        Partiya = self._model("agronova.ink.partiya")
        if Partiya is None:
            return self._detail(_("Inkubatsiya partiyalari"), "fa-life-ring")
        domain = [("holat", "=", "inkubatsiyada")] + self._company_domain(Partiya)
        recs = Partiya.search(domain, order="sana_kutilayotgan")
        today = fields.Date.context_today(self)
        cols = [("name", _("Partiya"), "text"), ("inkubator_id", _("Inkubator"), "m2o"),
                ("sana_qoyilgan", _("Qo'yilgan"), "date"),
                ("sana_kutilayotgan", _("Kutilayotgan ochilish"), "date"),
                ("tuxum_dona", _("Tuxum"), "int"), ("tuxum_qiymat", _("Qiymati"), "money")]
        columns, rows = self._rows_table(
            recs, cols, tone=lambda r, f: "danger" if f == "sana_kutilayotgan" and
            r.sana_kutilayotgan and r.sana_kutilayotgan < today else "")
        return self._detail(
            _("Inkubatsiyadagi partiyalar"), "fa-life-ring", "blue",
            stats=[self._stat(_("Partiyalar"), len(recs), "int"),
                   self._stat(_("Tuxum"), sum(recs.mapped("tuxum_dona")), "int"),
                   self._stat(_("Bugun/ertaga ochiladi"),
                              len(recs.filtered(lambda r: r.sana_kutilayotgan and
                                                r.sana_kutilayotgan <= today
                                                + relativedelta(days=1))), "int")],
            columns=columns, rows=rows, action=self._act(Partiya._name, domain, _("Partiyalar")))

    def _detail_soyish_jarayonlar(self, ctx, ref):
        Jarayon = self._model("agronova.soyish.jarayon")
        domain = [("holat", "=", "done"), ("sana", ">=", ctx["d_from_s"]),
                  ("sana", "<=", ctx["d_to_s"])] + self._company_domain(Jarayon)
        recs = Jarayon.search(domain, order="sana desc")
        norm = self._norm("soyish_chiqim")
        kunlik = defaultdict(float)
        for j in recs:
            kunlik[j.sana] += j.tushka_vazn_kg or 0.0
        cols = [("name", _("Hujjat"), "text"), ("sana", _("Sana"), "date"),
                ("soyilgan_son", _("So'yilgan"), "int"), ("nobud_son", _("Nobud/brak"), "int"),
                ("tushka_vazn_kg", _("Tushka"), "kg"), ("chiqim_foiz", _("Chiqim"), "pct"),
                ("tirik_qiymat", _("Tirik qiymati"), "money")]
        columns, rows = self._rows_table(
            recs, cols, tone=lambda j, f: "danger" if f == "chiqim_foiz" and
            (j.chiqim_foiz or 0) < norm else "")
        return self._detail(
            _("So'yish jarayonlari"), "fa-cutlery", "orange",
            stats=[self._stat(_("Hujjatlar"), len(recs), "int"),
                   self._stat(_("So'yilgan bosh"), sum(recs.mapped("soyilgan_son")), "int"),
                   self._stat(_("Tushka"), sum(recs.mapped("tushka_vazn_kg")), "kg"),
                   self._stat(_("O'rtacha chiqim"), self._ortacha(recs.mapped("chiqim_foiz")),
                              "pct", hint=_("norma %s%%", norm))],
            chart=self._trend_panel(_("Kunlik tushka"), "fa-bar-chart", ctx, kunlik,
                                    label_a=_("Tushka"), value_fmt="kg"),
            columns=columns, rows=rows, action=self._act(Jarayon._name, domain, _("So'yish")))

    def _detail_mrp_orders(self, ctx, ref):
        Mrp = self.env["mrp.production"].sudo()
        domain = [("state", "=", "done"), ("date_start", ">=", ctx["dt_from_s"]),
                  ("date_start", "<=", ctx["dt_to_s"]), ("company_id", "in", ctx["companies"])]
        recs = Mrp.search(domain, order="date_start desc", limit=MAX_ROWS)
        total = Mrp.search_count(domain)
        kunlik = defaultdict(float)
        for b in recs:
            if b.date_start:
                kunlik[b.date_start.date()] += b.agronova_miqdor_kg or 0.0
        kg = sum(recs.mapped("agronova_miqdor_kg"))
        cols = [("name", _("Buyurtma"), "text"), ("date_start", _("Sana"), "datetime"),
                ("product_id", _("Mahsulot"), "m2o"), ("agronova_miqdor_kg", _("Miqdor"), "kg"),
                ("agronova_jami_tannarx", _("Tannarx"), "money"),
                ("agronova_tannarx_1_kg", _("1 kg fakt"), "money"),
                ("agronova_reja_tannarx_1_kg", _("1 kg reja"), "money"),
                ("agronova_chetlanish", _("Chetlanish"), "pct")]
        columns, rows = self._rows_table(
            recs, cols, tone=lambda b, f: ("danger" if (b.agronova_chetlanish or 0) > 0 else "ok")
            if f == "agronova_chetlanish" else "")
        return self._detail(
            _("Yem ishlab chiqarish buyurtmalari"), "fa-industry", "blue",
            stats=[self._stat(_("Buyurtmalar"), total, "int"),
                   self._stat(_("Hajm"), kg / 1000.0, "ton"),
                   self._stat(_("Jami tannarx"), sum(recs.mapped("agronova_jami_tannarx"))),
                   self._stat(_("1 kg o'rtacha"),
                              (sum(recs.mapped("agronova_jami_tannarx")) / kg) if kg else 0.0)],
            chart=self._trend_panel(_("Kunlik hajm"), "fa-bar-chart", ctx, kunlik,
                                    label_a=_("Yem"), value_fmt="kg"),
            columns=columns, rows=rows, total=total,
            action=self._act("mrp.production", domain, _("Buyurtmalar")))

    def _detail_qx_partiyalar(self, ctx, ref):
        Partiya = self._model("agronova.qx.partiya")
        domain = [("holat", "=", "active")] + self._company_domain(Partiya)
        recs = Partiya.search(domain)
        cols = [("name", _("Partiya"), "text"), ("ekin_id", _("Ekin"), "m2o"),
                ("yer_id", _("Yer"), "m2o"), ("ekish_sana", _("Ekilgan"), "date"),
                ("maydoni_ga", _("Maydon"), "ga"), ("olingan_hosil_kg", _("Hosil"), "kg"),
                ("hosildorlik", _("kg/ga"), "qty"), ("reja_bajarilishi", _("Reja"), "pct"),
                ("qoldiq_kg", _("Qoldiq"), "kg")]
        columns, rows = self._rows_table(recs, cols, row_detail=lambda p: self._det("qx_partiya", p.id))
        return self._detail(
            _("Faol ekin partiyalari"), "fa-leaf", "green",
            stats=[self._stat(_("Partiyalar"), len(recs), "int"),
                   self._stat(_("Maydon"), sum(recs.mapped("maydoni_ga")), "ga"),
                   self._stat(_("Hosil"), sum(recs.mapped("olingan_hosil_kg")), "kg")],
            columns=columns, rows=rows, action=self._act(Partiya._name, domain, _("Partiyalar")))

    def _detail_qx_partiya(self, ctx, ref):
        Partiya = self._model("agronova.qx.partiya")
        p = Partiya.browse(self._ref_id(ref)).exists() if Partiya is not None else None
        if not p:
            return self._detail(_("Partiya topilmadi"), "fa-leaf")
        return self._detail(
            _("Ekin partiyasi %s", p.name), "fa-leaf", "green",
            subtitle="%s · %s" % (p.ekin_id.display_name or "—", p.yer_id.display_name or "—"),
            stats=[self._stat(_("Maydon"), p.maydoni_ga, "ga"),
                   self._stat(_("Ekilgan"), format_date(self.env, p.ekish_sana)
                              if p.ekish_sana else "—", None),
                   self._stat(_("Reja hosil"), p.reja_hosil_kg, "kg"),
                   self._stat(_("Olingan hosil"), p.olingan_hosil_kg, "kg", tone="strong"),
                   self._stat(_("Hosildorlik"), p.hosildorlik, "qty", hint=_("kg/ga")),
                   self._stat(_("Reja bajarilishi"), p.reja_bajarilishi, "pct",
                              tone="ok" if (p.reja_bajarilishi or 0) >= 100 else "bad"),
                   self._stat(_("Berilgan"), p.berilgan_kg, "kg"),
                   self._stat(_("Qoldiq"), p.qoldiq_kg, "kg"),
                   self._stat(_("Jami xarajat"), p.jami_xarajat),
                   self._stat(_("1 kg tannarx"), p.tannarx_1_kg)],
            action={"res_model": p._name, "res_id": p.id, "name": p.name})

    def _detail_trips(self, ctx, ref):
        Trip = self._model("agronova.trip")
        domain = [("date", ">=", ctx["d_from_s"]), ("date", "<=", ctx["d_to_s"])] \
            + self._company_domain(Trip)
        did = self._ref_id(ref)
        if did:
            domain.append(("driver_id", "=", did))
        recs = Trip.search(domain, order="date desc")
        ds, xs = defaultdict(float), defaultdict(float)
        for r in recs:
            if r.date:
                ds[r.date] += r.revenue or 0.0
                xs[r.date] += r.expense_total or 0.0
        cols = [("date", _("Sana"), "date"), ("name", _("Reys"), "text"),
                ("driver_id", _("Haydovchi"), "m2o"), ("trip_type", _("Turi"), "sel"),
                ("distance_km", _("Km"), "qty"), ("cargo_weight_ton", _("Yuk"), "ton"),
                ("revenue", _("Daromad"), "money"), ("expense_total", _("Xarajat"), "money"),
                ("profit", _("Foyda"), "money"), ("state", _("Holat"), "sel")]
        columns, rows = self._rows_table(
            recs, cols, tone=lambda r, f: ("danger" if (r.profit or 0) < 0 else "ok")
            if f == "profit" else "")
        foyda = sum(recs.mapped("profit"))
        return self._detail(
            _("Reyslar"), "fa-truck", "blue",
            subtitle=recs[:1].driver_id.display_name if did and recs else "",
            stats=[self._stat(_("Reyslar"), len(recs), "int"),
                   self._stat(_("Daromad"), sum(recs.mapped("revenue")), tone="ok"),
                   self._stat(_("Xarajat"), sum(recs.mapped("expense_total")), tone="bad"),
                   self._stat(_("Foyda"), foyda, tone="ok" if foyda >= 0 else "bad"),
                   self._stat(_("Masofa"), sum(recs.mapped("distance_km")), "qty",
                              hint=_("km"))],
            chart=self._trend_panel(_("Kunlar kesimida"), "fa-bar-chart", ctx, ds, xs,
                                    label_a=_("Daromad"), label_b=_("Xarajat")),
            columns=columns, rows=rows, action=self._act("agronova.trip", domain, _("Reyslar")))

    # ==================================================================
    # XARID
    # ==================================================================
    def _kirim_detail(self, ctx, domain, title, subtitle=""):
        Kirim = self._model("agronova.kirim")
        recs = Kirim.search(domain, order="sotib_olingan_sana desc, id desc")
        series = defaultdict(float)
        for k in recs:
            if k.sotib_olingan_sana:
                series[k.sotib_olingan_sana] += k.jami_summa or 0.0
        jami = sum(recs.mapped("jami_summa"))
        tolangan = sum(recs.mapped("tolangan_summa"))
        cols = [("name", _("Kirim"), "text"), ("sotib_olingan_sana", _("Sana"), "date"),
                ("kontragent_id", _("Ta'minotchi"), "m2o"), ("zakupchik_id", _("Zakupchik"), "m2o"),
                ("jami_summa", _("Summa"), "money"), ("tolangan_summa", _("To'langan"), "money"),
                ("ogish_foizi", _("Narx og'ishi"), "pct"), ("holat", _("Holat"), "sel")]
        columns, rows = self._rows_table(
            recs, cols,
            tone=lambda k, f: ("danger" if f == "ogish_foizi" and k.ogish_chegara
                               and (k.ogish_foizi or 0) > k.ogish_chegara else
                               "strong" if f == "jami_summa" else ""))
        return self._detail(
            title, "fa-shopping-basket", "blue", subtitle=subtitle,
            stats=[self._stat(_("Kirimlar"), len(recs), "int"),
                   self._stat(_("Jami"), jami),
                   self._stat(_("To'langan"), tolangan, tone="ok"),
                   self._stat(_("Qarz"), max(jami - tolangan, 0.0),
                              tone="bad" if jami > tolangan else ""),
                   self._stat(_("O'rtacha ball"), self._ortacha(recs.mapped("ball_ortacha")),
                              "qty")],
            chart=self._trend_panel(_("Kunlar kesimida"), "fa-bar-chart", ctx, series,
                                    label_a=_("Xarid")),
            columns=columns, rows=rows, action=self._act("agronova.kirim", domain, title))

    def _kirim_base(self, ctx):
        Kirim = self._model("agronova.kirim")
        return [("holat", "!=", "bekor"), ("sotib_olingan_sana", ">=", ctx["d_from_s"]),
                ("sotib_olingan_sana", "<=", ctx["d_to_s"])] + self._company_domain(Kirim)

    def _detail_zk_kirimlar(self, ctx, ref):
        domain = self._kirim_base(ctx)
        title = _("Xarid kirimlari")
        if ref == "qarz":
            # Qarz: to'lanmagan qismi borlari — Python'da filtrlanadi (maydonlar farqi).
            Kirim = self._model("agronova.kirim")
            ids = Kirim.search(domain).filtered(
                lambda k: (k.jami_summa or 0) > (k.tolangan_summa or 0)).ids
            domain = [("id", "in", ids)]
            title = _("To'lanmagan xaridlar")
        elif ref == "ogish":
            Kirim = self._model("agronova.kirim")
            ids = Kirim.search(domain).filtered(
                lambda k: k.ogish_chegara and (k.ogish_foizi or 0) > k.ogish_chegara).ids
            domain = [("id", "in", ids)]
            title = _("Narxi chegaradan oshgan xaridlar")
        elif isinstance(ref, str) and ref in ("draft", "tasdiqlangan", "qabul_qilindi"):
            domain = domain + [("holat", "=", ref)]
        return self._kirim_detail(ctx, domain, title)

    def _detail_zk_kontragent(self, ctx, ref):
        pid = self._ref_id(ref)
        partner = self.env["res.partner"].sudo().browse(pid).exists()
        return self._kirim_detail(ctx, self._kirim_base(ctx) + [("kontragent_id", "=", pid)],
                                  partner.display_name or _("Ta'minotchi"),
                                  _("Davrdagi xaridlar"))

    def _detail_zk_zayavkalar(self, ctx, ref):
        Zayavka = self._model("agronova.zayavka")
        if Zayavka is None:
            return self._detail(_("Zayavkalar"), "fa-list-alt")
        domain = [("holat", "in", ["zakupchikka_yuborildi", "qabul_qilindi", "qisman_bajarildi"])] \
            + self._company_domain(Zayavka)
        now = fields.Datetime.now()
        if ref == "kech":
            domain = domain + [("holat", "=", "zakupchikka_yuborildi"),
                               ("javob_muddati", "<", fields.Datetime.to_string(now))]
        recs = Zayavka.search(domain, order="sana desc")
        cols = [("name", _("Zayavka"), "text"), ("sana", _("Sana"), "date"),
                ("warehouse_id", _("Ombor"), "m2o"), ("zakupchik_id", _("Zakupchik"), "m2o"),
                ("muhimlik_darajasi", _("Muhimlik"), "sel"), ("holat", _("Holat"), "sel"),
                ("javob_muddati", _("Javob muddati"), "datetime"),
                ("bajarilish_foizi", _("Bajarilish"), "pct")]
        columns, rows = self._rows_table(
            recs, cols, tone=lambda z, f: "danger" if f == "javob_muddati" and z.javob_muddati
            and z.javob_muddati < now and z.holat == "zakupchikka_yuborildi" else "")
        return self._detail(
            _("Muddati o'tgan zayavkalar") if ref == "kech" else _("Ochiq zayavkalar"),
            "fa-list-alt", "indigo",
            stats=[self._stat(_("Zayavkalar"), len(recs), "int"),
                   self._stat(_("O'rtacha bajarilish"),
                              self._ortacha(recs.mapped("bajarilish_foizi")), "pct")],
            columns=columns, rows=rows, action=self._act("agronova.zayavka", domain, _("Zayavkalar")))

    # ==================================================================
    # POS / OMBOR / ISH HAQI / DAVOMAT
    # ==================================================================
    def _detail_pos_orders(self, ctx, ref):
        Order = self._model("pos.order")
        domain = self._pos_domain(ctx)
        cid = self._ref_id(ref)
        if cid:
            domain.append(("config_id", "=", cid))
        recs = Order.search(domain, order="date_order desc", limit=MAX_ROWS)
        total = Order.search_count(domain)
        jami_rows = Order._read_group(domain, [], ["amount_total:sum"])
        jami = (jami_rows[0][0] if jami_rows else 0.0) or 0.0
        series = defaultdict(float)
        for day, amount in Order._read_group(domain, ["date_order:day"], ["amount_total:sum"]):
            if day:
                series[fields.Date.to_date(day)] += amount or 0.0
        cols = [("name", _("Chek"), "text"), ("date_order", _("Vaqt"), "datetime"),
                ("config_id", _("Do'kon"), "m2o"), ("partner_id", _("Mijoz"), "m2o"),
                ("amount_total", _("Summa"), "money"), ("state", _("Holat"), "sel")]
        columns, rows = self._rows_table(recs, cols)
        return self._detail(
            _("Do'kon cheklari"), "fa-shopping-cart", "blue",
            stats=[self._stat(_("Cheklar"), total, "int"),
                   self._stat(_("Savdo"), jami, tone="strong"),
                   self._stat(_("O'rtacha chek"), (jami / total) if total else 0.0)],
            chart=self._trend_panel(_("Kunlik savdo"), "fa-bar-chart", ctx, series,
                                    label_a=_("Savdo")),
            columns=columns, rows=rows, total=total,
            action=self._act("pos.order", domain, _("Cheklar")))

    def _detail_pos_products(self, ctx, ref):
        Order = self._model("pos.order")
        Line = self._model("pos.order.line")
        orders = Order.search(self._pos_domain(ctx))
        data = Line._read_group([("order_id", "in", orders.ids)], ["product_id"],
                                ["qty:sum", "price_subtotal_incl:sum"],
                                order="price_subtotal_incl:sum desc") if orders else []
        rows = [{"cells": [{"text": p.display_name or "—"},
                           {"text": self._fmt(q, "qty"), "align": "right"},
                           {"text": self._fmt(s), "align": "right", "tone": "strong"}],
                 "open": {"res_model": "product.product", "res_id": p.id} if p else None}
                for p, q, s in data[:MAX_ROWS]]
        return self._detail(
            _("Sotilgan mahsulotlar"), "fa-cubes", "orange",
            stats=[self._stat(_("Mahsulot turlari"), len(data), "int"),
                   self._stat(_("Jami savdo"), sum(s for _p, _q, s in data))],
            columns=[{"label": _("Mahsulot")}, {"label": _("Miqdor"), "align": "right"},
                     {"label": _("Summa"), "align": "right"}],
            rows=rows)

    def _detail_ombor_quants(self, ctx, ref):
        Quant = self._model("stock.quant")
        domain = [("location_id.usage", "=", "internal")] + self._company_domain(Quant)
        title = _("Ombor qoldiqlari")
        if ref == "manfiy":
            domain.append(("quantity", "<", 0))
            title = _("Manfiy qoldiqlar")
        else:
            wid = self._ref_id(ref)
            if wid:
                domain.append(("location_id.warehouse_id", "=", wid))
                wh = self.env["stock.warehouse"].sudo().browse(wid).exists()
                title = _("%s — qoldiqlar", wh.display_name)
        recs = Quant.search(domain, limit=5000).sorted(lambda q: -(q.value or 0.0))
        cols = [("product_id", _("Mahsulot"), "m2o"), ("location_id", _("Joy"), "m2o"),
                ("lot_id", _("Lot"), "m2o"), ("quantity", _("Miqdor"), "qty"),
                ("product_uom_id", _("O'lchov"), "m2o"), ("value", _("Qiymati"), "money")]
        columns, rows = self._rows_table(
            recs, cols, open_record=False,
            tone=lambda q, f: "danger" if f == "quantity" and q.quantity < 0 else "")
        return self._detail(
            title, "fa-cubes", "blue",
            stats=[self._stat(_("Qoldiq qatorlari"), len(recs), "int"),
                   self._stat(_("Mahsulotlar"), len(recs.mapped("product_id")), "int"),
                   self._stat(_("Jami qiymat"), sum(recs.mapped("value")), tone="strong")],
            columns=columns, rows=rows, total=len(recs),
            action=self._act("stock.quant", domain, title))

    def _detail_ombor_muddat(self, ctx, ref):
        Quant = self._model("stock.quant")
        limit = datetime.combine(fields.Date.context_today(self) + relativedelta(days=7), time.max)
        domain = [("location_id.usage", "=", "internal"), ("quantity", ">", 0),
                  ("lot_id.expiration_date", "!=", False),
                  ("lot_id.expiration_date", "<=", fields.Datetime.to_string(limit))] \
            + self._company_domain(Quant)
        recs = Quant.search(domain).sorted(lambda q: q.lot_id.expiration_date)
        now = fields.Datetime.now()
        cols = [("product_id", _("Mahsulot"), "m2o"), ("lot_id", _("Lot"), "m2o"),
                ("lot_id.expiration_date", _("Yaroqlilik muddati"), "datetime"),
                ("quantity", _("Miqdor"), "qty"), ("location_id", _("Joy"), "m2o"),
                ("value", _("Qiymati"), "money")]
        columns, rows = self._rows_table(
            recs, cols, open_record=False,
            tone=lambda q, f: "danger" if f == "lot_id.expiration_date"
            and q.lot_id.expiration_date < now else "")
        otgan = recs.filtered(lambda q: q.lot_id.expiration_date < now)
        return self._detail(
            _("Muddati tugayotgan lotlar"), "fa-clock-o", "red",
            subtitle=_("7 kun ichida yoki allaqachon muddati o'tgan"),
            stats=[self._stat(_("Lotlar"), len(recs), "int"),
                   self._stat(_("Muddati o'tgan"), len(otgan), "int",
                              tone="bad" if otgan else "ok"),
                   self._stat(_("Xavf ostidagi qiymat"), sum(recs.mapped("value")), tone="bad")],
            columns=columns, rows=rows, action=self._act("stock.quant", domain, _("Lotlar")))

    def _detail_ish_haqi_davrlar(self, ctx, ref):
        Davr = self._model("agronova.ish_haqi.davr")
        domain = [("holat", "=", "posted"), ("davr_boshi", "<=", ctx["d_to_s"]),
                  ("davr_oxiri", ">=", ctx["d_from_s"])] + self._company_domain(Davr)
        recs = Davr.search(domain, order="davr_boshi desc")
        cols = [("display_name", _("Hujjat"), "text"), ("davr_boshi", _("Boshi"), "date"),
                ("davr_oxiri", _("Oxiri"), "date"), ("xodim_soni", _("Xodim"), "int"),
                ("jami_hisoblangan", _("Hisoblangan"), "money"), ("jami_bonus", _("Bonus"), "money"),
                ("jami_avans", _("Avans"), "money"), ("jami_jarima", _("Jarima"), "money"),
                ("jami_qolga", _("Qo'lga"), "money")]
        columns, rows = self._rows_table(recs, cols)
        return self._detail(
            _("Ish haqi hujjatlari"), "fa-calculator", "blue",
            stats=[self._stat(_("Hujjatlar"), len(recs), "int"),
                   self._stat(_("Hisoblangan"), sum(recs.mapped("jami_hisoblangan"))),
                   self._stat(_("Qo'lga tegadi"), sum(recs.mapped("jami_qolga")), tone="strong")],
            columns=columns, rows=rows, action=self._act(Davr._name, domain, _("Ish haqi")))

    def _detail_ish_haqi_qatorlar(self, ctx, ref):
        Davr = self._model("agronova.ish_haqi.davr")
        Qator = self._model("agronova.ish_haqi.davr.qator")
        davrlar = Davr.search([("holat", "=", "posted"), ("davr_boshi", "<=", ctx["d_to_s"]),
                               ("davr_oxiri", ">=", ctx["d_from_s"])] + self._company_domain(Davr))
        domain = [("davr_id", "in", davrlar.ids)]
        did = self._ref_id(ref)
        if did:
            domain.append(("department_id", "=", did))
        recs = Qator.search(domain).sorted(lambda q: -(q.qolga or 0.0))
        cols = [("employee_id", _("Xodim"), "m2o"), ("department_id", _("Bo'lim"), "m2o"),
                ("tarif_id", _("Tarif"), "m2o"), ("ishlagan_kun", _("Kun"), "qty"),
                ("hisoblangan", _("Hisoblangan"), "money"), ("bonus", _("Bonus"), "money"),
                ("avans", _("Avans"), "money"), ("jarima", _("Jarima"), "money"),
                ("qolga", _("Qo'lga"), "money")]
        columns, rows = self._rows_table(recs, cols, open_record=False)
        return self._detail(
            _("Xodimlar bo'yicha ish haqi"), "fa-users", "green",
            subtitle=recs[:1].department_id.display_name if did and recs else "",
            stats=[self._stat(_("Xodimlar"), len(recs.mapped("employee_id")), "int"),
                   self._stat(_("Hisoblangan"), sum(recs.mapped("hisoblangan"))),
                   self._stat(_("Bonus"), sum(recs.mapped("bonus")), tone="ok"),
                   self._stat(_("Jarima"), sum(recs.mapped("jarima")), tone="bad"),
                   self._stat(_("Qo'lga tegadi"), sum(recs.mapped("qolga")), tone="strong")],
            columns=columns, rows=rows)

    def _detail_xodim_balans(self, ctx, ref):
        Emp = self.env["hr.employee"].sudo()
        if "agronova_balans" not in Emp._fields:
            return self._detail(_("Xodimlar balansi"), "fa-balance-scale")
        recs = Emp.search([("active", "=", True)] + self._company_domain(Emp)).filtered(
            lambda e: e.agronova_balans).sorted(lambda e: -(e.agronova_balans or 0.0))
        cols = [("name", _("Xodim"), "text"), ("department_id", _("Bo'lim"), "m2o"),
                ("agronova_hisoblandi", _("Hisoblandi"), "money"),
                ("agronova_berildi", _("Berildi"), "money"), ("agronova_balans", _("Qoldiq"), "money")]
        columns, rows = self._rows_table(
            recs, cols, tone=lambda e, f: ("ok" if e.agronova_balans >= 0 else "danger")
            if f == "agronova_balans" else "")
        return self._detail(
            _("Xodimlar bilan hisob-kitob"), "fa-balance-scale", "indigo",
            subtitle=_("Musbat — korxona xodimga qarzdor, manfiy — xodim korxonaga"),
            stats=[self._stat(_("Xodimlar"), len(recs), "int"),
                   self._stat(_("Korxona qarzi"),
                              sum(e.agronova_balans for e in recs if e.agronova_balans > 0)),
                   self._stat(_("Xodimlar qarzi"),
                              abs(sum(e.agronova_balans for e in recs if e.agronova_balans < 0)),
                              tone="bad")],
            columns=columns, rows=rows)

    def _detail_davomat(self, ctx, ref):
        Att = self._model("hr.attendance")
        Emp = self.env["hr.employee"].sudo()
        title = _("Davomat")
        if ref in ("bugun", "ichkarida", "kelmagan"):
            today = fields.Date.context_today(self)
            ctx = self._ctx_for(today, today)
        domain = [("check_in", ">=", ctx["dt_from_s"]), ("check_in", "<=", ctx["dt_to_s"])] \
            + self._company_domain(Att)
        if ref == "kelmagan":
            kelgan = Att.search(domain).mapped("employee_id")
            recs = Emp.search([("active", "=", True), ("id", "not in", kelgan.ids)]
                              + self._company_domain(Emp))
            columns, rows = self._rows_table(recs, [("name", _("Xodim"), "text"),
                                               ("department_id", _("Bo'lim"), "m2o"),
                                               ("job_id", _("Lavozim"), "m2o")])
            return self._detail(_("Bugun kelmagan xodimlar"), "fa-user-times", "red",
                                stats=[self._stat(_("Xodimlar"), len(recs), "int", tone="bad")],
                                columns=columns, rows=rows)
        if ref == "ichkarida":
            domain.append(("check_out", "=", False))
            title = _("Hozir ishdagilar")
        elif ref == "bugun":
            title = _("Bugungi davomat")
        else:
            did = self._ref_id(ref)
            if did:
                domain.append(("employee_id.department_id", "=", did))
        recs = Att.search(domain, order="check_in desc", limit=MAX_ROWS)
        cols = [("employee_id", _("Xodim"), "m2o"), ("employee_id.department_id", _("Bo'lim"), "m2o"),
                ("check_in", _("Kirish"), "datetime"), ("check_out", _("Chiqish"), "datetime"),
                ("worked_hours", _("Soat"), "hours")]
        columns, rows = self._rows_table(recs, cols)
        return self._detail(
            title, "fa-clock-o", "teal",
            stats=[self._stat(_("Yozuvlar"), len(recs), "int"),
                   self._stat(_("Xodimlar"), len(recs.mapped("employee_id")), "int"),
                   self._stat(_("Jami soat"), sum(recs.mapped("worked_hours")), "hours")],
            columns=columns, rows=rows, action=self._act("hr.attendance", domain, title))
