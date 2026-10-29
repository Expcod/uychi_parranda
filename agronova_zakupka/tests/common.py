# -*- coding: utf-8 -*-
"""Xarid testlari uchun umumiy tayyorgarlik.

Har bir B-band testi shu sinfdan meros oladi: rollar, ombor, kontragent,
tovar va depozit bir marta quriladi.
"""
from odoo import fields
from odoo.tests.common import TransactionCase


class AgroNovaZakupkaCommon(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.env.user.group_ids |= cls.env.ref('agronova_zakupka.group_zakupka_admin')
        # Orqaga sana bilan kiritish testlari uchun — TZ 12-bo'limda bu
        # huquq bosh buxgalterda.
        cls.env.user.group_ids |= cls.env.ref(
            'agronova_base.group_agronova_bosh_buxgalter')

        # Standart chegara (500 000) test summalaridan katta bo'lgani uchun
        # zanjir bitta tasdiqqa qisqarardi — testlarda o'chiramiz; kichik
        # summa qoidasi o'z testida alohida yoqiladi.
        cls.env['ir.config_parameter'].sudo().set_param(
            'agronova_zakupka.bitta_tasdiq_chegara', '0')

        cls.warehouse = cls.env['stock.warehouse'].search(
            [('company_id', '=', cls.company.id)], limit=1)
        assert cls.warehouse, "Test bazasida ombor topilmadi"

        # --- hisoblar. Bazadagi mavjud kategoriyadan nusxa olamiz:
        #     hisoblar rejasi loyihaga qarab har xil, qattiq kod yozmaymiz.
        cls.jurnal_xarid = cls.env['account.journal'].search(
            [('type', '=', 'purchase'), ('company_id', '=', cls.company.id)],
            limit=1)
        cls.jurnal_umumiy = cls.env['account.journal'].search(
            [('type', '=', 'general'), ('company_id', '=', cls.company.id)],
            limit=1)
        cls.hisob_xarajat = cls.env['account.account'].search(
            [('account_type', '=', 'expense'),
             ('company_ids', 'in', cls.company.id)], limit=1)
        cls.hisob_zaxira = cls.env['account.account'].search(
            [('account_type', '=', 'asset_current'),
             ('company_ids', 'in', cls.company.id)], limit=1)

        # --- kategoriyalar
        cls.categ_hom = cls.env.ref('agronova_zakupka.categ_hom_ashyo')
        cls.categ_dori = cls.env.ref('agronova_zakupka.categ_dori')
        cls.categ_uskuna = cls.env.ref('agronova_zakupka.categ_uskuna')
        for categ in (cls.categ_hom, cls.categ_dori, cls.categ_uskuna):
            categ.property_account_expense_categ_id = cls.hisob_xarajat
            categ.property_account_income_categ_id = cls.hisob_xarajat
        # Hom ashyoda kategoriya limiti bor — norma narxning 2-qatlami
        # ishlaydi va testlar «birinchi xarid» rejimiga tushib qolmaydi.
        cls.categ_hom.kategoriya_limit_narx = 1000.0

        # --- tovarlar
        cls.tovar = cls.env['product.product'].create({
            'name': "Test hom ashyo",
            'categ_id': cls.categ_hom.id,
            'type': 'consu',
            'is_storable': True,
            'purchase_ok': True,
            'standard_price': 1000.0,
        })
        cls.tovar_dori = cls.env['product.product'].create({
            'name': "Test dori",
            'categ_id': cls.categ_dori.id,
            'type': 'consu',
            'is_storable': True,
            'purchase_ok': True,
        })
        cls.tovar_uskuna = cls.env['product.product'].create({
            'name': "Test uskuna",
            'categ_id': cls.categ_uskuna.id,
            'type': 'consu',
            'is_storable': True,
            'purchase_ok': True,
        })

        # --- kontragent
        cls.kontragent = cls.env['res.partner'].create({
            'name': "Test ta'minotchi",
            'shaxs_turi': 'yuridik',
            'stir': '300111222',
            'qqs_tolovchi': True,
            'bank_hisob_raqami': '20208000900000000001',
            'bank_mfo': '00014',
            'supplier_rank': 1,
        })

        # --- rollar
        cls.grup_zakupchik = cls.env.ref('agronova_zakupka.group_zakupka_zakupchik')
        cls.grup_boshliq = cls.env.ref('agronova_zakupka.group_zakupka_bolim_boshligi')
        cls.grup_sifat = cls.env.ref('agronova_zakupka.group_zakupka_sifat_nazorat')
        cls.grup_omborchi = cls.env.ref('agronova_zakupka.group_zakupka_omborchi')
        cls.grup_buxgalter = cls.env.ref('agronova_zakupka.group_zakupka_buxgalter')

        cls.user_zakupchik = cls._user("zakupchik", cls.grup_zakupchik)
        cls.user_boshliq = cls._user("boshliq", cls.grup_boshliq)
        cls.user_sifat = cls._user("sifat", cls.grup_sifat)
        cls.user_omborchi = cls._user("omborchi", cls.grup_omborchi)
        cls.user_buxgalter = cls._user("buxgalter", cls.grup_buxgalter)
        cls.user_rahbar = cls._user("rahbar", cls.grup_boshliq | cls.grup_sifat)
        cls.user_boshliq.zakupka_rahbar_id = cls.user_rahbar
        cls.user_sifat.zakupka_orinbosar_id = cls.user_rahbar

        # --- depozit (agronova_savdo_moliya)
        cls.xodim = cls.env['hr.employee'].create({
            'name': "Zakupchik xodim",
            'user_id': cls.user_zakupchik.id,
            'company_id': cls.company.id,
        })
        cls.depozit = cls.env['agronova.depozit'].create({
            'name': "Zakupchik depoziti",
            'egasi_id': cls.xodim.id,
            'company_id': cls.company.id,
        })
        cls.env['agronova.depozit.harakat'].create({
            'depozit_id': cls.depozit.id,
            'turi': 'kirim',
            'summa': 10_000_000.0,
            'holat': 'tasdiqlangan',
            'izoh': "Boshlang'ich avans",
        })

    @classmethod
    def _user(cls, login, groups):
        user = cls.env['res.users'].create({
            'name': login.capitalize(),
            'login': 'agronova_zk_%s' % login,
            'email': 'agronova_zk_%s@example.com' % login,
            'company_id': cls.company.id,
            'company_ids': [(6, 0, cls.company.ids)],
            'group_ids': [(4, cls.env.ref('base.group_user').id)] + [
                (4, g.id) for g in groups],
        })
        return user

    # ------------------------------------------------------------ yordamchi
    @classmethod
    def _ruxsat_yaratish(cls, product=None, narx=1000.0, miqdor=10.0,
                         zakupchik=None):
        return cls.env['agronova.ruxsat'].create({
            'zakupchik_id': (zakupchik or cls.user_zakupchik).id,
            'product_id': (product or cls.tovar).id,
            'miqdor': miqdor,
            'taklif_narx': narx,
            'kontragent_id': cls.kontragent.id,
            'sotib_olish_joyi': "Test bozori",
            'asos': "Test uchun",
        })

    @classmethod
    def _ruxsatni_tasdiqlash(cls, ruxsat):
        """Zanjirni oxirigacha o'tkazadi (testlarda takrorlanadigan qism)."""
        ruxsat.action_yuborish()
        ruxsat.with_user(cls.user_boshliq).action_tasdiqlash()
        if ruxsat.holat == 'sifat_nazorat':
            ruxsat.with_user(cls.user_sifat).action_tasdiqlash()
        return ruxsat

    @classmethod
    def _kirim_yaratish(cls, ruxsat, narx=None, miqdor=None, ilova=b'test',
                        xarid_turi='B_mahalliy', lot=None, sana=None):
        qator = {
            'product_id': ruxsat.product_id.id,
            'miqdor': miqdor if miqdor is not None else ruxsat.miqdor,
            'narx': narx if narx is not None else ruxsat.taklif_narx,
        }
        if lot:
            qator['lot_nomi'] = lot
            qator['yaroqlilik_sanasi'] = fields.Datetime.now()
        vals = {
            'xarid_turi': xarid_turi,
            'tasdiqlangan_ruxsat_id': ruxsat.id,
            'zakupchik_id': ruxsat.zakupchik_id.id,
            'kontragent_id': ruxsat.kontragent_id.id,
            'maqsad_ombor_id': cls.warehouse.id,
            'ilova': ilova,
            'ilova_filename': 'chek.png',
            'qator_ids': [(0, 0, qator)],
        }
        if sana:
            vals['sotib_olingan_sana'] = sana
        if xarid_turi == 'A_naqd':
            vals['depozit_id'] = cls.depozit.id
            vals['tolangan_summa'] = qator['miqdor'] * qator['narx']
        return cls.env['agronova.kirim'].create(vals)
