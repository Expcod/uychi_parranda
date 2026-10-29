# -*- coding: utf-8 -*-
"""POS buyurtmasi: TZ M08 qoidalari va FEFO lot biriktirish.

Ikkita qoida shu yerda tekshiriladi:

* **tannarxdan past sotuv taqiqi** — chegirma tannarxdan pastga tushsa
  buyurtma qabul qilinmaydi;
* **kredit limiti** — «keyin to'lash» usulida mijozning jami qarzi
  kartochkasidagi limitdan oshsa sotuv bloklanadi.

Tekshiruv **serverda** turadi. Tannarxni brauzerga yuklab, JS da
tekshirish tezroq bo'lardi, lekin TZ M13 tannarxni maydon darajasida
yopishni talab qiladi — kassirning brauzeriga tannarx tushmasligi kerak.
Shuning uchun POS to'lovdan oldin serverga bitta so'rov yuboradi
(`agronova_tekshir`), aloqa uzilgan bo'lsa esa buyurtma sinxronlanganda
`_process_order` da baribir ushlanadi.
"""
from odoo import _, api, models
from odoo.exceptions import UserError


class PosOrder(models.Model):
    _inherit = 'pos.order'

    # ------------------------------------------------------------------
    # TEKSHIRUVLAR
    # ------------------------------------------------------------------

    @api.model
    def _agronova_tannarx_xatolari(self, config, qatorlar):
        """Tannarxdan past sotilayotgan qatorlar ro'yxati.

        `qatorlar` — `[{'product_id': int, 'price_unit': float,
        'discount': float, 'qty': float}, ...]` ko'rinishida.
        """
        if not config.agronova_tannarx_nazorati:
            return []
        Product = self.env['product.product']
        xatolar = []
        for q in qatorlar:
            mahsulot = Product.browse(int(q['product_id']))
            if not mahsulot.exists():
                continue
            tannarx = mahsulot.standard_price
            # Tannarxi kiritilmagan mahsulot tekshirilmaydi — aks holda
            # bazadagi 0 li kartochkalar butun savdoni to'xtatib qo'yardi.
            if not tannarx:
                continue
            if float(q.get('qty') or 0.0) <= 0:
                continue  # qaytarish (refund) tekshirilmaydi
            narx = float(q.get('price_unit') or 0.0)
            chegirma = float(q.get('discount') or 0.0)
            sof = narx * (1.0 - chegirma / 100.0)
            if config.currency_id.compare_amounts(sof, tannarx) < 0:
                xatolar.append({
                    'mahsulot': mahsulot.display_name,
                    'narx': sof,
                    'tannarx': tannarx,
                })
        return xatolar

    @api.model
    def _agronova_kredit_xatosi(self, config, partner, qarz_summa):
        """Kredit limitidan oshgan bo'lsa — xato matni, aks holda False."""
        if not config.agronova_kredit_nazorati or not partner or not qarz_summa:
            return False
        limit = partner.credit_limit
        if not limit:
            return False
        jami = partner.credit + qarz_summa
        if config.currency_id.compare_amounts(jami, limit) <= 0:
            return False
        return _(
            "«%(mijoz)s» ning kredit limiti oshib ketadi.\n"
            "Limit: %(limit)s\nHozirgi qarzi: %(qarz)s\n"
            "Shu sotuvdan keyin: %(jami)s\n\n"
            "Qarzga berish uchun avval eski qarzni yoping yoki bosh "
            "buxgalter limitni oshirsin.",
            mijoz=partner.display_name, limit=limit,
            qarz=partner.credit, jami=jami)

    @api.model
    def agronova_tekshir(self, config_id, qatorlar, partner_id=False,
                      qarz_summa=0.0):
        """POS ekranidan to'lovdan oldin chaqiriladigan tekshiruv.

        Xato matnini qaytaradi (bo'sh bo'lsa — hammasi joyida). Bu yerda
        `UserError` ko'tarilmaydi: POS oflayn bo'lishi mumkin va xato
        oynasi buyurtmani yo'qotib qo'ymasligi kerak — ekranning o'zi
        matnni chiroyli ko'rsatadi.
        """
        config = self.env['pos.config'].browse(int(config_id))
        xatolar = self._agronova_tannarx_xatolari(config, qatorlar or [])
        if xatolar:
            return self._agronova_tannarx_matni(xatolar)
        partner = self.env['res.partner'].browse(int(partner_id)) \
            if partner_id else self.env['res.partner']
        return self._agronova_kredit_xatosi(
            config, partner, float(qarz_summa or 0.0)) or ''

    @api.model
    def _agronova_tannarx_matni(self, xatolar):
        satrlar = [_(
            "Tannarxdan past sotib bo'lmaydi (TZ M08). Quyidagi "
            "qatorlarni tekshiring:")]
        for x in xatolar:
            satrlar.append(_(
                " • %(mahsulot)s — sotuv %(narx)s, tannarx %(tannarx)s",
                mahsulot=x['mahsulot'], narx=round(x['narx'], 2),
                tannarx=round(x['tannarx'], 2)))
        return "\n".join(satrlar)

    # ------------------------------------------------------------------
    # SINXRONLASH
    # ------------------------------------------------------------------

    @api.model
    def _process_order(self, order, existing_order):
        """Buyurtma serverga tushganda oxirgi to'siq.

        Oflayn ishlagan POS xatoni to'lov paytida ko'rsata olmaydi,
        shuning uchun qoida shu yerda ham tekshiriladi. Xato
        ko'tarilganda buyurtma saqlanmaydi va POS uni qayta yuborishga
        urinadi — kassir xabarni ko'radi.
        """
        self._agronova_kirish_tekshiruvi(order)
        return super()._process_order(order, existing_order)

    @api.model
    def _agronova_kirish_tekshiruvi(self, order):
        """Kiruvchi lug'atni TZ M08 qoidalari bo'yicha tekshiradi."""
        if order.get('state') == 'draft':
            return  # hali to'lanmagan qoralama — tekshirish erta
        session = self.env['pos.session'].browse(order.get('session_id'))
        config = session.config_id
        if not config:
            return

        qatorlar = []
        for qator in order.get('lines') or []:
            vals = qator[2] if isinstance(qator, (list, tuple)) and len(qator) == 3 else qator
            if not isinstance(vals, dict) or not vals.get('product_id'):
                continue
            qatorlar.append({
                'product_id': vals['product_id'],
                'price_unit': vals.get('price_unit') or 0.0,
                'discount': vals.get('discount') or 0.0,
                'qty': vals.get('qty') or 0.0,
            })
        xatolar = self._agronova_tannarx_xatolari(config, qatorlar)
        if xatolar:
            raise UserError(self._agronova_tannarx_matni(xatolar))

        partner = self.env['res.partner'].browse(order['partner_id']) \
            if order.get('partner_id') else self.env['res.partner']
        qarz = 0.0
        for tolov in order.get('payment_ids') or []:
            vals = tolov[2] if isinstance(tolov, (list, tuple)) and len(tolov) == 3 else tolov
            if not isinstance(vals, dict):
                continue
            usul = self.env['pos.payment.method'].browse(
                vals.get('payment_method_id'))
            if usul.type == 'pay_later':
                qarz += float(vals.get('amount') or 0.0)
        xato = self._agronova_kredit_xatosi(config, partner, qarz)
        if xato:
            raise UserError(xato)

    # ------------------------------------------------------------------
    # OMBOR
    # ------------------------------------------------------------------

    def _create_order_picking(self):
        """Ombor hujjatidan keyin lotni FEFO bo'yicha to'ldiradi.

        Standart Odoo lotsiz tracked mahsulotda hujjatni jimgina ochiq
        qoldiradi (xato `try/except` da yutiladi), ya'ni tovar hisobdan
        chiqmaydi. `stock_picking.py` dagi izohga qarang.
        """
        res = super()._create_order_picking()
        for order in self:
            if not order.config_id.agronova_fefo:
                continue
            ochiq = order.picking_ids.filtered(
                lambda p: p.state not in ('done', 'cancel'))
            if ochiq:
                ochiq.sudo()._agronova_fefo_lot_biriktirish()
        return res
