# -*- coding: utf-8 -*-
"""Ona tovuq partiyasi (B03).

Jo'ja o'stirish partiyasi yopilganda avtomat ochiladi. Boshlang'ich qiymat —
o'stirishdagi 1 bosh tannarxi (bozor narxida qayta baholash yo'q).

Poda eskirganda (tuxum berish % normadan tushganda) partiya yopiladi va
bosh soni **so'yishga ichki sotuv** sifatida o'tkaziladi.
"""
from odoo import _, api, fields, models
from odoo.exceptions import UserError

from .agronova_ona_tovuq_normativ import DEFAULT_NORMA


class AgroNovaOnaTovuqPartiyaTuxum(models.Model):
    _name = 'agronova.ona_tovuq.partiya.tuxum'
    _description = "Ona tovuq partiyasi"
    _inherit = ['agronova.ona_tovuq.partiya.mixin']
    _agronova_tannarx_fields = ('boshlangich_tannarx',)

    ostirish_partiya_id = fields.Many2one(
        'agronova.ona_tovuq.partiya.ostirish', string="Jo'ja o'stirish partiyasi",
        required=True, readonly=True, ondelete='restrict', index=True)
    ochilish_sana = fields.Date(
        "Ochilish sanasi", required=True, readonly=True,
        default=fields.Date.context_today,
        help="Jo'ja o'stirish partiyasi yopilgan sana.")
    yopilish_sana = fields.Date("Yopilgan sana", readonly=True, copy=False)
    yosh_hafta = fields.Integer("Yoshi (hafta)", compute='_compute_yosh')

    # Meros qiymat — readonly, o'stirishdan ko'chadi.
    boshlangich_tannarx = fields.Monetary(
        "Meros 1 bosh tannarxi", readonly=True,
        help="Jo'ja o'stirish partiyasidan ko'chgan qiymat. Qo'lda kiritilmaydi.")

    holat = fields.Selection(
        [('active', "Faol"), ('closed', "Yopilgan")],
        string="Holati", default='active', required=True, tracking=True, copy=False)
    yopilish_sababi = fields.Selection(
        [('eskirgan', "Poda eskirgan"), ('boshqa', "Boshqa sabab")],
        string="Yopilish sababi", copy=False)
    soyishga_otkazish_id = fields.Many2one(
        'agronova.ona_tovuq.ichki_sotuv', string="So'yishga o'tkazish hujjati",
        readonly=True, copy=False)

    jurnal_ids = fields.One2many(
        'agronova.ona_tovuq.jurnal.tuxum', 'partiya_id', string="Kunlik jurnal")
    kirim_ids = fields.One2many(
        'agronova.ona_tovuq.tuxum.kirim', 'partiya_id', string="Tuxum kirimlari")

    # --- xo'roz / tovuq
    # Xo'roz soni har kuni qo'lda yozilmaydi: poda kelganda bir marta
    # kiritiladi, keyin kunlik jurnalda «nobuddan nechtasi xo'roz» degan
    # bitta raqamdan hisoblanib boradi. Tovuq soni esa qoldiqdan chiqadi.
    xoroz_boshlangich = fields.Integer(
        "Boshlang'ich xo'roz soni", tracking=True,
        help="Poda kelganda nechta xo'roz bo'lgani. Keyingi o'zgarish "
             "kunlik jurnaldagi nobud/brak orqali hisoblanadi.")
    xoroz_son = fields.Integer(
        "Xo'roz soni", compute='_compute_xoroz_tovuq', store=True,
        help="Boshlang'ich xo'roz soni minus jurnallardagi xo'roz yo'qotishi.")
    tovuq_son = fields.Integer(
        "Tovuq soni", compute='_compute_xoroz_tovuq', store=True,
        help="Joriy bosh soni minus xo'roz soni.")
    xoroz_tovuq_nisbati = fields.Float(
        "Xo'roz / tovuq nisbati", compute='_compute_xoroz_tovuq', store=True,
        digits=(12, 4))
    nisbat_norma = fields.Float(
        "Nisbat normasi", compute='_compute_normalar', digits=(12, 4))
    nisbat_ogohlantirish = fields.Boolean(
        "Nisbat normadan chetlangan", compute='_compute_normalar')

    # --- tuxum ko'rsatkichlari
    jami_tuxum = fields.Integer(
        "Jami tuxum (dona)", compute='_compute_tuxum', store=True)
    sifatli_tuxum = fields.Integer("Sifatli tuxum", compute='_compute_tuxum', store=True)
    brak_tuxum = fields.Integer("Brak tuxum", compute='_compute_tuxum', store=True)
    inkubatsiyaga_yarokli = fields.Integer(
        "Inkubatsiyaga yaroqli", compute='_compute_tuxum', store=True)
    tuxum_berish_foiz = fields.Float(
        "O'rtacha tuxum berish (%)", compute='_compute_tuxum', store=True)
    uruglanish_foiz = fields.Float(
        "O'rtacha urug'lanish (%)", compute='_compute_tuxum', store=True)
    norma_tuxum_berish = fields.Float(
        "Tuxum berish normasi (%)", compute='_compute_normalar')
    eskirganmi = fields.Boolean(
        "Eskirgan (normadan past)", compute='_compute_normalar',
        help="So'nggi 7 kunlik o'rtacha tuxum berish % eskirish chegarasidan "
             "past bo'lsa belgilanadi.")

    # --- tannarx
    tannarx_1_dona = fields.Monetary(
        "1 dona tuxum tannarxi", compute='_compute_tannarx', readonly=True,
        help="Jami xarajat / jami ishlab chiqarilgan tuxum. Qo'lda kiritilmaydi.")

    # ------------------------------------------------------------- compute
    @api.depends('boshlangich_son', 'chiqim_son',
                 'jurnal_ids.nobud_son', 'jurnal_ids.brak_son')
    def _compute_son(self):
        return super()._compute_son()

    @api.depends('ochilish_sana', 'yopilish_sana')
    def _compute_yosh(self):
        bugun = fields.Date.context_today(self)
        for p in self:
            oxir = p.yopilish_sana or bugun
            kun = (oxir - p.ochilish_sana).days if p.ochilish_sana else 0
            # Podaning umumiy yoshi = o'stirish davri + tuxum davri
            ostirish_kun = p.ostirish_partiya_id.yosh_kun or 0
            p.yosh_hafta = max((ostirish_kun + kun) // 7, 0)

    @api.depends('xoroz_boshlangich', 'jurnal_ids.nobud_xoroz', 'joriy_son')
    def _compute_xoroz_tovuq(self):
        for p in self:
            yoqotilgan = sum(p.jurnal_ids.mapped('nobud_xoroz'))
            p.xoroz_son = max(p.xoroz_boshlangich - yoqotilgan, 0)
            p.tovuq_son = max(p.joriy_son - p.xoroz_son, 0)
            p.xoroz_tovuq_nisbati = (
                p.xoroz_son / p.tovuq_son if p.tovuq_son else 0.0)

    @api.depends('jurnal_ids.jami_tuxum', 'jurnal_ids.sifatli_tuxum',
                 'jurnal_ids.brak_tuxum', 'jurnal_ids.inkubatsiyaga_yarokli',
                 'jurnal_ids.tuxum_berish_foiz', 'jurnal_ids.uruglanish_foiz')
    def _compute_tuxum(self):
        for p in self:
            jurnal = p.jurnal_ids
            p.jami_tuxum = sum(jurnal.mapped('jami_tuxum'))
            p.sifatli_tuxum = sum(jurnal.mapped('sifatli_tuxum'))
            p.brak_tuxum = sum(jurnal.mapped('brak_tuxum'))
            p.inkubatsiyaga_yarokli = sum(jurnal.mapped('inkubatsiyaga_yarokli'))
            foizlar = [j.tuxum_berish_foiz for j in jurnal if j.tuxum_berish_foiz]
            p.tuxum_berish_foiz = sum(foizlar) / len(foizlar) if foizlar else 0.0
            urug = [j.uruglanish_foiz for j in jurnal if j.uruglanish_foiz]
            p.uruglanish_foiz = sum(urug) / len(urug) if urug else 0.0

    @api.depends('zot_id', 'yosh_hafta', 'tuxum_berish_foiz',
                 'xoroz_tovuq_nisbati', 'jurnal_ids')
    def _compute_normalar(self):
        Normativ = self.env['agronova.ona_tovuq.normativ']
        ICP = self.env['ir.config_parameter'].sudo()
        chegara = float(ICP.get_param(
            'agronova_ona_tovuq.eskirish_chegara',
            DEFAULT_NORMA['eskirish_chegara_foiz']))
        for p in self:
            p.norma_tuxum_berish = Normativ.qiymat(
                'tuxum_berish_foiz', zot=p.zot_id, hafta=p.yosh_hafta)
            p.nisbat_norma = Normativ.qiymat(
                'xoroz_tovuq_nisbati', zot=p.zot_id, hafta=p.yosh_hafta)
            # Nisbat normadan 20% dan ko'proq chetlansa — ogohlantirish
            p.nisbat_ogohlantirish = bool(
                p.tovuq_son and p.nisbat_norma
                and abs(p.xoroz_tovuq_nisbati - p.nisbat_norma) / p.nisbat_norma > 0.20)
            p.eskirganmi = bool(p.oxirgi_hafta_tuxum_foiz() < chegara
                                and p.jurnal_ids)

    def oxirgi_hafta_tuxum_foiz(self):
        """So'nggi 7 kunlik o'rtacha tuxum berish foizi."""
        self.ensure_one()
        jurnal = self.jurnal_ids.sorted('date')[-7:]
        foizlar = [j.tuxum_berish_foiz for j in jurnal if j.tuxum_berish_foiz]
        return sum(foizlar) / len(foizlar) if foizlar else 0.0

    def _compute_tannarx(self):
        for p in self:
            # Tannarx faqat ishlab chiqarish xarajatidan hisoblanadi:
            # sotilgan tuxumning tannarx chiqimi bu bazaga kirmaydi, aks
            # holda har sotuvda tannarx o'z-o'zidan oshib ketadi.
            ishlab_chiqarish = p._agronova_analytic_amount(
                sign='cost', faqat_tannarx=True)
            p.tannarx_1_dona = (ishlab_chiqarish / p.jami_tuxum
                                if p.jami_tuxum else 0.0)

    # ------------------------------------------------------------- yaratish
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('name') or vals['name'] == _("Yangi"):
                vals['name'] = self.env['ir.sequence'].next_by_code(
                    'agronova.ona_tovuq.partiya.tuxum') or _("Yangi")
        return super().create(vals_list)

    # ------------------------------------------------------------ tannarx
    def _joriy_tannarx_1_dona(self, sana=None):
        """Kirim paytidagi 1 dona tuxum tannarxi.

        Davr yopilishini kutmasdan, partiyaning shu paytgacha yig'ilgan
        xarajati va ishlab chiqarilgan tuxumi nisbati olinadi (yugurib
        boruvchi o'rtacha). Oy yopilganda `agronova.ona_tovuq.tannarx` hisoboti
        aniq davr tannarxini ko'rsatadi.
        """
        self.ensure_one()
        xarajat = self._agronova_analytic_amount(sign='cost', date_to=sana)
        jurnal = self.jurnal_ids
        if sana:
            jurnal = jurnal.filtered(lambda j: j.date <= sana)
        tuxum = sum(jurnal.mapped('jami_tuxum'))
        return xarajat / tuxum if tuxum else 0.0

    # -------------------------------------------------------------- holatlar
    def action_yopish(self, sabab='eskirgan'):
        for p in self:
            if p.holat != 'active':
                raise UserError(_("Faqat faol partiya yopiladi."))
            if p.joriy_son > 0 and not p.soyishga_otkazish_id:
                raise UserError(_(
                    "«%(nom)s» partiyasida %(son)s bosh qolgan. Avval podani "
                    "so'yishga o'tkazish hujjatini rasmiylashtiring "
                    "(«So'yishga o'tkazish» tugmasi).",
                    nom=p.name, son=p.joriy_son))
            p.write({
                'holat': 'closed',
                'yopilish_sababi': sabab,
                'yopilish_sana': fields.Date.context_today(p),
            })
            p.message_post(body=_("Ona tovuq partiyasi yopildi. Sabab: %s", sabab))
        return True

    def action_soyishga_otkazish(self):
        """Eskirgan podani so'yishga ichki sotuv hujjatini ochadi."""
        self.ensure_one()
        if self.joriy_son <= 0:
            raise UserError(_("Partiyada o'tkaziladigan bosh soni yo'q."))
        return {
            'type': 'ir.actions.act_window',
            'name': _("Podani so'yishga o'tkazish"),
            'res_model': 'agronova.ona_tovuq.ichki_sotuv',
            'view_mode': 'form',
            'target': 'new',
            # Maydon nomlari model bilan bir xil bo'lishi shart, aks
            # holda forma bo'sh ochiladi: tur / partiya_id / dona.
            'context': {
                'default_tur': 'poda_soyish',
                'default_partiya_id': self.id,
                'default_dona': self.joriy_son,
            },
        }

    def action_open_jurnal(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _("«%s» kunlik jurnali", self.name),
            'res_model': 'agronova.ona_tovuq.jurnal.tuxum',
            'view_mode': 'list,form',
            'domain': [('partiya_id', '=', self.id)],
            'context': {'default_partiya_id': self.id},
        }

    def write(self, vals):
        qulf_tashqari = {'holat', 'yopilish_sababi', 'yopilish_sana',
                         'soyishga_otkazish_id', 'chiqim_son',
                         'message_follower_ids', 'message_ids', 'activity_ids'}
        if set(vals) - qulf_tashqari:
            for p in self:
                if p.holat == 'closed':
                    raise UserError(_(
                        "«%s» tuxum partiyasi yopilgan — tahrirlash taqiqlanadi.",
                        p.name))
        return super().write(vals)

    def unlink(self):
        raise UserError(_(
            "Ona tovuq partiyasi o'chirilmaydi — u jo'ja o'stirish partiyasining davomi "
            "va tannarx zanjirini uzadi."))
