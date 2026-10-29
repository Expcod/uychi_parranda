# -*- coding: utf-8 -*-
"""Brigadir paneli — sehdagi kunlik ishning bitta ekrani.

TZ 9 va 10-bandlar brigadirning kunlik vazifalarini sanaydi: sehni
nazorat qilish, jo'jalar holatini tekshirish, o'lganini aniqlash,
haroratni o'lchash, yem va suv holatini ko'rish, **kuniga kamida 3 marta
obxod** qilish va **kunlik ma'lumotlarni tizimga kiritish**.

Bu ishlarning har biri uchun modulda alohida hujjat bor (obxod, kunlik
jurnal, vazn, xarajat), lekin brigadir ularni sehda, telefonda, qo'li
ifloslangan holda to'ldiradi — Odooning standart formalari bunga
qulay emas. Panel shu to'rt hujjatni bitta ekranga yig'adi va eng
muhimini yuzaga chiqaradi: **bugun nima qilinmagan**.

Butun hisob-kitob shu yerda — serverda. Panel faqat ko'rsatadi va
formani yuboradi, shuning uchun paneldagi raqam hech qachon hujjatdagi
raqamdan farq qilmaydi.

Huquqlar alohida yozilmagan: `security/agronova_boquv_rules.xml` dagi
record rule'lar brigadirni o'z filiali bilan cheklaydi, panel esa oddiy
`search` ishlatadi — demak kimga nima ko'rinishi bitta joyda hal
bo'ladi.
"""
from odoo import _, api, fields, models
from odoo.exceptions import UserError

# TZ 10-band: kuniga kamida shuncha obxod.
OBXOD_NORMA = 3

HOLAT_TARJIMA = {
    'yaxshi': "Yaxshi",
    'qoniqarli': "Qoniqarli",
    'yomon': "Yomon",
}


class AgroNovaBoquvPartiya(models.Model):
    _inherit = 'agronova.boquv.partiya'

    # ------------------------------------------------------------------
    # YORDAMCHI
    # ------------------------------------------------------------------

    @api.model
    def _panel_xodim(self):
        """Joriy foydalanuvchining xodim kartochkasi."""
        return self.env['hr.employee'].sudo().search(
            [('user_id', '=', self.env.user.id)], limit=1)

    @api.model
    def _panel_depozit(self):
        """Brigadirning qo'lidagi naqd (agronova.depozit)."""
        return self.env['agronova.depozit'].sudo().search([
            ('egasi_id.user_id', '=', self.env.user.id),
        ], limit=1)

    @api.model
    def _panel_partiyalar(self):
        """Brigadir ko'radigan faol partiyalar.

        Domen ataylab sodda — kim nimani ko'rishini record rule hal
        qiladi, shu sababli qoida bir joyda turadi va panel bilan
        ro'yxat ko'rinishi hech qachon bir-biridan ajralib qolmaydi.
        """
        return self.search([('holat', '=', 'active')],
                           order='filial_id, bino_id, name')

    def _panel_kart(self):
        """Partiya kartochkasi — panelning asosiy birligi."""
        self.ensure_one()
        bugun = fields.Date.context_today(self)
        bugungi_jurnal = self.jurnal_ids.filtered(lambda j: j.sana == bugun)
        oxirgi_obxod = self.obxod_ids.sorted('vaqt', reverse=True)[:1]
        oxirgi_vazn = self.vazn_ids.sorted('sana', reverse=True)[:1]
        return {
            'id': self.id,
            'name': self.name,
            'filial': self.filial_id.name or '',
            'bino': self.bino_id.display_name or '',
            'yosh_kun': self.yosh_kun,
            'reja_kun': self.reja_kun,
            'boshlangich_son': self.boshlangich_son,
            'joriy_son': self.joriy_son,
            'nobud_son': self.nobud_son,
            'nobud_foiz': round(self.nobud_foiz or 0.0, 2),
            'nobud_norma': round(self.nobud_norma or 0.0, 2),
            'yashovchanlik': round(self.yashovchanlik or 0.0, 2),
            'ortacha_vazn': round(self.ortacha_vazn or 0.0, 3),
            'fcr': round(self.fcr or 0.0, 3),
            'fcr_norma': round(self.fcr_norma or 0.0, 3),
            'epef': round(self.epef or 0.0, 1),
            'ogish_bormi': self.ogish_bormi,
            'obxod_bugun': self.obxod_bugun_soni,
            'obxod_norma': OBXOD_NORMA,
            'jurnal_bugun': bool(bugungi_jurnal),
            'jurnal_holati': bugungi_jurnal[:1].holat or '',
            'oxirgi_obxod': (fields.Datetime.to_string(oxirgi_obxod.vaqt)
                             if oxirgi_obxod else ''),
            'oxirgi_harorat': oxirgi_obxod.harorat if oxirgi_obxod else 0.0,
            'harorat_holati': (oxirgi_obxod.harorat_holati or '') if oxirgi_obxod else '',
            'oxirgi_vazn_sana': (fields.Date.to_string(oxirgi_vazn.sana)
                                 if oxirgi_vazn else ''),
        }

    def _panel_ogohlantirish(self):
        """Kartochka bo'yicha «bugun nima qilinmagan» ro'yxati."""
        self.ensure_one()
        bugun = fields.Date.context_today(self)
        natija = []
        if not self.jurnal_ids.filtered(lambda j: j.sana == bugun):
            natija.append({
                'tur': 'jurnal',
                'daraja': 'xavf',
                'matn': _("Bugungi kunlik jurnal to'ldirilmagan"),
            })
        if self.obxod_bugun_soni < OBXOD_NORMA:
            natija.append({
                'tur': 'obxod',
                'daraja': 'ogoh',
                'matn': _("Obxod %(bor)s/%(kerak)s — yana %(qolgan)s marta kerak",
                          bor=self.obxod_bugun_soni, kerak=OBXOD_NORMA,
                          qolgan=OBXOD_NORMA - self.obxod_bugun_soni),
            })
        oxirgi = self.obxod_ids.sorted('vaqt', reverse=True)[:1]
        if oxirgi and oxirgi.harorat_holati in ('past', 'yuqori'):
            natija.append({
                'tur': 'harorat',
                'daraja': 'xavf',
                'matn': _("Harorat me'yordan %(tomon)s: %(qiymat)s °C",
                          tomon=(_("past") if oxirgi.harorat_holati == 'past'
                                 else _("yuqori")),
                          qiymat=oxirgi.harorat),
            })
        if self.ogish_bormi:
            natija.append({
                'tur': 'ogish',
                'daraja': 'ogoh',
                'matn': _("Ko'rsatkich normadan chetlashgan (FCR %(fcr)s / "
                          "norma %(norma)s)",
                          fcr=round(self.fcr or 0, 2),
                          norma=round(self.fcr_norma or 0, 2)),
            })
        return natija

    def _panel_normativ(self):
        """Shu yoshdagi normativ — panelda «qancha bo'lishi kerak»."""
        self.ensure_one()
        Normativ = self.env['agronova.boquv.normativ']
        yosh = self.yosh_kun
        return {
            'harorat_min': Normativ.qiymat('harorat_min', yosh_kun=yosh),
            'harorat_max': Normativ.qiymat('harorat_max', yosh_kun=yosh),
            'yem_bosh_kunlik_gr': Normativ.qiymat('yem_bosh_kunlik_gr',
                                                  yosh_kun=yosh),
            'ortacha_vazn_norma': Normativ.qiymat('ortacha_vazn_norma',
                                                  yosh_kun=yosh),
            'fcr_norma': Normativ.qiymat('fcr_norma', yosh_kun=yosh),
        }

    # ------------------------------------------------------------------
    # PANEL RPC — o'qish
    # ------------------------------------------------------------------

    @api.model
    def ui_home(self):
        """Panel ochilishi: partiyalar, ogohlantirishlar va ma'lumotnomalar."""
        partiyalar = self._panel_partiyalar()
        xodim = self._panel_xodim()
        depozit = self._panel_depozit()
        kartlar = []
        ogohlar = []
        for p in partiyalar:
            kartlar.append(p._panel_kart())
            for o in p._panel_ogohlantirish():
                ogohlar.append(dict(o, partiya_id=p.id, partiya=p.name,
                                    bino=p.bino_id.display_name or ''))
        kategoriyalar = self.env['agronova.xarajat.kategoriya'].search([])
        return {
            'brigadir': xodim.name or self.env.user.name,
            'sana': fields.Date.to_string(fields.Date.context_today(self)),
            'partiyalar': kartlar,
            'ogohlar': ogohlar,
            'jami': {
                'partiya': len(partiyalar),
                'joriy_son': sum(partiyalar.mapped('joriy_son')),
                'nobud_son': sum(partiyalar.mapped('nobud_son')),
                'jurnalsiz': len([k for k in kartlar if not k['jurnal_bugun']]),
                'obxod_yetmagan': len([k for k in kartlar
                                       if k['obxod_bugun'] < OBXOD_NORMA]),
            },
            'depozit': {
                'id': depozit.id,
                'name': depozit.name,
                'balans': depozit.balans,
            } if depozit else None,
            'valyuta': (self.env.company.currency_id.symbol
                        or self.env.company.currency_id.name),
            'nobud_sabablari': [
                {'kod': k, 'nom': n} for k, n in
                self.env['agronova.boquv.jurnal']._fields['nobud_sabab'].selection
            ],
            'sarf_turlari': [
                {'kod': k, 'nom': n} for k, n in
                self.env['agronova.boquv.jurnal.sarf']._fields['tur'].selection
            ],
            'holat_baholari': [
                {'kod': k, 'nom': n} for k, n in
                self.env['agronova.boquv.obxod']._fields['jojalar_holati'].selection
            ],
            'kategoriyalar': [
                {'id': k.id, 'nom': k.name,
                 'baza': k.taqsimlash_bazasi or 'teng'}
                for k in kategoriyalar
            ],
        }

    @api.model
    def ui_partiya(self, partiya_id):
        """Bitta partiyaning batafsil ko'rinishi."""
        p = self.browse(int(partiya_id))
        if not p.exists():
            raise UserError(_("Partiya topilmadi."))
        bugun = fields.Date.context_today(self)
        bugungi_obxodlar = p.obxod_ids.filtered(
            lambda o: o.vaqt and fields.Datetime.context_timestamp(
                o, o.vaqt).date() == bugun).sorted('vaqt', reverse=True)
        oxirgi_jurnallar = p.jurnal_ids.sorted('sana', reverse=True)[:7]
        return {
            'kart': p._panel_kart(),
            'normativ': p._panel_normativ(),
            'ogohlar': p._panel_ogohlantirish(),
            'obxodlar': [{
                'id': o.id,
                'vaqt': fields.Datetime.to_string(o.vaqt),
                'harorat': o.harorat,
                'harorat_holati': o.harorat_holati or '',
                'jojalar': HOLAT_TARJIMA.get(o.jojalar_holati, ''),
                'yem': HOLAT_TARJIMA.get(o.yem_holati, ''),
                'suv': HOLAT_TARJIMA.get(o.suv_holati, ''),
                'olgan_joja': o.olgan_joja,
                'muammo': o.muammo or '',
                'chora': o.chora or '',
                'brigadir': o.brigadir_id.name or '',
            } for o in bugungi_obxodlar],
            'jurnallar': [{
                'id': j.id,
                'sana': fields.Date.to_string(j.sana),
                'nobud_son': j.nobud_son,
                'kun_oxiri_son': j.kun_oxiri_son,
                'yem_kg': round(j.yem_kg or 0.0, 2),
                'suv_litr': round(j.suv_litr or 0.0, 1),
                'harorat': j.harorat,
                'holat': j.holat,
            } for j in oxirgi_jurnallar],
        }

    @api.model
    def ui_search_product(self, term, tur='yem', limit=12):
        """Sarf qatori uchun mahsulot tanlagichi."""
        domain = [('is_storable', '=', True)]
        if term:
            domain.append(('name', 'ilike', term))
        mahsulotlar = self.env['product.product'].search(domain, limit=limit)
        return [{
            'id': m.id, 'nom': m.display_name,
            'uom': m.uom_id.name, 'uom_id': m.uom_id.id,
        } for m in mahsulotlar]

    # ------------------------------------------------------------------
    # PANEL RPC — yozish
    # ------------------------------------------------------------------

    def _panel_tekshir(self):
        """Partiya panel orqali yozuv qabul qila oladimi."""
        self.ensure_one()
        if self.holat != 'active':
            raise UserError(_(
                "«%s» partiyasi faol emas — unga yozuv kiritilmaydi.",
                self.name))

    @api.model
    def ui_obxod(self, vals):
        """Obxod qayd etish (TZ 10-band)."""
        p = self.browse(int(vals['partiya_id']))
        p._panel_tekshir()
        obxod = self.env['agronova.boquv.obxod'].create({
            'partiya_id': p.id,
            'brigadir_id': (self._panel_xodim().id or p.brigadir_id.id),
            'harorat': float(vals.get('harorat') or 0.0),
            'namlik': float(vals.get('namlik') or 0.0),
            'jojalar_holati': vals.get('jojalar_holati') or 'yaxshi',
            'yem_holati': vals.get('yem_holati') or 'yaxshi',
            'suv_holati': vals.get('suv_holati') or 'yaxshi',
            'olgan_joja': int(vals.get('olgan_joja') or 0),
            'muammo': vals.get('muammo') or '',
            'chora': vals.get('chora') or '',
        })
        return {'id': obxod.id, 'partiya': self.ui_partiya(p.id)}

    @api.model
    def ui_jurnal(self, vals):
        """Kunlik jurnal: nobud, suv, harorat va resurs sarfi.

        Bir partiyaga kuniga bitta jurnal yuritiladi (SQL cheklovi), shu
        sababli o'sha kunning qoralamasi bo'lsa ustiga yoziladi.
        Tasdiqlangani esa tegilmaydi — sarf allaqachon ombordan chiqqan.
        """
        p = self.browse(int(vals['partiya_id']))
        p._panel_tekshir()
        sana = vals.get('sana') or fields.Date.to_string(
            fields.Date.context_today(self))
        Jurnal = self.env['agronova.boquv.jurnal']
        mavjud = Jurnal.search([
            ('partiya_id', '=', p.id), ('sana', '=', sana),
        ], limit=1)
        if mavjud and mavjud.holat == 'posted':
            raise UserError(_(
                "%(sana)s kuni uchun jurnal allaqachon tasdiqlangan. "
                "Tuzatish kerak bo'lsa hisobchiga murojaat qiling — sarf "
                "ombordan chiqib bo'lgan.", sana=sana))

        sarflar = []
        for qator in vals.get('sarflar') or []:
            miqdor = float(qator.get('miqdor') or 0.0)
            if not qator.get('product_id') or miqdor <= 0:
                continue
            satr = {
                'product_id': int(qator['product_id']),
                'tur': qator.get('tur') or 'yem',
                'miqdor': miqdor,
            }
            if qator.get('uom_id'):
                satr['uom_id'] = int(qator['uom_id'])
            sarflar.append((0, 0, satr))

        jurnal_vals = {
            'partiya_id': p.id,
            'sana': sana,
            'nobud_son': int(vals.get('nobud_son') or 0),
            'nobud_sabab': vals.get('nobud_sabab') or False,
            'suv_litr': float(vals.get('suv_litr') or 0.0),
            'harorat': float(vals.get('harorat') or 0.0),
            'izoh': vals.get('izoh') or '',
            'mas_ul_id': (self._panel_xodim().id or p.brigadir_id.id),
        }
        if mavjud:
            # Qoralamani qayta yozamiz: eski sarf qatorlari o'chiriladi,
            # aks holda ikki marta yozilgan yem qo'shilib ketardi.
            mavjud.sarf_ids.unlink()
            mavjud.write(dict(jurnal_vals, sarf_ids=sarflar))
            jurnal = mavjud
        else:
            jurnal = Jurnal.create(dict(jurnal_vals, sarf_ids=sarflar))
        if vals.get('tasdiqlash'):
            jurnal.action_tasdiqlash()
        return {'id': jurnal.id, 'holat': jurnal.holat,
                'partiya': self.ui_partiya(p.id)}

    @api.model
    def ui_vazn(self, vals):
        """Vazn nazorati (TZ 13-band)."""
        p = self.browse(int(vals['partiya_id']))
        p._panel_tekshir()
        tortilgan = int(vals.get('tortilgan_son') or 0)
        ortacha = float(vals.get('ortacha_vazn') or 0.0)
        # Modelda SQL CHECK bor, lekin u foydalanuvchiga tushunarsiz
        # «violates check constraint» matnini beradi. Panel telefonda
        # ishlatilgani uchun xato o'zbekcha va aniq bo'lishi kerak.
        if tortilgan <= 0 or ortacha <= 0:
            raise UserError(_(
                "Tortilgan bosh soni ham, o'rtacha vazn ham noldan katta "
                "bo'lishi kerak (kiritilgani: %(son)s bosh, %(vazn)s kg).",
                son=tortilgan, vazn=ortacha))
        vazn = self.env['agronova.boquv.vazn'].create({
            'partiya_id': p.id,
            'sana': vals.get('sana') or fields.Date.to_string(
                fields.Date.context_today(self)),
            'tortilgan_son': tortilgan,
            'ortacha_vazn': ortacha,
            'min_vazn': float(vals.get('min_vazn') or 0.0),
            'max_vazn': float(vals.get('max_vazn') or 0.0),
            'izoh': vals.get('izoh') or '',
            'mas_ul_id': (self._panel_xodim().id or p.brigadir_id.id),
        })
        return {'id': vazn.id, 'partiya': self.ui_partiya(p.id)}

    @api.model
    def ui_xarajat(self, vals):
        """Xarajat hujjati.

        Naqd to'lovda `agronova.xarajat.mixin` foto va depozitni majburiy
        qiladi — panel ularni yuboradi, tekshiruv esa mixin'da qoladi,
        ya'ni qoida bitta joyda turadi.
        """
        p = self.browse(int(vals['partiya_id']))
        p._panel_tekshir()
        xarajat = self.env['agronova.boquv.xarajat'].create({
            'sana': vals.get('sana') or fields.Date.to_string(
                fields.Date.context_today(self)),
            'kategoriya_id': int(vals['kategoriya_id']),
            'nom': vals.get('nom') or '',
            'miqdor': float(vals.get('miqdor') or 1.0),
            'narx': float(vals.get('narx') or 0.0),
            'tolov_turi': vals.get('tolov_turi') or 'naqd',
            'kontragent_id': (int(vals['kontragent_id'])
                              if vals.get('kontragent_id') else False),
            'depozit_id': (int(vals['depozit_id'])
                           if vals.get('depozit_id') else False),
            'foto': vals.get('foto') or False,
            'foto_filename': vals.get('foto_filename') or '',
            # Panel orqali kiritilgan xarajat har doim bitta partiyaga
            # tegishli — brigadir aynan shu sehda turib yozadi.
            'partiya_id': p.id,
            'filial_id': p.filial_id.id,
            'maqsad_turi': 'bitta',
            'taqsimlash_bazasi': 'togridan',
            'izoh': vals.get('izoh') or '',
        })
        if vals.get('tasdiqlash'):
            xarajat.action_tasdiqlash()
        depozit = self._panel_depozit()
        return {
            'id': xarajat.id,
            'holat': xarajat.holat,
            'depozit_balans': depozit.balans if depozit else 0.0,
            'partiya': self.ui_partiya(p.id),
        }
