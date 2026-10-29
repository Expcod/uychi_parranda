# -*- coding: utf-8 -*-
"""B03 — ruxsat: uch bosqichli zanjir, o'z-o'zini tasdiqlash taqiqi,
uch qatlamli narx normasi, «birinchi xarid» va og'ish nazorati."""
from odoo.exceptions import UserError, ValidationError
from odoo.tests import tagged

from .common import AgroNovaZakupkaCommon


@tagged('post_install', '-at_install', 'agronova_zakupka')
class TestB03Ruxsat(AgroNovaZakupkaCommon):

    # ------------------------------------------------------------- zanjir
    def test_zanjir_ketma_ket_otadi(self):
        ruxsat = self._ruxsat_yaratish()
        ruxsat.action_yuborish()
        self.assertEqual(ruxsat.holat, 'bolim_boshligi')

        # Sifat nazorati birinchi bosqichni tasdiqlay olmaydi — zanjir
        # ketma-ket, parallel emas.
        with self.assertRaises(UserError):
            ruxsat.with_user(self.user_sifat).action_tasdiqlash()

        ruxsat.with_user(self.user_boshliq).action_tasdiqlash()
        self.assertEqual(ruxsat.holat, 'sifat_nazorat')
        self.assertEqual(ruxsat.tasdiqlovchi_1_id, self.user_boshliq)

        ruxsat.with_user(self.user_sifat).action_tasdiqlash()
        self.assertEqual(ruxsat.holat, 'tasdiqlandi')
        self.assertEqual(ruxsat.tasdiqlovchi_2_id, self.user_sifat)

    def test_oz_ozini_tasdiqlash_bloklanadi(self):
        """So'rovchi o'sha bosqich tasdiqlovchisi bo'lsa — bir pog'ona yuqoriga."""
        ruxsat = self._ruxsat_yaratish(zakupchik=self.user_boshliq)
        ruxsat.action_yuborish()

        # Bo'lim boshlig'i o'zi so'ragan — o'zi tasdiqlay olmaydi.
        with self.assertRaises(UserError):
            ruxsat.with_user(self.user_boshliq).action_tasdiqlash()

        # Guruhda qolgan boshqa odam (rahbar) tasdiqlaydi.
        ruxsat.with_user(self.user_rahbar).action_tasdiqlash()
        self.assertEqual(ruxsat.holat, 'sifat_nazorat')

    def test_yolgiz_tasdiqlovchi_rahbarga_kotariladi(self):
        """Guruhda so'rovchidan boshqa odam qolmasa — yuqori rahbarga."""
        # Rahbarni bo'lim boshliqlari guruhidan chiqaramiz: guruhda faqat
        # so'rovchining o'zi qoladi.
        self.user_rahbar.group_ids -= self.grup_boshliq
        self.env.user.group_ids -= self.grup_boshliq
        self.env.user.group_ids -= self.env.ref('agronova_zakupka.group_zakupka_admin')

        ruxsat = self._ruxsat_yaratish(zakupchik=self.user_boshliq)
        userlar, kotarildi = ruxsat._agronova_bosqich_tasdiqlovchilari('bolim_boshligi')
        self.assertTrue(kotarildi)
        self.assertEqual(userlar, self.user_rahbar)

    def test_kichik_summaga_bitta_tasdiq(self):
        self.env['ir.config_parameter'].sudo().set_param(
            'agronova_zakupka.bitta_tasdiq_chegara', '50000')
        ruxsat = self._ruxsat_yaratish(narx=1000.0, miqdor=10.0)   # 10 000
        self.assertTrue(ruxsat.bitta_tasdiq)

        ruxsat.action_yuborish()
        ruxsat.with_user(self.user_boshliq).action_tasdiqlash()
        self.assertEqual(ruxsat.holat, 'tasdiqlandi',
                         "Chegaradan past summada ikkinchi bosqich "
                         "o'tkazib yuboriladi")

    def test_rad_etish_sababsiz_bolmaydi(self):
        ruxsat = self._ruxsat_yaratish()
        ruxsat.action_yuborish()
        with self.assertRaises(UserError):
            ruxsat.with_user(self.user_boshliq).action_rad_etish()
        ruxsat.rad_izohi = "Hozircha kerak emas"
        ruxsat.with_user(self.user_boshliq).action_rad_etish()
        self.assertEqual(ruxsat.holat, 'rad_etildi')

    # ---------------------------------------------------------- narx normasi
    def test_norma_narx_kategoriya_limitidan(self):
        """Xarid tarixi yo'q — 2-qatlam ishlaydi."""
        ruxsat = self._ruxsat_yaratish(narx=1000.0)
        self.assertFalse(ruxsat.birinchi_xarid)
        self.assertEqual(ruxsat.norma_narx, 1000.0)
        self.assertIn("Kategoriya", ruxsat.norma_manba)
        self.assertAlmostEqual(ruxsat.ogish_foizi, 0.0, places=2)
        self.assertFalse(ruxsat.ogishli)

    def test_ogish_chegaradan_oshsa_belgilanadi(self):
        ruxsat = self._ruxsat_yaratish(narx=1200.0)   # limit 1000, +20%
        self.assertAlmostEqual(ruxsat.ogish_foizi, 20.0, places=2)
        self.assertEqual(ruxsat.ogish_chegara, 10.0)
        self.assertTrue(ruxsat.ogishli)

    def test_birinchi_xarid_uch_taklif_talab_qiladi(self):
        """Norma narx yo'q tovar — 3-qatlam."""
        yangi = self.env['product.product'].create({
            'name': "Normasiz tovar",
            'categ_id': self.env.ref('agronova_zakupka.categ_vh').id,
            'type': 'consu',
            'purchase_ok': True,
        })
        ruxsat = self._ruxsat_yaratish(product=yangi, narx=5000.0)
        self.assertTrue(ruxsat.birinchi_xarid)

        # Takliflarsiz yuborib bo'lmaydi.
        with self.assertRaises(ValidationError):
            ruxsat.action_yuborish()

        for nom, narx in (("A do'kon", 5200.0), ("B do'kon", 5000.0),
                          ("C do'kon", 5600.0)):
            self.env['agronova.taklif'].create({
                'ruxsat_id': ruxsat.id, 'taklif_beruvchi': nom, 'narx': narx})
        ruxsat.action_yuborish()
        ruxsat.with_user(self.user_boshliq).action_tasdiqlash()

        # Taklif tanlanmasdan yakuniy tasdiq bo'lmaydi.
        with self.assertRaises(UserError):
            ruxsat.with_user(self.user_sifat).action_tasdiqlash()

        ruxsat.tanlangan_taklif_id = ruxsat.taklif_ids.filtered(
            lambda t: t.narx == 5000.0)
        with self.assertRaises(UserError):
            ruxsat.with_user(self.user_sifat).action_tasdiqlash()

        ruxsat.tanlov_sababi = "Eng arzon va yetkazib berish muddati qisqa"
        ruxsat.with_user(self.user_sifat).action_tasdiqlash()
        self.assertEqual(ruxsat.holat, 'tasdiqlandi')

        # Tasdiqlangan narx avtomat norma narxga aylandi.
        norma = self.env['agronova.narx.normasi'].search([
            ('product_id', '=', yangi.id)])
        self.assertEqual(len(norma), 1)
        self.assertEqual(norma.norma_narx, 5000.0)
        self.assertEqual(norma.manba, 'birinchi_xarid')

    def test_xarid_tarixi_normani_siljitadi(self):
        """1-qatlam 2-qatlamdan ustun turadi."""
        ruxsat = self._ruxsat_yaratish(narx=1000.0)
        self._ruxsatni_tasdiqlash(ruxsat)
        kirim = self._kirim_yaratish(ruxsat, narx=900.0)
        kirim.action_tasdiqlash()

        natija = self.env['agronova.narx.normasi']._agronova_norma(self.tovar)
        self.assertEqual(natija['manba'], 'xarid_tarixi')
        self.assertAlmostEqual(natija['narx'], 900.0, places=2)

    def test_narx_eskirishi_belgilanadi(self):
        from dateutil.relativedelta import relativedelta

        from odoo import fields as f
        norma = self.env['agronova.narx.normasi']._agronova_yozuvni_yangilash(
            self.tovar, 1000.0, 'qolda')
        norma.sana = f.Date.context_today(self) - relativedelta(months=12)
        norma.invalidate_recordset()
        self.assertTrue(norma.eski)
        self.assertIn(norma, self.env['agronova.narx.normasi'].search(
            [('eski', '=', True)]))
