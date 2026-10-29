# Hikvision Face ID Integration (Odoo)

## Qisqa mazmun
Bu addon Hikvision qurilmadan kelgan hodisalarni `hr.attendance` ga yozadi va xodim ma'lumotlarini qurilma bilan sinxronlaydi.

## Asosiy oqim
1. `hikvision.device` yozuvi yaratiladi va `action_test_connection` bilan ulanish tekshiriladi.
2. Loglar 2 usulda keladi:
   - Cron (`_cron_fetch_logs`) orqali polling.
   - Webhook (`/hikvision/webhook`) orqali real-time.
3. Har bir logdan xodim `barcode` bo'yicha topiladi.
4. Log `check_in` yoki `check_out` ga map qilinadi.
5. `hr.attendance` yozuvi yaratiladi yoki ochiq yozuv `check_out` bilan yopiladi.
6. Xodim create/write/unlink bo'lganda qurilmaga user/face auto-sync qilinadi (agar `auto_sync_enabled` yoqilgan bo'lsa).

## Attendance bilan bog'lanish
- Asosiy yozuv metodi: `models/hikvision_attendance.py::_process_attendance`
- Log deduplikatsiya: `hikvision.log` modeli orqali (`device_id + employee_id + timestamp`)
- `check_in/check_out` aniqlash:
  - Avval device nomi (`check in/check out`, `kirish/chiqish`)
  - Keyin log label
  - So'ng fallback: xodimning oxirgi attendance holatidan avtomatik aniqlash

## Muhim tugmalar
- `Ulanishni Tekshirish`
- `Webhook Sozlash`
- `Loglarni Olish`
- `Xodimlarni Yuklash`
- `Ta'tillarni Sinxronlash`

## Muhit talablar
`requests`, `pytz`, `PIL` (Pillow)

## Telegram loglar (ixtiyoriy)
`_cron_send_logs_to_telegram` ishlashi uchun quyidagi env variable'larni berish kerak:
- `HIKVISION_TELEGRAM_BOT_TOKEN`
- `HIKVISION_TELEGRAM_CHAT_ID`

## Eslatma
Qurilmadagi `employeeNo` va Odoo'dagi `hr.employee.barcode` bir xil bo'lishi shart.
