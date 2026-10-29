# -*- coding: utf-8 -*-
"""POS sotuvida lotni FEFO bo'yicha avtomat biriktirish.

**Muammo.** Go'sht mahsulotlari lot va yaroqlilik muddati bilan
yuritiladi (TZ M06), lekin kassir har tarozi urishida lot raqamini terib
o'tira olmaydi — do'konda navbat turadi.

Odooning bunday holatdagi xatti-harakati xavfli: POS ombor hujjatini
yaratadi, `_action_done()` esa «You need to supply a Lot/Serial Number»
bilan yiqiladi va bu xato `point_of_sale/models/stock_picking.py` dagi
`try/except (UserError, ValidationError): pass` blokida **jimgina
yutiladi**. Natijada pul olindi, chek chiqdi, tovar esa ombordan
hisobdan chiqmadi — qoldiq asta-sekin haqiqatdan uzoqlashadi va buni
hech kim sezmaydi.

**Yechim.** Sotuvdan keyin lot avtomat biriktiriladi: muddati eng oldin
tugaydigan partiya birinchi ketadi (FEFO — TZ M01 talabi). Zaxira
yetmasa, qolgan miqdor eng erta lotga yoziladi va hujjatga izoh
qoldiriladi — do'konda tarozi farqi tufayli qoldiq manfiyga tushishi
odatiy hol, lekin u ko'rinmay qolmasligi kerak.
"""
import logging

from odoo import _, models

_logger = logging.getLogger(__name__)


class StockPicking(models.Model):
    _inherit = 'stock.picking'

    def _agronova_fefo_lot_biriktirish(self):
        """Lotsiz qolgan qatorlarga FEFO bo'yicha lot qo'yadi."""
        for picking in self:
            if picking.state in ('done', 'cancel'):
                continue
            ozgardi = False
            for move in picking.move_ids:
                if move.product_id.tracking == 'none':
                    continue
                if move._agronova_fefo_toldirish():
                    ozgardi = True
            if not ozgardi:
                continue
            try:
                with picking.env.cr.savepoint():
                    picking._action_done()
            except Exception as e:  # noqa: BLE001 — chek allaqachon chiqqan
                # Bu yerda ko'tarilgan xato kassirga chiqmaydi (sotuv
                # tugagan), lekin jimgina yo'qolmasligi ham kerak.
                _logger.warning(
                    "POS ombor hujjatini yopib bo'lmadi (%s): %s",
                    picking.name, e)
                picking.message_post(body=_(
                    "⚠ Ombor hujjati avtomat yopilmadi: %s\n"
                    "Omborchi qo'lda yakunlashi kerak — aks holda tovar "
                    "hisobdan chiqmay qoladi.", e))
        return True


class StockMove(models.Model):
    _inherit = 'stock.move'

    def _agronova_fefo_lot_navbati(self):
        """Manba lokatsiyadagi partiyalar — FEFO tartibida.

        Tartib: muddati oldin tugaydigani birinchi; muddati ko'rsatilmagan
        lotlar oxirida, ular orasida esa omborga oldin kelgani birinchi
        (FIFO) — bu Odooning o'z FEFO qoidasi bilan bir xil mantiq.
        """
        self.ensure_one()
        quants = self.env['stock.quant'].sudo().search([
            ('product_id', '=', self.product_id.id),
            ('location_id', 'child_of', self.location_id.id),
            ('lot_id', '!=', False),
            ('quantity', '>', 0),
        ])
        return quants.sorted(key=lambda q: (
            q.lot_id.removal_date or q.lot_id.expiration_date or False,
            q.in_date or False,
            q.id,
        ))

    def _agronova_fefo_toldirish(self):
        """Lotsiz qatorlarni FEFO lotlari bilan almashtiradi.

        Qaytaradi: biror narsa o'zgargan bo'lsa True.
        """
        self.ensure_one()
        if self.product_id.tracking == 'none':
            return False
        lotli = sum(self.move_line_ids.filtered('lot_id').mapped('quantity'))
        kerak = self.product_uom_qty - lotli
        if self.product_id.uom_id.compare(kerak, 0) <= 0:
            return False

        # Lotsiz qatorlar o'rniga lotli qatorlar quriladi.
        self.move_line_ids.filtered(lambda ml: not ml.lot_id).unlink()
        navbat = self._agronova_fefo_lot_navbati()
        if not navbat:
            self.picking_id.message_post(body=_(
                "«%s» uchun omborda lotli qoldiq topilmadi — FEFO "
                "biriktirilmadi.", self.product_id.display_name))
            return False

        Satr = self.env['stock.move.line'].sudo()
        qoldi = kerak
        oxirgi = None
        for quant in navbat:
            if self.product_id.uom_id.compare(qoldi, 0) <= 0:
                break
            mavjud = quant.quantity - quant.reserved_quantity
            if self.product_id.uom_id.compare(mavjud, 0) <= 0:
                continue
            olinadi = min(mavjud, qoldi)
            Satr.create(self._agronova_satr_vals(quant.lot_id, olinadi))
            qoldi -= olinadi
            oxirgi = quant.lot_id

        if self.product_id.uom_id.compare(qoldi, 0) > 0:
            # Zaxira yetmadi. Do'konda tarozi farqi tufayli bu odatiy hol,
            # shuning uchun sotuvni to'xtatmaymiz — qolganini eng erta
            # lotga yozamiz va hujjatga ogohlantirish qoldiramiz.
            lot = oxirgi or navbat[0].lot_id
            Satr.create(self._agronova_satr_vals(lot, qoldi))
            self.picking_id.message_post(body=_(
                "⚠ «%(mahsulot)s»: omborda %(kam)s %(birlik)s yetmadi, "
                "qolgan miqdor «%(lot)s» partiyasiga yozildi — qoldiq "
                "manfiyga tushishi mumkin. Inventarizatsiya qiling.",
                mahsulot=self.product_id.display_name,
                kam=round(qoldi, 3), birlik=self.product_id.uom_id.name,
                lot=lot.name))
        self.picked = True
        return True

    def _agronova_satr_vals(self, lot, miqdor):
        """FEFO bo'yicha yaratiladigan ombor qatorining qiymatlari."""
        self.ensure_one()
        return {
            'move_id': self.id,
            'picking_id': self.picking_id.id,
            'product_id': self.product_id.id,
            'product_uom_id': self.product_id.uom_id.id,
            'location_id': self.location_id.id,
            'location_dest_id': self.location_dest_id.id,
            'lot_id': lot.id,
            'quantity': miqdor,
            'company_id': self.company_id.id,
        }
