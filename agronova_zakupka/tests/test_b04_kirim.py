# -*- coding: utf-8 -*-
"""B04 — kirim va tranzit: tovar/faktura ajratilishi, narx og'ishi taqiqi,
omborchi qabuli va uch o'lchovli ball, lot majburiyati, qaytarish."""
from datetime import timedelta

from odoo import fields
from odoo.exceptions import UserError, ValidationError
from odoo.tests import tagged

from .common import AgroNovaZakupkaCommon


@tagged('post_install', '-at_install', 'agronova_zakupka')
class TestB04Kirim(AgroNovaZakupkaCommon):

    def setUp(self):
        super().setUp()
        self.ruxsat = self._ruxsat_yaratish(narx=1000.0, miqdor=10.0)
        self._ruxsatni_tasdiqlash(self.ruxsat)

    # -------------------------------------------------------- tasdiqlanishi
    def test_ruxsatsiz_kirim_bolmaydi(self):
        yangi = self._ruxsat_yaratish()
        with self.assertRaises(UserError):
            kirim = self._kirim_yaratish(yangi)
            kirim.action_tasdiqlash()

    def test_ilovasiz_kirim_tasdiqlanmaydi(self):
        kirim = self._kirim_yaratish(self.ruxsat, ilova=False)
        with self.assertRaises(ValidationError):
            kirim.action_tasdiqlash()

    def test_tovar_tranzitga_tushadi_qarz_darhol_yoziladi(self):
        kirim = self._kirim_yaratish(self.ruxsat)
        kirim.action_tasdiqlash()

        self.assertEqual(kirim.holat, 'tasdiqlangan')
        tranzit = self.user_zakupchik.zakupka_tranzit_id
        self.assertEqual(kirim.tranzit_id, tranzit)

        # 1) Tovar — zakupchik tranzitida, asosiy omborda emas.
        self.assertEqual(kirim.picking_kirim_id.state, 'done')
        self.assertEqual(kirim.picking_kirim_id.location_dest_id, tranzit)
        miqdor = self.env['stock.quant']._get_available_quantity(
            self.tovar, tranzit)
        self.assertAlmostEqual(miqdor, 10.0, places=2)

        # 2) Qarz — o'sha zahoti, omborchi tasdig'iga bog'liq emas (MSFO).
        self.assertTrue(kirim.faktura_id)
        self.assertEqual(kirim.faktura_id.move_type, 'in_invoice')
        self.assertEqual(kirim.faktura_id.state, 'posted')
        self.assertEqual(kirim.faktura_holati, 'kutilmoqda')

        # 3) Ikkalasi alohida hujjat — biri ikkinchisining ichida emas.
        self.assertNotEqual(
            kirim.picking_kirim_id._name, kirim.faktura_id._name)

    def test_naqd_xarid_depozitdan_chiqadi(self):
        boshlangich = self.depozit.balans
        kirim = self._kirim_yaratish(self.ruxsat, xarid_turi='A_naqd')
        kirim.action_tasdiqlash()

        self.assertTrue(kirim.depozit_harakat_id)
        self.assertEqual(kirim.depozit_harakat_id.turi, 'chiqim')
        self.depozit.invalidate_recordset()
        self.assertAlmostEqual(
            self.depozit.balans, boshlangich - 10_000.0, places=2)

    def test_narx_ogishi_hujjatni_saqlatmaydi(self):
        """TZ 19 — chegaradan oshgan narxda hujjat saqlanmaydi."""
        with self.assertRaises(ValidationError):
            self._kirim_yaratish(self.ruxsat, narx=1300.0)   # +30%, chegara 10%

    def test_kelajak_sana_va_ochirish_taqiqi(self):
        with self.assertRaises(ValidationError):
            kirim = self._kirim_yaratish(self.ruxsat)
            kirim.sotib_olingan_sana = fields.Date.add(
                fields.Date.context_today(self), days=1)

        kirim = self._kirim_yaratish(self.ruxsat)
        kirim.action_tasdiqlash()
        with self.assertRaises(UserError):
            kirim.unlink()
        with self.assertRaises(UserError):
            kirim.summa = 1.0

    # ------------------------------------------------------- omborchi qabuli
    def test_omborchi_qabuli_va_uch_olchovli_ball(self):
        kirim = self._kirim_yaratish(self.ruxsat)
        kirim.action_tasdiqlash()

        wizard = self.env['agronova.qabul.wizard'].with_user(
            self.user_omborchi).with_context(
            default_kirim_id=kirim.id).create({'kirim_id': kirim.id})
        self.assertEqual(len(wizard.qator_ids), 1)

        # To'liq bo'lmagan ballda izoh majburiy.
        with self.assertRaises(ValidationError):
            wizard.write({'ball_muddat': 8, 'ball_izohi': False})

        wizard.write({
            'ball_izohi': "1 dona kam keldi, kechikdi",
            'ball_muddat': 8,
            'ball_sifat': 10,
            'ball_sababi': 'zakupchik_aybi',
        })
        # 10 ta so'ralib 9 tasi keldi -> to'liqlik bali avtomat 9 bo'ladi.
        wizard.qator_ids.qabul_miqdor = 9.0
        self.assertEqual(wizard.ball_toliqlik, 9)

        wizard.action_qabul_qilish()

        self.assertEqual(kirim.holat, 'qabul_qilindi')
        self.assertEqual(kirim.ball_toliqlik, 9)
        self.assertEqual(kirim.ball_muddat, 8)
        self.assertEqual(kirim.ball_sifat, 10)
        self.assertEqual(kirim.omborchi_id, self.user_omborchi)

        # Tovar asosiy omborga o'tdi, 1 dona tranzitda qoldi.
        self.assertEqual(kirim.picking_qabul_id.state, 'done')
        omborda = self.env['stock.quant']._get_available_quantity(
            self.tovar, self.warehouse.lot_stock_id)
        self.assertAlmostEqual(omborda, 9.0, places=2)
        tranzitda = self.env['stock.quant']._get_available_quantity(
            self.tovar, kirim.tranzit_id)
        self.assertAlmostEqual(tranzitda, 1.0, places=2)

        # Uchala o'lcham ham alohida KPI yozuvi bo'ldi.
        ballar = self.env['agronova.kpi'].search([
            ('manba_id', '=', kirim.id),
            ('manba_model', '=', 'agronova.kirim'),
        ])
        mezonlar = set(ballar.mapped('mezon_turi'))
        self.assertTrue({'toliqlik', 'muddat', 'sifat'} <= mezonlar)

    def test_obyektiv_sabab_kpiga_tegmaydi(self):
        kirim = self._kirim_yaratish(self.ruxsat)
        kirim.action_tasdiqlash()
        wizard = self.env['agronova.qabul.wizard'].with_context(
            default_kirim_id=kirim.id).create({'kirim_id': kirim.id})
        wizard.qator_ids.qabul_miqdor = 5.0
        wizard.write({
            'ball_toliqlik': 5, 'ball_muddat': 10, 'ball_sifat': 10,
            'ball_sababi': 'obyektiv_sabab',
            'ball_izohi': "Yetkazib beruvchida tovar tugagan",
        })
        wizard.action_qabul_qilish()

        ballar = self.env['agronova.kpi'].search([
            ('manba_id', '=', kirim.id),
            ('mezon_turi', 'in', ('toliqlik', 'muddat', 'sifat')),
        ])
        self.assertFalse(
            ballar, "Obyektiv sababda zakupchik bali yozilmasligi kerak")

    # ------------------------------------------------------------- lot/muddat
    def test_dorida_lot_va_muddat_majburiy(self):
        ruxsat = self._ruxsat_yaratish(product=self.tovar_dori, narx=500.0)
        self.env['agronova.narx.normasi']._agronova_yozuvni_yangilash(
            self.tovar_dori, 500.0, 'qolda')
        ruxsat.invalidate_recordset()
        self._ruxsatni_tasdiqlash(ruxsat)

        kirim = self._kirim_yaratish(ruxsat, narx=500.0)
        with self.assertRaises(ValidationError):
            kirim.action_tasdiqlash()

        kirim.qator_ids.write({
            'lot_nomi': 'LOT-TEST-1',
            'yaroqlilik_sanasi': fields.Datetime.now() + timedelta(days=90),
        })
        kirim.action_tasdiqlash()
        lot = kirim.qator_ids.lot_id
        self.assertTrue(lot)
        self.assertEqual(lot.name, 'LOT-TEST-1')
        self.assertTrue(lot.expiration_date, "Yaroqlilik muddati lotga yozilsin")

    # ----------------------------------------------------------- landed cost
    def test_transport_tannarxga_qoshiladi(self):
        """IAS 2 — transport alohida xarajat emas, Landed Cost."""
        self.categ_hom.write({
            'property_valuation': 'real_time',
            'property_cost_method': 'fifo',
            'property_stock_valuation_account_id': self.hisob_zaxira.id,
            'property_stock_journal': self.jurnal_umumiy.id,
        })
        kirim = self._kirim_yaratish(self.ruxsat)
        kirim.transport_xarajati = 50_000.0
        kirim.action_tasdiqlash()

        self.assertTrue(kirim.landed_cost_id)
        self.assertEqual(kirim.landed_cost_id.state, 'done')
        self.assertAlmostEqual(
            kirim.landed_cost_id.amount_total, 50_000.0, places=2)
        self.assertTrue(kirim.landed_cost_id.valuation_adjustment_lines,
                        "Taqsimot qatorlari Odoo tomonidan tuzilishi kerak")

    # -------------------------------------------------------------- tranzit
    def test_tranzit_hisoboti_va_eslatmasi(self):
        kirim = self._kirim_yaratish(self.ruxsat)
        kirim.action_tasdiqlash()
        kirim.tranzit_sanasi = fields.Datetime.now() - timedelta(days=10)
        kirim.invalidate_recordset()
        self.assertEqual(kirim.tranzit_kunlari, 10)

        topilgan = self.env['agronova.kirim'].search([('tranzit_kunlari', '>', 3)])
        self.assertIn(kirim, topilgan)

        self.env['agronova.kirim']._cron_tranzit_nazorati()
        self.assertTrue(kirim.activity_ids.filtered(
            lambda a: a.user_id == self.user_zakupchik))

    # ------------------------------------------------------------ qaytarish
    def test_qaytarish_tovar_va_qarzni_teskari_yozadi(self):
        kirim = self._kirim_yaratish(self.ruxsat)
        kirim.action_tasdiqlash()

        qaytarish = self.env['agronova.qaytarish'].create({
            'kirim_id': kirim.id,
            'sabab': 'buzuq',
            'izoh': "3 dona yaroqsiz chiqdi",
        })
        qaytarish.action_qatorlarni_toldirish()
        qaytarish.qator_ids.miqdor = 3.0
        qaytarish.action_tasdiqlash()

        self.assertEqual(qaytarish.holat, 'tasdiqlangan')
        self.assertEqual(qaytarish.picking_id.state, 'done')
        self.assertEqual(qaytarish.kredit_nota_id.move_type, 'in_refund')
        self.assertEqual(qaytarish.kredit_nota_id.state, 'posted')

        qolgan = self.env['stock.quant']._get_available_quantity(
            self.tovar, kirim.tranzit_id)
        self.assertAlmostEqual(qolgan, 7.0, places=2)

        # Olingandan ko'p qaytarib bo'lmaydi.
        with self.assertRaises(ValidationError):
            qaytarish.qator_ids.miqdor = 99.0
