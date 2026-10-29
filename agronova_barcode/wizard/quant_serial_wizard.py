"""Inventarizatsiyada serial miqdorini ommaviy boshqarish.

Odoo standartida serialli mahsulotni inventarizatsiya qilishda har bir seriya
qo'lda kiritiladi — 100 dona tovar uchun 100 marta. Ommaviy generatsiya
(`stock.move._generate_serial_numbers`) faqat `stock.move` da yashaydi, ya'ni
qabul qilish/yetkazishda. Inventarizatsiya esa `stock.quant` orqali ishlaydi va
u mexanizmga ulanmagan — shu bo'shliqni to'ldiradi.

Wizard "yangi miqdorni yozing" tamoyilida ishlaydi: hozirgi son ko'rsatiladi,
foydalanuvchi kerakli sonni yozadi, farqiga qarab seriya qo'shiladi yoki
chiqariladi. Bu har bir qatorni qo'lda nollashdan ancha qulay.
"""
from odoo import _, api, fields, models
from odoo.exceptions import UserError

# Bir martada qo'shish/chiqarish mumkin bo'lgan chegara. Ko'p bo'lsa so'rov uzoq
# ketadi va foydalanuvchi "osilib qoldi" deb o'ylaydi; xato bo'lsa tozalash og'ir.
MAX_SERIALS = 500


class StockQuantSerialWizard(models.TransientModel):
    _name = "agronova.quant.serial.wizard"
    _description = "Serial miqdorini o'zgartirish"

    # Mahsulot kartasidan ("Quantity On Hand" → Update Quantity) kirilganda Odoo
    # `default_product_id` ni kontekstga qo'yadi — maydon o'zi to'ladi va
    # `product_locked` uni o'zgartirishga yo'l qo'ymaydi: omborchi boshqa
    # mahsulotga seriya yozib yubormasligi kerak.
    product_id = fields.Many2one(
        "product.product", "Mahsulot", required=True,
        domain=[("tracking", "=", "serial"), ("is_storable", "=", True)],
        help="Faqat seriya bo'yicha kuzatiladigan mahsulotlar.",
    )
    product_locked = fields.Boolean(
        compute="_compute_product_locked",
        help="Mahsulot kartasidan kirilganda mahsulot o'zgartirilmaydi.",
    )
    location_id = fields.Many2one(
        "stock.location", "Lokatsiya", required=True,
        domain=[("usage", "in", ["internal", "transit"])],
        default=lambda self: self._default_location_id(),
        help="Tovar qaysi joyda turibdi.",
    )
    company_id = fields.Many2one(
        "res.company", "Kompaniya", required=True,
        default=lambda self: self.env.company,
    )

    current_qty = fields.Integer(
        "Hozirgi soni", compute="_compute_current_qty",
        help="Shu lokatsiyada hozir nechta seriya bor.",
    )
    count = fields.Integer(
        "Yangi soni", default=1, required=True,
        help="Jami nechta bo'lishi kerak. Ko'proq yozsangiz yangi seriya "
             "yaratiladi, kamroq yozsangiz ortiqchasi chiqariladi.",
    )
    diff = fields.Integer("Farq", compute="_compute_current_qty")
    diff_mode = fields.Selection(
        [("add", "qo'shiladi"), ("remove", "chiqariladi"), ("none", "o'zgarmaydi")],
        compute="_compute_current_qty",
    )

    # --- kamaytirishda qaysi seriyalar chiqishi ---
    removal_mode = fields.Selection(
        [("auto", "Tizim tanlasin (eng eskisidan)"), ("manual", "O'zim tanlayman")],
        string="Chiqariladigan seriyalar", default="auto", required=True,
        help="Avtomatik: eng oldin yaratilganlari chiqariladi.\n"
             "Qo'lda: ro'yxatdan o'zingiz belgilaysiz — javondagi haqiqiy "
             "tovarga mos bo'ladi.",
    )
    # Ikkala many2many ham `stock.lot` ga qaraydi — jadval nomlari ATAYLAB
    # qo'lda berilgan, avtomatik nom ikkalasiga bir xil chiqib to'qnashardi.
    removal_lot_ids = fields.Many2many(
        "stock.lot", "quant_serial_wiz_removal_lot_rel",
        string="Chiqariladigan seriyalar",
        help="Qaysi seriyalar omborda qolmaydi.",
    )
    # Compute many2many — jadval nomi berilmaydi (saqlanmaydi).
    available_lot_ids = fields.Many2many(
        "stock.lot", string="Mavjud seriyalar", compute="_compute_current_qty",
        help="Qo'lda tanlashda ro'yxat shulardan iborat bo'ladi.",
    )

    @api.depends("product_id", "location_id", "count")
    def _compute_current_qty(self):
        """Hozirgi qoldiq, farq va tanlash uchun mavjud seriyalar ro'yxati."""
        for wiz in self:
            lots = wiz._existing_lots()
            wiz.available_lot_ids = lots
            wiz.current_qty = len(lots)
            diff = wiz.count - len(lots)
            wiz.diff = abs(diff)
            wiz.diff_mode = "add" if diff > 0 else ("remove" if diff < 0 else "none")

    def _existing_lots(self):
        """Shu mahsulot+lokatsiyada ijobiy qoldiqli seriyalar.

        Har bir serial quant 1 donadan bo'lgani uchun (buni
        `stock_quant._check_serial_quantity` kafolatlaydi) seriyalar soni =
        jami miqdor. `id` bo'yicha tartib — avtomatik chiqarishda eng eskisi
        birinchi bo'lishi uchun.
        """
        self.ensure_one()
        if not self.product_id or not self.location_id:
            return self.env["stock.lot"]
        quants = self.env["stock.quant"].sudo().search([
            ("product_id", "=", self.product_id.id),
            ("location_id", "=", self.location_id.id),
            ("lot_id", "!=", False),
            ("quantity", ">", 0),
        ], order="lot_id")
        return quants.mapped("lot_id").sorted("id")

    @api.model
    def default_get(self, fields_list):
        """Mahsulot kartasidan kelgan `default_product_id` ni tekshiradi.

        Tugma quant ro'yxatining sarlavhasida turadi va u yerda yozuv konteksti
        yo'q — `tracking` ni view darajasida tekshirib bo'lmaydi. Shuning uchun
        serialli emas mahsulotda tugma bosilsa, tushunarli xato shu yerda
        chiqadi (aks holda mahsulot domenga tushmay, oyna bo'sh ochilardi).
        """
        res = super().default_get(fields_list)
        product_id = res.get("product_id") or self.env.context.get("default_product_id")
        if product_id:
            product = self.env["product.product"].browse(product_id)
            if product.tracking != "serial":
                raise UserError(_(
                    "«%(product)s» seriya bo'yicha kuzatilmaydi — ommaviy seriya "
                    "yaratish faqat seriyali mahsulotlar uchun.",
                ) % {"product": product.display_name})
            res["product_id"] = product.id

        # `count` boshlang'ich qiymati — hozirgi qoldiq. Shunda oyna ochilganda
        # foydalanuvchi haqiqiy holatni ko'radi va uni kerakli songa o'zgartiradi.
        # Bo'sh yoki 1 bo'lsa "hammasini o'chirmoqchimisiz?" degan xavf tug'ilardi.
        if "count" in fields_list and res.get("product_id"):
            location_id = res.get("location_id") or self._default_location_id()
            if location_id:
                res["location_id"] = location_id
                probe = self.new({
                    "product_id": res["product_id"],
                    "location_id": location_id,
                })
                res["count"] = len(probe._existing_lots()) or 1
        return res

    @api.model
    def _default_location_id(self):
        """Ombor bitta lokatsiyali bo'lsa Odoo `default_location_id` beradi.

        Bermasa — omborning asosiy zaxira joyi. Ko'p lokatsiyali ombor bo'lsa
        ham bu eng ehtimolli javob, foydalanuvchi kerak bo'lsa o'zgartiradi.
        """
        if self.env.context.get("default_location_id"):
            return self.env.context["default_location_id"]
        warehouse = self.env["stock.warehouse"].search(
            [("company_id", "=", self.env.company.id)], limit=1)
        return warehouse.lot_stock_id.id if warehouse else False

    @api.depends_context("single_product")
    def _compute_product_locked(self):
        locked = bool(self.env.context.get("single_product"))
        for wiz in self:
            wiz.product_locked = locked

    @api.constrains("count")
    def _check_count(self):
        for wiz in self:
            if wiz.count < 0:
                raise UserError(_("Soni manfiy bo'lishi mumkin emas."))

    def _check_batch_size(self, size):
        if size > MAX_SERIALS:
            raise UserError(_(
                "Bir martada eng ko'pi %(max)d ta seriya o'zgartirish mumkin "
                "(so'raldi: %(asked)d). Kattaroq partiyani bo'lib bajaring."
            ) % {"max": MAX_SERIALS, "asked": size})

    def _check_ready(self):
        """Ishga kirishishdan oldingi umumiy tekshiruvlar."""
        self.ensure_one()
        self._check_count()

        if self.product_id.tracking != "serial":
            raise UserError(_("Bu mahsulot seriya bo'yicha kuzatilmaydi."))

        # Lokatsiya boshqa kompaniyaniki bo'lsa Odoo `_check_company` bilan
        # tushunarsiz xato beradi — oldindan aniq xabar chiqargan ma'qul.
        loc_company = self.location_id.company_id
        if loc_company and loc_company != self.company_id:
            raise UserError(_(
                "«%(location)s» lokatsiyasi «%(loc_company)s» kompaniyasiga tegishli, "
                "siz esa «%(company)s» ni tanladingiz.",
            ) % {
                "location": self.location_id.display_name,
                "loc_company": loc_company.name,
                "company": self.company_id.name,
            })

    def action_apply(self):
        """Miqdorni kiritilgan songa keltiradi.

        Farq musbat bo'lsa yangi seriya yaratadi, manfiy bo'lsa mavjudlarini
        chiqaradi. O'zgarish darhol kuchga kiradi — alohida "Apply" shart emas.
        """
        self._check_ready()

        existing = self._existing_lots()
        diff = self.count - len(existing)
        if diff == 0:
            raise UserError(_(
                "Miqdor o'zgarmadi — hozir ham %d ta.") % len(existing))

        self._check_batch_size(abs(diff))
        if diff > 0:
            return self._add_serials(diff)
        return self._remove_serials(existing, -diff)

    # ------------------------------------------------------------------
    def _add_serials(self, count):
        """`count` ta yangi seriya yaratadi, har biriga 1 dona qoldiq."""
        names = self.env["stock.lot"].generate_complex_serials(count)

        # Lotlar bir marta, ommaviy yaratiladi — bittalab `create` sekin ishlardi.
        lots = self.env["stock.lot"].create([{
            "name": name,
            "product_id": self.product_id.id,
            "company_id": self.company_id.id,
        } for name in names])

        # `inventory_quantity_auto_apply` ATAYLAB ishlatiladi, `quantity` emas.
        # To'g'ridan-to'g'ri `quantity` yozish quantni jimgina paydo qiladi —
        # `stock.move` yaratilmaydi va tovar qayerdan kelgani ombor tarixida
        # ko'rinmay qoladi. `auto_apply` esa darhol tasdiqlaydi VA harakatni
        # yozadi, ya'ni oddiy inventarizatsiya kabi hisobga tushadi.
        Quant = self.env["stock.quant"].with_context(inventory_mode=True)
        Quant.create([{
            "product_id": self.product_id.id,
            "location_id": self.location_id.id,
            "lot_id": lot.id,
            "inventory_quantity_auto_apply": 1.0,
        } for lot in lots])

        return self._notify(_(
            "%(count)d ta seriya qo'shildi. Stikerlari hali chop etilmagan — "
            "ro'yxatdan tanlab chop eting."
        ) % {"count": len(lots)})

    def _remove_serials(self, existing, count):
        """`count` ta seriyani ombordan chiqaradi (qoldiqni 0 qiladi).

        Lot yozuvi O'CHIRILMAYDI — faqat qoldiq nolga tushadi. Sabab: lot
        tarixga bog'langan (qaysi buyurtmada ketgan, qaysi MO da chiqqan) va
        uni o'chirish o'sha izlarni ham yo'q qiladi. Odoo inventarizatsiyasi
        ham xuddi shunday ishlaydi.
        """
        if self.removal_mode == "manual":
            lots = self.removal_lot_ids
            if not lots:
                raise UserError(_(
                    "Chiqariladigan seriyalarni belgilang yoki «Tizim tanlasin» "
                    "rejimiga o'ting."))
            wrong = lots - existing
            if wrong:
                raise UserError(_(
                    "Bu seriyalar shu lokatsiyada mavjud emas: %s"
                ) % ", ".join(wrong.mapped("name")[:5]))
            if len(lots) != count:
                raise UserError(_(
                    "%(need)d ta seriya chiqarilishi kerak, siz %(got)d tasini "
                    "belgiladingiz."
                ) % {"need": count, "got": len(lots)})
        else:
            # Eng eskisidan — `_existing_lots` `id` bo'yicha tartiblangan.
            lots = existing[:count]

        quants = self.env["stock.quant"].sudo().search([
            ("product_id", "=", self.product_id.id),
            ("location_id", "=", self.location_id.id),
            ("lot_id", "in", lots.ids),
        ])
        # `inventory_quantity_auto_apply` = 0 — qoldiqni nolga tushiradi va
        # tegishli `stock.move` ni yozadi.
        quants.with_context(inventory_mode=True).write({
            "inventory_quantity_auto_apply": 0,
        })

        return self._notify(_(
            "%(count)d ta seriya ombordan chiqarildi."
        ) % {"count": len(lots)})

    def _notify(self, message):
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Bajarildi"),
                "message": message,
                "type": "success",
                "sticky": False,
                "next": {"type": "ir.actions.act_window_close"},
            },
        }
