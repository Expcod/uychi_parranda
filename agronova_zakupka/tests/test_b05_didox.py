# -*- coding: utf-8 -*-
"""B05 — Didox: avtomat solishtirish va ikki tomonlama hisobot."""
from datetime import timedelta

from odoo import fields
from odoo.tests import tagged

from .common import AgroNovaZakupkaCommon


@tagged('post_install', '-at_install', 'agronova_zakupka')
class TestB05Didox(AgroNovaZakupkaCommon):

    def setUp(self):
        super().setUp()
        self.ruxsat = self._ruxsat_yaratish(narx=1000.0, miqdor=10.0)
        self._ruxsatni_tasdiqlash(self.ruxsat)
        self.kirim = self._kirim_yaratish(self.ruxsat)
        self.kirim.action_tasdiqlash()

    def _didox(self, summa=None, sana=None, stir=None, name='DX-1'):
        return self.env['agronova.didox.log'].create({
            'name': name,
            'sana': sana or self.kirim.sotib_olingan_sana,
            'stir': stir or self.kontragent.stir,
            'summa': summa if summa is not None else self.kirim.jami_summa,
        })

    def test_stir_summa_sana_boyicha_moslashadi(self):
        log = self._didox()
        self.assertEqual(log.kontragent_id, self.kontragent)
        log.action_solishtirish()

        self.assertEqual(log.holat, 'moslashtirildi')
        self.assertEqual(log.moslashtirilgan_kirim_id, self.kirim)
        self.kirim.invalidate_recordset()
        self.assertEqual(self.kirim.faktura_holati, 'moslashtirildi')
        self.assertEqual(self.kirim.didox_log_id, log)
        self.assertIn('DX-1', self.kirim.faktura_id.ref,
                      "Didox raqami buxgalteriya hujjatida ko'rinsin")

    def test_summa_farq_qilsa_nomos_belgilanadi(self):
        log = self._didox(summa=self.kirim.jami_summa + 5000.0)
        log.action_solishtirish()
        self.assertEqual(log.holat, 'nomos')
        self.assertIn("summa", (log.nomoslik_izohi or '').lower())
        self.kirim.invalidate_recordset()
        self.assertEqual(self.kirim.faktura_holati, 'kutilmoqda')

    def test_tovari_yoq_faktura_kutilmoqdada_qoladi(self):
        """«Fakturasi bor, tovari yo'q» hisoboti shu holatdan quriladi."""
        begona = self.env['res.partner'].create({
            'name': "Begona ta'minotchi",
            'shaxs_turi': 'yuridik',
            'stir': '300999888',
        })
        log = self._didox(stir=begona.stir, name='DX-2')
        log.action_solishtirish()
        self.assertEqual(log.holat, 'kutilmoqda')
        self.assertIn(log, self.env['agronova.didox.log'].search(
            [('holat', 'in', ('kutilmoqda', 'nomos'))]))

    def _eski_kirim(self, kun=10):
        """Orqadagi sana bilan kirim — tasdiqlangan hujjat sanasi
        keyinchalik tahrirlanmaydi (TZ 21.6), shuning uchun darhol
        shunday yaratamiz."""
        ruxsat = self._ruxsat_yaratish(narx=1000.0, miqdor=5.0)
        self._ruxsatni_tasdiqlash(ruxsat)
        kirim = self._kirim_yaratish(
            ruxsat, miqdor=5.0,
            sana=fields.Date.subtract(fields.Date.context_today(self), days=kun))
        kirim.action_tasdiqlash()
        return kirim

    def test_faktura_kutilayotgan_tovarlar_hisoboti(self):
        self.assertIn(self.kirim, self.env['agronova.kirim'].search(
            [('faktura_holati', '=', 'kutilmoqda')]))

        eski = self._eski_kirim(10)
        self.assertEqual(eski.faktura_kutish_kuni, 10)
        self.assertIn(eski, self.env['agronova.kirim'].search(
            [('faktura_kutish_kuni', '>', 3)]))

    def test_kechikkan_fakturaga_buxgalter_ogohlantiriladi(self):
        eski = self._eski_kirim(10)
        self.env['agronova.kirim']._cron_faktura_ogohlantirish()
        self.assertTrue(
            eski.activity_ids.filtered(
                lambda a: a.user_id == self.user_buxgalter),
            "Faktura kechikkanda buxgalterga faoliyat ochilishi kerak")

    def test_rekvizitsiz_cron_xatoga_tushmaydi(self):
        """Didox sozlanmagan bo'lsa cron jim o'tadi — oqim to'xtamaydi."""
        param = self.env['ir.config_parameter'].sudo()
        param.set_param('agronova_zakupka.didox_url', '')
        param.set_param('agronova_zakupka.didox_token', '')
        self.assertEqual(
            self.env['agronova.didox.log']._agronova_didox_soov(
                fields.Date.context_today(self) - timedelta(days=1),
                fields.Date.context_today(self)),
            [])
        self.env['agronova.didox.log']._cron_didox_tortish()
        self.env['agronova.didox.log']._cron_didox_solishtirish()
