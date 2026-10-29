"""Mahsulotga ichki EAN-13 barcode yaratish.

Chiziqli kod stikeri mahsulot barcode'idan chiqishi mumkin (kassa va sotuv
uchun bir xil mahsulotda kod bir xil bo'lsin degan talab). Lekin Odoo'da
barcode'ni avtomatik yaratadigan mexanizm yo'q — omborchi har bir mahsulotga
qo'lda o'ylab kod yozishi kerak bo'lardi, bu esa takrorlanuvchi kodlarga olib
keladi.

Shuning uchun ro'yxatdan mahsulotlarni belgilab "EAN-13 barcode yaratish"
amalini bajarish mumkin. Kod `200` prefiksi bilan boshlanadi — bu GS1 da
ICHKI foydalanish uchun ajratilgan diapazon, ya'ni bunday kod hech qachon
boshqa korxonaning haqiqiy mahsulot kodi bilan to'qnashmaydi.
"""
from odoo import _, models
from odoo.exceptions import UserError

# GS1 da ichki (do'kon/korxona ichidagi) kodlar uchun ajratilgan prefiks.
INTERNAL_PREFIX = "200"


def ean13_check_digit(twelve):
    """EAN-13 ning 13-chi (tekshiruv) raqami.

    Qoida: toq o'rindagi raqamlar 1 ga, juft o'rindagilar 3 ga ko'paytiriladi,
    yig'indi keyingi o'nlikkacha to'ldiriladi.
    """
    total = sum(int(ch) * (3 if i % 2 else 1) for i, ch in enumerate(twelve))
    return str((10 - total % 10) % 10)


class ProductTemplate(models.Model):
    _inherit = "product.template"

    def action_generate_ean13(self):
        """Belgilangan mahsulotlarga ichki EAN-13 kod beradi.

        Barcode'i bor mahsulotlar chetlab o'tiladi — mavjud kodni almashtirish
        skanerlangan eski stikerlarni ishlamay qo'yardi.
        """
        created = 0
        for template in self:
            if template.barcode:
                continue
            base = "%s%09d" % (INTERNAL_PREFIX, template.id)
            barcode = base + ean13_check_digit(base)
            if self.search_count([("barcode", "=", barcode)], limit=1):
                raise UserError(_(
                    "«%s» uchun kod (%s) bandligi aniqlandi. "
                    "Administratorga murojaat qiling."
                ) % (template.display_name, barcode))
            template.barcode = barcode
            created += 1

        message = (_("%d ta mahsulotga barcode berildi.") % created if created
                   else _("Barcha tanlangan mahsulotlarda barcode allaqachon bor."))
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "message": message,
                "type": "success" if created else "warning",
                "sticky": False,
            },
        }
