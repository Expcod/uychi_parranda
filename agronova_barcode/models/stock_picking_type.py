"""Operatsiya turi darajasida majburiy skanerlashni o'chirish.

Majburiy QR skanerlash ombordan tayyor mahsulot chiqarilayotganda kerak —
omborchi sonni qo'lda yozsa xato ketadi. Lekin sotuv agentining o'z omborida
bu talab ortiqcha:

  • agent tovarni filialdan qabul qilganda allaqachon skanerlagan
    (kiruvchi transferda skanerlash SAQLANADI — nazorat nuqtasi o'sha yerda);
  • mijozga sotish esa ko'chada, telefonda, `agent_sales_app` orqali bo'ladi —
    u yerda skaner ham, stiker ham yo'q.

Shuning uchun istisno OPERATSIYA TURI darajasida beriladi: har omborning o'z
"Yetkazib berish" turi bor, ya'ni granularlik aynan kerakligicha — agentning
mijozga chiqishi ozod bo'ladi, o'sha agentning kiruvchi transferi esa yo'q.
Foydalanuvchi/guruh bo'yicha qilib bo'lmasdi: `agent_sales_app` yetkazishni
`sudo()` bilan tasdiqlaydi, ya'ni huquq konteksti yo'qoladi.
"""
from odoo import fields, models


class StockPickingType(models.Model):
    _inherit = "stock.picking.type"

    qr_scan_exempt = fields.Boolean(
        "QR skanerlash shart emas",
        help="Belgilansa, bu operatsiya turidagi transferlarni serial "
             "mahsulotlarni skanerlamasdan tasdiqlash mumkin va sonni qo'lda "
             "kiritsa bo'ladi. Sotuv agentlarining mijozga yetkazib berish "
             "turlari uchun mo'ljallangan.",
    )
