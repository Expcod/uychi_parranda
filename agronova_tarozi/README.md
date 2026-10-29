# AgroNova — Tarozi (`agronova_tarozi`)

Avtomobil, platforma va qadoqlash tarozilarini Odoo'ga ulaydi. Yem zavodi, so'yish
va boshqa bo'limlar shu moduldan foydalanadi.

## Qanday ishlaydi

1. **Agent** tarozi indikatoridan (RS-232 / RS-485 / TCP) vaznni o'qiydi va
   `POST /agronova/tarozi/vazn` ga yuboradi:

   ```json
   {"jsonrpc": "2.0", "params": {"kod": "AVTO-1", "kalit": "<agent kaliti>", "vazn": 42320, "barqaror": true}}
   ```

   Kalit tarozi kartasida (faqat administrator ko'radi). Odoo protokolni bilmaydi —
   boshqa ishlab chiqaruvchining tarozisi uchun faqat agent o'zgaradi.
2. **Tortish varaqasi** ikki marta tortish tamoyilida: «1-tortish» va «2-tortish»
   tugmalari tarozining oxirgi **barqaror** va **2 daqiqadan yangi** ko'rsatkichini oladi.
   `Netto = Brutto − Tara` (brutto — kattasi, yo'nalishdan qat'i nazar).
3. **Qo'lda o'zgartirish** — faqat «Tarozi — vaznni tuzatish» huquqi bilan; eski va
   yangi qiymat chatterga yoziladi.
4. **Tafovut** — hujjatdagi netto bilan farq. Daraja: me'yorda · ogohlantirish ·
   tasdiq kerak · kritik (Sozlamalar → Ombor → Tarozi tafovutlari). «Tasdiq kerak» va
   «kritik» da varaqa mas'ul sabab yozib tasdiqlamaguncha yopilmaydi.
5. **Ombor hujjati** — kirim hujjatidan «Tarozida tortish»; yakunlanganda kirim
   miqdori haqiqiy nettoga moslanadi. Chiqimda hujjatdagi miqdor qoladi — farq
   avtomatik yo'qotish deb yozilmaydi.

Agentsiz sinov: tarozi kartasida «Sinov ko'rsatkichi» (administrator uchun).
