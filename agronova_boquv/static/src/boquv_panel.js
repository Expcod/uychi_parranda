import { Component, useState, onWillStart } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";
import { deserializeDateTime } from "@web/core/l10n/dates";

const { DateTime } = luxon;
const UZ_TZ = "Asia/Tashkent";

/**
 * Brigadir paneli — sehdagi kunlik ishning bitta ekrani.
 *
 * Barcha hisob-kitob serverda (`agronova.boquv.partiya` dagi ui_* metodlari),
 * bu yerda faqat ko'rsatish va forma. Shu sababli paneldagi raqam hujjat
 * ochilganda ko'rinadigan raqamdan farq qilmaydi.
 */
export class BoquvBrigadirPanel extends Component {
    static template = "agronova_boquv.BrigadirPanel";
    static props = ["*"];

    setup() {
        this.orm = useService("orm");
        this.notification = useService("notification");
        this.state = useState({
            loading: true,
            saving: false,
            home: null,
            partiyaId: null,
            detail: null,
            // modallar
            showObxod: false,
            showJurnal: false,
            showVazn: false,
            showXarajat: false,
            obxod: this._emptyObxod(),
            jurnal: this._emptyJurnal(),
            vazn: this._emptyVazn(),
            xarajat: this._emptyXarajat(),
            // mahsulot qidiruvi (sarf qatorlari uchun)
            qidiruvIndex: null,
            qidiruvMatn: "",
            qidiruvNatija: [],
        });
        onWillStart(() => this.load());
    }

    // ------------------------------------------------------------------
    // Bo'sh formalar
    // ------------------------------------------------------------------
    _emptyObxod() {
        return {
            harorat: "",
            namlik: "",
            jojalar_holati: "yaxshi",
            yem_holati: "yaxshi",
            suv_holati: "yaxshi",
            olgan_joja: "",
            muammo: "",
            chora: "",
        };
    }

    _emptyJurnal() {
        return {
            nobud_son: "",
            nobud_sabab: "",
            suv_litr: "",
            harorat: "",
            izoh: "",
            sarflar: [],
        };
    }

    _emptyVazn() {
        return {
            tortilgan_son: 100,
            ortacha_vazn: "",
            min_vazn: "",
            max_vazn: "",
            izoh: "",
        };
    }

    _emptyXarajat() {
        return {
            kategoriya_id: "",
            nom: "",
            miqdor: 1,
            narx: "",
            tolov_turi: "naqd",
            izoh: "",
            foto: null,
            foto_filename: "",
        };
    }

    // ------------------------------------------------------------------
    // Yuklash
    // ------------------------------------------------------------------
    async load() {
        this.state.loading = true;
        try {
            const home = await this.orm.call(
                "agronova.boquv.partiya",
                "ui_home",
                []
            );
            this.state.home = home;
            if (!this.state.partiyaId && home.partiyalar.length) {
                this.state.partiyaId = home.partiyalar[0].id;
            }
            if (this.state.partiyaId) {
                await this.loadPartiya();
            }
        } finally {
            this.state.loading = false;
        }
    }

    async loadPartiya() {
        this.state.detail = await this.orm.call(
            "agronova.boquv.partiya",
            "ui_partiya",
            [this.state.partiyaId]
        );
        this._applyKart(this.state.detail.kart);
    }

    /** Kartochkani ro'yxatda ham yangilab qo'yamiz — ikkita raqam bo'lmasin. */
    _applyKart(kart) {
        if (!this.state.home) {
            return;
        }
        const idx = this.state.home.partiyalar.findIndex((p) => p.id === kart.id);
        if (idx >= 0) {
            this.state.home.partiyalar[idx] = kart;
        }
    }

    async selectPartiya(id) {
        this.state.partiyaId = id;
        await this.loadPartiya();
    }

    // ------------------------------------------------------------------
    // Ko'rsatish yordamchilari
    // ------------------------------------------------------------------
    get partiya() {
        if (!this.state.home) {
            return null;
        }
        return (
            this.state.home.partiyalar.find((p) => p.id === this.state.partiyaId) ||
            null
        );
    }

    get kart() {
        return this.state.detail ? this.state.detail.kart : null;
    }

    get normativ() {
        return this.state.detail ? this.state.detail.normativ : null;
    }

    son(v) {
        return (Number(v) || 0).toLocaleString("ru-RU");
    }

    pul(v) {
        const belgi = this.state.home ? this.state.home.valyuta : "";
        return `${this.son(Math.round(Number(v) || 0))} ${belgi}`;
    }

    formatVaqt(s) {
        return s ? deserializeDateTime(s).setZone(UZ_TZ).toFormat("HH:mm") : "";
    }

    formatSana(s) {
        return s ? DateTime.fromISO(s).toFormat("dd.MM") : "";
    }

    /** Obxod normasi bajarilganini rangda ko'rsatish uchun. */
    obxodKlass(kart) {
        if (!kart) {
            return "";
        }
        return kart.obxod_bugun >= kart.obxod_norma ? "text-success" : "text-danger";
    }

    haroratKlass(holat) {
        if (holat === "past" || holat === "yuqori") {
            return "text-danger fw-bold";
        }
        if (holat === "normal") {
            return "text-success";
        }
        return "";
    }

    // ------------------------------------------------------------------
    // Umumiy saqlash o'ramchisi
    // ------------------------------------------------------------------
    async _saqla(metod, vals, xabar) {
        if (this.state.saving) {
            return null;
        }
        this.state.saving = true;
        try {
            const res = await this.orm.call("agronova.boquv.partiya", metod, [vals]);
            if (res.partiya) {
                this.state.detail = res.partiya;
                this._applyKart(res.partiya.kart);
            }
            // Ogohlantirishlar ro'yxati butun panel bo'yicha — qayta olamiz.
            await this._ogohlarniYangila();
            this.notification.add(xabar, { type: "success" });
            return res;
        } finally {
            this.state.saving = false;
        }
    }

    async _ogohlarniYangila() {
        const home = await this.orm.call("agronova.boquv.partiya", "ui_home", []);
        // Tanlangan partiyani almashtirmasdan faqat umumiy holatni yangilaymiz.
        this.state.home.ogohlar = home.ogohlar;
        this.state.home.jami = home.jami;
        this.state.home.depozit = home.depozit;
        this.state.home.partiyalar = home.partiyalar;
    }

    // ------------------------------------------------------------------
    // Obxod
    // ------------------------------------------------------------------
    openObxod() {
        this.state.obxod = this._emptyObxod();
        const n = this.normativ;
        if (n && n.harorat_min && n.harorat_max) {
            // Me'yorning o'rtasini taklif qilamiz — brigadir odatda shundan
            // uncha uzoq bo'lmagan qiymat kiritadi, terish kamayadi.
            this.state.obxod.harorat = String(
                Math.round(((n.harorat_min + n.harorat_max) / 2) * 10) / 10
            );
        }
        this.state.showObxod = true;
    }

    closeObxod() {
        this.state.showObxod = false;
    }

    get obxodValid() {
        return Number(this.state.obxod.harorat) > -50;
    }

    async saveObxod() {
        const o = this.state.obxod;
        const res = await this._saqla(
            "ui_obxod",
            { partiya_id: this.state.partiyaId, ...o },
            _t("Obxod qayd etildi")
        );
        if (res) {
            this.state.showObxod = false;
        }
    }

    // ------------------------------------------------------------------
    // Kunlik jurnal
    // ------------------------------------------------------------------
    openJurnal() {
        this.state.jurnal = this._emptyJurnal();
        this.addSarf();
        this.state.showJurnal = true;
    }

    closeJurnal() {
        this.state.showJurnal = false;
        this._qidiruvYop();
    }

    addSarf() {
        this.state.jurnal.sarflar.push({
            tur: "yem",
            product_id: null,
            product_nom: "",
            uom: "",
            uom_id: null,
            miqdor: "",
        });
    }

    removeSarf(index) {
        this.state.jurnal.sarflar.splice(index, 1);
        if (this.state.qidiruvIndex === index) {
            this._qidiruvYop();
        }
    }

    _qidiruvYop() {
        this.state.qidiruvIndex = null;
        this.state.qidiruvMatn = "";
        this.state.qidiruvNatija = [];
    }

    async searchProduct(index, ev) {
        const term = ev.target.value;
        this.state.qidiruvIndex = index;
        this.state.qidiruvMatn = term;
        const qator = this.state.jurnal.sarflar[index];
        qator.product_id = null;
        qator.product_nom = term;
        this.state.qidiruvNatija = await this.orm.call(
            "agronova.boquv.partiya",
            "ui_search_product",
            [term, qator.tur]
        );
    }

    pickProduct(rec) {
        const qator = this.state.jurnal.sarflar[this.state.qidiruvIndex];
        if (!qator) {
            return;
        }
        qator.product_id = rec.id;
        qator.product_nom = rec.nom;
        qator.uom = rec.uom;
        qator.uom_id = rec.uom_id;
        this._qidiruvYop();
    }

    /** Kutilayotgan yem sarfi: bosh soni × normadagi kunlik gramm. */
    get yemKutilgan() {
        const k = this.kart;
        const n = this.normativ;
        if (!k || !n || !n.yem_bosh_kunlik_gr) {
            return 0;
        }
        return Math.round((k.joriy_son * n.yem_bosh_kunlik_gr) / 1000);
    }

    /** Nobud kiritilgan, lekin sabab tanlanmagan — shablon shuni ko'rsatadi. */
    get nobudSababKerak() {
        const j = this.state.jurnal;
        return Number(j.nobud_son) > 0 && !j.nobud_sabab;
    }

    get jurnalValid() {
        const j = this.state.jurnal;
        const nobud = Number(j.nobud_son) || 0;
        if (nobud < 0) {
            return false;
        }
        if (nobud > 0 && !j.nobud_sabab) {
            return false;
        }
        // To'ldirilgan sarf qatorida mahsulot ham, miqdor ham bo'lishi shart.
        return j.sarflar.every(
            (s) =>
                (!s.product_id && !s.miqdor) ||
                (s.product_id && Number(s.miqdor) > 0)
        );
    }

    async saveJurnal(tasdiqlash) {
        const j = this.state.jurnal;
        const res = await this._saqla(
            "ui_jurnal",
            {
                partiya_id: this.state.partiyaId,
                nobud_son: Number(j.nobud_son) || 0,
                nobud_sabab: j.nobud_sabab || false,
                suv_litr: Number(j.suv_litr) || 0,
                harorat: Number(j.harorat) || 0,
                izoh: j.izoh,
                tasdiqlash: !!tasdiqlash,
                sarflar: j.sarflar
                    .filter((s) => s.product_id && Number(s.miqdor) > 0)
                    .map((s) => ({
                        product_id: s.product_id,
                        tur: s.tur,
                        miqdor: Number(s.miqdor),
                        uom_id: s.uom_id,
                    })),
            },
            tasdiqlash ? _t("Jurnal tasdiqlandi") : _t("Jurnal saqlandi")
        );
        if (res) {
            this.state.showJurnal = false;
            this._qidiruvYop();
        }
    }

    // ------------------------------------------------------------------
    // Vazn
    // ------------------------------------------------------------------
    openVazn() {
        this.state.vazn = this._emptyVazn();
        this.state.showVazn = true;
    }

    closeVazn() {
        this.state.showVazn = false;
    }

    get vaznValid() {
        const v = this.state.vazn;
        return Number(v.tortilgan_son) > 0 && Number(v.ortacha_vazn) > 0;
    }

    async saveVazn() {
        const v = this.state.vazn;
        const res = await this._saqla(
            "ui_vazn",
            { partiya_id: this.state.partiyaId, ...v },
            _t("Vazn qayd etildi")
        );
        if (res) {
            this.state.showVazn = false;
        }
    }

    // ------------------------------------------------------------------
    // Xarajat
    // ------------------------------------------------------------------
    openXarajat() {
        this.state.xarajat = this._emptyXarajat();
        this.state.showXarajat = true;
    }

    closeXarajat() {
        this.state.showXarajat = false;
    }

    setTolovTuri(tur) {
        this.state.xarajat.tolov_turi = tur;
    }

    get xarajatSummasi() {
        const x = this.state.xarajat;
        return (Number(x.miqdor) || 0) * (Number(x.narx) || 0);
    }

    get depozitYetmaydi() {
        const d = this.state.home && this.state.home.depozit;
        if (!d || this.state.xarajat.tolov_turi !== "naqd") {
            return false;
        }
        return this.xarajatSummasi > d.balans;
    }

    get xarajatValid() {
        const x = this.state.xarajat;
        if (!x.kategoriya_id || !(x.nom || "").trim()) {
            return false;
        }
        if (!(this.xarajatSummasi > 0)) {
            return false;
        }
        if (x.tolov_turi === "naqd") {
            // Naqd xarajat fotosiz saqlanmaydi — serverdagi qoidaning
            // ko'zgusi, foydalanuvchi xatoni yozishdan oldin ko'rsin.
            if (!x.foto || !this.state.home.depozit) {
                return false;
            }
        }
        return true;
    }

    async onFotoChange(ev) {
        const file = ev.target.files && ev.target.files[0];
        if (!file) {
            return;
        }
        const base64 = await new Promise((resolve, reject) => {
            const reader = new FileReader();
            reader.onload = () => resolve(String(reader.result).split(",")[1]);
            reader.onerror = reject;
            reader.readAsDataURL(file);
        });
        this.state.xarajat.foto = base64;
        this.state.xarajat.foto_filename = file.name;
    }

    async saveXarajat() {
        const x = this.state.xarajat;
        const depozit = this.state.home.depozit;
        const res = await this._saqla(
            "ui_xarajat",
            {
                partiya_id: this.state.partiyaId,
                kategoriya_id: parseInt(x.kategoriya_id),
                nom: x.nom,
                miqdor: Number(x.miqdor) || 1,
                narx: Number(x.narx) || 0,
                tolov_turi: x.tolov_turi,
                depozit_id: x.tolov_turi === "naqd" && depozit ? depozit.id : false,
                foto: x.foto,
                foto_filename: x.foto_filename,
                izoh: x.izoh,
                tasdiqlash: true,
            },
            _t("Xarajat yozildi")
        );
        if (res) {
            this.state.showXarajat = false;
        }
    }
}

registry.category("actions").add("agronova_boquv.brigadir_panel", BoquvBrigadirPanel);
