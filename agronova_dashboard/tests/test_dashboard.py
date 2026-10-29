# -*- coding: utf-8 -*-
"""Rahbar paneli: har bo'lim va har tafsilot xatosiz, JSON ga aylanadigan javob beradi."""
import json

from odoo.exceptions import AccessError, UserError
from odoo.tests import TransactionCase, tagged


def _collect(obj, acc):
    if isinstance(obj, dict):
        if set(obj) == {"key", "ref"} and isinstance(obj["key"], str):
            acc.append(obj)
        for v in obj.values():
            _collect(v, acc)
    elif isinstance(obj, list):
        for v in obj:
            _collect(v, acc)


@tagged("post_install", "-at_install")
class TestRahbarPaneli(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.D = cls.env["agronova.executive.dashboard"]

    def test_bolimlar_va_tafsilotlar(self):
        meta = self.D.get_dashboard_meta()
        self.assertIn("overview", meta["sections"])
        details = []
        for section in meta["sections"]:
            for period in ("today", "week", "month", "6months", "year"):
                data = self.D.get_dashboard_data(section, period)
                json.dumps(data)
                self.assertTrue(data["available"], "%s: %s" % (section, data.get("message")))
                _collect(data, details)
        for d in details:
            json.dumps(self.D.get_detail(d["key"], "year", False, False, d["ref"]))

    def test_barcha_tafsilot_metodlari(self):
        keys = [n[len("_detail_"):] for n in dir(type(self.D)) if n.startswith("_detail_")]
        for key in keys:
            for ref in (None, 999999, "xavfli", {"from": "2026-01-01", "to": "2026-01-31"}):
                json.dumps(self.D.get_detail(key, "month", False, False, ref))

    def test_notogri_kalit_rad_etiladi(self):
        for bad in ("../x", "a;b", "", None, "yoq_bunday"):
            with self.assertRaises(UserError):
                self.D.get_detail(bad)

    def test_huquqsiz_foydalanuvchi(self):
        user = self.env["res.users"].create({
            "name": "Oddiy", "login": "oddiy_panel_test",
            "group_ids": [(6, 0, [self.env.ref("base.group_user").id])],
        })
        with self.assertRaises(AccessError):
            self.D.with_user(user).get_dashboard_data("overview")
