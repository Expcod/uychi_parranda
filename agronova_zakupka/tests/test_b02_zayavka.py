# -*- coding: utf-8 -*-
"""B02 — zayavka: qabul/rad, muddat nazorati, eskalatsiya, qisman bajarish."""
from datetime import timedelta

from odoo import fields
from odoo.exceptions import UserError
from odoo.tests import tagged

from .common import AgroNovaZakupkaCommon


@tagged('post_install', '-at_install', 'agronova_zakupka')
class TestB02Zayavka(AgroNovaZakupkaCommon):

    def _zayavka(self, muhimlik='2_orta'):
        return self.env['agronova.zayavka'].create({
            'warehouse_id': self.warehouse.id,
            'omborchi_id': self.user_omborchi.id,
            'muhimlik_darajasi': muhimlik,
            'maksimal_muddat': fields.Datetime.now() + timedelta(days=3),
            'qator_ids': [(0, 0, {
                'product_id': self.tovar.id,
                'miqdor': 10.0,
            })],
        })

    def test_bosh_zayavka_yuborilmaydi(self):
        zayavka = self.env['agronova.zayavka'].create({
            'warehouse_id': self.warehouse.id,
            'omborchi_id': self.user_omborchi.id,
            'maksimal_muddat': fields.Datetime.now() + timedelta(days=1),
        })
        with self.assertRaises(UserError):
            zayavka.action_yuborish()

    def test_javob_muddati_ish_kalendari_boyicha(self):
        """Muddat astronomik emas, ish soati bo'yicha qo'yiladi (TZ 21.7)."""
        zayavka = self._zayavka('1_juda_muhim')
        zayavka.action_yuborish()
        self.assertEqual(zayavka.holat, 'zakupchikka_yuborildi')
        self.assertTrue(zayavka.javob_muddati)
        self.assertGreater(zayavka.javob_muddati, zayavka.yuborilgan_vaqti,
                           "Muddat yuborilgan paytdan keyin bo'lishi kerak")
        # Kalendar haqiqatan ishlatilganini tekshiramiz: ish soatlarini
        # sanaganda 1 soat chiqadi (astronomik farq undan katta bo'lishi
        # mumkin — tunga tushsa muddat ertangi kunga suriladi).
        ish_soati = zayavka._agronova_ish_soatlari(
            zayavka.yuborilgan_vaqti, zayavka.javob_muddati)
        self.assertAlmostEqual(ish_soati, 1.0, places=1)

    def test_qabul_qilish_kpi_yozadi(self):
        zayavka = self._zayavka()
        zayavka.action_yuborish()
        zayavka.with_user(self.user_zakupchik).action_qabul_qilish()

        self.assertEqual(zayavka.holat, 'qabul_qilindi')
        self.assertEqual(zayavka.zakupchik_id, self.user_zakupchik)
        self.assertTrue(zayavka.javob_vaqti)
        self.assertFalse(zayavka.kechikdimi, "Muddat ichida javob berildi")

        kpi = self.env['agronova.kpi'].search([
            ('xodim_id', '=', self.user_zakupchik.id),
            ('mezon_turi', '=', 'javob_tezligi'),
            ('manba_id', '=', zayavka.id),
        ])
        self.assertEqual(len(kpi), 1)
        self.assertEqual(kpi.ball, 10.0, "Muddat ichidagi javob — to'liq ball")

    def test_rad_etish_sababsiz_bolmaydi(self):
        zayavka = self._zayavka()
        zayavka.action_yuborish()
        with self.assertRaises(UserError):
            zayavka.with_user(self.user_zakupchik).action_rad_etish()

        zayavka.rad_sababi = 'bozorda_yoq'
        zayavka.with_user(self.user_zakupchik).action_rad_etish()
        self.assertEqual(zayavka.holat, 'rad_etildi')

        zayavka.action_qoralamaga()
        self.assertEqual(zayavka.holat, 'draft')
        self.assertFalse(zayavka.javob_vaqti)

    def test_muddat_otsa_eskalatsiya_boladi(self):
        zayavka = self._zayavka('1_juda_muhim')
        zayavka.action_yuborish()
        # Muddatni orqaga suramiz — cron uni kechikkan deb topishi kerak.
        zayavka.javob_muddati = fields.Datetime.now() - timedelta(hours=2)

        self.env['agronova.zayavka']._cron_muddat_nazorati()
        zayavka.invalidate_recordset()
        self.assertTrue(zayavka.kechikdimi)
        self.assertGreaterEqual(zayavka.eskalatsiya_darajasi, 1)
        self.assertTrue(
            zayavka.activity_ids,
            "Eskalatsiyada rahbarga faoliyat ochilishi kerak")

    def test_qisman_bajarish_kuzatiladi(self):
        zayavka = self._zayavka()
        zayavka.action_yuborish()
        zayavka.with_user(self.user_zakupchik).action_qabul_qilish()
        qator = zayavka.qator_ids

        ruxsat = self._ruxsat_yaratish(miqdor=10.0)
        ruxsat.zayavka_id = zayavka
        ruxsat.zayavka_qatori_id = qator
        self._ruxsatni_tasdiqlash(ruxsat)

        kirim = self._kirim_yaratish(ruxsat, miqdor=6.0)
        kirim.qator_ids.zayavka_qatori_id = qator
        kirim.action_tasdiqlash()
        kirim.qator_ids.qabul_miqdor = 6.0
        kirim.invalidate_recordset()

        self.assertEqual(qator.bajarilgan_miqdor, 6.0)
        self.assertEqual(qator.qoldiq_miqdor, 4.0)
        self.assertAlmostEqual(zayavka.bajarilish_foizi, 60.0, places=1)
