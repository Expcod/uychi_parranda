# -*- coding: utf-8 -*-
"""
Hikvision Attendance Mixin

Bu mixin davomat loglarini olish va qayta ishlash
uchun metodlarni o'z ichiga oladi.
"""

import json
import logging
import pytz
from datetime import datetime, timedelta

from psycopg2 import IntegrityError

from odoo import models

# Konstantalar
DEFAULT_TIMEZONE = 'Asia/Tashkent'
DEFAULT_PAGE_SIZE = 30
HIKVISION_MAJOR_ACCESS_CONTROL = 5
HIKVISION_MINOR_ALL = 0

# Qurilmadan kelgan minor kodlari (DS-K1T671MF da amalda tekshirilgan).
# Faqat MUVAFFAQIYATLI shaxs autentifikatsiyasi davomat hisoblanadi.
#   75  - yuz orqali muvaffaqiyatli
#   1   - karta orqali muvaffaqiyatli
#   6   - karta orqali muvaffaqiyatli (Check Out qurilmasi shuni beradi)
#   38  - karta (boshqa tur)
#   113 - barmoq izi
# Qabul qilinmaydi:
#   76      - yuz autentifikatsiyasi MUVAFFAQIYATSIZ (kuniga 3-8 ta keladi)
#   21, 22  - eshik ochilishi/yopilishi (shaxsga bog'liq emas)
#   9, 104  - boshqa texnik hodisalar
#
# 6 QO'SHILDI (2026-08-17): Check Out qurilmasida xodimlar karta
# o'tkazadi va u minor=6 beradi. Kod uni rad etardi -> all_logs bo'sh
# qaytardi -> lekin last_fetch_time baribir surilardi -> oyna oldinga
# ketib, o'sha kunning yuz loglari (minor=75) ham birga yo'qolardi.
# Natijada 10 kun davomida chiqish umuman yozilmadi.
SUCCESS_AUTH_MINORS = {1, 6, 38, 75, 113}

# Bir so'rovda olinadigan maksimal sahifa (cheksiz tsikldan himoya)
MAX_PAGES_PER_FETCH = 200

# Fetch oynasi last_fetch_time dan shuncha daqiqa ORQAGA suriladi.
#
# Nega 1 daqiqa emas: oyna faqat oldinga suriladi va orqaga qaytmaydi.
# Biror sabab bilan log o'tkazib yuborilsa (qurilma javob bermadi,
# minor kodi tanilmadi, tarmoq uzildi), keyingi cron allaqachon undan
# keyingi oynani so'raydi va o'sha yozuvlar ABADIY yo'qoladi.
# Kengroq ustma-ustlik shu xavfni kamaytiradi; takroriy yozuvlar
# _create_log_record dagi DB constraint bilan kesiladi.
FETCH_OVERLAP_MINUTES = 30

_logger = logging.getLogger(__name__)


class HikvisionAttendanceMixin(models.AbstractModel):
    """Hikvision attendance metodlari uchun mixin"""
    
    _name = 'hikvision.attendance.mixin'
    _description = 'Hikvision Attendance Mixin'

    def _get_local_timezone(self):
        """Lokal timezone ni olish"""
        return pytz.timezone(DEFAULT_TIMEZONE)
    
    def _parse_log_time(self, time_str):
        """Hikvision log vaqtini parse qilish."""
        local_tz = self._get_local_timezone()
        
        if '+' in time_str:
            log_time_local = datetime.fromisoformat(time_str)
        else:
            log_time_local = datetime.strptime(time_str[:19], '%Y-%m-%dT%H:%M:%S')
            log_time_local = local_tz.localize(log_time_local)
        
        return log_time_local.astimezone(pytz.UTC).replace(tzinfo=None)
    
    def _get_device_attendance_type(self):
        """Qurilma nomidan attendance turini aniqlash."""
        device_name_lower = self.name.lower()
        
        if any(keyword in device_name_lower for keyword in ['check in', 'checkin', 'kirish']):
            return 'check_in'
        elif any(keyword in device_name_lower for keyword in ['check out', 'checkout', 'chiqish']):
            return 'check_out'
        return None
    
    def _build_log_search_payload(self, search_position, start_str, end_str):
        """
        Hikvision log qidirish uchun payload yaratish.

        MUHIM: timeReverseOrder=False.
        Qurilma loglarni ESKIDAN YANGIGA qaytaradi. Bu shart, chunki
        check-in va check-out juftlanishi vaqt tartibiga bog'liq:
        chiqish kirishdan oldin qayta ishlansa, "ochiq davomat yo'q"
        deb rad etiladi va chiqish butunlay yo'qoladi.
        """
        return {
            "AcsEventCond": {
                "searchID": "1",
                "searchResultPosition": search_position,
                "maxResults": DEFAULT_PAGE_SIZE,
                "major": HIKVISION_MAJOR_ACCESS_CONTROL,
                "minor": HIKVISION_MINOR_ALL,
                "startTime": start_str,
                "endTime": end_str,
                "isAttendanceInfo": True,
                "timeReverseOrder": False
            }
        }

    def _is_real_attendance_log(self, log):
        """
        Log haqiqiy davomat hodisasimi?

        Qurilma har bir kirish uchun bir nechta yozuv qaytaradi:
        bittasi shaxs autentifikatsiyasi, qolganlari eshik hodisalari.
        Amalda: 532 yozuvdan atigi 274 tasi haqiqiy.
        """
        if not log.get('employeeNoString') or not log.get('time'):
            return False
        return log.get('minor') in SUCCESS_AUTH_MINORS
    
    def _get_fetch_window(self):
        """
        Qurilmadan qaysi vaqt oralig'ini so'rashni aniqlash.

        last_fetch_time dan boshlanadi (1 daqiqa buffer bilan).
        Kun chegarasiga bog'lanmaydi - tungi smena va yarim tundan
        keyingi chiqishlar ham qamrab olinadi.

        Returns:
            tuple: (start_local, end_local)
        """
        self.ensure_one()

        local_tz = self._get_local_timezone()
        now = datetime.now(local_tz)

        if self.last_fetch_time:
            last_local = pytz.UTC.localize(self.last_fetch_time).astimezone(local_tz)
            start_time = last_local - timedelta(minutes=FETCH_OVERLAP_MINUTES)
            # Juda eskirib ketgan bo'lsa (cron uzoq to'xtagan) - 3 kun bilan cheklaymiz,
            # aks holda bitta cron ishga tushishi minglab yozuvni tortadi.
            oldest = now - timedelta(days=3)
            if start_time < oldest:
                start_time = oldest
                _logger.warning(
                    f"Hikvision [{self.name}]: last_fetch_time juda eski, "
                    f"3 kun bilan cheklandi"
                )
        else:
            # Birinchi marta - bugungi kun boshidan
            start_time = now.replace(hour=0, minute=0, second=0, microsecond=0)

        # Kelajakka biroz zaxira - qurilma soati bir necha daqiqa
        # oldinda bo'lishi mumkin (amalda 3 daqiqa farq kuzatilgan)
        end_time = now + timedelta(minutes=5)

        return start_time, end_time

    def _fetch_all_logs_raw(self):
        """
        Qurilmadan barcha loglarni olish (qayta ishlamasdan).

        MUHIM: last_fetch_time bu yerda YANGILANMAYDI.
        U faqat loglar muvaffaqiyatli qayta ishlangandan keyin,
        cron tomonidan yangilanadi. Aks holda qayta ishlashda
        xato bo'lsa, o'sha loglar abadiy yo'qoladi.

        Returns:
            tuple: (logs_list, device_attendance_type)
        """
        self.ensure_one()

        start_time, end_time = self._get_fetch_window()
        start_str = start_time.isoformat(timespec='seconds')
        end_str = end_time.isoformat(timespec='seconds')

        device_attendance_type = self._get_device_attendance_type()

        all_logs = []
        seen = set()
        search_position = 0
        total_matches = None
        pages = 0

        while pages < MAX_PAGES_PER_FETCH:
            payload = self._build_log_search_payload(search_position, start_str, end_str)
            response = self._make_request('POST', 'AccessControl/AcsEvent?format=json',
                                          data=json.dumps(payload))

            try:
                data = response.json()
            except ValueError:
                # Qurilma Content-Type: application/json desa ham
                # ba'zan XML qaytaradi (DS-K1T671MF da kuzatilgan)
                _logger.error(
                    f"Hikvision [{self.name}]: javob JSON emas "
                    f"({response.headers.get('Content-Type')})"
                )
                break

            acs = data.get('AcsEvent', {})
            pages += 1

            if total_matches is None:
                total_matches = acs.get('totalMatches', 0)

            logs = acs.get('InfoList') or []
            num_matches = acs.get('numOfMatches', len(logs))
            status = acs.get('responseStatusStrg', '')

            if not logs:
                break

            # serialNo bo'yicha dedup - sahifalar chegarasida
            # bir xil yozuv ikki marta kelishi mumkin
            for log in logs:
                key = log.get('serialNo')
                if key is None:
                    key = (log.get('time'), log.get('employeeNoString'), log.get('minor'))
                if key in seen:
                    continue
                seen.add(key)
                all_logs.append(log)

            # Qurilma qancha qaytargan bo'lsa - shuncha oldinga surish.
            # Qat'iy DEFAULT_PAGE_SIZE ga surish yozuv tushib qolishiga olib keladi.
            search_position += (num_matches or len(logs))

            # Qurilmaning o'zi "yana bor" deb aytmasa - to'xtaymiz
            if status != 'MORE':
                break

        if pages >= MAX_PAGES_PER_FETCH:
            _logger.warning(
                f"Hikvision [{self.name}]: sahifa chegarasiga yetildi "
                f"({MAX_PAGES_PER_FETCH}), qolgani keyingi cronda olinadi"
            )

        _logger.info(
            f"Hikvision [{self.name}]: {len(all_logs)}/{total_matches} ta log olindi "
            f"({pages} so'rov)"
        )

        return all_logs, device_attendance_type
    
    def _create_log_record(self, log, employee, log_time_utc, attendance_type):
        """
        Xom logni bazaga yozish.

        IKKI QATLAMLI DEDUP - va tartib muhim:

        1) Oldindan qidirish (asosiy yo'l). Fetch oynasi har safar
           FETCH_OVERLAP_MINUTES ga orqaga suriladi, ya'ni HAR siklda
           o'nlab allaqachon yozilgan log qaytadan keladi. Bu kutilgan
           holat, istisno emas - shuning uchun ular bazaga urilmasdan,
           shu yerda kesiladi.

        2) savepoint + IntegrityError (faqat poyga holati uchun). Cron
           va qo'lda "Loglarni yuklash" bir vaqtda ishlasa, ikkalasi ham
           1-qadamda "yo'q ekan" deb topib, ikki marta yozishi mumkin.
           Bunday to'qnashuv kamdan-kam va constraint uni ushlaydi.

        NEGA 1-QADAM KERAK (bu shunchaki optimizatsiya EMAS):
        Odoo'ning savepoint'i rollback paytida _FlushingSavepoint.rollback()
        -> cr.clear() -> Transaction.clear() zanjirini ishga tushiradi va u
        "discard all fields to recompute" qiladi - ya'ni BUTUN tranzaksiya
        bo'yicha kutilayotgan compute'larni tashlab yuboradi.

        Amalda bu shunday ko'rinardi: hr.attendance yaratilgach
        hr_employee.last_attendance_id (compute, store=True) qayta
        hisoblash navbatiga tushadi; keyingi dublikat log rollback
        qilganda o'sha navbat tozalanadi; natijada last_attendance_id
        NULL qolib, xodim kartochkasida "Absent" ko'rinadi - garchi
        hr_attendance qatori bazada bor bo'lsa ham.

        2026-08-19: bugungi 35 davomatdan 31 tasi aynan shu sababdan
        "Absent" bo'lib qolgan edi. Dublikatni bazaga umuman
        yubormaslik - rollback'ni, demak kesh tozalanishini ham yo'q
        qiladi.

        Returns:
            hikvision.log yozuvi, yoki dublikat bo'lsa None
        """
        Log = self.env['hikvision.log']
        mavjud = Log.search([
            ('device_id', '=', self.id),
            ('employee_id', '=', employee.id),
            ('timestamp', '=', log_time_utc),
        ], limit=1)
        if mavjud:
            return None

        vals = {
            'device_id': self.id,
            'employee_id': employee.id,
            'timestamp': log_time_utc,
            'attendance_type': attendance_type,
            'raw_minor': log.get('minor'),
            'serial_no': str(log['serialNo']) if log.get('serialNo') is not None else False,
            'state': 'unpaired',
        }
        try:
            with self.env.cr.savepoint():
                return Log.create(vals)
        except IntegrityError:
            # Poyga: 1-qadamdan keyin boshqa jarayon shu logni yozib
            # ulgurdi. Kesh tozalangan bo'lishi mumkin, shuning uchun
            # chaqiruvchi (_process_single_log) 'duplicate' qaytaradi va
            # _cron_fetch_logs oxirida last_attendance_id majburiy
            # yangilanadi (_refresh_attendance_cache).
            return None

    def _pair_log(self, log_record, employee, log_time_utc, attendance_type):
        """
        Yozilgan logni hr.attendance ga bog'lashga urinish.

        Juftlanmasa - bu xato EMAS. Xodim chiqishni unutib ikki marta
        kirsa yoki kirishsiz chiqsa, hodisa baribir sodir bo'lgan va
        log'da qoladi. Sabab skip_reason'ga yoziladi.
        """
        open_attendance = self._find_open_attendance(employee, log_time_utc)

        if attendance_type == 'check_in' and open_attendance:
            log_record.skip_reason = (
                f"Ochiq davomat bor ({open_attendance.check_in}) - "
                f"chiqish belgilanmagan")
            _logger.debug(
                "Hikvision: %s - CHECK IN juftlanmadi (ochiq davomat bor)",
                employee.name)
            return 'unpaired'

        if attendance_type == 'check_out' and not open_attendance:
            log_record.skip_reason = "Ochiq davomat topilmadi - kirish yozilmagan"
            _logger.debug(
                "Hikvision: %s - CHECK OUT juftlanmadi (ochiq davomat yo'q)",
                employee.name)
            return 'unpaired'

        attendance = self._process_attendance(employee, log_time_utc, attendance_type)

        if not attendance:
            # _process_attendance o'zi rad etdi (masalan 16 soatdan
            # eski ochiq davomat core validatsiyasini buzardi).
            log_record.skip_reason = "Davomat yozuvi yaratilmadi"
            return 'unpaired'

        log_record.write({
            'state': 'paired',
            'attendance_id': attendance.id,
            'skip_reason': False,
        })
        return 'paired'

    def _process_single_log(self, log, device_attendance_type, employee_map=None):
        """
        Bitta logni qayta ishlash: avval SAQLASH, keyin juftlash.

        Bu tartib muhim. Ilgari juftlash birinchi bo'lgan va juftlanmagan
        log butunlay tashlab yuborilardi - kun ichidagi qo'shimcha
        o'tishlar hech qayerda qolmasdi.

        Args:
            log: qurilmadan kelgan yozuv
            device_attendance_type: 'check_in' yoki 'check_out'
            employee_map: {barcode: employee} - oldindan tayyorlangan xarita.
                          Berilmasa, har log uchun alohida search qilinadi (sekin).

        Returns:
            'paired'    - log yozildi va davomatga bog'landi
            'unpaired'  - log yozildi, lekin davomatga bog'lanmadi
            'duplicate' - bu log allaqachon bazada bor
            'skipped'   - log davomat hodisasi emas yoki xodim topilmadi
            'error'     - kutilmagan xato
        """
        try:
            # Eshik hodisalari va muvaffaqiyatsiz urinishlarni kesish.
            # Bular haqiqiy o'tish emas - saqlashning ma'nosi yo'q.
            if not self._is_real_attendance_log(log):
                return 'skipped'

            if not device_attendance_type:
                # Bu qurilma modelida label kelmaydi - tur faqat
                # qurilma nomidan aniqlanadi. Aniqlanmasa - o'tkazamiz.
                return 'skipped'
            attendance_type = device_attendance_type

            employee_no = log.get('employeeNoString')
            if employee_map is not None:
                employee = employee_map.get(employee_no)
            else:
                employee = self.env['hr.employee'].search(
                    [('barcode', '=', employee_no)], limit=1)
            if not employee:
                # Odoo'da bunday barcode yo'q - qaysi xodim ekani
                # noma'lum, employee_id esa required.
                return 'skipped'

            log_time_utc = self._parse_log_time(log.get('time'))

            # 1. SAQLASH - juftlanishidan qat'i nazar
            log_record = self._create_log_record(
                log, employee, log_time_utc, attendance_type)
            if not log_record:
                return 'duplicate'

            # 2. JUFTLASH - alohida ish, natijasi log'da qayd etiladi
            return self._pair_log(
                log_record, employee, log_time_utc, attendance_type)

        except Exception:
            _logger.exception(
                f"Hikvision [{self.name}]: log qayta ishlashda xato "
                f"(emp={log.get('employeeNoString')}, time={log.get('time')})"
            )
            return 'error'

    def _find_open_attendance(self, employee, log_time_utc, max_shift_hours=16):
        """
        Xodimning ochiq davomatini topish.

        Kun chegarasiga bog'lanmaydi: tungi smenada kirish va chiqish
        turli kunlarga tushadi. Buning o'rniga smena uzunligi bilan
        cheklanadi - juda eski ochiq yozuvga chiqish yopishmasin.
        """
        return self.env['hr.attendance'].search([
            ('employee_id', '=', employee.id),
            ('check_out', '=', False),
            ('check_in', '<=', log_time_utc),
            ('check_in', '>=', log_time_utc - timedelta(hours=max_shift_hours)),
        ], order='check_in desc', limit=1)
    
    def action_fetch_logs(self):
        """
        Qurilmadan loglarni qo'lda olish ("Loglarni yuklash" tugmasi).

        Cron bilan bir xil mantiqdan foydalanadi - kod takrorlanmaydi.
        """
        self.ensure_one()

        fetch_started = datetime.now(pytz.UTC).replace(tzinfo=None)

        try:
            logs, device_attendance_type = self._fetch_all_logs_raw()
        except Exception as e:
            return self._notify('Loglarni olishda xato', str(e), 'danger', sticky=True)

        if not logs:
            self.last_fetch_time = fetch_started
            return self._notify('Log topilmadi', "Yangi loglar yo'q", 'warning')

        # Vaqt bo'yicha tartiblash - juftlash to'g'ri ishlashi uchun
        logs_sorted = sorted(logs, key=lambda x: x.get('time', ''))

        # Xodimlarni bitta so'rovda yuklash (N+1 oldini olish)
        barcodes = {l.get('employeeNoString') for l in logs_sorted if l.get('employeeNoString')}
        employee_map = {}
        if barcodes:
            employees = self.env['hr.employee'].search([('barcode', 'in', list(barcodes))])
            employee_map = {e.barcode: e for e in employees}

        counts = dict.fromkeys(
            ('paired', 'unpaired', 'duplicate', 'skipped', 'error'), 0)
        for log in logs_sorted:
            result = self._process_single_log(
                log, device_attendance_type, employee_map=employee_map)
            counts[result] = counts.get(result, 0) + 1

        # Faqat muvaffaqiyatli qayta ishlangandan keyin
        self.last_fetch_time = fetch_started

        # Juftlanmagan log XATO emas - hodisa qayd etilgan, faqat
        # davomatga bog'lanmagan (chiqishni unutgan xodim va h.k.).
        message = (
            f"Olindi: {len(logs)}, Juftlandi: {counts['paired']}, "
            f"Juftlanmadi: {counts['unpaired']}, Skip: {counts['skipped']}"
        )
        if counts['duplicate']:
            message += f", Takroriy: {counts['duplicate']}"
        if counts['error']:
            message += f", Xato: {counts['error']}"
        return self._notify(
            f'Loglar yuklandi ({self.name})', message,
            'warning' if counts['error'] else 'success')

    def _process_attendance(self, employee, log_time, attendance_type):
        """
        HR Attendance yozuvini yaratish yoki yangilash.

        Returns:
            hr.attendance yozuvi, yoki yaratilmasa/yangilanmasa None.
            Chaqiruvchi shu natijaga qarab logni 'paired' deb belgilaydi.
        """
        if attendance_type == 'check_in':
            existing = self.env['hr.attendance'].search([
                ('employee_id', '=', employee.id),
                ('check_in', '=', log_time)
            ], limit=1)

            if existing:
                # Aynan shu vaqtdagi davomat allaqachon bor -
                # log o'sha yozuvga bog'lanadi.
                return existing

            # Core hr.attendance._check_validity bitta xodimda faqat BITTA
            # ochiq davomatga ruxsat beradi. _find_open_attendance 16 soatlik
            # oyna bilan qidiradi, ya'ni undan eski ochiq yozuv "yo'q" deb
            # hisoblanadi - lekin core uni ko'radi va ValidationError beradi.
            # Auto-close olib tashlangandan keyin "chiqishni unutgan" xodim
            # oddiy holat, shuning uchun buni aniq hal qilamiz.
            stale = self.env['hr.attendance'].search([
                ('employee_id', '=', employee.id),
                ('check_out', '=', False),
            ], order='check_in desc', limit=1)

            if stale:
                _logger.warning(
                    "Attendance: %s - %s dan beri ochiq davomat bor, "
                    "yangi CHECK IN (%s) yozilmadi. Chiqish belgilanmagan.",
                    employee.name, stale.check_in, log_time)
                return None

            attendance = self.env['hr.attendance'].create({
                'employee_id': employee.id,
                'check_in': log_time,
                # Core hr.attendance qaysi usulda yozilganini kuzatadi.
                # 'technical' = tashqi tizim yozgan (qo'lda emas).
                'in_mode': 'technical',
            })
            _logger.info(f"Attendance: {employee.name} - CHECK IN yaratildi ({log_time})")
            return attendance

        elif attendance_type == 'check_out':
            open_attendance = self._find_open_attendance(employee, log_time)

            if open_attendance:
                open_attendance.write({
                    'check_out': log_time,
                    'out_mode': 'technical',
                })
                _logger.info(f"Attendance: {employee.name} - CHECK OUT belgilandi ({log_time})")
                return open_attendance

        return None
