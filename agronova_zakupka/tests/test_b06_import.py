# -*- coding: utf-8 -*-
"""B06 — import: C1/C2 farqi, GTD majburiyati, Assets ulanishi."""
from odoo import fields
from odoo.exceptions import ValidationError
from odoo.tests import tagged

from .common import AgroNovaZakupkaCommon


@tagged('post_install', '-at_install', 'agronova_zakupka')
class TestB06Import(AgroNovaZakupkaCommon):

    def _import(self, turi='C1_tovar'):
        return self.env['agronova.import'].create({
            'import_turi': turi,
            'kontragent_id': self.kontragent.id,
            'zakupchik_id': self.user_zakupchik.id,
            'shartnoma_raqami': 'SH-2026-01',
            'shartnoma_sanasi': fields.Date.context_today(self),
            'yetkazib_berish_sharti': 'CIF',
            'valyuta_id': self.company.currency_id.id,
            'kutilayotgan_sana': fields.Date.context_today(self),
            'transport_xalqaro': 300_000.0,
            'sugurta': 100_000.0,
            'bojxona_bojji': 200_000.0,
        })

    def test_qoshimcha_xarajat_jamlanadi(self):
        imp = self._import()
        self.assertAlmostEqual(imp.qoshimcha_jami, 600_000.0, places=2)

    def test_gtdsiz_partiya_yopilmaydi(self):
        imp = self._import()
        imp.action_yolda()
        imp.action_bojxonada()
        with self.assertRaises(ValidationError):
            imp.action_keldi()
        imp.gtd_raqami = 'GTD-123456'
        imp.action_keldi()
        self.assertEqual(imp.holat, 'keldi')
        self.assertTrue(imp.haqiqiy_kelish_sanasi)

    def test_c1_tovar_omborga_tushadi(self):
        imp = self._import('C1_tovar')
        ruxsat = self._ruxsat_yaratish(narx=1000.0, miqdor=10.0)
        self._ruxsatni_tasdiqlash(ruxsat)
        kirim = self._kirim_yaratish(ruxsat, xarid_turi='C1_import_tovar')
        kirim.import_id = imp
        kirim.action_tasdiqlash()

        self.assertTrue(kirim.picking_kirim_id,
                        "C1 tovari omborga (tranzitga) tushadi")
        self.assertFalse(kirim.qator_ids.asset_id)

    def test_c2_uskuna_assetsga_tushadi(self):
        """TZ 10 — C2 omborga tushmaydi, asosiy vosita bo'ladi."""
        self.env['agronova.narx.normasi']._agronova_yozuvni_yangilash(
            self.tovar_uskuna, 5_000_000.0, 'qolda')
        ruxsat = self._ruxsat_yaratish(
            product=self.tovar_uskuna, narx=5_000_000.0, miqdor=1.0)
        self._ruxsatni_tasdiqlash(ruxsat)

        kirim = self._kirim_yaratish(
            ruxsat, xarid_turi='C2_import_uskuna', narx=5_000_000.0, miqdor=1.0)
        kirim.action_tasdiqlash()

        self.assertFalse(kirim.picking_kirim_id,
                         "C2 uskunasi omborga tushmasligi kerak")
        asset = kirim.qator_ids.asset_id
        self.assertTrue(asset, "Asosiy vosita kartochkasi ochilishi kerak")
        self.assertAlmostEqual(asset.original_value, 5_000_000.0, places=2)
        # Qarz baribir yozilgan — moliyaviy tan olinish tovar joyiga bog'liq emas.
        self.assertEqual(kirim.faktura_id.state, 'posted')

    def test_import_kirim_konteksti_xarajatni_uzatadi(self):
        imp = self._import('C1_tovar')
        imp.action_yolda()
        imp.action_bojxonada()
        action = imp.action_kirim_yaratish()
        ctx = action['context']
        self.assertEqual(ctx['default_xarid_turi'], 'C1_import_tovar')
        self.assertAlmostEqual(ctx['default_transport_xarajati'], 300_000.0)
        self.assertAlmostEqual(ctx['default_qoshimcha_xarajat'], 300_000.0)
