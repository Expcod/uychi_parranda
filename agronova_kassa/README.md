# AgroNova — Kassa (`agronova_kassa`)

AgroNova ning **M04 Kassa** moduli.

Kassir naqd pulni shu yerda yuritadi, buxgalter esa hech narsani qo'lda
ko'chirmaydi: har bir yozuv o'z provodkasini o'zi yozadi.

---

## Nega alohida modul

TZ da M04 uchun joy `agronova_savdo_moliya` da rejalashtirilgan edi, lekin
kassa oxir-oqibat depozitdan kattaroq bo'lib chiqdi (6 model, hisobotlar,
OWL paneli, ochiq veb-sahifa). Shuning uchun kassa alohida ilova sifatida
yozildi, `agronova_savdo_moliya` esa depozit yadrosi bo'lib qoldi —
`agronova_kassa` unga `depends` qiladi va depozitni faqat kengaytiradi
(xmlid egaligi buzilmaydi).

## Modellar

| Model | Vazifasi |
|---|---|
| `agronova.kassa` | Kassa kartochkasi — 3 tur: markaziy / filial / valyuta |
| `agronova.kassa.modda` | Kirim-chiqim moddasi: hisob + xatti-harakat bayrog'i |
| `agronova.kassa.harakat` | Kirim (KKO) va chiqim (KCHO) orderi |
| `agronova.kassa.kun` | Kassa kitobining kunlik varag'i |
| `agronova.kassa.otkazma` | Kassalararo transfer (3 bosqich) |
| `agronova.kassa.inkassatsiya` | Kassa → bank topshiruvi (3 bosqich) |

## Asosiy qarorlar

**Filial = korxona.** AgroNovada 7 filialning har biri alohida
`res.company` (branch). Shuning uchun «filial bo'yicha cheklov» uchun
alohida mexanizm yozilmadi — Odooning ko'p korxonali record rule'i
o'sha ishni bajaradi. O'rnatishda har korxonaga bittadan naqd jurnal va
kassa yaratiladi.

**Storno, o'chirish emas.** Tasdiqlangan order hech qachon
o'chirilmaydi. Storno qilinganda yozuv `storno` holatiga o'tadi (kassa
kitobida ustidan chizilgan holda qoladi), buxgalteriyada esa
`_reverse_moves` bilan **teskari provodka** yoziladi — `button_cancel`
emas, chunki bekor qilingan provodka jurnal raqamlarida bo'shliq
qoldiradi va audit izini buzadi.

**Yo'ldagi pul (5710).** Transfer ham, inkassatsiya ham uch bosqichli:
`qoralama → yo'lda → tasdiq / rad`. «Yo'lda» bosqichida pul manba
kassadan chiqib bo'lgan, lekin qabul qiluvchiga hali kirmagan — u
tranzit hisobida turadi. Ikki bosqichli sxemada (jo'natgan zahoti
ikkinchi kassaga kirim) hali qo'lga tegmagan pul boshqa kassada «bor»
bo'lib ko'rinardi.

**Analitikasiz xarajat yo'q.** Moddada `analitik_majburiy` yoqilgan
bo'lsa, analitik taqsimotsiz yozuv saqlanmaydi — TZ ning «xarajat
analitik kesimga biriktirilmasa saqlanmaydi» talabi kassaga ham tegishli,
aks holda naqd xarajat tannarxga tushmay qoladi.

**Depozit bilan zanjir.** Kassadan CHIQIM (depozit moddasi bilan) →
`agronova.depozit` ga KIRIM; kassaga KIRIM → depozitdan CHIQIM. Depozitdagi
pul kassa qoldig'iga kirmaydi — u kassadan chiqib bo'lgan. Ikkovining
yig'indisi korxona qo'lidagi umumiy naqdni beradi.

**Mijoz/yetkazuvchi qarzi.** `qarz_yopish` yoki `yetkazuvchi_tolov`
moddasi tanlansa, oddiy provodka o'rniga `account.payment` yaratiladi va
kontragentning eng eski ochiq hujjatlari bilan yarashtiriladi. Shunda
qarz avtomat kamayadi va to'lov Odooning o'z hisobotlarida ham ko'rinadi.

## Odoo 19 tuzoqlari (shu modulda uchradi)

1. **To'lovga outstanding hisobi shart.** Odoo 19 da naqd jurnalning
   to'lov usulida `payment_account_id` bo'sh bo'lsa, `action_post()`
   to'lovni `in_process` holatida qoldiradi va **umuman `account.move`
   yaratmaydi**. Kassa uchun bu jimgina yo'qotish bo'lardi. Yechim:
   `AgroNovaKassa._jurnal_outstanding_sozlash()` — kassa saqlanganda naqd
   jurnalning outstanding hisobi kassa hisobining o'ziga (5010) qo'yiladi,
   natijada to'lov darhol `Dt 5010 / Kt 4010` bo'lib tushadi.
2. **Menejer ham kassir qoidasiga tushadi.** `implied_ids` orqali meros
   olingan guruh record rule'ni ham meros qiladi, shuning uchun
   menejerga alohida `[(1,'=',1)]` qoidasi qo'yilgan (guruh qoidalari
   OR bilan birlashadi).
3. **`farq` — saqlanmaydigan compute.** Domen bo'yicha qidirib va list
   viewda `sum=` qilib bo'lmaydi; ro'yxatda faqat rang bilan ajratildi.
4. **py.js da `PyDate.replace` yo'q.** Search view domenida oy boshini
   `context_today().strftime('%Y-%m-01')` bilan olish kerak, aks holda
   filtr bosilganda brauzerda OWL yiqiladi.
5. **QWeb da `urlencode` yordamchisi yo'q** — QR manzili Python tomonda
   (`chek_qr_src`) tayyorlanadi.

## Chek va QR

Har orderga 80mm chek chiqadi (`agronova_kassa.action_report_kassa_chek`).
Chekdagi QR kod `/kassa/chek/<token>` ochiq sahifasiga olib boradi:
mijoz telefonida ochib chek haqiqiyligini tekshiradi. Token — 32 belgili
tasodifiy `uuid4`, shuning uchun raqamni ketma-ket terib boshqa cheklarni
ko'rib bo'lmaydi. Sahifa faqat chekda allaqachon bosilgan ma'lumotni
ko'rsatadi.

## Sinov

```bash
# Baza tayyorlash (agronova_savdo_moliya o'rnatilgan nusxadan)
python run_odoo.py -c odoo-agronova.conf -d agronova_kassa_test \
    -i agronova_kassa --stop-after-init

# 85 ta tekshiruv
echo "exec(open(r'agronova_custom/scripts/30_kassa_test.py', encoding='utf-8').read())" \
  | python run_odoo.py shell -c odoo-agronova.conf -d agronova_kassa_test --no-http

# OWL panelini brauzersiz tekshirish
node donxolm_custom/tools/owl_smoke.mjs \
    agronova_custom/agronova_kassa/static/src/kassa_panel.js AgroNovaKassaPanel
```

> Windows'da `Get-Content | python` ishlatmang — PowerShell quvurga BOM
> qo'shadi va shell `U+FEFF` xatosi beradi. `exec(open(...))` shakli
> ishlatilsin.

## Keyingi bosqich (TZ M04 dan qolgani)

* SMS tasdiq (Eskiz.uz) — kalit kerak;
* chekni Telegram / WhatsApp orqali PDF holida yuborish;
* tasdiqlanmagan hujjat bo'yicha har 5 daqiqada eskalatsiya;
* `agronova_kassa.orqaga_kun` sozlamasi hozir `0` — buyurtmachi qancha kun
  orqaga yozishga ruxsat berishini aytishi kerak.
