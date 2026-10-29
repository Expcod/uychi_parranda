# -*- coding: utf-8 -*-
"""
Hikvision API Request Mixin

Bu mixin Hikvision qurilmalariga HTTP so'rovlar yuborish uchun
asosiy metodlarni o'z ichiga oladi.
"""

import logging
import threading

import requests
from requests.adapters import HTTPAdapter
from requests.auth import HTTPDigestAuth
from urllib3.util.retry import Retry

from odoo import models

# Timeout sozlamalari
DEFAULT_TIMEOUT = 10
MULTIPART_TIMEOUT = 30

# Vaqtinchalik xatolarda qayta urinish
RETRY_TOTAL = 2
RETRY_BACKOFF = 0.4
RETRY_STATUSES = (500, 502, 503, 504)

_logger = logging.getLogger(__name__)


class HikvisionDeviceError(Exception):
    """
    Qurilma bilan bog'lanishda xato.

    UserError EMAS: UserError "foydalanuvchi noto'g'ri narsa qildi"
    degan ma'noni bildiradi va cron kontekstida noo'rin. Qurilmaning
    javob bermasligi - infratuzilma nosozligi.

    Asl xato __cause__ da saqlanadi (raise ... from e), shuning uchun
    chaqiruvchi timeout bilan 401 ni ajrata oladi.
    """


# Thread-local sessiyalar: {device_id: Session}
# Sessiya TCP ulanishni qayta ishlatadi - har so'rovda yangi ulanish
# va Digest 401-challenge qilinmaydi (2 barobar kam round-trip).
_sessions = threading.local()


def _get_session(device_id):
    """Qurilma uchun sessiya olish (thread-local)."""
    pool = getattr(_sessions, 'pool', None)
    if pool is None:
        pool = _sessions.pool = {}

    session = pool.get(device_id)
    if session is None:
        session = requests.Session()
        adapter = HTTPAdapter(
            max_retries=Retry(
                total=RETRY_TOTAL,
                backoff_factor=RETRY_BACKOFF,
                status_forcelist=RETRY_STATUSES,
                allowed_methods=frozenset(['GET', 'POST', 'PUT']),
            ),
            pool_connections=4,
            pool_maxsize=4,
        )
        session.mount('http://', adapter)
        session.mount('https://', adapter)
        pool[device_id] = session
    return session


class HikvisionApiMixin(models.AbstractModel):
    """Hikvision API so'rovlari uchun mixin"""

    _name = 'hikvision.api.mixin'
    _description = 'Hikvision API Mixin'

    def _get_isapi_url(self, endpoint):
        """ISAPI endpoint URL'ini yaratish"""
        self.ensure_one()
        return f"http://{self.ip_address}:{self.port}/ISAPI/{endpoint}"

    def _get_auth(self):
        """Digest auth obyekti.

        Har so'rovda yangi obyekt qaytariladi: qurilma nonce'ni
        eskirtirganda bir xil obyekt 401 bera boshlaydi.

        sudo() shart: username/password maydonlari
        groups='hr.group_hr_manager' bilan himoyalangan, oddiy
        foydalanuvchi kontekstida ular bo'sh qaytadi.
        """
        self.ensure_one()
        device = self.sudo()
        return HTTPDigestAuth(device.username, device.password)

    def _make_request(self, method, endpoint, data=None, params=None):
        """
        Hikvision qurilmasiga HTTP so'rov yuborish.
        
        Args:
            method: 'GET', 'POST', 'PUT'
            endpoint: ISAPI endpoint (masalan: 'System/deviceInfo')
            data: Request body (string yoki dict)
            params: Query parameters
        
        Returns:
            requests.Response object
        
        Raises:
            Exception: Ulanish xatosi bo'lganda
        """
        self.ensure_one()

        if method not in ('GET', 'POST', 'PUT'):
            raise ValueError(f"Unsupported HTTP method: {method}")

        url = self._get_isapi_url(endpoint)
        session = _get_session(self.id)

        try:
            response = session.request(
                method, url,
                auth=self._get_auth(),
                data=data,
                params=params,
                timeout=DEFAULT_TIMEOUT,
            )
            response.raise_for_status()
            return response

        except requests.exceptions.RequestException as e:
            # Asl xato turini saqlaymiz - chaqiruvchi timeout bilan
            # 401 ni ajrata olishi uchun
            raise HikvisionDeviceError(
                f"[{self.name}] {method} {endpoint}: {e}"
            ) from e
    
    def _make_request_multipart(self, method, endpoint, data=None, content_type=None):
        """
        Multipart so'rovlar uchun maxsus metod (fayllar yuklash uchun).
        
        Args:
            method: HTTP method
            endpoint: ISAPI endpoint
            data: Binary data
            content_type: Content-Type header
        
        Returns:
            requests.Response object
        """
        self.ensure_one()

        url = self._get_isapi_url(endpoint)
        headers = {}
        if content_type:
            headers['Content-Type'] = content_type

        try:
            response = _get_session(self.id).post(
                url, auth=self._get_auth(), data=data,
                headers=headers, timeout=MULTIPART_TIMEOUT,
            )
            response.raise_for_status()
            return response
        except requests.exceptions.RequestException as e:
            raise HikvisionDeviceError(
                f"[{self.name}] Yuklash xatosi: {e}") from e
    
    def _make_request_multipart_put(self, endpoint, data=None, content_type=None):
        """
        PUT metodi bilan multipart so'rov yuborish (yuz rasmini yangilash uchun).
        
        Hikvision dokumentatsiyasiga ko'ra FDModify endpoint PUT talab qiladi.
        
        Args:
            endpoint: ISAPI endpoint
            data: Binary data
            content_type: Content-Type header
        
        Returns:
            requests.Response object
        """
        self.ensure_one()

        url = self._get_isapi_url(endpoint)
        headers = {}
        if content_type:
            headers['Content-Type'] = content_type

        try:
            response = _get_session(self.id).put(
                url, auth=self._get_auth(), data=data,
                headers=headers, timeout=MULTIPART_TIMEOUT,
            )
            response.raise_for_status()
            return response
        except requests.exceptions.RequestException as e:
            raise HikvisionDeviceError(
                f"[{self.name}] Yangilash xatosi: {e}") from e
