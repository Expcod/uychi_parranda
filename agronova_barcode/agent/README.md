# Odoo stiker chop etish agenti

Sexdagi kompyuterda ishlaydi. VPS'dagi Odoo'ning chop etish navbatini kuzatib
turadi va kelgan stikerlarni USB printerga yuboradi.

```
[Sex kompyuteri]  ──HTTPS──►  [VPS Odoo]
   OdooPrintAgent.exe          agronova.label.print.job
        │
        └─USB─► Xprinter
```

Agent o'zi murojaat qiladi, shuning uchun **serverdan printerga ulanish kerak
emas** — VPS uchun yagona ishlaydigan yechim.

## Fayllar

| Fayl | Nima |
|---|---|
| `agent_gui.py` | Sozlash oynasi (tkinter) |
| `print_agent.py` | Chop etish mantig'i — navbat, XML-RPC, printer |
| `agent.spec` | PyInstaller sozlamasi |
| `build.ps1` | Exe yasash skripti |
| `agent.ini.example` | Sozlama namunasi (oynasiz ishlatish uchun) |

## Exe yasash (dasturchi uchun)

```powershell
.\build.ps1
```

Natija: `dist\OdooPrintAgent.exe` — bitta fayl, ~11 MB, Python kerak emas.

## O'rnatish (sexdagi kompyuterda)

1. `OdooPrintAgent.exe` ni `C:\odoo-agent\` ga ko'chiring
2. Ikki marta bosing
3. Odoo ma'lumotlarini to'ldiring:
   - Server manzili, baza nomi, login, parol
   - **Agent kaliti** — Odoo'da: Ombor → Sozlamalar → Stiker printerlari
4. Printerni ro'yxatdan tanlang (bo'sh qoldirilsa Odoo'dagi nom ishlatiladi)
5. **Ulanishni tekshirish** → yashil javob kutiladi
6. **Ishga tushirish**
7. Odoo'da "Sinov chop etish" — stiker chiqishi kerak

Sozlama `agent.ini` ga yoziladi, keyingi ochilishda o'zi o'qiladi.

## Doimiy ishlashi uchun

Oynadagi **"Xizmat qilib o'rnatish"** tugmasi ikki yo'lni ko'rsatadi:
avtoyuklash (oson) yoki NSSM xizmati (ishonchli, hech kim kirmasa ham ishlaydi).

## Oynasiz ishlatish

```powershell
python print_agent.py --config agent.ini --log agent.log
```

## Muammolarni tekshirish

Loglar `agent.log` da — exe turgan papkada.

| Log yozuvi | Sabab |
|---|---|
| `Odoo'ga kirib bo'lmadi` | Login/parol xato yoki 2FA yoqilgan |
| `Access Denied` | Agent kaliti xato |
| `getaddrinfo failed` | Server manzili xato yoki internet yo'q |
| `database ... does not exist` | Baza nomi xato |
| `Job N chop etilmadi` | Printer nomi xato yoki printer o'chiq |

## Diqqat

`agent.ini` ichida **parol va kalit** bor — uni hech kimga bermang va repoga
qo'shmang (`.gitignore` da).
