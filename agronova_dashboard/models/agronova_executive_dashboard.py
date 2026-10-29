# -*- coding: utf-8 -*-
"""Rahbar paneli — OWL mijoz amali uchun server tomonidagi ma'lumot manbai.

Mijoz (static/src/dashboard/) uchta RPC chaqiradi:

* :meth:`get_dashboard_meta` — brend, korxona va o'rnatilgan bo'limlar ro'yxati
  (bir marta, panel ochilganda);
* :meth:`get_dashboard_data` — tanlangan bo'limning KPI, panel va 3D sahnasi;
* :meth:`get_detail` — kartochka / qator / ustun bosilganda ochiladigan
  tafsilot oynasi (``agronova_dashboard_detail.py``).

Har bo'lim alohida ``try`` ichida hisoblanadi — bitta modul o'rnatilmagan yoki
xato bergan bo'lsa, qolganlari ishlashda davom etadi. Bo'lim o'z modeli
o'rnatilmagan bo'lsa navigatsiyadan butunlay yashiriladi: bitta kod istalgan
tarkibdagi agro-holdingga (faqat boquv, faqat tuxum, to'liq zanjir) mos keladi.

Raqamlar ``sudo()`` bilan olinadi: kirish menyu va guruh orqali cheklangan
(:meth:`_check_dashboard_access`), rahbarning har bir modulga alohida o'qish
huquqi bo'lmasligi mumkin.
"""
import logging
import math
from collections import defaultdict
from datetime import datetime, time

from dateutil.relativedelta import relativedelta

from odoo import _, api, fields, models
from odoo.exceptions import AccessError
from odoo.tools.misc import formatLang

_logger = logging.getLogger(__name__)

# RPC javobi cheksiz o'smasligi uchun ro'yxatlar chegarasi (20 sahifa).
MAX_ROWS = 200

# Mijoz taniydigan rang kalitlari (dashboard.scss / dashboard.js).
_COLORS = ("green", "blue", "purple", "orange", "red", "teal", "indigo", "gray")

# Brend — ``Sozlamalar → AgroNova`` dan o'zgartiriladi (oq yorliq / white-label).
BRAND_DEFAULT = "AgroNova"
TAGLINE_DEFAULT = "Agro-sanoat korxonasi uchun yagona boshqaruv paneli"
PARAM_PREFIX = "agronova."

# Normativlar (birlamchi qiymatlar). Har korxona o'zinikini sozlamalarda beradi.
NORM_DEFAULTS = {
    "fcr": 1.60,            # 1 kg tirik vaznga yem sarfi
    "nobud": 3.5,           # boquvdagi nobudgarchilik, %
    "vazn": 2.60,           # o'rtacha tirik vazn, kg
    "soyish_chiqim": 74.0,  # so'yishdagi chiqim, %
    "ochilish": 85.0,       # inkubatsiyadagi ochilish, %
    "tuxum_berish": 80.0,   # ona tovuqning tuxum berishi, %
}
# Eski import'lar buzilmasin.
NORM_FCR = NORM_DEFAULTS["fcr"]
NORM_NOBUD = NORM_DEFAULTS["nobud"]
NORM_VAZN = NORM_DEFAULTS["vazn"]
NORM_SOYISH_CHIQIM = NORM_DEFAULTS["soyish_chiqim"]
NORM_OCHILISH = NORM_DEFAULTS["ochilish"]
NORM_TUXUM_BERISH = NORM_DEFAULTS["tuxum_berish"]

# Bo'lim → u ishlashi uchun registrda bo'lishi shart model.
# None — har doim mavjud. Tartib navigatsiyadagi tartib emas (u mijozda).
SECTION_MODELS = {
    "overview": None,
    "moliya": "account.move",
    "qarzdorlar": "agronova.debt.aging.report",
    "ombor": "stock.quant",
    "zakupka": "agronova.kirim",
    "pos": "pos.order",
    "transport": "agronova.trip",
    "yem_zavodi": "mrp.production",
    "ona_tovuq": "agronova.ona_tovuq.jurnal.tuxum",
    "inkubatoriya": "agronova.ink.ochilish",
    "boquv": "agronova.boquv.partiya",
    "soyish": "agronova.soyish.jarayon",
    "qishloq_xojaligi": "agronova.qx.partiya",
    "ish_haqi": "agronova.ish_haqi.davr",
    "davomat": "hr.attendance",
}

POS_DONE_STATES = ("paid", "done", "invoiced")


class AgroNovaExecutiveDashboard(models.TransientModel):
    _name = 'agronova.executive.dashboard'
    _description = "Rahbar paneli (Executive Dashboard)"

    # ==================================================================
    # Kirish nuqtalari (OWL mijoz amalidan RPC orqali chaqiriladi)
    # ==================================================================
    def _check_dashboard_access(self):
        """Ma'lumot ``sudo`` bilan olinadi — shuning uchun eshik shu yerda."""
        if self.env.is_superuser() or self.env.user.has_group('base.group_system'):
            return
        if not self.env.user.has_group('agronova_dashboard.group_agronova_dashboard_user'):
            raise AccessError(_("Rahbar paneliga kirish huquqingiz yo'q."))

    @api.model
    def get_dashboard_meta(self):
        """Brend, korxona va mavjud bo'limlar — panel sarlavhasi va menyusi uchun."""
        self._check_dashboard_access()
        icp = self.env["ir.config_parameter"].sudo()
        company = self.env.company
        return {
            "brand": icp.get_param(PARAM_PREFIX + "brand_name") or BRAND_DEFAULT,
            "tagline": icp.get_param(PARAM_PREFIX + "brand_tagline") or _(TAGLINE_DEFAULT),
            "company": company.name or "",
            "company_logo": "/web/image/res.company/%s/logo" % company.id if company.logo else "",
            "sections": [code for code in SECTION_MODELS if self._section_available(code)],
            "currency_symbol": company.currency_id.symbol or "",
            "user": self.env.user.name,
        }

    @api.model
    def get_dashboard_data(self, section="overview", period="month", date_from=None, date_to=None):
        self._check_dashboard_access()
        ctx = self._make_ctx(period, date_from, date_to)
        section = section or "overview"
        method = getattr(self, "_section_%s" % section, None) if section in SECTION_MODELS else None
        try:
            if not method:
                payload = {"available": False, "message": _("Noma'lum bo'lim.")}
            elif not self._section_available(section):
                payload = {"available": False,
                           "message": _("Bu bo'lim uchun kerakli modul o'rnatilmagan.")}
            else:
                payload = method(ctx)
        except Exception as exc:  # pragma: no cover - interfeys himoyasi
            _logger.exception("Dashboard bo'limi %r xato berdi", section)
            payload = {
                "available": False,
                "message": _("Ushbu bo'limni yuklashda xatolik: %s", exc),
            }
        payload.setdefault("available", True)
        payload.setdefault("kpis", [])
        payload.setdefault("panels", [])
        payload.setdefault("alerts", [])
        payload.update({
            "section": section,
            "period": period or "month",
            "date_from": ctx["d_from_s"],
            "date_to": ctx["d_to_s"],
            "currency_symbol": self.env.company.currency_id.symbol or "",
        })
        return payload

    # ==================================================================
    # Davr, sozlama va formatlash yordamchilari
    # ==================================================================
    def _make_ctx(self, period, date_from=None, date_to=None):
        d_from, d_to = self._resolve_period(period, date_from, date_to)
        return self._ctx_for(d_from, d_to)

    def _ctx_for(self, d_from, d_to):
        return {
            "d_from": d_from,
            "d_to": d_to,
            "d_from_s": fields.Date.to_string(d_from),
            "d_to_s": fields.Date.to_string(d_to),
            "dt_from_s": fields.Datetime.to_string(datetime.combine(d_from, time.min)),
            "dt_to_s": fields.Datetime.to_string(datetime.combine(d_to, time.max)),
            "companies": self.env.companies.ids,
        }

    def _prev_ctx(self, ctx):
        """Xuddi shu uzunlikdagi oldingi davr — KPI o'zgarishini (▲/▼) hisoblash uchun."""
        span = (ctx["d_to"] - ctx["d_from"]).days + 1
        d_to = ctx["d_from"] - relativedelta(days=1)
        return self._ctx_for(d_to - relativedelta(days=span - 1), d_to)

    def _resolve_period(self, period, date_from, date_to):
        """[date_from, date_to] oynasini aniqlaydi. Tayyor davrlar bugun bilan tugaydi."""
        today = fields.Date.context_today(self)
        d_from = d_to = None
        if period == "custom" and date_from and date_to:
            d_from = fields.Date.to_date(date_from)
            d_to = fields.Date.to_date(date_to)
        elif period == "today":
            d_from, d_to = today, today
        elif period == "week":
            d_from, d_to = today - relativedelta(weeks=1), today
        elif period == "6months":
            d_from, d_to = today - relativedelta(months=6), today
        elif period == "year":
            d_from, d_to = today - relativedelta(years=1), today
        else:  # "month" (birlamchi)
            d_from, d_to = today - relativedelta(months=1), today
        if not d_from:
            d_from = today - relativedelta(months=1)
        if not d_to:
            d_to = today
        if d_from > d_to:
            d_from, d_to = d_to, d_from
        return d_from, d_to

    def _norm(self, key):
        """Normativ: sozlamada berilgan bo'lsa o'sha, aks holda birlamchi qiymat."""
        raw = self.env["ir.config_parameter"].sudo().get_param(PARAM_PREFIX + "norm_" + key)
        try:
            value = float(raw) if raw not in (None, False, "") else 0.0
        except (TypeError, ValueError):
            value = 0.0
        return value or NORM_DEFAULTS[key]

    def _has(self, model_name):
        """Modul o'rnatilganmi (modelning registrda borligi)."""
        return model_name in self.env

    def _section_available(self, code):
        model_name = SECTION_MODELS.get(code)
        if model_name is None:
            return code in SECTION_MODELS
        if not self._has(model_name):
            return False
        if code == "yem_zavodi":
            return "agronova_miqdor_kg" in self.env["mrp.production"]._fields
        if code == "ombor":
            return "value" in self.env["stock.quant"]._fields
        if code == "pos":
            return self._has("pos.payment")
        return True

    def _model(self, model_name):
        """Modelni sudo bilan qaytaradi, o'rnatilmagan bo'lsa None."""
        return self.env[model_name].sudo() if self._has(model_name) else None

    def _company_domain(self, model):
        """Modelda `company_id` bo'lsa — faol korxonalar bo'yicha filtr."""
        if model is not None and "company_id" in model._fields:
            return [("company_id", "in", self.env.companies.ids)]
        return []

    def _fmt(self, value, kind="money", uom=None):
        """Qiymatni server tomonda formatlaydi — valyuta va til doim to'g'ri."""
        value = value or 0.0
        if kind == "money":
            # 0 kasr: so'mda tiyin ishlatilmaydi va uzun ".00" kartochkaga sig'maydi.
            currency = self.env.company.currency_id
            number = formatLang(self.env, value, digits=0)
            symbol = currency.symbol or currency.name or ""
            if currency.position == "before":
                return "%s%s" % (symbol, number)
            return "%s %s" % (number, symbol)
        if kind == "usd":
            return "$%s" % formatLang(self.env, value, digits=0)
        if kind == "int":
            return formatLang(self.env, float(int(round(value))), digits=0)
        if kind == "qty":
            text = formatLang(self.env, value, digits=1)
            return "%s %s" % (text, uom) if uom else text
        if kind == "kg":
            return "%s kg" % formatLang(self.env, value, digits=1)
        if kind == "ton":
            return "%s t" % formatLang(self.env, value, digits=2)
        if kind == "ga":
            return "%s ga" % formatLang(self.env, value, digits=2)
        if kind == "coef":
            return formatLang(self.env, value, digits=3)
        if kind == "hours":
            return _("%s soat", formatLang(self.env, value, digits=1))
        if kind == "days":
            return _("%s kun", round(value, 1))
        if kind == "pct":
            return "%s%%" % round(value, 1)
        return str(value)

    def _fmt_compact(self, value):
        """Qisqa yozuv (207.5 mln) — donut markazi va 3D yorliqlar kabi tor joylar uchun."""
        value = value or 0.0
        sign = "-" if value < 0 else ""
        v = abs(value)
        if v >= 1e9:
            return "%s%s mlrd" % (sign, round(v / 1e9, 1))
        if v >= 1e6:
            return "%s%s mln" % (sign, round(v / 1e6, 1))
        if v >= 1e3:
            return "%s%s ming" % (sign, round(v / 1e3, 1))
        return "%s%s" % (sign, round(v))

    # ==================================================================
    # Panel qurish yordamchilari
    # ==================================================================
    def _kpi(self, label, value, kind, icon, color, hint="", action=None, tone="",
             detail=None, prev=None, higher_is_better=True, spark=None):
        """Bitta KPI kartochkasi.

        ``tone``   — "" | "ok" | "bad": normativdan og'ishni rang bilan ko'rsatadi.
        ``detail`` — {"key", "ref"}: bosilganda ochiladigan tafsilot oynasi.
        ``prev``   — oldingi davr qiymati: kartochkada ▲/▼ foiz chiqadi.
        ``spark``  — 0..100 qiymatlar ro'yxati: kartochka ostidagi mini-grafik.
        """
        delta = None
        if prev is not None:
            if prev:
                pct = (value - prev) / abs(prev) * 100.0
            else:
                pct = 100.0 if value else 0.0
            if abs(pct) >= 0.05:
                delta = {
                    "pct": round(pct, 1),
                    "display": "%s%s%%" % ("+" if pct > 0 else "", round(pct, 1)),
                    "up": pct > 0,
                    "good": (pct > 0) == bool(higher_is_better),
                }
        return {
            "label": label,
            "value": value,
            "display": self._fmt(value, kind),
            "icon": icon,
            "color": color if color in _COLORS else "blue",
            "hint": hint,
            "action": action,
            "tone": tone,
            "detail": detail,
            "delta": delta,
            "spark": spark or [],
        }

    def _act(self, res_model, domain, name):
        """Bosiladigan KPI: modelning ro'yxatini domen bo'yicha ochadi."""
        return {"res_model": res_model, "domain": domain, "name": name}

    @staticmethod
    def _det(key, ref=None):
        return {"key": key, "ref": ref}

    @staticmethod
    def _alert(text, tone="warn", icon="fa-exclamation-triangle", detail=None):
        """Bo'lim tepasidagi «diqqat» qatori: avtomatik topilgan muammo yoki yutuq."""
        return {"text": text, "tone": tone, "icon": icon, "detail": detail}

    def _rank_panel(self, title, icon, rows, color="blue", value_fmt="money", uom=None,
                    full=False):
        """Gorizontal ustunli reyting. ``rows`` = [{name, value, sub?, detail?}]."""
        clean = [r for r in rows if r.get("value") is not None][:MAX_ROWS]
        top = max((abs(r["value"]) for r in clean), default=0.0) or 0.0
        out = []
        for r in clean:
            out.append({
                "name": r.get("name") or _("Noma'lum"),
                "display": self._fmt(r["value"], value_fmt, r.get("uom", uom)),
                "sub": r.get("sub") or "",
                "pct": round((abs(r["value"]) / top) * 100, 1) if top else 0.0,
                "negative": r["value"] < 0,
                "detail": r.get("detail"),
            })
        return {"type": "rank", "title": title, "icon": icon, "color": color,
                "rows": out, "full": full}

    def _split_panel(self, title, icon, parts, value_fmt="money"):
        """Donut + izoh. ``parts`` = [{label, value, color, detail?}]."""
        parts = [p for p in parts if (p.get("value") or 0) > 0] or parts
        total = sum(max(p["value"] or 0.0, 0.0) for p in parts) or 0.0
        out = []
        for p in parts:
            out.append({
                "label": p["label"],
                "display": self._fmt(p["value"], value_fmt),
                "pct": round((max(p["value"] or 0.0, 0.0) / total) * 100, 1) if total else 0.0,
                "color": p.get("color", "blue"),
                "detail": p.get("detail"),
            })
        center = self._fmt_compact(total) if value_fmt == "money" else self._fmt(total, value_fmt)
        return {
            "type": "split", "title": title, "icon": icon,
            "total_display": self._fmt(total, value_fmt),
            "total_center": center, "parts": out,
        }

    def _grid_panel(self, title, icon, columns, rows, footer=None, message=""):
        """Ko'p ustunli jadval.

        ``columns`` = [{"label": str, "align": "left"|"right"}]
        ``rows``    = [{"cells": [{"text", "align", "tone"}], "detail"?: {...}}]
        ``footer``  = xuddi shu shakl, «JAMI» qatori (sahifalanmaydi).
        """
        return {
            "type": "gridtable", "title": title, "icon": icon,
            "columns": columns, "rows": rows[:MAX_ROWS],
            "footer": footer or [],
            "message": message or _("Bu davrda ma'lumot topilmadi."),
        }

    def _gauge(self, label, fact, norm, unit="coef", lower_is_better=True, scale=None):
        """Fakt va normativni bitta chiziqda taqqoslaydi.

        ``scale`` — chiziqning to'liq uzunligi. Berilmasa normativning 2 barobari
        olinadi, shunda normativ chizig'i o'rtada turadi va og'ish darrov ko'rinadi.
        """
        scale = scale or (norm * 2 if norm else max(fact, 1.0))
        scale = scale or 1.0
        delta = fact - norm
        yomon = (delta > 0) if lower_is_better else (delta < 0)
        return {
            "label": label,
            "fact_display": self._fmt(fact, unit),
            "norm_display": self._fmt(norm, unit),
            "delta_display": "%s%s" % ("+" if delta >= 0 else "", self._fmt(delta, unit)),
            "fact_pct": round(min(max(fact / scale * 100, 0), 100), 1),
            "norm_pct": round(min(max(norm / scale * 100, 0), 100), 1),
            "color": "red" if (yomon and fact) else "green",
            "verdict": (_("Normadan yomon") if yomon else _("Normada")) if fact else _("Ma'lumot yo'q"),
        }

    def _gauge_panel(self, title, icon, gauges):
        return {"type": "gauges", "title": title, "icon": icon, "gauges": gauges}

    def _buckets(self, ctx):
        """Davrni ustunlarga bo'ladi.

        Qadam davr uzunligiga qarab tanlanadi, chunki ustunlar soni ~15 tadan
        oshsa grafik panelga sig'may qoladi: 2 haftagacha — kunlik, 3 oygacha —
        haftalik, undan uzunda — oylik.
        """
        d_from, d_to = ctx["d_from"], ctx["d_to"]
        span = (d_to - d_from).days
        out = []
        if span <= 14:
            cur = d_from
            while cur <= d_to:
                out.append((cur, cur, cur.strftime("%d.%m")))
                cur += relativedelta(days=1)
        elif span <= 92:
            cur = d_from
            while cur <= d_to:
                end = min(cur + relativedelta(days=6), d_to)
                out.append((cur, end, cur.strftime("%d.%m")))
                cur = end + relativedelta(days=1)
        else:
            cur = d_from.replace(day=1)
            while cur <= d_to:
                end = cur + relativedelta(months=1, days=-1)
                out.append((max(cur, d_from), min(end, d_to), cur.strftime("%m.%Y")))
                cur += relativedelta(months=1)
        return out

    def _bucketize(self, ctx, series):
        return [sum(v for d, v in series.items() if start <= d <= end)
                for start, end, _label in self._buckets(ctx)]

    def _spark(self, ctx, series):
        """KPI ostidagi mini-grafik uchun 0..100 ga normallashtirilgan qiymatlar."""
        vals = self._bucketize(ctx, series)
        top = max((abs(v) for v in vals), default=0.0)
        if not top or len(vals) < 2:
            return []
        return [round(abs(v) / top * 100, 1) for v in vals]

    def _trend_panel(self, title, icon, ctx, series_a, series_b=None,
                     label_a="", label_b="", value_fmt="money", detail_key=None):
        """Ustunli grafik. ``series_*`` — {sana: qiymat} lug'ati.

        ``detail_key`` berilsa ustun bosilganda o'sha oraliq tafsiloti ochiladi.
        """
        buckets = self._buckets(ctx)
        rows = []
        for start, end, label in buckets:
            a = sum(v for d, v in series_a.items() if start <= d <= end)
            b = sum(v for d, v in (series_b or {}).items() if start <= d <= end)
            rows.append({"label": label, "a": a, "b": b, "start": start, "end": end})
        top = max((max(r["a"], r["b"]) for r in rows), default=0.0) or 0.0
        bars = []
        for r in rows:
            bars.append({
                "label": r["label"],
                "in_pct": round((r["a"] / top) * 100, 1) if top else 0.0,
                "out_pct": round((r["b"] / top) * 100, 1) if top else 0.0,
                "in_display": "%s: %s" % (label_a, self._fmt(r["a"], value_fmt)),
                "out_display": "%s: %s" % (label_b, self._fmt(r["b"], value_fmt)),
                "detail": self._det(detail_key, {
                    "from": fields.Date.to_string(r["start"]),
                    "to": fields.Date.to_string(r["end"]),
                }) if detail_key and (r["a"] or r["b"]) else None,
            })
        legend = [{"label": label_a, "color": "green"}]
        if series_b is not None:
            legend.append({"label": label_b, "color": "red"})
        total_a = sum(r["a"] for r in rows)
        total_b = sum(r["b"] for r in rows)
        summary = [{"label": label_a, "display": self._fmt(total_a, value_fmt), "color": "green"}]
        if series_b is not None:
            summary.append({"label": label_b, "display": self._fmt(total_b, value_fmt),
                            "color": "red"})
        return {
            "type": "trend", "title": title, "icon": icon, "bars": bars,
            "legend": legend, "two_series": series_b is not None,
            "empty": not top, "summary": summary,
        }

    # ==================================================================
    # Umumiy ma'lumot yig'uvchilar (bir nechta bo'lim ishlatadi)
    # ==================================================================
    def _kassa_qoldiqlari(self):
        """Kassa va depozit qoldiqlari valyuta kesimida.

        «uzs» kalitlari — korxonaning asosiy valyutasi, «usd» — boshqa (chet el)
        valyutalar. Kod bo'yicha emas, korxona valyutasi bilan solishtiriladi:
        panel so'mda ham, tengeda ham, dollarda ham to'g'ri ishlaydi.
        """
        main_currency = self.env.company.currency_id
        res = {"kassa_uzs": 0.0, "kassa_usd": 0.0, "kassa_soni": 0,
               "depozit_uzs": 0.0, "depozit_usd": 0.0, "kassalar": [], "depozitlar": []}
        Kassa = self._model("agronova.kassa")
        if Kassa is not None:
            kassalar = Kassa.search([("active", "=", True)] + self._company_domain(Kassa))
            res["kassa_soni"] = len(kassalar)
            for k in kassalar:
                summa = k.balance or 0.0
                if k.currency_id and k.currency_id != main_currency:
                    res["kassa_usd"] += summa
                else:
                    res["kassa_uzs"] += summa
                res["kassalar"].append({
                    "name": k.display_name,
                    "value": summa,
                    "uom": "",
                    "sub": k.currency_id.name or "",
                    "detail": self._det("kassa", k.id),
                })
        Depozit = self._model("agronova.depozit")
        if Depozit is not None:
            for d in Depozit.search([("active", "=", True)] + self._company_domain(Depozit)):
                summa = d.balans or 0.0
                if d.currency_id and d.currency_id != main_currency:
                    res["depozit_usd"] += summa
                else:
                    res["depozit_uzs"] += summa
                res["depozitlar"].append({"name": d.display_name, "value": summa,
                                          "sub": d.currency_id.name or ""})
        res["kassalar"].sort(key=lambda r: abs(r["value"]), reverse=True)
        res["depozitlar"].sort(key=lambda r: abs(r["value"]), reverse=True)
        return res

    def _move_domain(self, ctx, move_type):
        return [
            ("move_type", "=", move_type),
            ("state", "=", "posted"),
            ("invoice_date", ">=", ctx["d_from_s"]),
            ("invoice_date", "<=", ctx["d_to_s"]),
            ("company_id", "in", ctx["companies"]),
        ]

    def _unpaid_domain(self, move_type, companies):
        return [
            ("move_type", "=", move_type),
            ("state", "=", "posted"),
            ("payment_state", "in", ["not_paid", "partial"]),
            ("company_id", "in", companies),
        ]

    def _sum_moves(self, domain, field):
        Move = self.env["account.move"].sudo()
        rows = Move._read_group(domain, [], ["%s:sum" % field])
        return (rows[0][0] if rows else 0.0) or 0.0

    def _moliya_asosi(self, ctx):
        """Davr sotuvi, xaridi va ochiq qarzdorliklar (SQL yig'indisi bilan)."""
        sotuv = self._sum_moves(self._move_domain(ctx, "out_invoice"), "amount_total_signed")
        xarid = abs(self._sum_moves(self._move_domain(ctx, "in_invoice"), "amount_total_signed"))
        debitor = self._sum_moves(self._unpaid_domain("out_invoice", ctx["companies"]),
                                  "amount_residual_signed")
        kreditor = self._sum_moves(self._unpaid_domain("in_invoice", ctx["companies"]),
                                   "amount_residual_signed")
        return {
            "sotuv": sotuv, "xarid": xarid, "foyda": sotuv - xarid,
            "debitor": debitor, "kreditor": abs(kreditor),
        }

    def _move_series(self, ctx, move_type):
        """{sana: summa} — trend grafigi uchun."""
        Move = self.env["account.move"].sudo()
        out = defaultdict(float)
        for day, total in Move._read_group(self._move_domain(ctx, move_type),
                                           ["invoice_date:day"], ["amount_total_signed:sum"]):
            if day:
                out[fields.Date.to_date(day)] += abs(total or 0.0)
        return out

    def _kassa_series(self, ctx):
        """Kassa harakati: (kirim, chiqim) — {sana: summa}."""
        Harakat = self._model("agronova.kassa.harakat")
        kirim, chiqim = defaultdict(float), defaultdict(float)
        if Harakat is None:
            return kirim, chiqim
        for h in Harakat.search([
            ("state", "=", "posted"),
            ("date_day", ">=", ctx["d_from_s"]), ("date_day", "<=", ctx["d_to_s"]),
        ] + self._company_domain(Harakat)):
            if not h.date_day:
                continue
            if h.direction == "in":
                kirim[h.date_day] += h.amount or 0.0
            else:
                chiqim[h.date_day] += h.amount or 0.0
        return kirim, chiqim

    def _boquv_partiyalar(self):
        """Faol boquv partiyalari (modul yo'q bo'lsa None)."""
        Partiya = self._model("agronova.boquv.partiya")
        if Partiya is None:
            return None
        return Partiya.search(
            [("holat", "=", "active")] + self._company_domain(Partiya),
            order="filial_id, name",
        )

    @staticmethod
    def _ortacha(values):
        vals = [v for v in values if v]
        return (sum(vals) / len(vals)) if vals else 0.0

    @staticmethod
    def _weighted(records, value_field, weight_field):
        """Bosh soni bilan tortilgan o'rtacha — kichik partiya umumiy FCR ni buzmasin."""
        num = den = 0.0
        for r in records:
            v, w = r[value_field] or 0.0, r[weight_field] or 0.0
            if v and w:
                num += v * w
                den += w
        return (num / den) if den else 0.0

    # ==================================================================
    # 1. UMUMIY KO'RINISH
    # ==================================================================
    def _section_overview(self, ctx):
        prev = self._prev_ctx(ctx)
        pul = self._kassa_qoldiqlari()
        mol = self._moliya_asosi(ctx)
        mol_prev = self._moliya_asosi(prev)
        sotuv_s = self._move_series(ctx, "out_invoice")
        xarid_s = self._move_series(ctx, "in_invoice")
        partiyalar = self._boquv_partiyalar()
        tirik_bosh = sum(partiyalar.mapped("joriy_son")) if partiyalar else 0
        fcr = self._weighted(partiyalar, "fcr", "joriy_son") if partiyalar else 0.0
        nobud = self._weighted(partiyalar, "nobud_foiz", "boshlangich_son") if partiyalar else 0.0
        norm_fcr, norm_nobud = self._norm("fcr"), self._norm("nobud")

        kpis = [
            self._kpi(_("Kassa qoldig'i"), pul["kassa_uzs"], "money", "fa-money", "green",
                      hint=_("%s ta faol kassa", pul["kassa_soni"]),
                      detail=self._det("kassalar") if self._has("agronova.kassa") else None),
            self._kpi(_("Valyuta kassasi"), pul["kassa_usd"], "usd", "fa-dollar", "teal",
                      hint=_("Chet el valyutasidagi kassalar"),
                      detail=self._det("kassalar") if self._has("agronova.kassa") else None),
            self._kpi(_("Davr sotuvi"), mol["sotuv"], "money", "fa-shopping-cart", "blue",
                      prev=mol_prev["sotuv"], spark=self._spark(ctx, sotuv_s),
                      detail=self._det("sotuv")),
            self._kpi(_("Davr xaridi"), mol["xarid"], "money", "fa-shopping-basket", "orange",
                      prev=mol_prev["xarid"], higher_is_better=False,
                      spark=self._spark(ctx, xarid_s), detail=self._det("xarid")),
            self._kpi(_("Operatsion natija"), mol["foyda"], "money", "fa-line-chart",
                      "purple", hint=_("Sotuv minus xarid"), prev=mol_prev["foyda"],
                      tone="ok" if mol["foyda"] >= 0 else "bad", detail=self._det("sotuv")),
            self._kpi(_("Debitorlik"), mol["debitor"], "money", "fa-user-times", "red",
                      hint=_("Mijozlarning ochiq qarzi"), higher_is_better=False,
                      detail=self._det("debitor"),
                      action=self._act("account.move",
                                       self._unpaid_domain("out_invoice", ctx["companies"]),
                                       _("Mijozlar qarzdorligi"))),
            self._kpi(_("Kreditorlik"), mol["kreditor"], "money", "fa-truck", "indigo",
                      hint=_("Ta'minotchilarga qarz"), detail=self._det("kreditor"),
                      action=self._act("account.move",
                                       self._unpaid_domain("in_invoice", ctx["companies"]),
                                       _("Ta'minotchilarga qarz"))),
        ]
        if partiyalar is not None:
            kpis.append(self._kpi(
                _("Tirik parranda"), tirik_bosh, "int", "fa-home", "green",
                hint=_("%s ta faol partiya", len(partiyalar)),
                detail=self._det("boquv_partiyalar"),
                action=self._act("agronova.boquv.partiya", [("holat", "=", "active")],
                                 _("Faol boquv partiyalari"))))

        panels = [
            self._chain_scene(ctx),
            self._trend_panel(_("Sotuv va xarid dinamikasi"), "fa-bar-chart", ctx,
                              sotuv_s, xarid_s, label_a=_("Sotuv"), label_b=_("Xarid"),
                              detail_key="sotuv"),
            self._split_panel(_("Pul mablag'lari va qarzlar"), "fa-pie-chart", [
                {"label": _("Kassalar"), "value": pul["kassa_uzs"], "color": "green",
                 "detail": self._det("kassalar")},
                {"label": _("Depozitlar (mas'ul shaxslarda)"), "value": pul["depozit_uzs"],
                 "color": "orange", "detail": self._det("depozitlar")},
                {"label": _("Debitorlik"), "value": mol["debitor"], "color": "red",
                 "detail": self._det("debitor")},
            ]),
        ]
        alerts = []
        if partiyalar:
            filial = defaultdict(lambda: [0, None])
            for p in partiyalar:
                key = p.filial_id.display_name or str(_("Filialsiz"))
                filial[key][0] += p.joriy_son or 0
                filial[key][1] = p.filial_id.id or False
            panels.append(self._rank_panel(
                _("Filiallar bo'yicha tirik bosh soni"), "fa-sitemap",
                sorted(({"name": k, "value": v[0],
                         "detail": self._det("boquv_partiyalar", v[1])}
                        for k, v in filial.items()),
                       key=lambda r: r["value"], reverse=True),
                color="green", value_fmt="int"))
            panels.append(self._gauge_panel(_("Asosiy normativlar"), "fa-tachometer", [
                self._gauge(_("FCR (yem konversiyasi)"), fcr, norm_fcr, "coef"),
                self._gauge(_("Nobudgarchilik"), nobud, norm_nobud, "pct"),
            ]))
            yomon = partiyalar.filtered(
                lambda p: (p.fcr or 0) > norm_fcr or (p.nobud_foiz or 0) > norm_nobud)
            if yomon:
                alerts.append(self._alert(
                    _("%s ta boquv partiyasida FCR yoki nobudgarchilik normadan yuqori",
                      len(yomon)), "bad", "fa-heartbeat", self._det("boquv_ogish")))
        if mol["debitor"] and mol["sotuv"] and mol["debitor"] > mol["sotuv"]:
            alerts.append(self._alert(
                _("Debitorlik davr sotuvidan katta — to'lov intizomini tekshiring"),
                "warn", "fa-user-times", self._det("debitor")))
        if mol["foyda"] < 0:
            alerts.append(self._alert(_("Davrda xarid sotuvdan oshib ketdi"), "bad",
                                      "fa-arrow-down", self._det("xarid")))
        elif mol["sotuv"] and mol_prev["sotuv"] and mol["sotuv"] > mol_prev["sotuv"]:
            alerts.append(self._alert(
                _("Sotuv oldingi davrga nisbatan %s%% o'sdi",
                  round((mol["sotuv"] - mol_prev["sotuv"]) / mol_prev["sotuv"] * 100, 1)),
                "ok", "fa-arrow-up", self._det("sotuv")))
        return {"kpis": kpis, "panels": panels, "alerts": alerts}

    # ------------------------------------------------------------------
    # 3D: ishlab chiqarish zanjiri
    # ------------------------------------------------------------------
    # (kod, yorliq, shakl, [x, z] joylashuv) — chapdan o'ngga mahsulot oqimi.
    _CHAIN_LAYOUT = [
        ("zakupka", "Xarid", "crates", [-9, -2.6]),
        ("qishloq_xojaligi", "Dala", "field", [-9, 2.6]),
        ("yem_zavodi", "Yem zavodi", "silo", [-5.5, 0]),
        ("ona_tovuq", "Ona tovuq", "barn", [-2, -3]),
        ("inkubatoriya", "Inkubator", "dome", [1.5, -3]),
        ("boquv", "Boquv", "barn", [1.5, 1.8]),
        ("soyish", "So'yish", "factory", [5, 0]),
        ("transport", "Transport", "truck", [5, 4]),
        ("pos", "Do'kon / POS", "shop", [8.5, -2.4]),
        ("moliya", "Moliya", "bank", [8.5, 2.4]),
    ]
    _CHAIN_LINKS = [
        ("zakupka", "yem_zavodi"), ("qishloq_xojaligi", "yem_zavodi"),
        ("yem_zavodi", "ona_tovuq"), ("yem_zavodi", "boquv"),
        ("ona_tovuq", "inkubatoriya"), ("inkubatoriya", "boquv"),
        ("boquv", "soyish"), ("transport", "soyish"),
        ("soyish", "pos"), ("pos", "moliya"), ("soyish", "moliya"),
    ]

    def _chain_metric(self, code, ctx):
        """Zanjir tuguni uchun (qiymat, yozuv, holat). Holat: ok | bad | idle."""
        if code == "zakupka":
            Kirim = self._model("agronova.kirim")
            recs = Kirim.search([
                ("holat", "!=", "bekor"),
                ("sotib_olingan_sana", ">=", ctx["d_from_s"]),
                ("sotib_olingan_sana", "<=", ctx["d_to_s"]),
            ] + self._company_domain(Kirim))
            v = sum(recs.mapped("jami_summa"))
            return v, self._fmt_compact(v), _("Xarid summasi"), "ok" if v else "idle"
        if code == "qishloq_xojaligi":
            P = self._model("agronova.qx.partiya")
            recs = P.search([("holat", "=", "active")] + self._company_domain(P))
            v = sum(recs.mapped("olingan_hosil_kg"))
            return v, self._fmt(v, "kg"), _("Olingan hosil"), "ok" if recs else "idle"
        if code == "yem_zavodi":
            recs = self.env["mrp.production"].sudo().search([
                ("state", "=", "done"),
                ("date_start", ">=", ctx["dt_from_s"]), ("date_start", "<=", ctx["dt_to_s"]),
                ("company_id", "in", ctx["companies"]),
            ])
            v = sum(recs.mapped("agronova_miqdor_kg")) / 1000.0
            chet = self._ortacha(recs.mapped("agronova_chetlanish"))
            st = "idle" if not recs else ("bad" if chet > 0 else "ok")
            return v, self._fmt(v, "ton"), _("Ishlab chiqarilgan yem"), st
        if code == "ona_tovuq":
            J = self._model("agronova.ona_tovuq.jurnal.tuxum")
            recs = J.search([("date", ">=", ctx["d_from_s"]),
                             ("date", "<=", ctx["d_to_s"])] + self._company_domain(J))
            v = sum(recs.mapped("jami_tuxum"))
            berish = self._ortacha(recs.mapped("tuxum_berish_foiz"))
            st = "idle" if not recs else ("ok" if berish >= self._norm("tuxum_berish") else "bad")
            return v, _("%s dona", self._fmt(v, "int")), _("Tuxum"), st
        if code == "inkubatoriya":
            O = self._model("agronova.ink.ochilish")
            recs = O.search([("holat", "=", "done"), ("sana", ">=", ctx["d_from_s"]),
                             ("sana", "<=", ctx["d_to_s"])] + self._company_domain(O))
            joja = sum(recs.mapped("ochilgan_joja"))
            qoy = joja + sum(recs.mapped("ochilmagan_tuxum"))
            foiz = (joja / qoy * 100) if qoy else 0.0
            st = "idle" if not recs else ("ok" if foiz >= self._norm("ochilish") else "bad")
            return joja, _("%s jo'ja", self._fmt(joja, "int")), _("Ochilgan jo'ja"), st
        if code == "boquv":
            recs = self._boquv_partiyalar()
            v = sum(recs.mapped("joriy_son"))
            yomon = recs.filtered(lambda p: (p.fcr or 0) > self._norm("fcr")
                                  or (p.nobud_foiz or 0) > self._norm("nobud"))
            st = "idle" if not recs else ("bad" if yomon else "ok")
            return v, _("%s bosh", self._fmt(v, "int")), _("Tirik parranda"), st
        if code == "soyish":
            S = self._model("agronova.soyish.jarayon")
            recs = S.search([("holat", "=", "done"), ("sana", ">=", ctx["d_from_s"]),
                             ("sana", "<=", ctx["d_to_s"])] + self._company_domain(S))
            v = sum(recs.mapped("tushka_vazn_kg"))
            chiqim = self._ortacha(recs.mapped("chiqim_foiz"))
            st = "idle" if not recs else ("ok" if chiqim >= self._norm("soyish_chiqim") else "bad")
            return v, self._fmt(v, "kg"), _("Tayyor go'sht"), st
        if code == "transport":
            T = self._model("agronova.trip")
            recs = T.search([("date", ">=", ctx["d_from_s"]),
                             ("date", "<=", ctx["d_to_s"])] + self._company_domain(T))
            foyda = sum(recs.mapped("profit"))
            st = "idle" if not recs else ("ok" if foyda >= 0 else "bad")
            return len(recs), _("%s reys", len(recs)), _("Reyslar"), st
        if code == "pos":
            O = self._model("pos.order")
            recs = O.search([("state", "in", POS_DONE_STATES),
                             ("date_order", ">=", ctx["dt_from_s"]),
                             ("date_order", "<=", ctx["dt_to_s"])] + self._company_domain(O))
            v = sum(recs.mapped("amount_total"))
            return v, self._fmt_compact(v), _("Do'kon savdosi"), "ok" if recs else "idle"
        if code == "moliya":
            mol = self._moliya_asosi(ctx)
            return (abs(mol["foyda"]), self._fmt_compact(mol["foyda"]), _("Operatsion natija"),
                    "ok" if mol["foyda"] >= 0 else "bad")
        return 0.0, "", "", "idle"

    def _chain_scene(self, ctx):
        """Butun korxona bitta 3D xaritada: har bo'lim — bino, oqim — harakatlanuvchi nuqtalar.

        Bino balandligi faollik hajmini, rangi esa normativ holatini bildiradi:
        rahbar bir qarashda qaysi bo'g'in «qizil»ligini ko'radi va bosib o'tadi.
        """
        nodes = []
        for code, label, shape, pos in self._CHAIN_LAYOUT:
            if not self._section_available(code):
                continue
            try:
                value, display, metric, status = self._chain_metric(code, ctx)
            except Exception:  # pragma: no cover - bitta bo'g'in butun sahnani buzmasin
                _logger.exception("Zanjir tuguni %s hisoblanmadi", code)
                continue
            nodes.append({
                "id": code, "label": _(label), "shape": shape, "pos": pos,
                "value": value, "display": display, "metric": metric,
                "status": status, "section": code,
            })
        # Balandlik: logarifmik — tonna va dona bir sahnada solishtiriladi.
        logs = {n["id"]: math.log10(abs(n["value"]) + 1) for n in nodes}
        top = max(logs.values(), default=0.0) or 1.0
        for n in nodes:
            n["h"] = round(0.35 + 0.65 * (logs[n["id"]] / top), 3)
        ids = {n["id"] for n in nodes}
        links = [[a, b] for a, b in self._CHAIN_LINKS if a in ids and b in ids]
        return {
            "type": "scene3d", "mode": "chain", "title": _("Biznes zanjiri — 3D xarita"),
            "icon": "fa-cube", "nodes": nodes, "links": links,
            "hint": _("Sichqoncha bilan aylantiring, g'ildirak bilan yaqinlashtiring. "
                      "Binoni bosing — bo'limga o'tasiz."),
            "legend": [
                {"label": _("Normada"), "color": "green"},
                {"label": _("Normadan og'ish"), "color": "red"},
                {"label": _("Davrda faoliyat yo'q"), "color": "gray"},
            ],
        }

    # ==================================================================
    # 2. MOLIYA VA KASSA
    # ==================================================================
    def _section_moliya(self, ctx):
        prev = self._prev_ctx(ctx)
        pul = self._kassa_qoldiqlari()
        mol = self._moliya_asosi(ctx)
        mol_prev = self._moliya_asosi(prev)
        kirim_s, chiqim_s = self._kassa_series(ctx)
        sotuv_s = self._move_series(ctx, "out_invoice")
        xarid_s = self._move_series(ctx, "in_invoice")
        has_kassa = self._has("agronova.kassa")

        kpis = [
            self._kpi(_("Kassa (milliy valyuta)"), pul["kassa_uzs"], "money", "fa-money", "green",
                      hint=_("%s ta faol kassa", pul["kassa_soni"]),
                      detail=self._det("kassalar") if has_kassa else None),
            self._kpi(_("Kassa (valyuta)"), pul["kassa_usd"], "usd", "fa-dollar", "teal",
                      detail=self._det("kassalar") if has_kassa else None),
            self._kpi(_("Depozitlar (milliy)"), pul["depozit_uzs"], "money", "fa-briefcase",
                      "orange", hint=_("Mas'ul xodimlar qo'lidagi naqd"),
                      detail=self._det("depozitlar") if self._has("agronova.depozit") else None),
            self._kpi(_("Depozitlar (valyuta)"), pul["depozit_usd"], "usd", "fa-briefcase", "indigo",
                      detail=self._det("depozitlar") if self._has("agronova.depozit") else None),
            self._kpi(_("Davr sotuvi"), mol["sotuv"], "money", "fa-shopping-cart", "blue",
                      prev=mol_prev["sotuv"], spark=self._spark(ctx, sotuv_s),
                      detail=self._det("sotuv")),
            self._kpi(_("Davr xaridi"), mol["xarid"], "money", "fa-shopping-basket", "orange",
                      prev=mol_prev["xarid"], higher_is_better=False,
                      spark=self._spark(ctx, xarid_s), detail=self._det("xarid")),
            self._kpi(_("Operatsion natija"), mol["foyda"], "money", "fa-line-chart", "purple",
                      prev=mol_prev["foyda"], tone="ok" if mol["foyda"] >= 0 else "bad",
                      detail=self._det("sotuv")),
        ]
        if has_kassa:
            kirim, chiqim = sum(kirim_s.values()), sum(chiqim_s.values())
            kpis.append(self._kpi(
                _("Kassa oqimi (sof)"), kirim - chiqim, "money", "fa-exchange", "gray",
                hint=_("Kirim %s · Chiqim %s", self._fmt_compact(kirim), self._fmt_compact(chiqim)),
                tone="ok" if kirim >= chiqim else "bad", detail=self._det("kassa_harakat"),
                spark=self._spark(ctx, kirim_s)))

        panels = [
            self._trend_panel(_("Sotuv va xarid dinamikasi"), "fa-bar-chart", ctx,
                              sotuv_s, xarid_s, label_a=_("Sotuv"), label_b=_("Xarid"),
                              detail_key="sotuv"),
        ]
        if has_kassa:
            panels.append(self._trend_panel(
                _("Kassa: kirim va chiqim"), "fa-exchange", ctx, kirim_s, chiqim_s,
                label_a=_("Kirim"), label_b=_("Chiqim"), detail_key="kassa_harakat"))
            Harakat = self._model("agronova.kassa.harakat")
            modda = defaultdict(float)
            for h in Harakat.search([
                ("state", "=", "posted"), ("direction", "=", "out"),
                ("date_day", ">=", ctx["d_from_s"]), ("date_day", "<=", ctx["d_to_s"]),
            ] + self._company_domain(Harakat)):
                modda[h.modda_id.display_name or str(_("Moddasiz"))] += h.amount or 0.0
            if modda:
                panels.append(self._rank_panel(
                    _("Kassa chiqimi moddalar bo'yicha"), "fa-tags",
                    sorted(({"name": k, "value": v} for k, v in modda.items()),
                           key=lambda r: r["value"], reverse=True), color="orange"))
        panels.append(self._split_panel(_("Daromad va xarajat"), "fa-pie-chart", [
            {"label": _("Sotuv tushumi"), "value": mol["sotuv"], "color": "green",
             "detail": self._det("sotuv")},
            {"label": _("Xarid xarajati"), "value": mol["xarid"], "color": "red",
             "detail": self._det("xarid")},
        ]))
        if pul["kassalar"]:
            panels.append(self._rank_panel(_("Kassalar bo'yicha qoldiq"), "fa-archive",
                                           pul["kassalar"], color="green"))

        Move = self.env["account.move"].sudo()
        mijoz = []
        for partner, total in Move._read_group(self._move_domain(ctx, "out_invoice"),
                                               ["partner_id"], ["amount_total_signed:sum"]):
            mijoz.append({"name": partner.display_name or str(_("Noma'lum")),
                          "value": abs(total or 0.0),
                          "detail": self._det("partner", partner.id) if partner else None})
        if mijoz:
            panels.append(self._rank_panel(
                _("Eng yirik mijozlar (davr bo'yicha)"), "fa-users",
                sorted(mijoz, key=lambda r: r["value"], reverse=True), color="blue"))
        alerts = []
        if pul["kassalar"] and any(k["value"] < 0 for k in pul["kassalar"]):
            alerts.append(self._alert(_("Manfiy qoldiqli kassa bor — kassa kitobini tekshiring"),
                                      "bad", "fa-archive", self._det("kassalar")))
        return {"kpis": kpis, "panels": panels, "alerts": alerts}

    # ==================================================================
    # 3. QARZDORLAR
    # ==================================================================
    def _section_qarzdorlar(self, ctx):
        # Raqamlarni shu moduldagi SQL ko'rinish beradi — dashboard qayta hisoblamaydi.
        Aging = self.env["agronova.debt.aging.report"].sudo()
        qatorlar = Aging.search([("company_id", "in", ctx["companies"])], order="jami_qarz desc")

        jami = sum(qatorlar.mapped("jami_qarz"))
        q030 = sum(qatorlar.mapped("qarz_0_30"))
        q3160 = sum(qatorlar.mapped("qarz_31_60"))
        q60 = sum(qatorlar.mapped("qarz_60_plus"))

        kpis = [
            self._kpi(_("Jami debitorlik"), jami, "money", "fa-credit-card", "blue",
                      hint=_("%s ta mijoz", len(qatorlar)), detail=self._det("aging")),
            self._kpi(_("0 — 30 kun"), q030, "money", "fa-check-circle", "green",
                      hint=_("Joriy qarz"), detail=self._det("aging", "yaxshi")),
            self._kpi(_("31 — 60 kun"), q3160, "money", "fa-exclamation-circle", "orange",
                      hint=_("Kechikkan"), tone="bad" if q3160 else "",
                      detail=self._det("aging", "ogohlantirish")),
            self._kpi(_("60+ kun"), q60, "money", "fa-times-circle", "red",
                      hint=_("Xavfli qarz"), tone="bad" if q60 else "",
                      detail=self._det("aging", "xavfli"),
                      action=self._act("agronova.debt.aging.report",
                                       [("xavf_darajasi", "=", "xavfli")],
                                       _("Xavfli qarzdorlar"))),
        ]

        tones = {"yaxshi": "green", "ogohlantirish": "yellow", "xavfli": "red"}
        rows = []
        for r in qatorlar:
            rows.append({"detail": self._det("partner", r.partner_id.id), "cells": [
                {"text": r.partner_id.display_name or ""},
                {"text": r.masul_sotuvchi_id.display_name or "—"},
                {"text": self._fmt(r.jami_qarz), "align": "right", "tone": "strong"},
                {"text": self._fmt(r.qarz_0_30), "align": "right"},
                {"text": self._fmt(r.qarz_31_60), "align": "right",
                 "tone": "yellow" if r.qarz_31_60 else ""},
                {"text": self._fmt(r.qarz_60_plus), "align": "right",
                 "tone": "red" if r.qarz_60_plus else ""},
                {"text": self._fmt(r.kechikish_kun_soni, "int"), "align": "right",
                 "tone": tones.get(r.xavf_darajasi, "")},
            ]})
        columns = [
            {"label": _("Mijoz")}, {"label": _("Mas'ul sotuvchi")},
            {"label": _("Jami qarz"), "align": "right"},
            {"label": _("0–30 kun"), "align": "right"},
            {"label": _("31–60 kun"), "align": "right"},
            {"label": _("60+ kun"), "align": "right"},
            {"label": _("Kechikish (kun)"), "align": "right"},
        ]
        footer = [
            {"text": _("JAMI"), "tone": "strong"}, {"text": ""},
            {"text": self._fmt(jami), "align": "right", "tone": "strong"},
            {"text": self._fmt(q030), "align": "right"},
            {"text": self._fmt(q3160), "align": "right"},
            {"text": self._fmt(q60), "align": "right"},
            {"text": ""},
        ]
        sotuvchi = defaultdict(float)
        for r in qatorlar:
            sotuvchi[r.masul_sotuvchi_id.display_name or str(_("Biriktirilmagan"))] += r.jami_qarz
        panels = [
            self._split_panel(_("Qarzdorlik muddatlari bo'yicha"), "fa-pie-chart", [
                {"label": _("0 — 30 kun"), "value": q030, "color": "green",
                 "detail": self._det("aging", "yaxshi")},
                {"label": _("31 — 60 kun"), "value": q3160, "color": "orange",
                 "detail": self._det("aging", "ogohlantirish")},
                {"label": _("60+ kun"), "value": q60, "color": "red",
                 "detail": self._det("aging", "xavfli")},
            ]),
            self._rank_panel(_("Eng yirik qarzdorlar"), "fa-user-times",
                             [{"name": r.partner_id.display_name, "value": r.jami_qarz,
                               "sub": _("Kechikish: %s kun", r.kechikish_kun_soni),
                               "detail": self._det("partner", r.partner_id.id)}
                              for r in qatorlar],
                             color="red"),
            self._rank_panel(_("Mas'ul sotuvchilar bo'yicha qarz"), "fa-user",
                             sorted(({"name": k, "value": v} for k, v in sotuvchi.items()),
                                    key=lambda r: r["value"], reverse=True), color="orange"),
            self._grid_panel(_("To'lov intizomi (Aging)"), "fa-table", columns, rows, footer,
                             message=_("Ochiq qarzdorlik yo'q.")),
        ]
        alerts = []
        if q60:
            alerts.append(self._alert(
                _("60 kundan oshgan qarz: %s — %s ta mijoz", self._fmt(q60),
                  len(qatorlar.filtered(lambda r: r.qarz_60_plus))),
                "bad", "fa-times-circle", self._det("aging", "xavfli")))
        return {"kpis": kpis, "panels": panels, "alerts": alerts}

    # ==================================================================
    # 4. BOQUV
    # ==================================================================
    def _section_boquv(self, ctx):
        partiyalar = self._boquv_partiyalar()
        norm_fcr, norm_nobud, norm_vazn = self._norm("fcr"), self._norm("nobud"), self._norm("vazn")

        tirik = sum(partiyalar.mapped("joriy_son"))
        boshlangich = sum(partiyalar.mapped("boshlangich_son"))
        nobud_son = sum(partiyalar.mapped("nobud_son"))
        vazn = sum(partiyalar.mapped("jami_tirik_vazn"))
        fcr = self._weighted(partiyalar, "fcr", "joriy_son")
        nobud_foiz = (nobud_son / boshlangich * 100) if boshlangich else 0.0
        ort_vazn = (vazn / tirik) if tirik else self._ortacha(partiyalar.mapped("ortacha_vazn"))
        epef = self._weighted(partiyalar, "epef", "joriy_son")
        tannarx = self._weighted(partiyalar, "tannarx_1_kg", "jami_tirik_vazn")

        kpis = [
            self._kpi(_("Faol partiyalar"), len(partiyalar), "int", "fa-folder-open", "blue",
                      detail=self._det("boquv_partiyalar"),
                      action=self._act("agronova.boquv.partiya", [("holat", "=", "active")],
                                       _("Faol partiyalar"))),
            self._kpi(_("Tirik bosh soni"), tirik, "int", "fa-home", "green",
                      hint=_("Boshlang'ich: %s", self._fmt(boshlangich, "int")),
                      detail=self._det("boquv_partiyalar")),
            self._kpi(_("Jami tirik vazn"), vazn, "kg", "fa-balance-scale", "teal",
                      detail=self._det("boquv_partiyalar")),
            self._kpi(_("O'rtacha FCR"), fcr, "coef", "fa-cutlery", "purple",
                      hint=_("Normativ: %s", norm_fcr),
                      tone="bad" if fcr > norm_fcr else "ok", detail=self._det("boquv_ogish")),
            self._kpi(_("Nobudgarchilik"), nobud_foiz, "pct", "fa-heartbeat", "red",
                      hint=_("Normativ: %s%% · %s bosh", norm_nobud, self._fmt(nobud_son, "int")),
                      tone="bad" if nobud_foiz > norm_nobud else "ok",
                      detail=self._det("boquv_nobud"), higher_is_better=False),
            self._kpi(_("O'rtacha vazn"), ort_vazn, "qty", "fa-tachometer", "orange",
                      hint=_("Normativ: %s kg", norm_vazn),
                      tone="ok" if ort_vazn >= norm_vazn else "bad",
                      detail=self._det("boquv_partiyalar")),
            self._kpi(_("EPEF indeksi"), epef, "qty", "fa-trophy", "indigo",
                      hint=_("Samaradorlik indeksi (yuqori — yaxshi)"),
                      detail=self._det("boquv_partiyalar")),
            self._kpi(_("1 kg tirik vazn tannarxi"), tannarx, "money", "fa-money", "gray",
                      detail=self._det("boquv_partiyalar")),
        ]

        # Jonli bino kartochkalari: normadan og'ish bo'lsa qizil ramkaga o'tadi.
        cards, nodes = [], []
        top_bosh = max(partiyalar.mapped("joriy_son") or [0]) or 1
        for p in partiyalar:
            ogish = bool(p.ogish_bormi) or (p.fcr or 0) > norm_fcr or (p.nobud_foiz or 0) > norm_nobud
            det = self._det("boquv_partiya", p.id)
            if len(cards) < 24:
                cards.append({
                    "name": p.bino_id.display_name or p.name,
                    "sub": p.name,
                    "status": _("Og'ish bor") if ogish else _("Normada"),
                    "working": True,
                    "alert": ogish,
                    "age": _("%s-kun", p.yosh_kun or 0),
                    "progress": round(min((p.yosh_kun or 0) / (p.reja_kun or 42) * 100, 100), 1),
                    "head_display": self._fmt(p.joriy_son, "int"),
                    "fcr_display": self._fmt(p.fcr, "coef"),
                    "nobud_display": self._fmt(p.nobud_foiz, "pct"),
                    "detail": det,
                })
            nodes.append({
                "id": "p%s" % p.id,
                "label": p.bino_id.name or p.name,
                "group": p.filial_id.display_name or str(_("Filialsiz")),
                "shape": "barn",
                "h": round(0.3 + 0.7 * ((p.joriy_son or 0) / top_bosh), 3),
                "status": "bad" if ogish else "ok",
                "display": _("%s bosh", self._fmt(p.joriy_son, "int")),
                "metric": _("FCR %s · Nobud %s · %s-kun", self._fmt(p.fcr, "coef"),
                            self._fmt(p.nobud_foiz, "pct"), p.yosh_kun or 0),
                "detail": det,
            })

        filial = defaultdict(lambda: [0, None])
        for p in partiyalar:
            key = p.filial_id.display_name or str(_("Filialsiz"))
            filial[key][0] += p.joriy_son or 0
            filial[key][1] = p.filial_id.id or False

        rows = []
        for p in partiyalar:
            rows.append({"detail": self._det("boquv_partiya", p.id), "cells": [
                {"text": p.name or ""},
                {"text": p.filial_id.display_name or "—"},
                {"text": p.bino_id.display_name or "—"},
                {"text": self._fmt(p.yosh_kun, "int"), "align": "right"},
                {"text": self._fmt(p.joriy_son, "int"), "align": "right", "tone": "strong"},
                {"text": self._fmt(p.fcr, "coef"), "align": "right",
                 "tone": "danger" if (p.fcr or 0) > norm_fcr else "ok"},
                {"text": self._fmt(p.nobud_foiz, "pct"), "align": "right",
                 "tone": "danger" if (p.nobud_foiz or 0) > norm_nobud else "ok"},
                {"text": self._fmt(p.ortacha_vazn, "qty"), "align": "right"},
                {"text": self._fmt(p.epef, "qty"), "align": "right"},
                {"text": self._fmt(p.tannarx_1_kg), "align": "right"},
            ]})

        # Davr ichidagi kunlik nobud va yem sarfi — jurnal yozuvlaridan.
        nobud_s, yem_s = defaultdict(float), defaultdict(float)
        Jurnal = self._model("agronova.boquv.jurnal")
        if Jurnal is not None:
            for j in Jurnal.search([("sana", ">=", ctx["d_from_s"]), ("sana", "<=", ctx["d_to_s"])]
                                   + self._company_domain(Jurnal)):
                nobud_s[j.sana] += j.nobud_son or 0
                yem_s[j.sana] += j.yem_kg or 0.0

        panels = []
        if nodes:
            panels.append({
                "type": "scene3d", "mode": "farm", "title": _("Fermalar — 3D ko'rinish"),
                "icon": "fa-cube", "nodes": nodes, "links": [],
                "hint": _("Har bir bino — faol partiya. Balandlik — bosh soni, rang — "
                          "normativ holati. Binoni bosing — partiya kartasi ochiladi."),
                "legend": [{"label": _("Normada"), "color": "green"},
                           {"label": _("Og'ish bor"), "color": "red"}],
            })
        panels += [
            {"type": "farm", "title": _("Binolar holati (jonli)"), "icon": "fa-home",
             "cards": cards},
            self._gauge_panel(_("Normativdan og'ish"), "fa-tachometer", [
                self._gauge(_("FCR"), fcr, norm_fcr, "coef"),
                self._gauge(_("Nobudgarchilik (%)"), nobud_foiz, norm_nobud, "pct"),
                self._gauge(_("O'rtacha vazn (kg)"), ort_vazn, norm_vazn, "qty",
                            lower_is_better=False),
            ]),
            self._trend_panel(_("Kunlik nobudgarchilik (bosh)"), "fa-heartbeat", ctx,
                              nobud_s, label_a=_("Nobud"), value_fmt="int"),
            self._trend_panel(_("Yem sarfi dinamikasi"), "fa-cutlery", ctx,
                              yem_s, label_a=_("Yem (kg)"), value_fmt="kg"),
            self._rank_panel(_("Filiallar bo'yicha tirik bosh"), "fa-sitemap",
                             sorted(({"name": k, "value": v[0],
                                      "detail": self._det("boquv_partiyalar", v[1])}
                                     for k, v in filial.items()),
                                    key=lambda r: r["value"], reverse=True),
                             color="green", value_fmt="int"),
            self._rank_panel(_("FCR bo'yicha eng yomon partiyalar"), "fa-arrow-up",
                             sorted(({"name": p.name, "value": p.fcr,
                                      "sub": p.bino_id.display_name or "",
                                      "detail": self._det("boquv_partiya", p.id)}
                                     for p in partiyalar if p.fcr),
                                    key=lambda r: r["value"], reverse=True),
                             color="red", value_fmt="coef"),
            self._grid_panel(_("Faol partiyalar"), "fa-table", [
                {"label": _("Partiya")}, {"label": _("Filial")}, {"label": _("Bino")},
                {"label": _("Yosh (kun)"), "align": "right"},
                {"label": _("Tirik bosh"), "align": "right"},
                {"label": _("FCR"), "align": "right"},
                {"label": _("Nobud %"), "align": "right"},
                {"label": _("O'rt. vazn"), "align": "right"},
                {"label": _("EPEF"), "align": "right"},
                {"label": _("1 kg tannarx"), "align": "right"},
            ], rows, message=_("Faol partiya yo'q.")),
        ]
        alerts = []
        ogishlar = [c for c in nodes if c["status"] == "bad"]
        if ogishlar:
            alerts.append(self._alert(
                _("%s ta partiyada normativdan og'ish bor", len(ogishlar)), "bad",
                "fa-exclamation-triangle", self._det("boquv_ogish")))
        elif partiyalar:
            alerts.append(self._alert(_("Barcha faol partiyalar normada"), "ok", "fa-check"))
        kech = partiyalar.filtered(lambda p: (p.ortiqcha_kutish_kun or 0) > 0)
        if kech:
            alerts.append(self._alert(
                _("%s ta partiya rejadan ortiq turibdi (so'yishga topshirish kechikmoqda)",
                  len(kech)), "warn", "fa-clock-o", self._det("boquv_partiyalar")))
        return {"kpis": kpis, "panels": panels, "alerts": alerts}

    # ==================================================================
    # 5. ONA TOVUQ
    # ==================================================================
    def _section_ona_tovuq(self, ctx):
        Jurnal = self._model("agronova.ona_tovuq.jurnal.tuxum")
        norm = self._norm("tuxum_berish")
        jurnallar = Jurnal.search([
            ("date", ">=", ctx["d_from_s"]), ("date", "<=", ctx["d_to_s"]),
        ] + self._company_domain(Jurnal))

        jami = sum(jurnallar.mapped("jami_tuxum"))
        sifatli = sum(jurnallar.mapped("sifatli_tuxum"))
        brak = sum(jurnallar.mapped("brak_tuxum"))
        yarokli = sum(jurnallar.mapped("inkubatsiyaga_yarokli"))
        berish = self._ortacha(jurnallar.mapped("tuxum_berish_foiz"))

        Partiya = self._model("agronova.ona_tovuq.partiya.tuxum")
        partiyalar = Partiya.search(
            [("holat", "=", "active")] + self._company_domain(Partiya)
        ) if Partiya is not None else None
        tovuq = sum(partiyalar.mapped("tovuq_son")) if partiyalar else 0

        kpis = [
            self._kpi(_("Faol partiyalar"), len(partiyalar) if partiyalar else 0, "int",
                      "fa-folder-open", "blue", detail=self._det("ona_partiyalar")),
            self._kpi(_("Tuxum berayotgan tovuq"), tovuq, "int", "fa-circle-o", "green",
                      detail=self._det("ona_partiyalar")),
            self._kpi(_("Davrdagi tuxum"), jami, "int", "fa-circle", "orange",
                      hint=_("%s kunlik jurnal", len(jurnallar)), detail=self._det("ona_jurnal")),
            self._kpi(_("Tuxum berish"), berish, "pct", "fa-tachometer", "purple",
                      hint=_("Normativ: %s%%", norm),
                      tone="ok" if berish >= norm else "bad", detail=self._det("ona_jurnal")),
            self._kpi(_("Sifatli tuxum"), sifatli, "int", "fa-check-circle", "teal",
                      hint=_("%s%% jami tuxumdan", round(sifatli / jami * 100, 1) if jami else 0),
                      detail=self._det("ona_jurnal")),
            self._kpi(_("Brak tuxum"), brak, "int", "fa-times-circle", "red",
                      tone="bad" if brak else "", detail=self._det("ona_jurnal")),
            self._kpi(_("Inkubatsiyaga yaroqli"), yarokli, "int", "fa-life-ring", "indigo",
                      detail=self._det("ona_jurnal")),
        ]

        kunlik = defaultdict(float)
        sex = defaultdict(lambda: [0.0, None])
        for j in jurnallar:
            kunlik[j.date] += j.jami_tuxum or 0
            key = j.sex_id.display_name or str(_("Sexsiz"))
            sex[key][0] += j.jami_tuxum or 0
            sex[key][1] = j.sex_id.id or False

        panels = [
            self._trend_panel(_("Tuxum ishlab chiqarish dinamikasi"), "fa-bar-chart", ctx,
                              kunlik, label_a=_("Tuxum (dona)"), value_fmt="int",
                              detail_key="ona_jurnal"),
            self._split_panel(_("Tuxum sifati"), "fa-pie-chart", [
                {"label": _("Inkubatsiyaga yaroqli"), "value": yarokli, "color": "green"},
                {"label": _("Sifatli (qolgani)"), "value": max(sifatli - yarokli, 0),
                 "color": "blue"},
                {"label": _("Brak"), "value": brak, "color": "red"},
            ], value_fmt="int"),
            self._gauge_panel(_("Normativdan og'ish"), "fa-tachometer", [
                self._gauge(_("Tuxum berish (%)"), berish, norm, "pct",
                            lower_is_better=False, scale=100.0),
            ]),
            self._rank_panel(_("Sexlar bo'yicha tuxum"), "fa-sitemap",
                             sorted(({"name": k, "value": v[0],
                                      "detail": self._det("ona_jurnal", v[1])}
                                     for k, v in sex.items()),
                                    key=lambda r: r["value"], reverse=True),
                             color="orange", value_fmt="int"),
        ]
        alerts = []
        if jurnallar and berish < norm:
            alerts.append(self._alert(
                _("Tuxum berish normadan past: %s%% (norma %s%%)", round(berish, 1), norm),
                "bad", "fa-tachometer", self._det("ona_jurnal")))
        return {"kpis": kpis, "panels": panels, "alerts": alerts}

    # ==================================================================
    # 6. INKUBATORIYA
    # ==================================================================
    def _section_inkubatoriya(self, ctx):
        Ochilish = self._model("agronova.ink.ochilish")
        norm = self._norm("ochilish")
        ochilishlar = Ochilish.search([
            ("holat", "=", "done"),
            ("sana", ">=", ctx["d_from_s"]), ("sana", "<=", ctx["d_to_s"]),
        ] + self._company_domain(Ochilish))

        joja = sum(ochilishlar.mapped("ochilgan_joja"))
        ochilmagan = sum(ochilishlar.mapped("ochilmagan_tuxum"))
        nobud = sum(ochilishlar.mapped("nobud_son"))
        brak = sum(ochilishlar.mapped("brak_son"))
        sof = sum(ochilishlar.mapped("sof_joja"))
        qoyilgan = joja + ochilmagan
        ochilish_foiz = (joja / qoyilgan * 100) if qoyilgan else 0.0

        Partiya = self._model("agronova.ink.partiya")
        faol = Partiya.search(
            [("holat", "=", "inkubatsiyada")] + self._company_domain(Partiya)
        ) if Partiya is not None else None

        kpis = [
            self._kpi(_("Inkubatsiyadagi partiyalar"), len(faol) if faol else 0, "int",
                      "fa-life-ring", "blue", detail=self._det("ink_partiyalar")),
            self._kpi(_("Inkubatsiyadagi tuxum"), sum(faol.mapped("tuxum_dona")) if faol else 0,
                      "int", "fa-circle-o", "gray", detail=self._det("ink_partiyalar")),
            self._kpi(_("Ochilgan jo'ja"), joja, "int", "fa-child", "green",
                      hint=_("%s ta ochilish hujjati", len(ochilishlar)),
                      detail=self._det("ink_ochilish")),
            self._kpi(_("Ochilish foizi"), ochilish_foiz, "pct", "fa-tachometer", "purple",
                      hint=_("Normativ: %s%%", norm),
                      tone="ok" if ochilish_foiz >= norm else "bad",
                      detail=self._det("ink_ochilish")),
            self._kpi(_("Yaroqli jo'ja"), sof, "int", "fa-check-circle", "teal",
                      hint=_("Omborga kiradigani"), detail=self._det("ink_ochilish")),
            self._kpi(_("Nobud jo'ja"), nobud, "int", "fa-heartbeat", "red",
                      tone="bad" if nobud else "", detail=self._det("ink_ochilish")),
            self._kpi(_("Brak jo'ja"), brak, "int", "fa-times-circle", "orange",
                      tone="bad" if brak else "", detail=self._det("ink_ochilish")),
        ]

        kunlik = defaultdict(float)
        partiya_reyt = defaultdict(lambda: [0.0, None])
        for o in ochilishlar:
            kunlik[o.sana] += o.ochilgan_joja or 0
            key = o.partiya_id.display_name or str(_("Noma'lum"))
            partiya_reyt[key][0] += o.ochilgan_joja or 0
            partiya_reyt[key][1] = o.partiya_id.id or False

        panels = [
            self._split_panel(_("Inkubatsiya natijasi"), "fa-pie-chart", [
                {"label": _("Yaroqli jo'ja"), "value": sof, "color": "green"},
                {"label": _("Nobud"), "value": nobud, "color": "red"},
                {"label": _("Brak"), "value": brak, "color": "orange"},
                {"label": _("Ochilmagan tuxum"), "value": ochilmagan, "color": "gray"},
            ], value_fmt="int"),
            self._trend_panel(_("Ochilgan jo'jalar dinamikasi"), "fa-bar-chart", ctx,
                              kunlik, label_a=_("Jo'ja (dona)"), value_fmt="int",
                              detail_key="ink_ochilish"),
            self._gauge_panel(_("Normativdan og'ish"), "fa-tachometer", [
                self._gauge(_("Ochilish (%)"), ochilish_foiz, norm, "pct",
                            lower_is_better=False, scale=100.0),
            ]),
            self._rank_panel(_("Partiyalar bo'yicha ochilgan jo'ja"), "fa-list-ol",
                             sorted(({"name": k, "value": v[0],
                                      "detail": self._det("ink_ochilish", v[1])}
                                     for k, v in partiya_reyt.items()),
                                    key=lambda r: r["value"], reverse=True),
                             color="green", value_fmt="int"),
        ]
        alerts = []
        if ochilishlar and ochilish_foiz < norm:
            alerts.append(self._alert(
                _("Ochilish foizi normadan past: %s%% (norma %s%%)", round(ochilish_foiz, 1), norm),
                "bad", "fa-tachometer", self._det("ink_ochilish")))
        return {"kpis": kpis, "panels": panels, "alerts": alerts}

    # ==================================================================
    # 7. SO'YISH SEXI
    # ==================================================================
    def _section_soyish(self, ctx):
        Jarayon = self._model("agronova.soyish.jarayon")
        norm = self._norm("soyish_chiqim")
        jarayonlar = Jarayon.search([
            ("holat", "=", "done"),
            ("sana", ">=", ctx["d_from_s"]), ("sana", "<=", ctx["d_to_s"]),
        ] + self._company_domain(Jarayon))

        soyilgan = sum(jarayonlar.mapped("soyilgan_son"))
        nobud = sum(jarayonlar.mapped("nobud_son"))
        tushka = sum(jarayonlar.mapped("tushka_vazn_kg"))
        tirik_qiymat = sum(jarayonlar.mapped("tirik_qiymat"))
        chiqim = self._ortacha(jarayonlar.mapped("chiqim_foiz"))

        kpis = [
            self._kpi(_("So'yish hujjatlari"), len(jarayonlar), "int", "fa-file-text-o", "blue",
                      detail=self._det("soyish_jarayonlar")),
            self._kpi(_("So'yilgan bosh"), soyilgan, "int", "fa-cutlery", "orange",
                      detail=self._det("soyish_jarayonlar")),
            self._kpi(_("Tayyor mahsulot"), tushka, "kg", "fa-cube", "green",
                      detail=self._det("soyish_jarayonlar")),
            self._kpi(_("Chiqim foizi"), chiqim, "pct", "fa-tachometer", "purple",
                      hint=_("Normativ: %s%%", norm),
                      tone="ok" if chiqim >= norm else "bad",
                      detail=self._det("soyish_jarayonlar")),
            self._kpi(_("Nobud / brak"), nobud, "int", "fa-times-circle", "red",
                      tone="bad" if nobud else "", detail=self._det("soyish_jarayonlar")),
            self._kpi(_("Tirik parranda qiymati"), tirik_qiymat, "money", "fa-money", "gray",
                      detail=self._det("soyish_jarayonlar")),
        ]

        kunlik = defaultdict(float)
        for j in jarayonlar:
            kunlik[j.sana] += j.tushka_vazn_kg or 0.0

        panels = [
            self._trend_panel(_("Tayyor mahsulot dinamikasi"), "fa-bar-chart", ctx,
                              kunlik, label_a=_("Tushka (kg)"), value_fmt="kg",
                              detail_key="soyish_jarayonlar"),
            self._gauge_panel(_("Normativdan og'ish"), "fa-tachometer", [
                self._gauge(_("Chiqim (%)"), chiqim, norm, "pct",
                            lower_is_better=False, scale=100.0),
            ]),
        ]

        Natija = self._model("agronova.soyish.natija")
        if Natija is not None and jarayonlar:
            mahsulot = defaultdict(float)
            for n in Natija.search([("jarayon_id", "in", jarayonlar.ids)]):
                mahsulot[n.product_id.display_name or str(_("Noma'lum"))] += n.miqdor_kg or 0.0
            if mahsulot:
                parts = sorted(mahsulot.items(), key=lambda x: x[1], reverse=True)
                panels.append(self._split_panel(
                    _("Chiqim tarkibi"), "fa-pie-chart",
                    [{"label": k, "value": v, "color": _COLORS[i % len(_COLORS)]}
                     for i, (k, v) in enumerate(parts[:8])], value_fmt="kg"))
                panels.append(self._rank_panel(
                    _("Mahsulotlar bo'yicha chiqim"), "fa-cubes",
                    [{"name": k, "value": v} for k, v in parts], color="teal", value_fmt="kg"))
        alerts = []
        if jarayonlar and chiqim < norm:
            alerts.append(self._alert(
                _("Chiqim foizi normadan past: %s%% (norma %s%%)", round(chiqim, 1), norm),
                "bad", "fa-tachometer", self._det("soyish_jarayonlar")))
        return {"kpis": kpis, "panels": panels, "alerts": alerts}

    # ==================================================================
    # 8. YEM ZAVODI
    # ==================================================================
    def _yem_kun(self, dt):
        return fields.Datetime.context_timestamp(self, dt).date() if dt else None

    def _yem_davr(self, ctx, field):
        return [(field, ">=", ctx["dt_from_s"]), (field, "<=", ctx["dt_to_s"]),
                ("company_id", "in", ctx["companies"])]

    def _yem_asos(self, ctx):
        """Yem zavodi bo'limi va 3D sahna uchun umumiy hisob — bir marta yig'iladi."""
        env = self.env
        Mrp = env["mrp.production"].sudo()
        mos = Mrp.search([("state", "=", "done"), ("agronova_yem", "=", True)]
                         + self._yem_davr(ctx, "date_finished"))
        ochiq = Mrp.search([("state", "in", ("confirmed", "progress", "to_close")),
                            ("agronova_yem", "=", True), ("company_id", "in", ctx["companies"])])
        a = {"mos": mos, "ochiq": ochiq}
        a["kg"] = sum(mos.mapped("agronova_miqdor_kg"))
        a["kirim_kg"] = sum(mos.mapped("agronova_kirim_kg"))
        a["meyoriy_kg"] = sum(mos.mapped("agronova_meyoriy_yoqotish_kg"))
        a["haqiqiy_kg"] = sum(mos.mapped("agronova_haqiqiy_yoqotish_kg"))
        a["ortiq_kg"] = sum(mos.mapped("agronova_ortiqcha_yoqotish_kg"))
        a["tannarx"] = sum(mos.mapped("agronova_toliq_tannarx"))
        a["reja_1kg"] = self._ortacha([m for m in mos.mapped("agronova_reja_tannarx_1_kg") if m])
        a["ogish"] = mos.filtered("agronova_sarf_ogish")

        Q = env["agronova.yem.reja.qator"].sudo() if self._has("agronova.yem.reja.qator") else None
        qatorlar = Q.search([("reja_id.state", "not in", ("draft", "bekor")),
                             ("muddat", ">=", ctx["d_from_s"]), ("muddat", "<=", ctx["d_to_s"]),
                             ("company_id", "in", ctx["companies"])]) if Q is not None else []
        a["reja_kg"] = sum(qatorlar.mapped("miqdor_kg")) if Q is not None else 0.0
        a["reja_fakt_kg"] = sum(qatorlar.mapped("fakt_kg")) if Q is not None else 0.0
        a["kechikkan"] = qatorlar.filtered(lambda q: q.holat == "kechikmoqda") if Q is not None else []
        a["reja_kunlik"] = defaultdict(float)
        for q in (qatorlar or []):
            if q.muddat:
                a["reja_kunlik"][q.muddat] += q.miqdor_kg

        a["kunlik"] = defaultdict(float)
        a["mahsulot"] = defaultdict(float)
        for m in mos:
            a["kunlik"][self._yem_kun(m.date_finished)] += m.agronova_miqdor_kg or 0.0
            a["mahsulot"][m.product_id.display_name] += m.agronova_miqdor_kg or 0.0

        Qd = env["agronova.yem.qadoqlash"].sudo()
        qd = Qd.search([("state", "=", "tasdiqlangan")] + self._yem_davr(ctx, "sana"))
        a["qd"] = qd
        a["qadoq_kg"] = sum(qd.mapped("netto_kg"))
        a["qop"] = sum(qd.mapped("qop_soni"))
        a["qd_tafovut"] = qd.filtered(lambda r: r.toldirish_holat != "normal")

        J = env["agronova.yem.jonatma"].sudo()
        jon = J.search([("state", "=", "jonatildi")] + self._yem_davr(ctx, "sana"))
        a["jon"] = jon
        a["jon_kg"] = sum(jon.mapped("hujjat_kg"))
        a["jon_turi"] = defaultdict(float)
        for j in jon:
            a["jon_turi"][j.turi] += j.hujjat_kg
        a["sotuv_summa"] = sum(jon.filtered(lambda j: j.turi == "sotuv").mapped("summa"))

        Y = env["agronova.yem.yoqotish"].sudo()
        yoq = Y.search([("state", "!=", "rad")] + self._yem_davr(ctx, "sana"))
        a["yoq"] = yoq
        a["yoq_tekshiruv"] = Y.search([("state", "=", "tekshiruvda"), ("company_id", "in", ctx["companies"])])
        a["yoq_sabab"] = defaultdict(float)
        sab = dict(Y._fields["turi"].selection)
        for y in yoq:
            a["yoq_sabab"][sab.get(y.turi, y.turi)] += y.miqdor_kg

        Tx = env["agronova.yem.toxtash"].sudo()
        tox = Tx.search([("boshlanish", ">=", ctx["dt_from_s"]), ("boshlanish", "<=", ctx["dt_to_s"]),
                         ("company_id", "in", ctx["companies"])])
        a["tox"] = tox
        a["tox_min"] = sum(tox.mapped("davomiylik_min"))
        a["tox_hozir"] = Tx.search([("davom_etmoqda", "=", True), ("company_id", "in", ctx["companies"])])

        T = env["agronova.tarozi.tortish"].sudo()
        tt = T.search([("state", "=", "done")] + self._yem_davr(ctx, "sana"))
        a["tt"] = tt
        a["kirim_t_kg"] = sum(tt.filtered(lambda t: t.yonalish == "kirim").mapped("netto"))
        a["tt_tafovut"] = tt.filtered(lambda t: t.tafovut in ("ogohlantirish", "tasdiq", "kritik"))
        a["tt_kritik"] = tt.filtered(lambda t: t.tafovut == "kritik")
        a["tt_ochiq"] = T.search([("state", "=", "vazn1"), ("company_id", "in", ctx["companies"])])

        Z = env["agronova.yem.zaxira"].sudo()
        z = Z.search([("company_id", "in", ctx["companies"])])
        a["zaxira"] = z
        a["zaxira_xavf"] = z.filtered(lambda r: r.holat in ("kritik", "kam"))
        a["zaxira_kritik"] = z.filtered(lambda r: r.holat == "kritik")
        a["xomashyo_kg"] = sum(z.filtered(lambda r: r.yem_turi in ("xomashyo", "premiks")).mapped("qoldiq_kg"))

        E = env["agronova.yem.energiya"].sudo()
        en = E.search([("sana", ">=", ctx["d_from_s"]), ("sana", "<=", ctx["d_to_s"]),
                       ("company_id", "in", ctx["companies"])])
        a["kwh"] = sum(en.mapped("elektr_kwh"))
        a["kwh_t"] = (a["kwh"] / (sum(en.mapped("ishlab_chiqarilgan_t")) or 1.0)) if en else 0.0
        a["kwh_norma"] = float(env["ir.config_parameter"].sudo().get_param("agronova_yem.kwh_norma_t", 36) or 36)

        # Tayyor mahsulot — faqat zavod omborida: ona tovuq va boquvga jo'natilgani
        # ularning ombori, zavodniki emas.
        icp = env["ir.config_parameter"].sudo()
        ichki = [int(icp.get_param("agronova_yem.%s_location_id" % k, 0) or 0)
                 for k in ("ona_tovuq", "boquv", "ichki")]
        quants = env["stock.quant"].sudo().search([
            ("product_id.agronova_yem_turi", "=", "yem"), ("location_id.usage", "=", "internal"),
            ("company_id", "in", ctx["companies"])])
        chiqarilgan = env["stock.location"].sudo().browse([x for x in ichki if x]).exists()
        if chiqarilgan:
            quants = quants.filtered(lambda q: not any(
                q.location_id.parent_path.startswith(l.parent_path) for l in chiqarilgan))
        a["tayyor_kg"] = sum(env["product.product"]._agronova_kg(q.quantity, q.product_uom_id) for q in quants)
        S = env["agronova.yem.smena"].sudo()
        a["smenalar"] = S.search([("sana", ">=", ctx["d_from_s"]), ("sana", "<=", ctx["d_to_s"]),
                                  ("company_id", "in", ctx["companies"])])
        return a

    def _yem_scene(self, a):
        """Zavod ichidagi zanjir 3D da: kirim tarozisidan jo'natmagacha.

        Har bino — bitta bosqich, bosilsa o'sha bosqichning tafsiloti ochiladi.
        Rang — muammo bor-yo'qligi: kritik zaxira, me'yordan ortiq yo'qotish,
        to'xtab turgan liniya, kritik tarozi tafovuti.
        """
        lin = self.env["agronova.yem.liniya"].sudo().search([], limit=2)
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

    def _section_yem_zavodi(self, ctx):
        a = self._yem_asos(ctx)
        prev = self._prev_ctx(ctx)
        Mrp = self.env["mrp.production"].sudo()
        prev_kg = sum(Mrp.search([("state", "=", "done"), ("agronova_yem", "=", True)]
                                 + self._yem_davr(prev, "date_finished")).mapped("agronova_miqdor_kg"))
        kg = a["kg"]
        bajarilish = (a["reja_fakt_kg"] / a["reja_kg"] * 100.0) if a["reja_kg"] else 0.0
        meyor_pct = (a["meyoriy_kg"] / a["kirim_kg"] * 100.0) if a["kirim_kg"] else 0.0
        haqiqiy_pct = (a["haqiqiy_kg"] / a["kirim_kg"] * 100.0) if a["kirim_kg"] else 0.0
        bir_kg = (a["tannarx"] / kg) if kg else 0.0
        tt_farq = sum(abs(t.farq_kg) for t in a["tt_tafovut"])

        kpis = [
            self._kpi(_("Ishlab chiqarildi"), kg / 1000.0, "ton", "fa-industry", "green",
                      hint=_("%s ta buyurtma", len(a["mos"])), prev=prev_kg / 1000.0,
                      spark=self._spark(ctx, a["kunlik"]), detail=self._det("mrp_orders")),
            self._kpi(_("Reja bajarilishi"), bajarilish, "pct", "fa-bullseye", "blue",
                      hint=_("Reja %s", self._fmt(a["reja_kg"] / 1000.0, "ton")),
                      tone="ok" if bajarilish >= 98 else ("bad" if a["reja_kg"] else ""),
                      detail=self._det("yem_reja")),
            self._kpi(_("Haqiqiy yo'qotish"), haqiqiy_pct, "pct", "fa-exclamation-triangle", "red",
                      hint=_("Me'yor %(m)s%% · ortig'i %(o)s", m=round(meyor_pct, 2),
                             o=self._fmt(a["ortiq_kg"], "kg")),
                      tone="bad" if haqiqiy_pct > meyor_pct else "ok", detail=self._det("yem_yoqotish")),
            self._kpi(_("1 kg tannarxi"), bir_kg, "money", "fa-balance-scale", "purple",
                      hint=_("Reja: %s", self._fmt(a["reja_1kg"])),
                      tone="bad" if a["reja_1kg"] and bir_kg > a["reja_1kg"] * 1.02 else "",
                      detail=self._det("mrp_orders")),
            self._kpi(_("Qadoqlandi"), a["qadoq_kg"] / 1000.0, "ton", "fa-archive", "teal",
                      hint=_("%s qop", formatLang(self.env, a["qop"], digits=0)),
                      detail=self._det("yem_qadoqlash")),
            self._kpi(_("Jo'natildi"), a["jon_kg"] / 1000.0, "ton", "fa-truck", "orange",
                      hint=_("Sotuv %(s)s · ichki %(i)s",
                             s=self._fmt(a["jon_turi"].get("sotuv", 0.0) / 1000.0, "ton"),
                             i=self._fmt((a["jon_kg"] - a["jon_turi"].get("sotuv", 0.0)) / 1000.0, "ton")),
                      detail=self._det("yem_jonatma")),
            self._kpi(_("Xomashyo xavfi"), len(a["zaxira_xavf"]), "int", "fa-cubes", "red",
                      hint=_("Minimumdan past: %s", len(a["zaxira_kritik"])),
                      tone="bad" if a["zaxira_kritik"] else "ok", detail=self._det("yem_zaxira")),
            self._kpi(_("Liniya to'xtashi"), a["tox_min"] / 60.0, "hours", "fa-pause-circle", "gray",
                      hint=_("%s holat", len(a["tox"])), tone="bad" if a["tox_hozir"] else "",
                      detail=self._det("yem_toxtash")),
            self._kpi(_("Tarozi tafovuti"), tt_farq, "kg", "fa-balance-scale", "indigo",
                      hint=_("%(n)s ta tortishda, kritik: %(k)s", n=len(a["tt_tafovut"]), k=len(a["tt_kritik"])),
                      tone="bad" if a["tt_kritik"] else "", detail=self._det("yem_tortish")),
        ]

        mahsulot_rows = sorted(({"name": k, "value": v / 1000.0} for k, v in a["mahsulot"].items()),
                               key=lambda r: r["value"], reverse=True)
        tur_nomi = dict(self.env["agronova.yem.jonatma"]._fields["turi"].selection)
        rang = {"sotuv": "green", "ona_tovuq": "orange", "boquv": "blue", "ichki": "purple",
                "kochirish": "gray", "qaytarish": "red"}
        smena_rows = []
        guruh = defaultdict(lambda: {"fakt": 0.0, "reja": 0.0, "tox": 0})
        for s in a["smenalar"]:
            k = "%s · %s" % (s.liniya_id.name, s.smena_turi_id.name)
            guruh[k]["fakt"] += s.fakt_kg
            guruh[k]["reja"] += s.reja_kg or s.rejadagi_kg
            guruh[k]["tox"] += s.toxtash_min
            guruh[k]["liniya"] = s.liniya_id.id
        for k, g in guruh.items():
            smena_rows.append({"name": k, "value": g["fakt"] / 1000.0,
                               "sub": _("Reja %(r)s%% · to'xtash %(t)s daq.",
                                        r=round(g["fakt"] / g["reja"] * 100.0, 1) if g["reja"] else 0,
                                        t=int(g["tox"])),
                               "detail": self._det("yem_smena", g["liniya"])})
        zaxira_rows = []
        for z in a["zaxira"].sorted(lambda r: (r.holat_tartib, r.yetadi_kun))[:12]:
            ton = "danger" if z.holat == "kritik" else ("strong" if z.holat == "kam" else "")
            zaxira_rows.append({"detail": self._det("yem_zaxira"), "cells": [
                {"text": z.product_id.display_name},
                {"text": self._fmt(z.qoldiq_kg / 1000.0, "ton"), "align": "right", "tone": ton},
                {"text": self._fmt(z.min_kg / 1000.0, "ton"), "align": "right"},
                {"text": self._fmt(z.yetadi_kun, "days") if z.yetadi_kun < 999 else "—", "align": "right",
                 "tone": ton},
                {"text": dict(z._fields["holat"].selection).get(z.holat, ""), "tone": ton},
            ]})

        panels = [
            self._yem_scene(a),
            self._trend_panel(_("Ishlab chiqarish: fakt va reja"), "fa-bar-chart", ctx, a["kunlik"],
                              a["reja_kunlik"], label_a=_("Fakt"), label_b=_("Reja"), value_fmt="kg",
                              detail_key="mrp_orders"),
            self._gauge_panel(_("Asosiy me'yorlar"), "fa-tachometer", [
                self._gauge(_("Yo'qotish, %"), haqiqiy_pct, meyor_pct or 1.5, unit="pct"),
                self._gauge(_("Elektr, kVt·soat / t"), a["kwh_t"], a["kwh_norma"], unit="qty"),
                self._gauge(_("Reja bajarilishi, %"), bajarilish, 100.0, unit="pct",
                            lower_is_better=False, scale=120.0),
            ]),
            self._rank_panel(_("Mahsulotlar bo'yicha hajm"), "fa-cubes", mahsulot_rows, color="green",
                             value_fmt="ton"),
            self._split_panel(_("Jo'natma yo'nalishlari"), "fa-truck", [
                {"label": tur_nomi.get(k, k), "value": v / 1000.0, "color": rang.get(k, "gray"),
                 "detail": self._det("yem_jonatma", k)} for k, v in a["jon_turi"].items()], value_fmt="ton"),
            self._rank_panel(_("Smenalar samaradorligi"), "fa-users", smena_rows, color="blue", value_fmt="ton"),
            self._rank_panel(_("Yo'qotish sabablari"), "fa-exclamation-triangle",
                             sorted(({"name": k, "value": v, "detail": self._det("yem_yoqotish")}
                                     for k, v in a["yoq_sabab"].items()),
                                    key=lambda r: r["value"], reverse=True), color="red", value_fmt="kg"),
            self._grid_panel(_("Xomashyo zaxirasi"), "fa-database", [
                {"label": _("Xomashyo")}, {"label": _("Qoldiq"), "align": "right"},
                {"label": _("Minimum"), "align": "right"}, {"label": _("Yetadi"), "align": "right"},
                {"label": _("Holati")}], zaxira_rows,
                message=_("Zaxira jadvali bo'sh — «Xomashyo zaxirasi» da «Yangilash» ni bosing.")),
        ]

        alerts = []
        if a["tox_hozir"]:
            alerts.append(self._alert(
                _("Hozir to'xtab turibdi: %s", ", ".join(a["tox_hozir"].mapped("liniya_id.name"))),
                "bad", "fa-pause-circle", self._det("yem_toxtash")))
        if a["zaxira_kritik"]:
            alerts.append(self._alert(
                _("Minimumdan past xomashyo: %s", ", ".join(a["zaxira_kritik"].mapped("product_id.name")[:4])),
                "bad", "fa-cubes", self._det("yem_zaxira")))
        if a["yoq_tekshiruv"]:
            alerts.append(self._alert(
                _("%s ta yo'qotish boshliq tekshiruvini kutmoqda", len(a["yoq_tekshiruv"])),
                "warn", "fa-exclamation-triangle", self._det("yem_yoqotish")))
        if a["tt_kritik"]:
            alerts.append(self._alert(_("%s ta tortishda kritik og'irlik tafovuti", len(a["tt_kritik"])),
                                      "bad", "fa-balance-scale", self._det("yem_tortish")))
        if a["tt_ochiq"]:
            alerts.append(self._alert(_("Tarozida %s ta mashina 2-tortishni kutmoqda", len(a["tt_ochiq"])),
                                      "info", "fa-truck", self._det("yem_tortish")))
        if a["kechikkan"]:
            alerts.append(self._alert(_("Rejada %s ta qator kechikmoqda", len(a["kechikkan"])),
                                      "warn", "fa-clock-o", self._det("yem_reja")))
        if a["ogish"]:
            alerts.append(self._alert(_("%s ta buyurtmada sarf me'yordan chiqqan (tasdiqlangan)", len(a["ogish"])),
                                      "info", "fa-sliders", self._det("yem_sarf")))
        if a["reja_kg"] and bajarilish >= 98:
            alerts.append(self._alert(_("Reja %s%% bajarildi", round(bajarilish, 1)), "ok", "fa-check",
                                      self._det("yem_reja")))
        return {"kpis": kpis, "panels": panels, "alerts": alerts}

    # ==================================================================
    # 9. QISHLOQ XO'JALIGI
    # ==================================================================
    def _section_qishloq_xojaligi(self, ctx):
        Partiya = self._model("agronova.qx.partiya")
        partiyalar = Partiya.search(
            [("holat", "=", "active")] + self._company_domain(Partiya))

        maydon = sum(partiyalar.mapped("maydoni_ga"))
        hosil = sum(partiyalar.mapped("olingan_hosil_kg"))
        berilgan = sum(partiyalar.mapped("berilgan_kg"))
        qoldiq = sum(partiyalar.mapped("qoldiq_kg"))
        reja = sum(partiyalar.mapped("reja_hosil_kg"))
        hosildorlik = (hosil / maydon) if maydon else 0.0
        bajarilish = (hosil / reja * 100) if reja else 0.0

        kpis = [
            self._kpi(_("Faol partiyalar"), len(partiyalar), "int", "fa-leaf", "green",
                      detail=self._det("qx_partiyalar"),
                      action=self._act("agronova.qx.partiya", [("holat", "=", "active")],
                                       _("Faol ekin partiyalari"))),
            self._kpi(_("Ekin maydoni"), maydon, "ga", "fa-map-o", "teal",
                      detail=self._det("qx_partiyalar")),
            self._kpi(_("Olingan hosil"), hosil, "kg", "fa-shopping-basket", "orange",
                      detail=self._det("qx_partiyalar")),
            self._kpi(_("Hosildorlik"), hosildorlik, "qty", "fa-tachometer", "purple",
                      hint=_("kg / gektar"), detail=self._det("qx_partiyalar")),
            self._kpi(_("Reja bajarilishi"), bajarilish, "pct", "fa-check-circle", "blue",
                      hint=_("Reja: %s", self._fmt(reja, "kg")),
                      tone="ok" if bajarilish >= 100 else "bad",
                      detail=self._det("qx_partiyalar")),
            self._kpi(_("Omborda qoldiq"), qoldiq, "kg", "fa-archive", "gray",
                      hint=_("Berilgan: %s", self._fmt(berilgan, "kg")),
                      detail=self._det("qx_partiyalar")),
        ]

        ekin = defaultdict(float)
        nodes = []
        top = max(partiyalar.mapped("olingan_hosil_kg") or [0]) or 1
        for p in partiyalar:
            ekin[p.ekin_id.display_name or str(_("Noma'lum"))] += p.olingan_hosil_kg or 0.0
            nodes.append({
                "id": "q%s" % p.id, "label": p.ekin_id.display_name or p.name,
                "group": p.yer_id.display_name or str(_("Yer")), "shape": "field",
                "h": round(0.25 + 0.75 * ((p.olingan_hosil_kg or 0) / top), 3),
                "status": "ok" if (p.reja_bajarilishi or 0) >= 100 else "bad",
                "display": self._fmt(p.olingan_hosil_kg, "kg"),
                "metric": _("%s · reja %s", self._fmt(p.maydoni_ga, "ga"),
                            self._fmt(p.reja_bajarilishi, "pct")),
                "detail": self._det("qx_partiya", p.id),
            })

        rows = []
        for p in partiyalar:
            rows.append({"detail": self._det("qx_partiya", p.id), "cells": [
                {"text": p.name or ""},
                {"text": p.ekin_id.display_name or "—"},
                {"text": p.yer_id.display_name or "—"},
                {"text": self._fmt(p.maydoni_ga, "ga"), "align": "right"},
                {"text": self._fmt(p.olingan_hosil_kg, "kg"), "align": "right", "tone": "strong"},
                {"text": self._fmt(p.hosildorlik, "qty"), "align": "right"},
                {"text": self._fmt(p.reja_bajarilishi, "pct"), "align": "right",
                 "tone": "ok" if (p.reja_bajarilishi or 0) >= 100 else "danger"},
                {"text": self._fmt(p.qoldiq_kg, "kg"), "align": "right"},
            ]})

        panels = []
        if nodes:
            panels.append({
                "type": "scene3d", "mode": "farm", "title": _("Dalalar — 3D ko'rinish"),
                "icon": "fa-cube", "nodes": nodes, "links": [],
                "hint": _("Har bir maydon — ekin partiyasi. Balandlik — olingan hosil."),
                "legend": [{"label": _("Reja bajarilgan"), "color": "green"},
                           {"label": _("Rejadan orqada"), "color": "red"}],
            })
        panels += [
            self._rank_panel(_("Ekinlar bo'yicha hosil"), "fa-leaf",
                             sorted(({"name": k, "value": v} for k, v in ekin.items()),
                                    key=lambda r: r["value"], reverse=True),
                             color="green", value_fmt="kg"),
            self._split_panel(_("Hosil taqsimoti"), "fa-pie-chart", [
                {"label": _("Berilgan / sotilgan"), "value": berilgan, "color": "blue"},
                {"label": _("Omborda qoldiq"), "value": qoldiq, "color": "green"},
            ], value_fmt="kg"),
            self._grid_panel(_("Faol ekin partiyalari"), "fa-table", [
                {"label": _("Partiya")}, {"label": _("Ekin")}, {"label": _("Yer")},
                {"label": _("Maydon"), "align": "right"},
                {"label": _("Olingan hosil"), "align": "right"},
                {"label": _("Hosildorlik"), "align": "right"},
                {"label": _("Reja bajarilishi"), "align": "right"},
                {"label": _("Qoldiq"), "align": "right"},
            ], rows, message=_("Faol ekin partiyasi yo'q.")),
        ]
        return {"kpis": kpis, "panels": panels}

    # ==================================================================
    # 10. TRANSPORT
    # ==================================================================
    def _section_transport(self, ctx):
        Trip = self._model("agronova.trip")
        reyslar = Trip.search([
            ("date", ">=", ctx["d_from_s"]), ("date", "<=", ctx["d_to_s"]),
        ] + self._company_domain(Trip))

        daromad = sum(reyslar.mapped("revenue"))
        xarajat = sum(reyslar.mapped("expense_total"))
        foyda = sum(reyslar.mapped("profit"))
        tonna = sum(reyslar.mapped("cargo_weight_ton"))
        masofa = sum(reyslar.mapped("distance_km"))
        yakunlangan = len(reyslar.filtered(lambda r: r.state == "done"))

        kpis = [
            self._kpi(_("Reyslar"), len(reyslar), "int", "fa-truck", "blue",
                      hint=_("Yakunlangan: %s", yakunlangan), detail=self._det("trips")),
            self._kpi(_("Tashilgan yuk"), tonna, "ton", "fa-cubes", "teal",
                      detail=self._det("trips")),
            self._kpi(_("Bosib o'tilgan masofa"), masofa, "qty", "fa-road", "gray",
                      hint=_("km"), detail=self._det("trips")),
            self._kpi(_("Reys daromadi"), daromad, "money", "fa-money", "green",
                      detail=self._det("trips")),
            self._kpi(_("Reys xarajati"), xarajat, "money", "fa-credit-card", "orange",
                      detail=self._det("trips")),
            self._kpi(_("Sof foyda"), foyda, "money", "fa-line-chart", "purple",
                      tone="ok" if foyda >= 0 else "bad", detail=self._det("trips")),
        ]

        haydovchi = defaultdict(lambda: [0.0, None])
        tur = defaultdict(float)
        kunlik_d = defaultdict(float)
        kunlik_x = defaultdict(float)
        turlar = dict(Trip._fields["trip_type"]._description_selection(self.env))
        for r in reyslar:
            key = r.driver_id.display_name or str(_("Haydovchisiz"))
            haydovchi[key][0] += r.profit or 0.0
            haydovchi[key][1] = r.driver_id.id or False
            tur[str(turlar.get(r.trip_type) or r.trip_type or _("Noma'lum"))] += r.revenue or 0.0
            if r.date:
                kunlik_d[r.date] += r.revenue or 0.0
                kunlik_x[r.date] += r.expense_total or 0.0

        panels = [
            self._trend_panel(_("Daromad va xarajat dinamikasi"), "fa-bar-chart", ctx,
                              kunlik_d, kunlik_x,
                              label_a=_("Daromad"), label_b=_("Xarajat"), detail_key="trips"),
            self._split_panel(_("Reys turlari bo'yicha daromad"), "fa-pie-chart",
                              [{"label": k, "value": v,
                                "color": ["blue", "green", "orange", "purple"][i % 4]}
                               for i, (k, v) in enumerate(sorted(tur.items(),
                                                                 key=lambda x: x[1],
                                                                 reverse=True))]),
            self._rank_panel(_("Haydovchilar bo'yicha foyda"), "fa-user",
                             sorted(({"name": k, "value": v[0],
                                      "detail": self._det("trips", v[1])}
                                     for k, v in haydovchi.items()),
                                    key=lambda r: r["value"], reverse=True),
                             color="green"),
        ]
        alerts = []
        zarar = reyslar.filtered(lambda r: (r.profit or 0) < 0)
        if zarar:
            alerts.append(self._alert(_("%s ta reys zarar bilan yopilgan", len(zarar)),
                                      "warn", "fa-truck", self._det("trips")))
        return {"kpis": kpis, "panels": panels, "alerts": alerts}

    # ==================================================================
    # 11. XARID (ZAKUPKA)
    # ==================================================================
    def _section_zakupka(self, ctx):
        Kirim = self._model("agronova.kirim")
        prev = self._prev_ctx(ctx)

        def kirimlar(c):
            return Kirim.search([
                ("holat", "!=", "bekor"),
                ("sotib_olingan_sana", ">=", c["d_from_s"]),
                ("sotib_olingan_sana", "<=", c["d_to_s"]),
            ] + self._company_domain(Kirim))

        recs = kirimlar(ctx)
        recs_prev = kirimlar(prev)
        jami = sum(recs.mapped("jami_summa"))
        tolangan = sum(recs.mapped("tolangan_summa"))
        tranzit = recs.filtered(lambda k: k.holat == "tasdiqlangan")
        ogish = recs.filtered(lambda k: k.ogish_chegara and (k.ogish_foizi or 0) > k.ogish_chegara)
        ball = self._ortacha(recs.mapped("ball_ortacha"))

        Zayavka = self._model("agronova.zayavka")
        ochiq = Zayavka.search([("holat", "in", ["zakupchikka_yuborildi", "qabul_qilindi",
                                                 "qisman_bajarildi"])]
                               + self._company_domain(Zayavka)) if Zayavka is not None else []
        kech = ochiq.filtered(lambda z: z.holat == "zakupchikka_yuborildi" and z.javob_muddati
                              and z.javob_muddati < fields.Datetime.now()) if ochiq else []

        series = defaultdict(float)
        for k in recs:
            if k.sotib_olingan_sana:
                series[k.sotib_olingan_sana] += k.jami_summa or 0.0

        kpis = [
            self._kpi(_("Xarid summasi"), jami, "money", "fa-shopping-basket", "blue",
                      hint=_("%s ta kirim hujjati", len(recs)),
                      prev=sum(recs_prev.mapped("jami_summa")), higher_is_better=False,
                      spark=self._spark(ctx, series), detail=self._det("zk_kirimlar")),
            self._kpi(_("To'langan"), tolangan, "money", "fa-check-circle", "green",
                      detail=self._det("zk_kirimlar")),
            self._kpi(_("Ta'minotchiga qarz"), max(jami - tolangan, 0.0), "money",
                      "fa-credit-card", "red", detail=self._det("zk_kirimlar", "qarz")),
            self._kpi(_("Tranzitda"), len(tranzit), "int", "fa-truck", "orange",
                      hint=self._fmt(sum(tranzit.mapped("jami_summa"))),
                      detail=self._det("zk_kirimlar", "tasdiqlangan")),
            self._kpi(_("Ochiq zayavkalar"), len(ochiq), "int", "fa-list-alt", "indigo",
                      hint=_("Muddati o'tgan: %s", len(kech)),
                      tone="bad" if kech else "", detail=self._det("zk_zayavkalar")),
            self._kpi(_("Narx og'ishi"), len(ogish), "int", "fa-exclamation-triangle", "purple",
                      hint=_("Ruxsat narxidan chegaradan ortiq"),
                      tone="bad" if ogish else "ok", detail=self._det("zk_kirimlar", "ogish")),
            self._kpi(_("Ta'minot sifati"), ball, "qty", "fa-star", "teal",
                      hint=_("O'rtacha ball (to'liqlik, muddat, sifat)"),
                      detail=self._det("zk_kirimlar")),
        ]

        kontragent = defaultdict(lambda: [0.0, None])
        zakupchik = defaultdict(float)
        holat = defaultdict(float)
        holatlar = dict(Kirim._fields["holat"]._description_selection(self.env))
        for k in recs:
            key = k.kontragent_id.display_name or str(_("Noma'lum"))
            kontragent[key][0] += k.jami_summa or 0.0
            kontragent[key][1] = k.kontragent_id.id or False
            zakupchik[k.zakupchik_id.display_name or str(_("Noma'lum"))] += k.jami_summa or 0.0
            holat[k.holat] += k.jami_summa or 0.0

        colors = {"draft": "gray", "tasdiqlangan": "orange", "qabul_qilindi": "green"}
        panels = [
            self._trend_panel(_("Xarid dinamikasi"), "fa-bar-chart", ctx, series,
                              label_a=_("Xarid"), detail_key="zk_kirimlar"),
            self._split_panel(_("Kirimlar holati"), "fa-pie-chart", [
                {"label": str(holatlar.get(h, h)), "value": v, "color": colors.get(h, "blue"),
                 "detail": self._det("zk_kirimlar", h)}
                for h, v in holat.items()]),
            self._rank_panel(_("Ta'minotchilar bo'yicha xarid"), "fa-building",
                             sorted(({"name": k, "value": v[0],
                                      "detail": self._det("zk_kontragent", v[1])}
                                     for k, v in kontragent.items()),
                                    key=lambda r: r["value"], reverse=True), color="blue"),
            self._rank_panel(_("Zakupchiklar bo'yicha xarid"), "fa-user",
                             sorted(({"name": k, "value": v} for k, v in zakupchik.items()),
                                    key=lambda r: r["value"], reverse=True), color="indigo"),
        ]
        alerts = []
        if kech:
            alerts.append(self._alert(
                _("%s ta zayavkaga javob muddati o'tib ketgan", len(kech)), "bad",
                "fa-clock-o", self._det("zk_zayavkalar", "kech")))
        if ogish:
            alerts.append(self._alert(
                _("%s ta xaridda narx ruxsat etilgan chegaradan oshgan", len(ogish)), "warn",
                "fa-exclamation-triangle", self._det("zk_kirimlar", "ogish")))
        return {"kpis": kpis, "panels": panels, "alerts": alerts}

    # ==================================================================
    # 12. POS DO'KON
    # ==================================================================
    def _pos_domain(self, ctx):
        Order = self._model("pos.order")
        return [("state", "in", POS_DONE_STATES),
                ("date_order", ">=", ctx["dt_from_s"]),
                ("date_order", "<=", ctx["dt_to_s"])] + self._company_domain(Order)

    def _section_pos(self, ctx):
        Order = self._model("pos.order")
        prev = self._prev_ctx(ctx)
        orders = Order.search(self._pos_domain(ctx))
        prev_total = sum(Order.search(self._pos_domain(prev)).mapped("amount_total"))
        total = sum(orders.mapped("amount_total"))
        count = len(orders)
        avg = (total / count) if count else 0.0
        mijozlar = len(orders.mapped("partner_id"))

        series = defaultdict(float)
        soat = defaultdict(float)
        dokon = defaultdict(lambda: [0.0, None])
        for o in orders:
            local = fields.Datetime.context_timestamp(self, o.date_order) if o.date_order else None
            if local:
                series[local.date()] += o.amount_total or 0.0
                soat[local.hour] += o.amount_total or 0.0
            key = o.config_id.display_name or str(_("Noma'lum"))
            dokon[key][0] += o.amount_total or 0.0
            dokon[key][1] = o.config_id.id or False

        Line = self._model("pos.order.line")
        mahsulot = defaultdict(lambda: [0.0, 0.0])
        if orders:
            for product, qty, summa in Line._read_group(
                    [("order_id", "in", orders.ids)], ["product_id"],
                    ["qty:sum", "price_subtotal_incl:sum"]):
                mahsulot[product.display_name][0] += qty or 0.0
                mahsulot[product.display_name][1] += summa or 0.0

        Payment = self._model("pos.payment")
        tolov = []
        if orders:
            for i, (method, amount) in enumerate(Payment._read_group(
                    [("pos_order_id", "in", orders.ids)], ["payment_method_id"],
                    ["amount:sum"])):
                tolov.append({"label": method.display_name or str(_("Noma'lum")),
                              "value": amount or 0.0, "color": _COLORS[i % len(_COLORS)]})

        kpis = [
            self._kpi(_("Do'kon savdosi"), total, "money", "fa-shopping-cart", "blue",
                      prev=prev_total, spark=self._spark(ctx, series),
                      detail=self._det("pos_orders")),
            self._kpi(_("Cheklar soni"), count, "int", "fa-file-text-o", "green",
                      detail=self._det("pos_orders")),
            self._kpi(_("O'rtacha chek"), avg, "money", "fa-calculator", "purple",
                      detail=self._det("pos_orders")),
            self._kpi(_("Mijozlar (nomli)"), mijozlar, "int", "fa-users", "teal",
                      hint=_("Chekda mijoz ko'rsatilgan"), detail=self._det("pos_orders")),
            self._kpi(_("Sotilgan mahsulot turlari"), len(mahsulot), "int", "fa-cubes", "orange",
                      detail=self._det("pos_products")),
        ]
        panels = [
            self._trend_panel(_("Savdo dinamikasi"), "fa-bar-chart", ctx, series,
                              label_a=_("Savdo"), detail_key="pos_orders"),
            self._split_panel(_("To'lov usullari"), "fa-credit-card", tolov),
            self._rank_panel(_("Eng ko'p sotilgan mahsulotlar"), "fa-trophy",
                             sorted(({"name": k, "value": v[1],
                                      "sub": _("%s dona/kg", self._fmt(v[0], "qty"))}
                                     for k, v in mahsulot.items()),
                                    key=lambda r: r["value"], reverse=True), color="orange"),
            self._rank_panel(_("Do'konlar (kassalar) bo'yicha"), "fa-shopping-bag",
                             sorted(({"name": k, "value": v[0],
                                      "detail": self._det("pos_orders", v[1])}
                                     for k, v in dokon.items()),
                                    key=lambda r: r["value"], reverse=True), color="blue"),
            self._rank_panel(_("Soatlar bo'yicha savdo"), "fa-clock-o",
                             [{"name": "%02d:00 — %02d:00" % (h, h + 1), "value": soat[h]}
                              for h in sorted(soat)], color="teal"),
        ]
        return {"kpis": kpis, "panels": panels}

    # ==================================================================
    # 13. OMBOR
    # ==================================================================
    def _section_ombor(self, ctx):
        Quant = self._model("stock.quant")
        domain = [("location_id.usage", "=", "internal")] + self._company_domain(Quant)
        quants = Quant.search(domain, limit=20000)
        jami = sum(quants.mapped("value"))
        ombor = defaultdict(lambda: [0.0, None])
        kategoriya = defaultdict(float)
        manfiy = quants.filtered(lambda q: q.quantity < 0)
        for q in quants:
            wh = q.location_id.warehouse_id
            key = wh.display_name or q.location_id.display_name or str(_("Noma'lum"))
            ombor[key][0] += q.value or 0.0
            ombor[key][1] = wh.id or False
            kategoriya[q.product_id.categ_id.display_name or str(_("Kategoriyasiz"))] += q.value or 0.0

        Lot = self._model("stock.lot")
        muddat = []
        if Lot is not None and "expiration_date" in Lot._fields:
            chegara = fields.Datetime.to_string(
                datetime.combine(fields.Date.context_today(self) + relativedelta(days=7), time.max))
            muddat = quants.filtered(
                lambda q: q.quantity > 0 and q.lot_id.expiration_date
                and fields.Datetime.to_string(q.lot_id.expiration_date) <= chegara)

        Picking = self._model("stock.picking")
        kutilmoqda = Picking.search_count([("state", "in", ["confirmed", "assigned", "waiting"])]
                                          + self._company_domain(Picking))
        bajarildi = Picking.search_count([
            ("state", "=", "done"), ("date_done", ">=", ctx["dt_from_s"]),
            ("date_done", "<=", ctx["dt_to_s"])] + self._company_domain(Picking))

        kpis = [
            self._kpi(_("Ombor qiymati"), jami, "money", "fa-cubes", "blue",
                      hint=_("%s ta mahsulot qoldig'i", len(quants)),
                      detail=self._det("ombor_quants")),
            self._kpi(_("Omborlar"), len(ombor), "int", "fa-building", "teal",
                      detail=self._det("ombor_quants")),
            self._kpi(_("Kutilayotgan hujjatlar"), kutilmoqda, "int", "fa-hourglass-half",
                      "orange", hint=_("Kirim / chiqim / ko'chirish"),
                      action=self._act("stock.picking",
                                       [("state", "in", ["confirmed", "assigned", "waiting"])],
                                       _("Kutilayotgan ombor hujjatlari"))),
            self._kpi(_("Davrda bajarilgan"), bajarildi, "int", "fa-check-circle", "green",
                      action=self._act("stock.picking", [
                          ("state", "=", "done"), ("date_done", ">=", ctx["dt_from_s"]),
                          ("date_done", "<=", ctx["dt_to_s"])], _("Bajarilgan hujjatlar"))),
            self._kpi(_("Muddati yaqin (7 kun)"), len(muddat), "int", "fa-clock-o", "red",
                      tone="bad" if muddat else "ok", detail=self._det("ombor_muddat")),
            self._kpi(_("Manfiy qoldiq"), len(manfiy), "int", "fa-minus-circle", "purple",
                      tone="bad" if manfiy else "ok", detail=self._det("ombor_quants", "manfiy")),
        ]
        top = max((v[0] for v in ombor.values()), default=0.0) or 1.0
        nodes = [{
            "id": "w%s" % (v[1] or i), "label": k, "group": "", "shape": "crates",
            "h": round(0.25 + 0.75 * (max(v[0], 0) / top), 3), "status": "ok",
            "display": self._fmt_compact(v[0]), "metric": _("Ombor qiymati"),
            "detail": self._det("ombor_quants", v[1]),
        } for i, (k, v) in enumerate(sorted(ombor.items(), key=lambda x: x[1][0], reverse=True))]
        panels = []
        if nodes:
            panels.append({
                "type": "scene3d", "mode": "farm", "title": _("Omborlar — 3D ko'rinish"),
                "icon": "fa-cube", "nodes": nodes, "links": [],
                "hint": _("Taxlam balandligi — ombordagi tovar qiymati. Bosing — qoldiqlar ro'yxati."),
                "legend": [],
            })
        panels += [
            self._rank_panel(_("Omborlar bo'yicha qiymat"), "fa-building",
                             sorted(({"name": k, "value": v[0],
                                      "detail": self._det("ombor_quants", v[1])}
                                     for k, v in ombor.items()),
                                    key=lambda r: r["value"], reverse=True), color="blue"),
            self._split_panel(_("Kategoriyalar bo'yicha"), "fa-pie-chart",
                              [{"label": k, "value": v, "color": _COLORS[i % len(_COLORS)]}
                               for i, (k, v) in enumerate(sorted(
                                   kategoriya.items(), key=lambda x: x[1], reverse=True)[:8])]),
        ]
        alerts = []
        if muddat:
            alerts.append(self._alert(
                _("%s ta lotning yaroqlilik muddati 7 kun ichida tugaydi", len(muddat)),
                "bad", "fa-clock-o", self._det("ombor_muddat")))
        if manfiy:
            alerts.append(self._alert(_("%s ta manfiy qoldiq bor — inventarizatsiya kerak",
                                        len(manfiy)), "warn", "fa-minus-circle",
                                      self._det("ombor_quants", "manfiy")))
        return {"kpis": kpis, "panels": panels, "alerts": alerts}

    # ==================================================================
    # 14. ISH HAQI
    # ==================================================================
    def _section_ish_haqi(self, ctx):
        Davr = self._model("agronova.ish_haqi.davr")
        davrlar = Davr.search([
            ("holat", "=", "posted"),
            ("davr_boshi", "<=", ctx["d_to_s"]), ("davr_oxiri", ">=", ctx["d_from_s"]),
        ] + self._company_domain(Davr))
        hisob = sum(davrlar.mapped("jami_hisoblangan"))
        bonus = sum(davrlar.mapped("jami_bonus"))
        avans = sum(davrlar.mapped("jami_avans"))
        jarima = sum(davrlar.mapped("jami_jarima"))
        qolga = sum(davrlar.mapped("jami_qolga"))

        Qator = self._model("agronova.ish_haqi.davr.qator")
        qatorlar = Qator.search([("davr_id", "in", davrlar.ids)]) if davrlar else Qator.browse()
        xodimlar = len(qatorlar.mapped("employee_id"))
        bolim = defaultdict(lambda: [0.0, None])
        xodim = defaultdict(lambda: [0.0, None])
        for q in qatorlar:
            key = q.department_id.display_name or str(_("Bo'limsiz"))
            bolim[key][0] += q.hisoblangan or 0.0
            bolim[key][1] = q.department_id.id or False
            xkey = q.employee_id.display_name or ""
            xodim[xkey][0] += q.qolga or 0.0
            xodim[xkey][1] = q.employee_id.id

        Emp = self.env["hr.employee"].sudo()
        qarz_xodimlar = Emp.search([("active", "=", True)] + self._company_domain(Emp))
        balans = sum(e.agronova_balans for e in qarz_xodimlar if "agronova_balans" in e._fields)

        kpis = [
            self._kpi(_("Hisoblangan ish haqi"), hisob, "money", "fa-calculator", "blue",
                      hint=_("%s ta hujjat · %s xodim", len(davrlar), xodimlar),
                      detail=self._det("ish_haqi_davrlar")),
            self._kpi(_("Bonus"), bonus, "money", "fa-gift", "green",
                      detail=self._det("ish_haqi_qatorlar")),
            self._kpi(_("Avans"), avans, "money", "fa-hand-o-right", "orange",
                      detail=self._det("ish_haqi_qatorlar")),
            self._kpi(_("Jarima"), jarima, "money", "fa-gavel", "red",
                      detail=self._det("ish_haqi_qatorlar")),
            self._kpi(_("Qo'lga tegadi"), qolga, "money", "fa-money", "purple",
                      detail=self._det("ish_haqi_qatorlar")),
            self._kpi(_("Xodimlarga qarz (qoldiq)"), balans, "money", "fa-balance-scale", "indigo",
                      hint=_("Musbat — korxona xodimlarga qarzdor"),
                      detail=self._det("xodim_balans")),
        ]
        panels = [
            self._split_panel(_("Ish haqi tarkibi"), "fa-pie-chart", [
                {"label": _("Qo'lga tegadi"), "value": qolga, "color": "green"},
                {"label": _("Avans"), "value": avans, "color": "orange"},
                {"label": _("Jarima"), "value": jarima, "color": "red"},
            ]),
            self._rank_panel(_("Bo'limlar bo'yicha fond"), "fa-sitemap",
                             sorted(({"name": k, "value": v[0],
                                      "detail": self._det("ish_haqi_qatorlar", v[1])}
                                     for k, v in bolim.items()),
                                    key=lambda r: r["value"], reverse=True), color="blue"),
            self._rank_panel(_("Xodimlar: qo'lga tegadigan"), "fa-users",
                             sorted(({"name": k, "value": v[0]} for k, v in xodim.items()),
                                    key=lambda r: r["value"], reverse=True), color="green"),
        ]
        return {"kpis": kpis, "panels": panels}

    # ==================================================================
    # 15. DAVOMAT
    # ==================================================================
    def _section_davomat(self, ctx):
        Att = self._model("hr.attendance")
        recs = Att.search([("check_in", ">=", ctx["dt_from_s"]), ("check_in", "<=", ctx["dt_to_s"])]
                          + self._company_domain(Att))
        today = fields.Date.context_today(self)
        bugun_ctx = self._ctx_for(today, today)
        bugun = Att.search([("check_in", ">=", bugun_ctx["dt_from_s"]),
                            ("check_in", "<=", bugun_ctx["dt_to_s"])] + self._company_domain(Att))
        Emp = self.env["hr.employee"].sudo()
        jami_xodim = Emp.search_count([("active", "=", True)] + self._company_domain(Emp))
        bugun_kelgan = len(bugun.mapped("employee_id"))
        ichkarida = len(bugun.filtered(lambda a: not a.check_out).mapped("employee_id"))
        soat = sum(recs.mapped("worked_hours"))
        kunlar = len({(a.employee_id.id, a.check_in.date()) for a in recs if a.check_in})

        series = defaultdict(float)
        bolim = defaultdict(lambda: [0.0, None])
        for a in recs:
            if a.check_in:
                series[fields.Datetime.context_timestamp(self, a.check_in).date()] += 1
            key = a.employee_id.department_id.display_name or str(_("Bo'limsiz"))
            bolim[key][0] += a.worked_hours or 0.0
            bolim[key][1] = a.employee_id.department_id.id or False

        kpis = [
            self._kpi(_("Bugun kelganlar"), bugun_kelgan, "int", "fa-sign-in", "green",
                      hint=_("Jami faol xodim: %s", jami_xodim),
                      tone="ok" if jami_xodim and bugun_kelgan / jami_xodim >= 0.8 else "",
                      detail=self._det("davomat", "bugun")),
            self._kpi(_("Hozir ishda"), ichkarida, "int", "fa-building", "teal",
                      detail=self._det("davomat", "ichkarida")),
            self._kpi(_("Kelmaganlar (bugun)"), max(jami_xodim - bugun_kelgan, 0), "int",
                      "fa-user-times", "red", detail=self._det("davomat", "kelmagan")),
            self._kpi(_("Davrda ishlangan soat"), soat, "hours", "fa-clock-o", "blue",
                      detail=self._det("davomat")),
            self._kpi(_("O'rtacha ish kuni"), (soat / kunlar) if kunlar else 0.0, "hours",
                      "fa-hourglass-half", "purple", detail=self._det("davomat")),
        ]
        panels = [
            self._trend_panel(_("Kunlik davomat (kirishlar)"), "fa-bar-chart", ctx, series,
                              label_a=_("Kirishlar"), value_fmt="int", detail_key="davomat"),
            self._rank_panel(_("Bo'limlar bo'yicha ishlangan soat"), "fa-sitemap",
                             sorted(({"name": k, "value": v[0],
                                      "detail": self._det("davomat", v[1])}
                                     for k, v in bolim.items()),
                                    key=lambda r: r["value"], reverse=True),
                             color="blue", value_fmt="hours"),
        ]
        return {"kpis": kpis, "panels": panels}
