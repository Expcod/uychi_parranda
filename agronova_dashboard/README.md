# AgroNova — Rahbar paneli va analitika (`agronova_dashboard`)

Agro-sanoat (parrandachilik) korxonasi uchun yagona rahbar paneli. Texnik nom
`agronova_dashboard` saqlangan — ishlab turgan bazalar buzilmasin; foydalanuvchi
ko'radigan nom va brend sozlamalardan keladi.

## Nima beradi

| Imkoniyat | Qisqacha |
|---|---|
| 15 bo'lim | Umumiy, Moliya va kassa, Qarzdorlar, Ombor, Yem zavodi, Ona tovuq, Inkubatoriya, Boquv, So'yish, Qishloq xo'jaligi, Xarid, Do'kon (POS), Transport, Ish haqi, Davomat |
| Moslashuvchan tarkib | Modeli o'rnatilmagan bo'lim menyudan yashiriladi (`SECTION_MODELS`) — bitta kod istalgan tarkibdagi korxonaga |
| Drill-down | KPI, reyting qatori, donut bo'lagi, grafik ustuni, ferma kartochkasi, 3D bino, ogohlantirish — hammasi bosiladi. O'ngdan oyna ochiladi: ko'rsatkichlar, grafik, jadval, ichma-ich o'tish (filial → partiya → kunlik jurnal), «Odoo'da ochish» |
| 3D | Umumiy bo'limda biznes zanjiri xaritasi (oqim animatsiyasi), Boquv — fermalar, Qishloq xo'jaligi — dalalar, Ombor — taxlamlar. Balandlik = hajm, rang = normativ holati |
| Avtomatik xulosalar | Normadan og'ish, 60+ kunlik qarz, kechikkan zayavka, muddati tugayotgan lot va h.k. panel tepasida |
| Solishtirish | Asosiy pul KPI'larida oldingi xuddi shunday davrga nisbatan ▲/▼ % va mini-grafik |
| Oq yorliq | Sozlamalar → Rahbar paneli: panel nomi, shior, 6 ta texnologik normativ |
| Yorug' / qorong'i tema | Odoo temasiga ergashadi: `dashboard.dark.scss` (`web.assets_web_dark`) faqat `--smd-*` tokenlarini almashtiradi; 3D sahna tunga o'tadi |

## Arxitektura

- `models/agronova_executive_dashboard.py` — `get_dashboard_meta`, `get_dashboard_data`,
  har bo'lim `_section_<kod>(ctx)`; 3D zanjir `_chain_scene`.
- `models/agronova_dashboard_detail.py` — `get_detail(key, ..., ref)`; har tafsilot
  `_detail_<key>(ctx, ref)`. Mijoz model/domen yubora olmaydi — faqat shu metodlardan
  biri tanlanadi, shuning uchun `sudo()` xavfsiz.
- `models/res_config_settings.py` — `agronova.*` parametrlari (brend, normativlar).
- `static/src/dashboard/dashboard.js|xml|scss` — OWL mijoz amali `agronova_executive_dashboard`.
- `static/src/dashboard/scene3d.js` — three.js sahnasi (`static/lib/three/three.min.js`,
  r128, MIT). Kutubxona faqat 3D panel ochilganda `loadJS` bilan yuklanadi; WebGL
  yo'q bo'lsa oddiy kartochkalar ko'rinadi.

Kirish: `group_agronova_dashboard_user` (yoki tizim administratori). Ma'lumot `sudo` bilan
o'qiladi, eshik `_check_dashboard_access()` da.

## Yangi bo'lim / tafsilot qo'shish

1. `SECTION_MODELS` ga `kod: "model.nomi"` qo'shing va `_section_<kod>(self, ctx)` yozing
   (`{"kpis": [...], "panels": [...], "alerts": [...]}` qaytaradi).
2. `dashboard.js` dagi `SECTIONS` ga yorliq va ikonka qo'shing.
3. Bosiladigan element uchun `detail=self._det("kalit", ref)` bering va
   `agronova_dashboard_detail.py` da `_detail_<kalit>(self, ctx, ref)` yozing
   (`self._detail(...)` + `self._rows_table(...)` yordamchilari bor).

## Tuzoqlar

- Yordamchi metodga `_table` nomini bermang — Odoo modelining `_table` atributini bosib,
  registr yuklanmay qoladi (shu sabab `_rows_table`).
- SCSS da `min()/max()` CSS funksiyalarini yozmang — libsass ularni o'zi hisoblamoqchi
  bo'lib «Incompatible units» beradi va butun backend uslubsiz qoladi.
- Odoo 19 da `ir.actions.act_window.target = 'inline'` yo'q — `current`.
- 3D komponentida THREE obyektlarini OWL reaktiv `props` ichida saqlamang (`toRaw`).
- Yangi stilda rangni to'g'ridan-to'g'ri yozmang — `--smd-*` tokenidan oling, aks holda
  qorong'i temada oq dog' bo'lib qoladi.

## Tekshiruv

Smoke-test (odoo shell): har bo'lim × 6 davr, panellardagi barcha tafsilot havolalari,
barcha `_detail_*` metodlari (ref yo'q / mavjud bo'lmagan id / satr / sana oralig'i) va
noto'g'ri kalitlarning rad etilishi.
