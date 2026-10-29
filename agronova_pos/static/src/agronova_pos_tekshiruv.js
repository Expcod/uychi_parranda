import { patch } from "@web/core/utils/patch";
import { _t } from "@web/core/l10n/translation";
import { AlertDialog } from "@web/core/confirmation_dialog/confirmation_dialog";
import { PaymentScreen } from "@point_of_sale/app/screens/payment_screen/payment_screen";

/**
 * TZ M08 qoidalarini to'lovdan OLDIN tekshirish.
 *
 * Tekshiruvning o'zi serverda: tannarx brauzerga yuklanmaydi, chunki
 * TZ M13 uni maydon darajasida yopishni talab qiladi — kassir tannarxni
 * ko'rmasligi kerak. Shu sababli bu yerda faqat bitta so'rov yuboriladi
 * va javob matni ko'rsatiladi.
 *
 * Aloqa uzilgan bo'lsa tekshiruv o'tkazib yuboriladi va sotuv davom
 * etadi — POS oflayn ishlashi kerak. Qoida baribir buzilmaydi: buyurtma
 * serverga sinxronlanganda `_process_order` uni ushlaydi.
 */
patch(PaymentScreen.prototype, {
    /** Qarzga («keyin to'lash») to'lanayotgan summa. */
    agronovaQarzSummasi() {
        return this.currentOrder.payment_ids
            .filter((p) => p.payment_method_id?.type === "pay_later")
            .reduce((jami, p) => jami + (p.getAmount?.() ?? p.amount ?? 0), 0);
    },

    agronovaQatorlar() {
        return this.currentOrder
            .getOrderlines()
            .filter((l) => l.product_id)
            .map((l) => ({
                product_id: l.product_id.id,
                price_unit: l.price_unit,
                discount: l.discount || 0,
                qty: l.qty,
            }));
    },

    async agronovaTekshir() {
        const order = this.currentOrder;
        try {
            return await this.pos.data.call("pos.order", "agronova_tekshir", [
                this.pos.config.id,
                this.agronovaQatorlar(),
                order.partner_id ? order.partner_id.id : false,
                this.agronovaQarzSummasi(),
            ]);
        } catch {
            // Oflayn yoki server javob bermadi — sotuvni to'xtatmaymiz.
            return "";
        }
    },

    async validateOrder(isForceValidate = false) {
        const xato = await this.agronovaTekshir();
        if (xato) {
            this.dialog.add(AlertDialog, {
                title: _t("Sotuvga ruxsat yo'q"),
                body: xato,
            });
            return;
        }
        return await super.validateOrder(isForceValidate);
    },
});
