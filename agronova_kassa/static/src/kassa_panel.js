import { Component, useState, onWillStart } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";
import { deserializeDateTime } from "@web/core/l10n/dates";

const { DateTime } = luxon;
const UZ_TZ = "Asia/Tashkent";
const nowUz = () => DateTime.now().setZone(UZ_TZ);

/**
 * Kassir paneli.
 *
 * Butun hisob-kitob serverda (`agronova.kassa` dagi ui_* metodlari), bu yerda
 * faqat ko'rsatish va forma. Shu sababli panel va formalar bir xil raqamni
 * ko'rsatadi — qoldiq ikki joyda ikki xil hisoblanmaydi.
 */
export class AgroNovaKassaPanel extends Component {
    static template = "agronova_kassa.Panel";
    static props = ["*"];

    setup() {
        this.orm = useService("orm");
        this.notification = useService("notification");
        this.state = useState({
            loading: true,
            saving: false,
            kassalar: [],
            moddalar: [],
            kassaId: null,
            date: nowUz().toFormat("yyyy-MM-dd"),
            today: nowUz().toFormat("yyyy-MM-dd"),
            canClose: false,
            canReopen: false,
            day: null,
            kutilayotgan: [],
            form: this._emptyForm("in"),
            showForm: false,
            // «Kim» qidiruvi (kontragent / xodim / depozit)
            kimSearch: "",
            kimResults: [],
            showKimList: false,
            // Analitik hisob qidiruvi
            anaSearch: "",
            anaResults: [],
            showAnaList: false,
            showClose: false,
            closeForm: { sanoq: 0, note: "" },
            showOtkazma: false,
            otkazma: this._emptyOtkazma(),
        });
        onWillStart(() => this.load());
    }

    _emptyForm(direction) {
        return {
            direction: direction || "in",
            amount: "",
            moddaId: "",
            izoh: "",
            kimTur: direction === "out" ? "employee" : "partner",
            kim: null,
            analitik: null,
        };
    }

    _emptyOtkazma(yonalish) {
        return {
            yonalish: yonalish || "out",
            boshqaId: "",
            amount: "",
            izoh: "",
            olibBoruvchi: null,
        };
    }

    // ------------------------------------------------------------------
    // Yuklash
    // ------------------------------------------------------------------
    async load() {
        this.state.loading = true;
        try {
            const home = await this.orm.call("agronova.kassa", "ui_home", []);
            this.state.kassalar = home.kassalar;
            this.state.moddalar = home.moddalar;
            this.state.canClose = home.can_close;
            this.state.canReopen = home.can_reopen;
            this.state.today = home.today;
            if (!this.state.kassaId && home.kassalar.length) {
                this.state.kassaId = home.kassalar[0].id;
            }
            if (this.state.kassaId) {
                await this.loadDay();
            }
            await this.loadKutilayotgan();
        } finally {
            this.state.loading = false;
        }
    }

    async loadDay() {
        const day = await this.orm.call("agronova.kassa", "ui_day", [
            this.state.kassaId,
            this.state.date,
        ]);
        this._applyDay(day);
        this.state.closeForm.sanoq = day.kun && day.kun.sanoq ? day.kun.sanoq : 0;
        this.state.closeForm.note = (day.kun && day.kun.note) || "";
    }

    async loadKutilayotgan() {
        this.state.kutilayotgan = await this.orm.call(
            "agronova.kassa",
            "ui_kutilayotgan",
            []
        );
    }

    _applyDay(day) {
        this.state.day = day;
        const idx = this.state.kassalar.findIndex((k) => k.id === day.kassa.id);
        if (idx >= 0) {
            this.state.kassalar[idx] = day.kassa;
        }
    }

    async selectKassa(id) {
        this.state.kassaId = id;
        this.state.showForm = false;
        await this.loadDay();
    }

    async onDateChange(ev) {
        this.state.date = ev.target.value;
        await this.loadDay();
    }

    async goToday() {
        this.state.date = this.state.today;
        await this.loadDay();
    }

    // ------------------------------------------------------------------
    // Ko'rsatish yordamchilari
    // ------------------------------------------------------------------
    get kassa() {
        return this.state.kassalar.find((k) => k.id === this.state.kassaId) || null;
    }

    get dayClosed() {
        return !!(
            this.state.day &&
            this.state.day.kun &&
            this.state.day.kun.state === "closed"
        );
    }

    get isToday() {
        return this.state.date === this.state.today;
    }

    get moddalarForm() {
        return this.state.moddalar.filter(
            (m) => m.direction === this.state.form.direction
        );
    }

    get modda() {
        const id = parseInt(this.state.form.moddaId);
        return this.state.moddalar.find((m) => m.id === id) || null;
    }

    /** Tanlangan modda depozit egasini talab qiladimi. */
    get depozitKerak() {
        return !!(this.modda && this.modda.depozit);
    }

    /** Tanlangan modda analitik kesimni talab qiladimi. */
    get analitikKerak() {
        return !!(this.modda && this.modda.analitik_majburiy);
    }

    /** Kontragent majburiy bo'lgan moddalar (qarz yopish). */
    get kontragentKerak() {
        return !!(this.modda && this.modda.qarz);
    }

    money(v, kassa) {
        const k = kassa || this.kassa;
        const son = (Number(v) || 0).toLocaleString("ru-RU", {
            minimumFractionDigits: 0,
            maximumFractionDigits: k ? k.decimals : 2,
        });
        return k ? `${son} ${k.symbol}` : son;
    }

    formatTime(dateStr) {
        return dateStr
            ? deserializeDateTime(dateStr).setZone(UZ_TZ).toFormat("HH:mm")
            : "";
    }

    // ------------------------------------------------------------------
    // Kirim / chiqim formasi
    // ------------------------------------------------------------------
    openForm(direction) {
        if (this.dayClosed) {
            this.notification.add(
                _t("Bu kun yopilgan — yangi order qo'shib bo'lmaydi."),
                { type: "warning" }
            );
            return;
        }
        this.state.form = this._emptyForm(direction);
        this._resetKim();
        this._resetAna();
        this.state.showForm = true;
    }

    closeForm() {
        this.state.showForm = false;
    }

    _resetKim() {
        this.state.kimSearch = "";
        this.state.kimResults = [];
        this.state.showKimList = false;
    }

    _resetAna() {
        this.state.anaSearch = "";
        this.state.anaResults = [];
        this.state.showAnaList = false;
    }

    /** Modda o'zgarsa — u talab qiladigan maydonlarga moslanadi. */
    onModdaChange() {
        const m = this.modda;
        if (m && m.depozit) {
            this.state.form.kimTur = "depozit";
        } else if (m && m.qarz) {
            this.state.form.kimTur = "partner";
        }
        this.state.form.kim = null;
        this._resetKim();
    }

    setKimTur(tur) {
        this.state.form.kimTur = tur;
        this.state.form.kim = null;
        this._resetKim();
    }

    async searchKim(ev) {
        const term = ev.target.value;
        this.state.kimSearch = term;
        this.state.form.kim = null;
        const metod = {
            employee: "ui_search_employees",
            depozit: "ui_search_depozit",
            partner: "ui_search_partners",
        }[this.state.form.kimTur];
        this.state.kimResults = await this.orm.call("agronova.kassa", metod, [term]);
        this.state.showKimList = true;
    }

    pickKim(rec) {
        this.state.form.kim = rec;
        this.state.kimSearch = rec.name;
        this.state.showKimList = false;
    }

    focusKim() {
        if (this.state.kimResults.length) {
            this.state.showKimList = true;
        }
    }

    async searchAna(ev) {
        const term = ev.target.value;
        this.state.anaSearch = term;
        this.state.form.analitik = null;
        this.state.anaResults = await this.orm.call(
            "agronova.kassa",
            "ui_search_analytic",
            [term]
        );
        this.state.showAnaList = true;
    }

    pickAna(rec) {
        this.state.form.analitik = rec;
        this.state.anaSearch = rec.name;
        this.state.showAnaList = false;
    }

    focusAna() {
        if (this.state.anaResults.length) {
            this.state.showAnaList = true;
        }
    }

    get formValid() {
        const f = this.state.form;
        const m = this.modda;
        if (!(Number(f.amount) > 0) || !m) {
            return false;
        }
        if (m.izoh_majburiy && !(f.izoh || "").trim()) {
            return false;
        }
        if (m.analitik_majburiy && !f.analitik) {
            return false;
        }
        if (m.depozit && !(f.kim && f.kimTur === "depozit")) {
            return false;
        }
        if (m.qarz && !(f.kim && f.kimTur === "partner")) {
            return false;
        }
        return true;
    }

    async saveForm() {
        if (!this.formValid || this.state.saving) {
            return;
        }
        const f = this.state.form;
        this.state.saving = true;
        try {
            const vals = {
                kassa_id: this.state.kassaId,
                direction: f.direction,
                amount: Number(f.amount),
                modda_id: parseInt(f.moddaId),
                partner_id: f.kimTur === "partner" && f.kim ? f.kim.id : false,
                employee_id: f.kimTur === "employee" && f.kim ? f.kim.id : false,
                depozit_id: f.kimTur === "depozit" && f.kim ? f.kim.id : false,
                izoh: f.izoh,
            };
            if (f.analitik) {
                // Analitik taqsimot Odooda {hisob_id: foiz} ko'rinishida
                // saqlanadi — panelda bitta hisob 100% bilan beriladi.
                vals.analytic_distribution = { [String(f.analitik.id)]: 100 };
            }
            const res = await this.orm.call("agronova.kassa", "ui_create_harakat", [
                vals,
            ]);
            this.notification.add(
                f.direction === "in"
                    ? _t("Kirim orderi yozildi: %s", res.name)
                    : _t("Chiqim orderi yozildi: %s", res.name),
                { type: "success" }
            );
            this._applyDay(res.day);
            this.state.showForm = false;
        } finally {
            this.state.saving = false;
        }
    }

    async stornoLine(line) {
        if (line.auto) {
            this.notification.add(
                _t(
                    "Bu yozuv manba hujjatdan tushgan — storno manba hujjatdan qilinadi."
                ),
                { type: "warning" }
            );
            return;
        }
        const sabab = window.prompt(
            _t("«%s» nima uchun storno qilinyapti?", line.name)
        );
        if (!sabab) {
            return;
        }
        const day = await this.orm.call("agronova.kassa", "ui_storno_harakat", [
            line.id,
            sabab,
        ]);
        this._applyDay(day);
        this.notification.add(_t("Storno qilindi"), { type: "success" });
    }

    openChek(line) {
        if (line.chek_url) {
            window.open(line.chek_url, "_blank");
        }
    }

    // ------------------------------------------------------------------
    // Kassalararo transfer
    // ------------------------------------------------------------------
    get otkazmaKassalar() {
        const k = this.kassa;
        if (!k) {
            return [];
        }
        return this.state.kassalar.filter(
            (b) => b.id !== k.id && b.currency_id === k.currency_id
        );
    }

    get canOtkazma() {
        return this.otkazmaKassalar.length > 0;
    }

    get otkazmaBoshqa() {
        const id = parseInt(this.state.otkazma.boshqaId);
        return this.state.kassalar.find((k) => k.id === id) || null;
    }

    get otkazmaFrom() {
        return this.state.otkazma.yonalish === "out" ? this.kassa : this.otkazmaBoshqa;
    }

    get otkazmaTo() {
        return this.state.otkazma.yonalish === "out" ? this.otkazmaBoshqa : this.kassa;
    }

    get otkazmaYetmaydi() {
        const from = this.otkazmaFrom;
        const summa = Number(this.state.otkazma.amount) || 0;
        return !!(from && summa > 0 && from.balance < summa);
    }

    get otkazmaValid() {
        const from = this.otkazmaFrom;
        const to = this.otkazmaTo;
        if (!from || !to || from.id === to.id) {
            return false;
        }
        if (!(Number(this.state.otkazma.amount) > 0)) {
            return false;
        }
        return !this.otkazmaYetmaydi;
    }

    openOtkazma(yonalish) {
        if (this.dayClosed) {
            this.notification.add(_t("Bu kun yopilgan — transfer yozib bo'lmaydi."), {
                type: "warning",
            });
            return;
        }
        const kassalar = this.otkazmaKassalar;
        if (!kassalar.length) {
            this.notification.add(
                _t("Transfer uchun shu valyutadagi ikkinchi kassa kerak."),
                { type: "warning" }
            );
            return;
        }
        this.state.otkazma = this._emptyOtkazma(yonalish);
        if (kassalar.length === 1) {
            this.state.otkazma.boshqaId = String(kassalar[0].id);
        }
        this.state.showOtkazma = true;
    }

    closeOtkazma() {
        this.state.showOtkazma = false;
    }

    setOtkazmaYonalish(yonalish) {
        this.state.otkazma.yonalish = yonalish;
    }

    async saveOtkazma() {
        if (!this.otkazmaValid || this.state.saving) {
            return;
        }
        const o = this.state.otkazma;
        this.state.saving = true;
        try {
            const res = await this.orm.call("agronova.kassa", "ui_create_otkazma", [
                {
                    from_kassa_id: this.otkazmaFrom.id,
                    to_kassa_id: this.otkazmaTo.id,
                    amount: Number(o.amount),
                    izoh: o.izoh,
                },
            ]);
            this.state.showOtkazma = false;
            this.state.date = this.state.today;
            await this.load();
            this.notification.add(
                _t("Transfer jo'natildi: %s. Qabul qiluvchi tasdiqlashi kerak.", res.name),
                { type: "success" }
            );
        } finally {
            this.state.saving = false;
        }
    }

    // ------------------------------------------------------------------
    // Kutilayotgan transferlar (qabul / rad)
    // ------------------------------------------------------------------
    async qabulQilish(row) {
        const sanoq = window.prompt(
            _t("«%s» bo'yicha sanab olingan summani kiriting:", row.name),
            String(row.amount)
        );
        if (sanoq === null) {
            return;
        }
        this.state.saving = true;
        try {
            await this.orm.call("agronova.kassa", "ui_qabul_qilish", [
                row.id,
                Number(sanoq),
            ]);
            await this.load();
            this.notification.add(_t("Qabul qilindi"), { type: "success" });
        } finally {
            this.state.saving = false;
        }
    }

    async radEtish(row) {
        const sabab = window.prompt(_t("«%s» nima uchun rad etilyapti?", row.name));
        if (!sabab) {
            return;
        }
        this.state.saving = true;
        try {
            await this.orm.call("agronova.kassa", "ui_rad_etish", [row.id, sabab]);
            await this.load();
            this.notification.add(_t("Rad etildi — pul manba kassaga qaytdi"), {
                type: "success",
            });
        } finally {
            this.state.saving = false;
        }
    }

    // ------------------------------------------------------------------
    // Kunni yopish
    // ------------------------------------------------------------------
    openClose() {
        if (!this.state.day) {
            return;
        }
        this.state.closeForm.sanoq = this.state.day.closing;
        this.state.showClose = true;
    }

    hideClose() {
        this.state.showClose = false;
    }

    get closeFarq() {
        if (!this.state.day) {
            return 0;
        }
        return (Number(this.state.closeForm.sanoq) || 0) - this.state.day.closing;
    }

    async confirmClose() {
        this.state.saving = true;
        try {
            const day = await this.orm.call("agronova.kassa", "ui_close_day", [
                this.state.kassaId,
                this.state.date,
                Number(this.state.closeForm.sanoq) || 0,
                this.state.closeForm.note,
            ]);
            this._applyDay(day);
            this.state.showClose = false;
            this.notification.add(_t("Kun yopildi"), { type: "success" });
        } finally {
            this.state.saving = false;
        }
    }
}

registry.category("actions").add("agronova_kassa.panel", AgroNovaKassaPanel);
