# -*- coding: utf-8 -*-
"""B07 — KPI: ochiq formula, nizo mexanizmi, oy yopilgach qulf."""
from odoo.exceptions import UserError
from odoo.tests import tagged

from .common import AgroNovaZakupkaCommon


@tagged('post_install', '-at_install', 'agronova_zakupka')
class TestB07Kpi(AgroNovaZakupkaCommon):

    def test_formula_ochiq_va_chegaralangan(self):
        Kpi = self.env['agronova.kpi']
        # Muddat ichida javob — to'liq ball.
        self.assertEqual(Kpi._agronova_ball_hisoblash('javob_tezligi', 0.5, 1.0), 10.0)
        # 1 ish soati kechikish — 2 ball jarima.
        self.assertEqual(Kpi._agronova_ball_hisoblash('javob_tezligi', 2.0, 1.0), 8.0)
        # Ball manfiy bo'lmaydi.
        self.assertEqual(Kpi._agronova_ball_hisoblash('javob_tezligi', 20.0, 1.0), 0.0)
        # Omborchi bahosi to'g'ridan-to'g'ri ball.
        self.assertEqual(Kpi._agronova_ball_hisoblash('toliqlik', 9.0, 10.0), 9.0)
        # Narx tejami: boshlang'ich 5, har 1% tejam +1.
        self.assertEqual(Kpi._agronova_ball_hisoblash('narx_tejami', 3.0, 0.0), 8.0)
        self.assertEqual(Kpi._agronova_ball_hisoblash('narx_tejami', -8.0, 0.0), 0.0)
        # 10 dan oshmaydi.
        self.assertEqual(Kpi._agronova_ball_hisoblash('narx_tejami', 50.0, 0.0), 10.0)

    def test_narx_tejami_qabulda_yoziladi(self):
        """Bu mezon majburiy — TZ 13: aks holda zakupchik eng qimmatidan oladi."""
        ruxsat = self._ruxsat_yaratish(narx=1000.0, miqdor=10.0)
        self._ruxsatni_tasdiqlash(ruxsat)
        kirim = self._kirim_yaratish(ruxsat, narx=950.0)   # normadan 5% arzon
        kirim.action_tasdiqlash()

        wizard = self.env['agronova.qabul.wizard'].with_context(
            default_kirim_id=kirim.id).create({'kirim_id': kirim.id})
        wizard.write({'ball_sababi': 'obyektiv_sabab'})
        wizard.action_qabul_qilish()

        tejam = self.env['agronova.kpi'].search([
            ('manba_id', '=', kirim.id), ('mezon_turi', '=', 'narx_tejami')])
        self.assertEqual(len(tejam), 1)
        self.assertAlmostEqual(tejam.qiymat, 5.0, places=2)
        self.assertAlmostEqual(tejam.ball, 10.0, places=2)

    def test_etiroz_mexanizmi(self):
        kpi = self.env['agronova.kpi']._agronova_ball_yozish(
            user=self.user_zakupchik, mezon='sifat',
            manba=self.kontragent, qiymat=4.0, norma=10.0)
        self.assertEqual(kpi.ball, 4.0)

        etiroz = self.env['agronova.kpi.etiroz'].create({
            'kpi_id': kpi.id,
            'yangi_ball': 8.0,
            'sabab': "Tovar sifatsizligi yetkazib beruvchi aybi edi",
        })
        self.assertEqual(etiroz.holat, 'korib_chiqilmoqda')
        self.assertEqual(etiroz.eski_ball, 4.0)
        kpi.invalidate_recordset()
        self.assertEqual(kpi.holat, 'etiroz')

        etiroz.qaror_izohi = "Dalil ko'rildi, e'tiroz o'rinli"
        etiroz.with_user(self.user_boshliq).action_qondirish()
        kpi.invalidate_recordset()
        self.assertEqual(kpi.ball, 8.0)
        self.assertEqual(kpi.holat, 'qayta_yozildi')

    def test_etiroz_rad_etilishi(self):
        kpi = self.env['agronova.kpi']._agronova_ball_yozish(
            user=self.user_zakupchik, mezon='muddat',
            manba=self.kontragent, qiymat=6.0, norma=10.0)
        etiroz = self.env['agronova.kpi.etiroz'].create({
            'kpi_id': kpi.id, 'yangi_ball': 10.0, 'sabab': "Kechikmagan edim"})
        with self.assertRaises(UserError):
            etiroz.with_user(self.user_boshliq).action_rad_etish()
        etiroz.qaror_izohi = "Yetkazish sanasi hujjatda kechikkan"
        etiroz.with_user(self.user_boshliq).action_rad_etish()
        kpi.invalidate_recordset()
        self.assertEqual(kpi.ball, 6.0, "Rad etilgan e'tiroz ballni tegmaydi")
        self.assertEqual(kpi.holat, 'hisoblandi')

    def test_davr_yopilgach_ball_qulflanadi(self):
        kpi = self.env['agronova.kpi']._agronova_ball_yozish(
            user=self.user_zakupchik, mezon='sifat',
            manba=self.kontragent, qiymat=7.0, norma=10.0)
        davr = kpi.davr_id
        davr.action_yopish()

        kpi.invalidate_recordset()
        self.assertEqual(kpi.holat, 'qulflangan')
        with self.assertRaises(UserError):
            kpi.ball = 10.0
        with self.assertRaises(UserError):
            kpi.unlink()
        with self.assertRaises(UserError):
            kpi.action_etiroz()

    def test_ochiq_etiroz_borligida_davr_yopilmaydi(self):
        kpi = self.env['agronova.kpi']._agronova_ball_yozish(
            user=self.user_zakupchik, mezon='sifat',
            manba=self.kontragent, qiymat=3.0, norma=10.0)
        self.env['agronova.kpi.etiroz'].create({
            'kpi_id': kpi.id, 'yangi_ball': 9.0, 'sabab': "Nizo bor"})
        with self.assertRaises(UserError):
            kpi.davr_id.action_yopish()

    def test_xodim_faqat_oz_ballini_koradi(self):
        """Jonli ko'rinish — TZ 13.2, lekin boshqaning bali ko'rinmaydi."""
        meniki = self.env['agronova.kpi']._agronova_ball_yozish(
            user=self.user_zakupchik, mezon='sifat',
            manba=self.kontragent, qiymat=9.0, norma=10.0)
        boshqaniki = self.env['agronova.kpi']._agronova_ball_yozish(
            user=self.user_omborchi, mezon='sifat',
            manba=self.kontragent, qiymat=9.0, norma=10.0)

        korinadi = self.env['agronova.kpi'].with_user(self.user_zakupchik).search([])
        self.assertIn(meniki, korinadi)
        self.assertNotIn(boshqaniki, korinadi)
