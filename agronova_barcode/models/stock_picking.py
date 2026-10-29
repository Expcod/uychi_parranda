"""Transferda majburiy QR skanerlash (tayyor mahsulot, serial tracking).

Nima uchun: tayyor mahsulot serial raqam bilan yuradi. Omborchi sonni qo'lda
yozsa xato bo'lishi mumkin — shuning uchun son FAQAT skanerlash orqali kiritiladi.

Oqim:
  transfer sahifasi → [Skanerlashni boshlash] → QR skanerlanadi:
      • serial QR → 1 dona qo'shiladi
      • quti QR   → ichidagi barcha serial qo'shiladi (masalan 30 dona)
  → Validate: skanerlanmagan serial mahsulot bo'lsa BLOKLANADI

Chetlab o'tish: ombor menejeri (`stock.group_stock_manager`) sabab yozib
o'tkazib yuborishi mumkin — eski (QR'siz) lotlar yoki yirtilgan stiker uchun.
Chetlab o'tish transfer chatiga yoziladi.
"""
import logging
from datetime import datetime, time

from odoo import _, api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class StockPicking(models.Model):
    _inherit = "stock.picking"

    qr_scan_required = fields.Boolean(
        "QR skanerlash shart",
        compute="_compute_qr_scan_required",
        help="Transferda serial bilan kuzatiladigan mahsulot bormi.",
    )
    qr_scan_done = fields.Boolean(
        "Skanerlash yakunlangan",
        compute="_compute_qr_scan_state",
        help="Serial mahsulotlar to'liq skanerlanganmi.",
    )
    qr_scan_info = fields.Char(
        "Skanerlash holati", compute="_compute_qr_scan_state",
    )
    qr_scan_bypassed = fields.Boolean(
        "Skanerlash chetlab o'tilgan", copy=False, readonly=True,
    )

    @api.depends("move_ids.product_id.tracking", "move_ids.state",
                 "picking_type_id.qr_scan_exempt")
    def _compute_qr_scan_required(self):
        for picking in self:
            # Ozod qilingan operatsiya turi (masalan agentning mijozga
            # yetkazishi) — skanerlash umuman talab qilinmaydi. Bu yagona
            # nuqta: `button_validate` bloklamaydi, sonni qo'lda kiritsa
            # bo'ladi va formadagi skaner tinglovchisi ham o'zini o'chiradi
            # (`picking_qr_scan.js` `qr_scan_required` ga qaraydi).
            if picking.picking_type_id.qr_scan_exempt:
                picking.qr_scan_required = False
                continue
            picking.qr_scan_required = any(
                m.product_id.tracking == "serial"
                for m in picking.move_ids
                if m.state not in ("done", "cancel")
            )

    @api.depends("move_ids.move_line_ids.lot_id", "move_ids.move_line_ids.quantity",
                 "move_ids.move_line_ids.qr_scanned", "move_ids.product_uom_qty")
    def _compute_qr_scan_state(self):
        for picking in self:
            if not picking.qr_scan_required:
                picking.qr_scan_done = True
                picking.qr_scan_info = ""
                continue
            scanned, demand = picking._qr_scan_progress()
            picking.qr_scan_done = scanned >= demand
            picking.qr_scan_info = _("%(done)s / %(total)s skanerlangan") % {
                "done": int(scanned), "total": int(demand),
            }

    def _serial_moves(self):
        """Serial bilan kuzatiladigan, hali yakunlanmagan harakatlar."""
        return self.move_ids.filtered(
            lambda m: m.product_id.tracking == "serial"
            and m.state not in ("done", "cancel")
        )

    def _qr_scan_progress(self):
        """(skanerlangan, so'ralgan) — serial mahsulotlar bo'yicha.

        FAQAT `qr_scanned` belgisi qo'yilgan qatorlar hisoblanadi. Odoo
        rezervatsiyasi (`_action_assign`) ham `lot_id` to'ldiradi, lekin uni
        skanerlash deb hisoblash mumkin emas — omborchi tovarni ko'rmagan ham
        bo'lishi mumkin. Ilgari shu sabab filialga kelgan transfer darhol
        "4 / 10 skanerlangan" bo'lib turardi.

        ISTISNO: Agar seriyaning o'zida `qr_scan_required == False` bo'lsa
        (omborlardagi mavjud, QR stikeri yo'q eski tovarlar), ushbu seriya
        skanerlash talab qilinmaydigan deb hisoblanadi va to'g'ridan-to'g'ri
        tasdiqlashga ruxsat beriladi.
        """
        self.ensure_one()
        moves = self._serial_moves()
        demand = sum(moves.mapped("product_uom_qty"))
        scanned = sum(
            ml.quantity for ml in moves.mapped("move_line_ids")
            if ml.lot_id and (ml.qr_scanned or not ml.lot_id.qr_scan_required)
        )
        return scanned, demand

    def _check_fifo_order(self, lots, moves):
        """Source locationda skanerlanayotgandan ESKI seriallar bormi.

        FIFO: eng eski serial avval chiqishi kerak. Omborda hali
        chiqarilmagan, shu lotlardan ESKI serial mavjud bo'lsa —
        skanerlash bloklanadi va omborchiga qaysilarni avval olish
        kerakligi ko'rsatiladi.

        Taqqoslash faqat SANA bo'yicha (soat/daqiqa hisobga olinmaydi):
        bir kunda yaratilgan seriallar teng hisoblanadi va istalgan
        tartibda skanerlanishi mumkin. Faqat oldingi KUNdagi serial
        omborda qolgan bo'lsa bloklanadi.

        :return: eski lotlar recordset (create_date bo'yicha tartiblangan),
                 bo'sh bo'lsa FIFO buzilmagan.
        """
        if not lots:
            return self.env["stock.lot"]

        oldest_in_batch = min(
            lots, key=lambda l: l.create_date or fields.Datetime.now())
        if not oldest_in_batch.create_date:
            return self.env["stock.lot"]

        # Faqat sana bo'yicha: shu kunning boshi (00:00). Bir kunda
        # yaratilgan seriallar teng — ular "eski" deb hisoblanmaydi.
        oldest_day_start = datetime.combine(
            oldest_in_batch.create_date.date(), time.min)

        # Allaqachon skanerlangan — ular ketayotgan, tekshirish shart emas
        already_scanned = self.env["stock.lot"]
        for move in moves:
            already_scanned |= move.move_line_ids.filtered(
                lambda ml: ml.lot_id and ml.qr_scanned
            ).mapped("lot_id")

        exclude_ids = (lots | already_scanned).ids

        # Source location dagi shu mahsulotning eski seriallari
        product_ids = lots.mapped("product_id").ids
        source_loc_ids = moves.filtered(
            lambda m: m.product_id.id in product_ids
        ).mapped("location_id").ids

        older_quants = self.env["stock.quant"].sudo().search([
            ("product_id", "in", product_ids),
            ("location_id", "child_of", source_loc_ids),
            ("lot_id", "!=", False),
            ("lot_id", "not in", exclude_ids),
            ("quantity", ">", 0),
            ("lot_id.create_date", "<", oldest_day_start),
        ])

        return older_quants.mapped("lot_id").sorted("create_date")

    # ------------------------------------------------------------------
    # Skanerlash
    # ------------------------------------------------------------------
    def action_open_qr_scan(self):
        """"Skanerlanganlar" tugmasi — nimalar skanerlanganini ko'rsatadi.

        Skanerlashning O'ZI bu oynada emas: transfer sahifasi skanerni doim
        tinglaydi (`static/src/js/picking_qr_scan.js`). Oyna hisobot vazifasini
        bajaradi va skaner ishlamaganda kodni qo'lda kiritish imkonini beradi.
        """
        self.ensure_one()
        if not self.qr_scan_required:
            raise UserError(_(
                "Bu transferda serial raqam bilan kuzatiladigan mahsulot yo'q."))
        return {
            "type": "ir.actions.act_window",
            "name": _("Skanerlanganlar"),
            "res_model": "agronova.picking.qr.scan",
            "view_mode": "form",
            "target": "new",
            "context": {"default_picking_id": self.id},
        }

    def register_scanned_code(self, code):
        """Skanerlangan kodni transferga qo'shadi.

        :return: dict — `status`, `message`, `added` (qo'shilgan dona),
                 `scanned`/`demand` (umumiy holat).

        `status` qiymatlari:
          * `ok`         — qo'shildi
          * `duplicate`  — allaqachon skanerlangan
          * `unknown`    — bunday serial/quti topilmadi
          * `wrong`      — bu transferdagi mahsulotga tegishli emas
          * `excess`     — so'ralgan miqdordan oshib ketadi
          * `fifo_block` — omborda eski serial bor, FIFO buziladi
        """
        self.ensure_one()
        code = (code or "").strip()
        if not code:
            return self._scan_result("unknown", _("Kod bo'sh."))

        # Avval quti kodimi deb tekshiramiz — bitta skan bilan ko'p dona
        box = self.env["agronova.lot.box"].resolve_scan(code)
        if box:
            return self._register_lots(box.lot_ids, box=box)

        lot = self.env["stock.lot"].sudo().search([("name", "=", code)], limit=1)
        if not lot:
            return self._scan_result(
                "unknown", _("Bunday serial raqam yoki quti topilmadi: %s") % code)
        return self._register_lots(lot)

    def _register_lots(self, lots, box=None):
        """Lotlarni mos harakatlarga biriktiradi.

        :param box: quti QR skanerlangan bo'lsa — o'sha quti. Qatorlarga
                    yoziladi, shunda "Qutilar" tabida qaysi quti qachon
                    skanerlangani ko'rinadi.
        """
        self.ensure_one()
        moves = self._serial_moves()
        if not moves:
            return self._scan_result(
                "wrong", _("Bu transferda serial mahsulot yo'q."))

        # ── FIFO tekshiruvi ──
        fifo_older = self._check_fifo_order(lots, moves)
        if fifo_older:
            oldest_5 = fifo_older[:5]
            lines = [
                "%s  (%s)" % (
                    lot.name,
                    lot.create_date.strftime("%d.%m.%Y")
                    if lot.create_date else "?",
                )
                for lot in oldest_5
            ]
            msg = _(
                "FIFO: omborda eski seriallar bor — avval ularni chiqaring:\n%s"
            ) % "\n".join(lines)
            if len(fifo_older) > 5:
                msg += "\n" + _("... va yana %d ta") % (len(fifo_older) - 5)
            return self._scan_result("fifo_block", msg)

        added = 0
        skipped_dup = 0
        skipped_wrong = 0
        skipped_excess = 0

        for lot in lots:
            move = moves.filtered(lambda m: m.product_id == lot.product_id)[:1]
            if not move:
                skipped_wrong += 1
                continue

            # Takror skanerlash — bu lot allaqachon SKANERLANGANMI.
            # Rezerv qilingan (`qr_scanned` = False) qator takror hisoblanmaydi:
            # uni omborchi hali skanerlamagan, skanerlashga yo'l ochiq bo'lishi kerak.
            if move.move_line_ids.filtered(lambda ml: ml.lot_id == lot and ml.qr_scanned):
                skipped_dup += 1
                continue

            # So'ralgan miqdordan oshmasin — faqat skanerlanganlar sanaladi,
            # aks holda rezerv qilingan qatorlar limitni oldindan to'ldirib
            # qo'yardi va skanerlash "ortiqcha" deb rad etilardi.
            current = sum(
                ml.quantity for ml in move.move_line_ids if ml.lot_id and ml.qr_scanned
            )
            if current >= move.product_uom_qty:
                skipped_excess += 1
                continue

            # Rezervatsiya shu lotni allaqachon biriktirgan bo'lishi mumkin —
            # yangi qator yaratish o'rniga o'shani skanerlangan deb belgilaymiz,
            # aks holda miqdor ikki baravar bo'lib ketardi.
            reserved = move.move_line_ids.filtered(
                lambda ml: ml.lot_id == lot and not ml.qr_scanned)[:1]
            scan_vals = {
                "quantity": 1.0,
                "picked": True,
                "qr_scanned": True,
                "qr_box_id": box.id if box else False,
            }
            if reserved:
                reserved.write(scan_vals)
            else:
                vals = move._prepare_qr_scan_line_vals(lot)
                vals.update(scan_vals)
                new_line = self.env["stock.move.line"].create(vals)
                # `quantity`/`picked` compute maydonlar — create paytida compute
                # ularni qayta hisoblab yuborishi mumkin, shuning uchun aniq yozamiz.
                new_line.write(scan_vals)
            added += 1

        if added:
            parts = [_("%d dona qo'shildi") % added]
            if box:
                parts.insert(0, _("Quti %s") % box.name)
            if skipped_dup:
                parts.append(_("%d ta takror") % skipped_dup)
            if skipped_excess:
                parts.append(_("%d ta ortiqcha") % skipped_excess)
            if skipped_wrong:
                parts.append(_("%d ta mos emas") % skipped_wrong)
            return self._scan_result("ok", " — ".join(parts), added=added)

        if skipped_dup:
            return self._scan_result("duplicate", _("Allaqachon skanerlangan."))
        if skipped_excess:
            return self._scan_result(
                "excess", _("So'ralgan miqdor to'ldi — ortiqcha qo'shib bo'lmaydi."))
        return self._scan_result(
            "wrong", _("Bu mahsulot ushbu transferga tegishli emas."))

    def _scan_result(self, status, message, added=0):
        scanned, demand = self._qr_scan_progress()
        return {
            "status": status,
            "message": message,
            "added": added,
            "scanned": int(scanned),
            "demand": int(demand),
            "done": scanned >= demand,
        }

    # ------------------------------------------------------------------
    # Validate bloklash
    # ------------------------------------------------------------------
    def button_validate(self):
        for picking in self:
            if not picking.qr_scan_required or picking.qr_scan_bypassed:
                continue
            if self.env.context.get("qr_scan_bypass"):
                continue
            scanned, demand = picking._qr_scan_progress()
            if scanned < demand:
                raise UserError(_(
                    "Serial raqamli mahsulotlar to'liq skanerlanmagan: "
                    "%(done)s / %(total)s.\n\n"
                    "\"Skanerlashni boshlash\" tugmasi orqali QR kodlarni "
                    "skanerlang. Quti QR kodi bir vaqtda ichidagi barcha "
                    "mahsulotlarni qo'shadi.",
                    done=int(scanned), total=int(demand),
                ))
            picking._drop_unscanned_reservations()
        return super().button_validate()

    def _drop_unscanned_reservations(self):
        """Skanerlangan, lekin tasdiqlanmagan rezerv qatorlarini olib tashlaydi.

        Rezervatsiya omborda mavjud seriyalarni o'zi biriktiradi. Omborchi
        boshqa seriyalarni skanerlagan bo'lsa, rezerv qatorlar ham qolib ketadi
        va transfer so'ralganidan ko'p tovar jo'natardi (10 ta skanerlandi +
        4 ta rezerv = 14 dona). Skanerlash yakunlangach ular keraksiz.

        DIQQAT: `qr_scan_required == False` bo'lgan seriyalar olib tashlanmaydi —
        ular skanersiz o'tishi kerak bo'lgan seriyalardir.
        """
        self.ensure_one()
        stale = self._serial_moves().move_line_ids.filtered(
            lambda ml: not ml.qr_scanned and (not ml.lot_id or ml.lot_id.qr_scan_required)
        )
        if stale:
            stale.unlink()

    def action_bypass_qr_scan(self):
        """Menejer uchun chetlab o'tish (eski lotlar / yirtilgan stiker)."""
        self.ensure_one()
        if not self.env.user.has_group("stock.group_stock_manager"):
            raise UserError(_(
                "Skanerlashni faqat ombor menejeri chetlab o'ta oladi."))
        return {
            "type": "ir.actions.act_window",
            "name": _("Skanerlashni chetlab o'tish"),
            "res_model": "agronova.picking.qr.bypass",
            "view_mode": "form",
            "target": "new",
            "context": {"default_picking_id": self.id},
        }


class StockMove(models.Model):
    _inherit = "stock.move"

    @api.depends("product_id", "picking_id.qr_scan_required",
                 "picking_id.qr_scan_bypassed")
    def _compute_is_quantity_done_editable(self):
        """Serial mahsulotda sonni QO'LDA yozib bo'lmaydi — faqat skanerlash.

        Ikkita istisno qo'lda kiritishni qaytaradi:
          • menejer chetlab o'tgan (`qr_scan_bypassed`) — eski lotlar yoki
            yirtilgan stiker uchun yagona yo'l;
          • operatsiya turi ozod qilingan (`qr_scan_required` = False) —
            agentning mijozga yetkazishi.

        `qr_scan_required` ga tayanamiz, `product_id.tracking` ni qayta
        tekshirmaymiz: u allaqachon serial mahsulot bor-yo'qligini ham,
        istisnoni ham hisobga olgan.
        """
        super()._compute_is_quantity_done_editable()
        for move in self:
            if (move.product_id.tracking == "serial"
                    and move.picking_id
                    and move.picking_id.qr_scan_required
                    and not move.picking_id.qr_scan_bypassed):
                move.is_quantity_done_editable = False

    def _set_quantity(self):
        """Skanerlangan qatorlarni eskirgan forma qiymati o'chirib yubormasin.

        `quantity` — `store=True` + `inverse="_set_quantity"` maydon. Skanerlash
        oynasi `move_line` larni to'g'ridan-to'g'ri bazaga yozadi, orqada turgan
        transfer formasi esa hali ESKI `quantity` ni (masalan 0) ushlab turadi.
        Forma saqlanganda Odoo o'sha eski qiymatni qaytib yozadi va bu yerdagi
        `_process_decrease` skanerlangan qatorlarni kamaytiradi yoki `unlink`
        qiladi — omborchi uchun "miqdor o'zgarib qoldi" bo'lib ko'rinadi.

        Serial mahsulotda son FAQAT skanerlash orqali kiritiladi (shu sabab
        `is_quantity_done_editable` ham False). Demak bu yerda qo'lda kelgan
        qiymatni qabul qilishning ma'nosi yo'q: skanerlangan qatorlar
        yig'indisi yagona haqiqat. Ularni chetlab o'tamiz.
        """
        protected = self.filtered(
            lambda m: m.product_id.tracking == "serial"
            and m.picking_id.qr_scan_required
            and not m.picking_id.qr_scan_bypassed
            and m.move_line_ids.filtered("qr_scanned")
        )
        if protected:
            # Bazadagi haqiqiy yig'indini tiklaymiz — forma yuborgan eski
            # qiymat e'tiborga olinmaydi.
            protected.invalidate_recordset(["quantity"])
        rest = self - protected
        if rest:
            return super(StockMove, rest)._set_quantity()

    def _prepare_qr_scan_line_vals(self, lot):
        """Skanerlangan serial uchun move line qiymatlari.

        Serial tracking — har lot aynan 1 dona.
        """
        self.ensure_one()
        return {
            "move_id": self.id,
            "picking_id": self.picking_id.id,
            "product_id": self.product_id.id,
            "product_uom_id": self.product_uom.id,
            "location_id": self.location_id.id,
            "location_dest_id": self.location_dest_id.id,
            "lot_id": lot.id,
            "quantity": 1.0,
            "picked": True,
            "qr_scanned": True,
            "company_id": self.company_id.id,
        }
