# -*- coding: utf-8 -*-
"""
Hikvision Cron Jobs Mixin

Bu mixin rejalashtirilgan vazifalar (cron jobs) uchun
metodlarni o'z ichiga oladi.
"""

import logging
import pytz
from datetime import datetime

from odoo import models, api, fields
from .hikvision_logger import log_cron, log_error

DEFAULT_TIMEZONE = 'Asia/Tashkent'

_logger = logging.getLogger(__name__)


class HikvisionCronMixin(models.AbstractModel):
    """Hikvision cron job metodlari uchun mixin"""
    
    _name = 'hikvision.cron.mixin'
    _description = 'Hikvision Cron Mixin'

    @api.model
    def _cron_fetch_logs(self):
        """
        Barcha qurilmalardan loglarni olish va birga qayta ishlash.
        
        MUHIM: Barcha qurilmalardan loglarni AVVAL yig'ib, 
        keyin VAQT bo'yicha tartiblash va qayta ishlash.
        Bu bir kunda bir necha kirish-chiqish bo'lganda 
        to'g'ri ishlashni ta'minlaydi.
        """
        devices = self.search([('state', '=', 'confirmed')])

        if not devices:
            _logger.info("Cron: Tasdiqlangan qurilmalar topilmadi")
            return

        device_names = ', '.join(devices.mapped('name'))
        log_cron('Fetch Logs', f"Boshlandi: {len(devices)} ta qurilma ({device_names})")

        all_logs = []          # Barcha qurilmalardan barcha loglar
        fetch_marks = {}       # {device_id: fetch boshlangan vaqt (UTC, naive)}

        # 1-BOSQICH: Barcha qurilmalardan loglarni yig'ish
        for device in devices:
            # Fetch BOSHLANGAN vaqtni eslab qolamiz. last_fetch_time faqat
            # loglar muvaffaqiyatli qayta ishlangandan keyin shu qiymatga
            # o'rnatiladi - aks holda xato bo'lsa loglar abadiy yo'qoladi.
            fetch_started = datetime.now(pytz.UTC).replace(tzinfo=None)
            try:
                _logger.info(f"Cron: Collecting logs from {device.name}")
                logs, device_attendance_type = device._fetch_all_logs_raw()

                # Har bir logga qurilma ma'lumotlarini qo'shish
                for log in logs:
                    log['_device_id'] = device.id
                    log['_device_name'] = device.name
                    log['_attendance_type'] = device_attendance_type

                all_logs.extend(logs)
                fetch_marks[device.id] = fetch_started

                if logs:
                    log_cron('Fetch Logs', f"{device.name}: {len(logs)} ta log topildi")
                else:
                    log_cron('Fetch Logs', f"{device.name}: log yo'q")

            except Exception as e:
                # Bu qurilma uchun last_fetch_time YANGILANMAYDI -
                # keyingi cronda o'sha oynadan qayta so'raladi.
                _logger.error(f"Cron: {device.name} dan log olishda xato: {str(e)}")
                log_error(f"[CRON: Fetch Logs] {device.name} xatosi: {str(e)}")

        if not all_logs:
            self._mark_devices_fetched(fetch_marks)
            return

        # 2-BOSQICH: BARCHA loglarni vaqt bo'yicha tartiblash.
        # Bu shart: check-out o'zining check-in'idan keyin qayta
        # ishlanishi kerak, aks holda "ochiq davomat yo'q" deb rad etiladi.
        all_logs_sorted = sorted(all_logs, key=lambda x: x.get('time', ''))
        _logger.info(f"Cron: Jami {len(all_logs_sorted)} ta log vaqt bo'yicha tartiblandi")

        # 3-BOSQICH: Xodimlarni bitta so'rovda oldindan yuklash (N+1 oldini olish)
        barcodes = {
            log.get('employeeNoString')
            for log in all_logs_sorted
            if log.get('employeeNoString')
        }
        employee_map = {}
        if barcodes:
            employees = self.env['hr.employee'].search([('barcode', 'in', list(barcodes))])
            employee_map = {e.barcode: e for e in employees}
            _logger.info(
                f"Cron: {len(barcodes)} ta barcode, {len(employee_map)} ta xodim topildi"
            )

        # Qurilmalarni oldindan xaritaga olamiz - siklda browse() qilmaslik uchun
        devices_by_id = {d.id: d for d in devices}

        # 4-BOSQICH: Tartibda qayta ishlash
        counts = dict.fromkeys(
            ('paired', 'unpaired', 'duplicate', 'skipped', 'error'), 0)

        # Xato bo'lgan qurilmalar - ularning last_fetch_time'i surilmaydi
        failed_devices = set()

        for log in all_logs_sorted:
            device_id = log['_device_id']
            try:
                device = devices_by_id.get(device_id)
                if not device:
                    counts['skipped'] += 1
                    continue

                result = device._process_single_log(
                    log, log['_attendance_type'], employee_map=employee_map
                )
                counts[result] = counts.get(result, 0) + 1

                # DIQQAT: faqat 'error' oynani qaytaradi.
                # 'unpaired' - normal holat: hodisa saqlangan, lekin
                # davomatga bog'lanmagan. Uni qayta so'rashning ma'nosi
                # yo'q - natija o'sha bo'ladi, log esa allaqachon bazada.
                if result == 'error':
                    failed_devices.add(device_id)

            except Exception:
                counts['error'] += 1
                failed_devices.add(device_id)
                _logger.exception("Cron: Log qayta ishlashda xato")

        # 5-BOSQICH: last_fetch_time ni yangilash.
        #
        # Xato bo'lgan qurilma uchun YANGILANMAYDI - aks holda o'sha
        # loglar boshqa hech qachon so'ralmaydi va butunlay yo'qoladi.
        # Keyingi cron o'sha oynadan qayta so'raydi; muvaffaqiyatli
        # yozilganlari dedup constraint tufayli takrorlanmaydi.
        if failed_devices:
            for device_id in failed_devices:
                fetch_marks.pop(device_id, None)
            _logger.warning(
                "Cron: %s ta qurilmada xato bo'ldi, ularning oynasi "
                "keyingi ishga tushirishda qayta so'raladi", len(failed_devices))

        self._mark_devices_fetched(fetch_marks)

        # 6-BOSQICH: xodim holati keshini tiklash.
        #
        # hr_employee.last_attendance_id - compute, store=True maydon.
        # Odatda hr.attendance yaratilganda o'zi qayta hisoblanadi, lekin
        # shu sikl ichida biror savepoint rollback bo'lsa (masalan ikkita
        # jarayon bir logni bir vaqtda yozsa), Odoo "discard all fields to
        # recompute" qiladi va navbatdagi hisoblash yo'qoladi.
        #
        # Natijasi jimgina va chalg'ituvchi: hr_attendance qatori bazada
        # bor, lekin xodim kartochkasi "Absent" ko'rsatadi va HR hisoboti
        # uni kelmagan deb sanaydi.
        #
        # Shu sababli sikl oxirida bugun davomati o'zgargan xodimlar uchun
        # maydonni majburiy qayta hisoblaymiz. Bu arzon amal: bir necha
        # o'nlab xodim, har biriga bitta indeksli search.
        self._refresh_attendance_cache()

        # Yakuniy natija
        result_msg = (
            f"Yakunlandi: Juftlandi={counts['paired']}, "
            f"Juftlanmadi={counts['unpaired']}, Takroriy={counts['duplicate']}, "
            f"Skip={counts['skipped']}, Xato={counts['error']}"
        )
        _logger.info(f"Cron: {result_msg}")
        log_cron('Fetch Logs', result_msg)

    @api.model
    def _refresh_attendance_cache(self, employees=None):
        """
        hr_employee.last_attendance_id ni haqiqiy holatga keltirish.

        Bu maydon compute + store: Odoo uni attendance_ids o'zgarganda
        o'zi hisoblaydi. Lekin hisoblash DARHOL emas, tranzaksiya oxirida
        (flush paytida) bajariladi - ya'ni oradagi har qanday savepoint
        rollback uni navbatdan o'chirib yuborishi mumkin.

        Bu yerda maydonni to'g'ridan-to'g'ri yozmaymiz. modified() bilan
        Odoo'ga "attendance_ids o'zgardi" deb aytamiz va _compute'ni o'zi
        chaqiramiz - shunda last_check_in/last_check_out (related) va
        attendance_state ham zanjir bo'ylab to'g'ri yangilanadi. Qiymatni
        qo'lda yozsak, ular eski holatda qolib ketardi.

        Args:
            employees: tekshiriladigan xodimlar. Berilmasa - bugun
                davomati bo'lganlar (cron uchun odatdagi holat).
        """
        Attendance = self.env['hr.attendance'].sudo()

        if employees is None:
            bugun = fields.Date.context_today(self)
            recent = Attendance.search([('check_in', '>=', bugun)])
            employees = recent.employee_id
        if not employees:
            return 0

        employees = employees.sudo()
        employees.invalidate_recordset(['last_attendance_id'])
        employees.modified(['attendance_ids'])
        employees._compute_last_attendance_id()

        _logger.debug(
            "Cron: %s ta xodimning davomat keshi yangilandi", len(employees))
        return len(employees)

    @api.model
    def _cron_close_stale_attendances(self):
        """
        Kechagi va undan oldingi ochiq davomatlarni yopish.

        NEGA KERAK: core hr.attendance bitta xodimda faqat BITTA ochiq
        davomatga ruxsat beradi. Chiqishni unutgan xodim ertasi kuni
        Face ID dan o'tsa, _process_attendance yangi kirishni rad etadi
        (hikvision_attendance.py: "stale" tekshiruvi). Ya'ni bitta
        unutilgan chiqish keyingi KUNLARNI ham bloklaydi.

        Bu cron kechasi shu tiqilinchni ochadi: ochiq yozuvni yopadi va
        "yopilmagan" deb belgilaydi. Ertalab xodim normal kira oladi.

        DIQQAT - bu OLIB TASHLANGAN "Auto Close Attendance" croni EMAS.
        Farqi:
            eski: check_out = jadval oxiri (hammaga 17:00) -> soxta ish
                  soati; raw SQL -> worked_hours qayta hisoblanmasdi
            bu:   check_out = check_in -> worked_hours tabiiy 0;
                  ORM write() -> barcha compute'lar to'g'ri ishlaydi
        Soxta soat yozilmaydi, shuning uchun eski muammo takrorlanmaydi.

        BUGUNGI ochiq yozuvlarga TEGILMAYDI: xodim hozir ish joyida
        bo'lishi mumkin, uni yopish haqiqiy chiqishni yo'qotardi.

        CORE BILAN TO'QNASHUV YO'Q: Odoo'ning o'z _cron_auto_check_out'i
        res_company.auto_check_out sozlamasiga bog'liq va u default
        False. Agar kimdir uni Sozlamalardan yoqsa, ikkala cron bir xil
        yozuvlarga tegadi - o'sha sozlama o'chirilgan bo'lishi kerak.
        """
        local_tz = pytz.timezone(DEFAULT_TIMEZONE)
        now_local = datetime.now(local_tz)
        # Bugun 00:00 (lokal) -> UTC. Undan oldin boshlangan ochiq
        # yozuvlar "kechagi" hisoblanadi.
        today_start_local = local_tz.localize(datetime.combine(
            now_local.date(), datetime.min.time()))
        today_start_utc = today_start_local.astimezone(pytz.UTC).replace(tzinfo=None)

        stale = self.env['hr.attendance'].search([
            ('check_out', '=', False),
            ('check_in', '<', today_start_utc),
        ])

        if not stale:
            _logger.info("Cron: yopilmagan davomat topilmadi")
            return

        for attendance in stale:
            # Har biri alohida: bittasida validatsiya xatosi bo'lsa
            # qolganlari baribir yopilsin - aks holda bitta buzuq yozuv
            # tufayli hamma xodim ertasi kuni kira olmay qoladi.
            try:
                with self.env.cr.savepoint():
                    attendance.write({
                        'check_out': attendance.check_in,
                        'attendance_status': 'unclosed',
                    })
            except Exception:
                _logger.exception(
                    "Cron: davomat yopilmadi (id=%s, xodim=%s, kirish=%s)",
                    attendance.id, attendance.employee_id.name,
                    attendance.check_in)

        names = ', '.join(stale.mapped('employee_id.name')[:10])
        message = f"{len(stale)} ta ochiq davomat yopildi: {names}"
        if len(stale) > 10:
            message += f" va yana {len(stale) - 10} ta"
        _logger.info(f"Cron: {message}")
        log_cron('Close Stale Attendances', message)

    def _mark_devices_fetched(self, fetch_marks):
        """last_fetch_time ni fetch BOSHLANGAN vaqtga o'rnatish."""
        for device_id, mark in fetch_marks.items():
            device = self.browse(device_id)
            if device.exists():
                device.last_fetch_time = mark

    # OLIB TASHLANDI: _cron_send_logs_to_telegram va _cron_cleanup_logs
    #
    # Modul endi o'z log faylini yozmaydi (Odoo standart logging'i
    # ishlatiladi), shuning uchun na Telegram ga yuborish, na haftalik
    # fayl tozalash kerak emas.
