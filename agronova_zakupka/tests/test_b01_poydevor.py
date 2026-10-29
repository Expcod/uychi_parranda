# -*- coding: utf-8 -*-
"""B01 — poydevor: kontragent bazasi, tranzit ombori, depozit bog'lanishi."""
from psycopg2 import IntegrityError

from odoo.exceptions import UserError, ValidationError
from odoo.tests import tagged
from odoo.tools import mute_logger

from .common import AgroNovaZakupkaCommon


@tagged('post_install', '-at_install', 'agronova_zakupka')
class TestB01Poydevor(AgroNovaZakupkaCommon):

    def test_stir_takrorlanmaydi(self):
        with self.assertRaises(IntegrityError), mute_logger('odoo.sql_db'):
            with self.cr.savepoint():
                self.env['res.partner'].create({
                    'name': "Ikkinchi ta'minotchi",
                    'shaxs_turi': 'yuridik',
                    'stir': self.kontragent.stir,
                })

    def test_yuridik_shaxs_stirsiz_saqlanmaydi(self):
        with self.assertRaises(ValidationError):
            self.env['res.partner'].create({
                'name': "STIRsiz yuridik",
                'shaxs_turi': 'yuridik',
            })

    def test_bank_rekviziti_juft_kiritiladi(self):
        with self.assertRaises(ValidationError):
            self.env['res.partner'].create({
                'name': "Yarim rekvizitli",
                'shaxs_turi': 'jismoniy',
                'bank_hisob_raqami': '20208000900000000009',
            })

    def test_kontragent_ochirilmaydi_faqat_bloklanadi(self):
        with self.assertRaises(UserError):
            self.kontragent.unlink()

        with self.assertRaises(UserError):
            # Sababsiz bloklab bo'lmaydi.
            self.kontragent.action_zakupka_bloklash()

        self.kontragent.bloklash_sababi = "Sifatsiz tovar yetkazdi"
        self.kontragent.action_zakupka_bloklash()
        self.assertEqual(self.kontragent.zakupka_holati, 'bloklangan')

        # Bloklangan kontragent yangi hujjatda ishlatilmaydi...
        with self.assertRaises(ValidationError):
            self._ruxsat_yaratish()
        # ...lekin yozuvning o'zi joyida turadi (eski hujjatlar buzilmasin).
        self.assertTrue(self.kontragent.exists())

        self.kontragent.action_zakupka_faollashtirish()
        self.assertEqual(self.kontragent.zakupka_holati, 'faol')

    def test_zakupchikka_tranzit_ombori_ochiladi(self):
        tranzit = self.user_zakupchik._agronova_tranzit()
        self.assertTrue(tranzit)
        self.assertEqual(tranzit.usage, 'internal',
                         "Tranzit ichki joy bo'lishi kerak — tovar balansda "
                         "zakupchik zimmasida turadi")
        self.assertTrue(tranzit.zakupchik_tranzit)
        self.assertEqual(tranzit.zakupchik_user_id, self.user_zakupchik)
        # Ikkinchi chaqiruv yangi joy ochmaydi.
        self.assertEqual(self.user_zakupchik._agronova_tranzit(), tranzit)

    def test_depozit_userga_bogllanadi(self):
        self.assertEqual(self.user_zakupchik.zakupka_depozit_id, self.depozit)
        self.assertEqual(self.depozit.balans, 10_000_000.0)

    def test_kategoriya_kuzatuvi_tovarga_tarqaladi(self):
        """TZ 21.2 — dori va oziq-ovqatda kuzatuv boshidan yoqiladi."""
        self.assertTrue(self.tovar_dori.seriya_kuzatuv_shart)
        self.assertEqual(self.tovar_dori.tracking, 'lot')
        self.assertTrue(self.tovar_dori.use_expiration_date)
        self.assertEqual(self.tovar_uskuna.tracking, 'serial')
        self.assertEqual(self.tovar.tracking, 'none')

    def test_ogish_chegarasi_uch_darajada(self):
        """Tovar -> kategoriya -> umumiy tartibida eng aniqrog'i yutadi."""
        chegara, manba = self.tovar.product_tmpl_id._agronova_ogish_chegara()
        self.assertEqual(chegara, 10.0)
        self.assertIn("umumiy", manba)

        self.categ_hom.narx_ogish_foizi = 7.0
        chegara, manba = self.tovar.product_tmpl_id._agronova_ogish_chegara()
        self.assertEqual(chegara, 7.0)
        self.assertIn("kategoriya", manba)

        self.tovar.product_tmpl_id.narx_ogish_foizi = 3.0
        chegara, manba = self.tovar.product_tmpl_id._agronova_ogish_chegara()
        self.assertEqual(chegara, 3.0)
        self.assertIn("tovar", manba)
