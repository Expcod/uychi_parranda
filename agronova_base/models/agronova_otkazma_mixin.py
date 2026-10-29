# -*- coding: utf-8 -*-
"""Bo'limlararo mahsulot o'tkazish — umumiy ombor mantiqi.

Zanjirdagi har bir uzatish (Ona tovuq -> Inkubatsiya, Inkubatsiya ->
Boquv, Boquv -> So'yish) bir xil ishlaydi, faqat mahsuloti va tomonlari
boshqa. Shuning uchun ombor qismi shu yerda bir marta yozilgan.

Meros oluvchi modelda quyidagi maydonlar bo'lishi kutiladi:

* `product_id`, `dona`, `company_id` — jo'natuvchi tomon;
* `qabul_company_id` — qabul qiluvchi bo'lim;
* `birlik_narx` — ichki narx (qabul qiluvchi shu narxda oladi);
* `name` — hujjat raqami (`origin` sifatida yoziladi).

Model `_tannarx_1_birlik()` ni ham berishi kerak — jo'natuvchi tomonda
chiqim qaysi narxda yozilishi.
"""
from odoo import _, models
from odoo.exceptions import UserError


class AgroNovaOtkazmaMixin(models.AbstractModel):
    _name = 'agronova.otkazma.mixin'
    _description = "AgroNova — bo'limlararo o'tkazma mixin"

    def _tannarx_1_birlik(self):
        """Jo'natuvchi tomondagi 1 birlik tannarxi. Model qayta yozadi."""
        self.ensure_one()
        return 0.0

    def _transit_location(self):
        """Korxonalararo transit — korxonasi yo'q, shuning uchun ikkala
        tomon ham unga yoza oladi."""
        loc = self.env.ref('stock.stock_location_inter_company',
                           raise_if_not_found=False)
        if not loc:
            loc = self.env['stock.location'].sudo().search(
                [('usage', '=', 'transit'), ('company_id', '=', False)], limit=1)
        if not loc:
            raise UserError(_(
                "Korxonalararo transit lokatsiyasi topilmadi — mahsulotni "
                "bir bo'limdan ikkinchisiga ko'chirib bo'lmaydi."))
        return loc

    def _qabul_location(self):
        """Mahsulot qabul qiluvchi tomonda qaysi omborga tushadi.

        Ba'zi bo'limda bitta korxonada bir necha filial-ombor bor (Boquvda
        yettita). Model `qabul_warehouse_id` maydonini e'lon qilsa, aynan
        o'sha ombor ishlatiladi. Maydon yo'q yoki bo'sh bo'lsa — korxonaning
        birinchi ombori, ya'ni eski xatti-harakat saqlanadi.
        """
        self.ensure_one()
        wh = self.env['stock.warehouse']
        if 'qabul_warehouse_id' in self._fields:
            wh = self.qabul_warehouse_id
        if not wh:
            wh = wh.sudo().search(
                [('company_id', '=', self.qabul_company_id.id)], limit=1)
        if not wh:
            raise UserError(_(
                "«%s» korxonasida ombor yo'q — mahsulotni kirim qilib "
                "bo'lmaydi.", self.qabul_company_id.display_name))
        if wh.company_id != self.qabul_company_id:
            raise UserError(_(
                "«%(ombor)s» ombori «%(korxona)s» korxonasiga tegishli emas.",
                ombor=wh.display_name,
                korxona=self.qabul_company_id.display_name))
        return wh.lot_stock_id

    def _lot(self, nom, company):
        """Berilgan nomdagi lot (yo'q bo'lsa yaratiladi).

        Lot korxonaga bog'liq, shuning uchun jo'natuvchi va qabul qiluvchi
        tomonda bir xil nomli ikkita alohida yozuv bo'ladi — bu normal va
        kuzatuv zanjirini saqlab qoladi.
        """
        self.ensure_one()
        Lot = self.env['stock.lot'].sudo()
        lot = Lot.search([('name', '=', nom),
                          ('product_id', '=', self.product_id.id),
                          ('company_id', 'in', [company.id, False])], limit=1)
        return lot or Lot.create({
            'name': nom, 'product_id': self.product_id.id,
            'company_id': company.id})

    def _move_vals(self, src, dest, company, price):
        self.ensure_one()
        return {
            'product_id': self.product_id.id,
            'product_uom_qty': self.dona,
            'product_uom': self.product_id.uom_id.id,
            'location_id': src.id,
            'location_dest_id': dest.id,
            'company_id': company.id,
            'origin': self.name,
            'price_unit': price,
        }

    def _chiqim(self, manba, transit):
        """Jo'natuvchi tomondagi chiqim.

        Lot **majburlanmaydi** — Odoo o'zi ombordagi mavjud lotdan oladi.
        Oldin yangi lot yaratib qo'yilgani uchun chiqim mavjud qoldiqqa
        tegmay, o'sha yangi lotda manfiy qoldiq hosil qilardi.
        """
        self.ensure_one()
        move = self.env['stock.move'].sudo().with_company(self.company_id).create(
            self._move_vals(manba, transit, self.company_id,
                            self._tannarx_1_birlik()))
        move._action_confirm()
        move._action_assign()
        if move.state != 'assigned':
            raise UserError(_(
                "«%(joy)s» da %(son)s dona «%(mahsulot)s» yo'q — "
                "o'tkazib bo'lmaydi.",
                joy=manba.complete_name, son=self.dona,
                mahsulot=self.product_id.display_name))
        move.picked = True
        move._action_done()
        return move

    def _kirim(self, transit, dest, taqsimot):
        """Qabul qiluvchi tomondagi kirim.

        `taqsimot` — `[(lot nomi, miqdor), ...]`. Transitda rezerv qiladigan
        narsa yo'q, shuning uchun qatorlar qo'lda yoziladi.
        """
        self.ensure_one()
        company = self.qabul_company_id
        move = self.env['stock.move'].sudo().with_company(company).create(
            self._move_vals(transit, dest, company, self.birlik_narx))
        move._action_confirm()
        move.move_line_ids.unlink()
        kuzatiladi = self.product_id.tracking != 'none'
        lotlar = self.env['stock.lot']
        for nom, qty in taqsimot:
            lot = self._lot(nom, company) if kuzatiladi and nom else None
            lotlar |= lot or self.env['stock.lot']
            self.env['stock.move.line'].sudo().create({
                'move_id': move.id,
                'product_id': self.product_id.id,
                'quantity': qty,
                'location_id': transit.id,
                'location_dest_id': dest.id,
                'company_id': company.id,
                'lot_id': lot.id if lot else False,
                # `picked` qatorda ham belgilanishi shart: Odoo qiymatga
                # kiradigan qatorlarni (`_get_in_move_lines`) aynan shu
                # bayroq bo'yicha ajratadi. Faqat harakatda qo'yilsa,
                # qiymat hisoblanadi-yu, FIFO uni «kirim» deb sanamaydi va
                # qabul qiluvchi bo'lim tannarxi nol bo'lib qoladi.
                'picked': True,
            })
        move.picked = True
        # Qabul qiluvchi bo'lim mahsulotni **ichki narxda** oladi — ikki
        # qatlamli hisobning talabi. Oddiy kirim harakatida Odoo `price_unit`
        # ga qaramaydi, mahsulotning standart narxini oladi (u esa nol
        # bo'lishi mumkin), shuning uchun qiymat qo'lda belgilanadi.
        #
        # DIQQAT: `_action_done` dan OLDIN yozilishi shart. Odoo qiymatni
        # yakunlash paytida hisoblaydi va o'sha yerda mahsulotning standart
        # narxini yangilaydi. Keyin yozilsa harakatning qiymati to'g'ri
        # bo'ladi-yu, standart narx nolligicha qoladi — natijada qabul
        # qiluvchi bo'lim mahsulotni keyinchalik nol tannarxda hisobdan
        # chiqaradi.
        move.sudo().value_manual = self.birlik_narx * self.dona
        move._action_done()

        # Qabul qiluvchi bo'limning standart narxini ham ichki narxga
        # qo'yamiz.
        #
        # Nima uchun kerak. Odoo FIFO tannarxini ataylab **oddiy
        # foydalanuvchi** nomidan hisoblaydi (`_compute_value` ichida
        # `sudo(False)`). Hujjatni Ona tovuq xodimi o'tkazadi, uning
        # ruxsatida esa qabul qiluvchi korxona bo'lmaydi — natijada
        # qoldiq nol ko'rinadi va standart narx nolligicha qoladi.
        # Keyin So'yish bo'limi tirik tovuqni nol tannarxda hisobdan
        # chiqarib yuborardi.
        #
        # Cheklov: qabul qiluvchi omborda shu mahsulotdan boshqa narxdagi
        # qoldiq bo'lsa, u ham shu narxga tenglashadi. Tuxum va tirik
        # tovuqda bu muammo emas — ular partiyalab kelib, partiyalab
        # ishlatiladi.
        self.product_id.with_company(company).sudo().with_context(
            disable_auto_revaluation=True).standard_price = self.birlik_narx
        return move, lotlar[:1]
