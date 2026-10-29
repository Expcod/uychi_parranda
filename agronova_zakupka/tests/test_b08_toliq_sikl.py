# -*- coding: utf-8 -*-
"""B08 — to'liq sikl (TZ 14 va 22-bo'lim).

Omborchi zayavka -> zakupchik qabul -> ruxsat -> uch bosqichli tasdiq ->
kirim (picking + faktura ALOHIDA) -> tranzit -> omborchi qabuli + ball ->
Didox solishtiruvi -> hisobotlar.
"""
from datetime import timedelta

from odoo import fields
from odoo.tests import tagged

from .common import AgroNovaZakupkaCommon


@tagged('post_install', '-at_install', 'agronova_zakupka')
class TestB08ToliqSikl(AgroNovaZakupkaCommon):

    def test_toliq_zanjir(self):
        # --- 1. Omborchi zayavka berdi
        zayavka = self.env['agronova.zayavka'].with_user(self.user_omborchi).create({
            'warehouse_id': self.warehouse.id,
            'omborchi_id': self.user_omborchi.id,
            'muhimlik_darajasi': '2_orta',
            'maksimal_muddat': fields.Datetime.now() + timedelta(days=2),
            'qator_ids': [(0, 0, {'product_id': self.tovar.id, 'miqdor': 10.0})],
        })
        zayavka.action_yuborish()
        self.assertEqual(zayavka.holat, 'zakupchikka_yuborildi')

        # --- 2. Zakupchik qabul qildi (1-tasdiq)
        zayavka.with_user(self.user_zakupchik).action_qabul_qilish()
        self.assertEqual(zayavka.holat, 'qabul_qilindi')

        # --- 3. Ruxsat so'radi
        ruxsat = self.env['agronova.ruxsat'].create({
            'zayavka_id': zayavka.id,
            'zayavka_qatori_id': zayavka.qator_ids.id,
            'zakupchik_id': self.user_zakupchik.id,
            'product_id': self.tovar.id,
            'miqdor': 10.0,
            'taklif_narx': 1000.0,
            'kontragent_id': self.kontragent.id,
            'sotib_olish_joyi': "Chorsu bozori",
            'asos': "Ombor zaxirasi tugadi",
        })
        ruxsat.action_yuborish()

        # --- 4. Bo'lim boshlig'i (2-tasdiq)
        ruxsat.with_user(self.user_boshliq).action_tasdiqlash()
        self.assertEqual(ruxsat.holat, 'sifat_nazorat')
        # --- 5. Sifat va narx nazorati (3-tasdiq)
        ruxsat.with_user(self.user_sifat).action_tasdiqlash()
        self.assertEqual(ruxsat.holat, 'tasdiqlandi')

        # --- 6. Kirim hujjati: picking + faktura ALOHIDA
        kirim = self.env['agronova.kirim'].create({
            'xarid_turi': 'B_mahalliy',
            'tasdiqlangan_ruxsat_id': ruxsat.id,
            'zakupchik_id': self.user_zakupchik.id,
            'kontragent_id': self.kontragent.id,
            'maqsad_ombor_id': self.warehouse.id,
            'ilova': b'chek',
            'ilova_filename': 'chek.png',
            'qator_ids': [(0, 0, {
                'product_id': self.tovar.id,
                'zayavka_qatori_id': zayavka.qator_ids.id,
                'miqdor': 10.0,
                'narx': 1000.0,
            })],
        })
        kirim.action_tasdiqlash()

        # --- 7. Tranzit: tovar zakupchik zimmasida, qarz allaqachon yozilgan
        self.assertEqual(kirim.holat, 'tasdiqlangan')
        self.assertEqual(kirim.picking_kirim_id.location_dest_id,
                         self.user_zakupchik.zakupka_tranzit_id)
        self.assertEqual(kirim.faktura_id.state, 'posted')
        self.assertEqual(kirim.faktura_holati, 'kutilmoqda')

        # --- 8. Omborchi qabul qildi + ball qo'ydi (4-tasdiq)
        wizard = self.env['agronova.qabul.wizard'].with_user(
            self.user_omborchi).with_context(
            default_kirim_id=kirim.id).create({'kirim_id': kirim.id})
        wizard.write({'ball_sababi': 'obyektiv_sabab'})
        wizard.action_qabul_qilish()

        self.assertEqual(kirim.holat, 'qabul_qilindi')
        omborda = self.env['stock.quant']._get_available_quantity(
            self.tovar, self.warehouse.lot_stock_id)
        self.assertAlmostEqual(omborda, 10.0, places=2)

        # Zayavka to'liq bajarildi va yopildi.
        zayavka.invalidate_recordset()
        self.assertEqual(zayavka.qator_ids.bajarilgan_miqdor, 10.0)
        self.assertEqual(zayavka.holat, 'yopildi')

        # --- 9. Didox fakturasi keldi va solishtirildi
        log = self.env['agronova.didox.log'].create({
            'name': 'DX-SIKL-1',
            'sana': kirim.sotib_olingan_sana,
            'stir': self.kontragent.stir,
            'summa': kirim.jami_summa,
        })
        log.action_solishtirish()
        self.assertEqual(log.holat, 'moslashtirildi')
        kirim.invalidate_recordset()
        self.assertEqual(kirim.faktura_holati, 'moslashtirildi')

        # --- 10. Hisobotlar to'g'ri chiqadi
        self.assertNotIn(kirim, self.env['agronova.kirim'].search(
            [('holat', '=', 'tasdiqlangan')]), "Tranzitda qolmasligi kerak")
        self.assertNotIn(kirim, self.env['agronova.kirim'].search(
            [('faktura_holati', '=', 'kutilmoqda')]))
        self.assertNotIn(zayavka, self.env['agronova.zayavka'].search(
            [('holat', 'in', ('zakupchikka_yuborildi', 'qabul_qilindi',
                              'qisman_bajarildi'))]))

        # --- 11. KPI yozildi va xodimga ko'rinadi
        ballar = self.env['agronova.kpi'].search(
            [('xodim_id', '=', self.user_zakupchik.id)])
        self.assertTrue(ballar)
        self.assertTrue(
            set(ballar.mapped('mezon_turi')) & {'javob_tezligi', 'narx_tejami'})

    def test_nomenklatura_sorovi_tovar_yaratadi(self):
        sorov = self.env['agronova.nomenklatura.sorovi'].with_user(
            self.user_zakupchik).create({
                'nom': "Test hom ashyo qo'shimchasi",
                'olchov_birligi_id': self.tovar.uom_id.id,
                'kategoriya_id': self.categ_hom.id,
                'xarajat_turi': 'hom_ashyo',
                'izoh': "Yangi yetkazib beruvchidan",
            })
        # O'xshash nom topilishi kerak — «Test hom ashyo» bazada bor.
        self.assertGreater(sorov.oxshash_soni, 0)

        sorov.action_tekshirishga_yuborish()
        self.assertEqual(sorov.holat, 'tekshirilmoqda')
        sorov.with_user(self.user_boshliq).action_tasdiqlash()
        self.assertEqual(sorov.holat, 'tasdiqlandi')
        self.assertTrue(sorov.product_tmpl_id)
        self.assertEqual(sorov.product_tmpl_id.categ_id, self.categ_hom)
