/** @odoo-module **/

import { Component, onWillStart, useExternalListener, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { browser } from "@web/core/browser/browser";
import { DateTimeInput } from "@web/core/datetime/datetime_input";
import { deserializeDate, serializeDate } from "@web/core/l10n/dates";
import { Scene3D } from "./scene3d";

// Chap navigatsiya. Har bo'lim Python tomondagi `_section_<code>` metodiga mos.
// Server `get_dashboard_meta()` da qaysi bo'lim o'rnatilganini aytadi — qolganlari
// yashiriladi, shuning uchun bitta panel istalgan tarkibdagi korxonaga mos keladi.
const SECTIONS = [
    { code: "overview", label: "Umumiy ko'rinish", icon: "fa-th-large", group: "Boshqaruv" },
    { code: "moliya", label: "Moliya va kassa", icon: "fa-university", group: "Boshqaruv" },
    { code: "qarzdorlar", label: "Qarzdorlar", icon: "fa-user-times", group: "Boshqaruv" },
    { code: "ombor", label: "Ombor", icon: "fa-cubes", group: "Boshqaruv" },
    { code: "yem_zavodi", label: "Yem zavodi", icon: "fa-industry", group: "Ishlab chiqarish" },
    { code: "ona_tovuq", label: "Ona tovuq", icon: "fa-circle-o", group: "Ishlab chiqarish" },
    { code: "inkubatoriya", label: "Inkubatoriya", icon: "fa-life-ring", group: "Ishlab chiqarish" },
    { code: "boquv", label: "Boquv", icon: "fa-home", group: "Ishlab chiqarish" },
    { code: "soyish", label: "So'yish sexi", icon: "fa-cutlery", group: "Ishlab chiqarish" },
    { code: "qishloq_xojaligi", label: "Qishloq xo'jaligi", icon: "fa-leaf", group: "Ishlab chiqarish" },
    { code: "zakupka", label: "Xarid", icon: "fa-shopping-basket", group: "Savdo va logistika" },
    { code: "pos", label: "Do'kon (POS)", icon: "fa-shopping-cart", group: "Savdo va logistika" },
    { code: "transport", label: "Transport", icon: "fa-truck", group: "Savdo va logistika" },
    { code: "ish_haqi", label: "Ish haqi", icon: "fa-money", group: "Xodimlar" },
    { code: "davomat", label: "Davomat", icon: "fa-clock-o", group: "Xodimlar" },
];

const PERIODS = [
    { code: "today", label: "Bugun" },
    { code: "week", label: "Hafta" },
    { code: "month", label: "Oy" },
    { code: "6months", label: "6 oy" },
    { code: "year", label: "Yil" },
];

// Backend qaytaradigan rang kalitlari → inline uslublar uchun HEX qiymatlar.
const COLORS = {
    green: "#16a34a",
    blue: "#2563eb",
    purple: "#7c3aed",
    orange: "#ea580c",
    red: "#dc2626",
    teal: "#0d9488",
    indigo: "#4f46e5",
    gray: "#64748b",
};

// Tanlangan bo'lim va davr brauzerda saqlanadi: F5 dan keyin ham joyida qoladi.
const STORAGE_KEY = "agronova_dashboard.state";

// Bir sahifada nechta qator. Server ro'yxatni to'liq yuboradi, sahifalash shu yerda.
const PAGE_SIZE = 10;
const DETAIL_PAGE_SIZE = 15;
const PAGED_TYPES = ["rank", "gridtable"];

export class AgroNovaExecutiveDashboard extends Component {
    static template = "agronova_dashboard.Dashboard";
    static components = { DateTimeInput, Scene3D };
    static props = ["*"];

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.notification = useService("notification");
        this.periods = PERIODS;
        this.state = useState({
            loading: true,
            error: false,
            section: "overview",
            period: "month",
            dateFrom: "",
            dateTo: "",
            data: null,
            meta: null,
            loadSeq: 0,
            updatedAt: "",
            navOpen: false,
            // Tafsilot oynasi: stack — ichma-ich ochilgan oynalar (orqaga qaytish uchun).
            detail: { open: false, loading: false, stack: [] },
            ...this._restoreState(),
            ...(this._forcedSection() ? { section: this._forcedSection() } : {}),
        });
        useExternalListener(window, "keydown", (ev) => {
            if (ev.key === "Escape" && this.state.detail.open) {
                this.closeDetail();
            }
        });
        onWillStart(async () => {
            await this.loadMeta();
            await this.load();
        });
    }

    // ------------------------------------------------------------------
    // Navigatsiya
    // ------------------------------------------------------------------
    get visibleSections() {
        const allowed = this.state.meta?.sections;
        return allowed ? SECTIONS.filter((s) => allowed.includes(s.code)) : SECTIONS;
    }

    get navGroups() {
        const groups = [];
        for (const s of this.visibleSections) {
            let g = groups.find((x) => x.label === s.group);
            if (!g) {
                g = { label: s.group, items: [] };
                groups.push(g);
            }
            g.items.push(s);
        }
        return groups;
    }

    get currentSection() {
        return SECTIONS.find((s) => s.code === this.state.section) || SECTIONS[0];
    }

    get brandName() {
        return (this.state.meta && this.state.meta.brand) || "AgroNova";
    }

    get companyName() {
        return (this.state.meta && this.state.meta.company) || "";
    }

    toggleNav() {
        this.state.navOpen = !this.state.navOpen;
    }

    get brandInitials() {
        const name = this.brandName;
        return name
            .split(/\s+/)
            .map((w) => w[0])
            .join("")
            .slice(0, 2)
            .toUpperCase();
    }

    // ------------------------------------------------------------------
    // Tanlovni eslab qolish (bo'lim + davr)
    // ------------------------------------------------------------------
    _restoreState() {
        let saved;
        try {
            saved = JSON.parse(browser.localStorage.getItem(STORAGE_KEY) || "null");
        } catch {
            saved = null;
        }
        if (!saved || typeof saved !== "object") {
            return {};
        }
        const restored = {};
        if (SECTIONS.some((s) => s.code === saved.section)) {
            restored.section = saved.section;
        }
        if (saved.period === "custom" || PERIODS.some((p) => p.code === saved.period)) {
            restored.period = saved.period;
        }
        if (this._isIsoDate(saved.dateFrom) && this._isIsoDate(saved.dateTo)) {
            restored.dateFrom = saved.dateFrom;
            restored.dateTo = saved.dateTo;
        }
        if (restored.period === "custom" && !restored.dateFrom) {
            delete restored.period;
        }
        return restored;
    }

    /** Menyudan ochilganda bo'lim majburan tanlanishi mumkin
     *  (masalan Yem zavodi ilovasidagi «Boshqaruv paneli»). */
    _forcedSection() {
        const code = this.props.action?.context?.agronova_section;
        return SECTIONS.some((s) => s.code === code) ? code : null;
    }

    _isIsoDate(value) {
        return typeof value === "string" && /^\d{4}-\d{2}-\d{2}$/.test(value);
    }

    _persistState() {
        try {
            browser.localStorage.setItem(
                STORAGE_KEY,
                JSON.stringify({
                    section: this.state.section,
                    period: this.state.period,
                    dateFrom: this.state.dateFrom,
                    dateTo: this.state.dateTo,
                })
            );
        } catch {
            // Maxfiy rejim / to'lgan xotira — eslab qolish shart emas.
        }
    }

    // ------------------------------------------------------------------
    // Ma'lumot yuklash
    // ------------------------------------------------------------------
    async loadMeta() {
        try {
            this.state.meta = await this.orm.call("agronova.executive.dashboard", "get_dashboard_meta", []);
        } catch {
            this.state.meta = null;
        }
        // Saqlangan bo'lim endi mavjud bo'lmasa (modul o'chirilgan) — umumiyga qaytamiz.
        if (!this.visibleSections.some((s) => s.code === this.state.section)) {
            this.state.section = "overview";
        }
    }

    async load() {
        this.state.loading = true;
        this.state.error = false;
        try {
            const data = await this.orm.call("agronova.executive.dashboard", "get_dashboard_data", [
                this.state.section,
                this.state.period,
                this.state.dateFrom || false,
                this.state.dateTo || false,
            ]);
            this._decorate(data.panels || []);
            this.state.data = data;
            this.state.dateFrom = data.date_from;
            this.state.dateTo = data.date_to;
            this.state.period = data.period || this.state.period;
            this.state.loadSeq++;
            this.state.updatedAt = new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
            this._persistState();
        } catch (e) {
            this.state.error = true;
            throw e;
        } finally {
            this.state.loading = false;
        }
    }

    /** Shablon kutadigan inline rang/gradient qiymatlarini qo'shadi. */
    _decorate(panels) {
        for (const panel of panels) {
            if (!panel) {
                continue;
            }
            if (PAGED_TYPES.includes(panel.type)) {
                panel.page = 0;
            }
            if (panel.type === "split") {
                let acc = 0;
                const segments = [];
                for (const part of panel.parts) {
                    part.hex = COLORS[part.color] || COLORS.gray;
                    const start = acc;
                    acc += part.pct;
                    segments.push(`${part.hex} ${start}% ${acc}%`);
                }
                if (!segments.length || acc <= 0) {
                    panel.gradient = `conic-gradient(${COLORS.gray} 0% 100%)`;
                    panel.empty = true;
                } else {
                    if (acc < 100) {
                        segments.push(`var(--smd-track) ${acc}% 100%`);
                    }
                    panel.gradient = `conic-gradient(${segments.join(", ")})`;
                    panel.empty = false;
                }
            } else if (panel.type === "rank") {
                panel.hex = COLORS[panel.color] || COLORS.blue;
            } else if (panel.type === "gauges") {
                for (const g of panel.gauges) {
                    g.hex = COLORS[g.color] || COLORS.blue;
                }
            }
        }
    }

    // ------------------------------------------------------------------
    // Ko'rinish yordamchilari
    // ------------------------------------------------------------------
    cellClass(cell) {
        const parts = [];
        if (cell.align === "right") {
            parts.push("o_smd_t_num");
        }
        if (cell.tone) {
            parts.push("o_smd_tone_" + cell.tone);
        }
        return parts.join(" ");
    }

    hex(color) {
        return COLORS[color] || COLORS.gray;
    }

    /** KPI ostidagi mini-grafik uchun SVG nuqtalari (100×28 maydon). */
    sparkPoints(kpi) {
        const vals = kpi.spark || [];
        if (vals.length < 2) {
            return "";
        }
        const step = 100 / (vals.length - 1);
        return vals.map((v, i) => `${(i * step).toFixed(1)},${(26 - (v / 100) * 24).toFixed(1)}`).join(" ");
    }

    sparkArea(kpi) {
        const pts = this.sparkPoints(kpi);
        return pts ? `0,28 ${pts} 100,28` : "";
    }

    isClickable(item) {
        return Boolean(item && (item.detail || item.action || item.open));
    }

    _pageSize(panel) {
        return panel.pageSize || PAGE_SIZE;
    }

    pageCount(panel) {
        return Math.max(1, Math.ceil((panel.rows || []).length / this._pageSize(panel)));
    }

    pageRows(panel) {
        const size = this._pageSize(panel);
        const start = (panel.page || 0) * size;
        return (panel.rows || []).slice(start, start + size);
    }

    rowNumber(panel, index) {
        return (panel.page || 0) * this._pageSize(panel) + index + 1;
    }

    pageLabel(panel) {
        const total = (panel.rows || []).length;
        if (!total) {
            return "";
        }
        const size = this._pageSize(panel);
        const start = (panel.page || 0) * size;
        return `${start + 1}–${Math.min(start + size, total)} / ${total}`;
    }

    isPaged(panel) {
        return (panel.rows || []).length > this._pageSize(panel);
    }

    turnPage(panel, delta) {
        const pages = this.pageCount(panel);
        panel.page = ((panel.page || 0) + delta + pages) % pages;
    }

    // ------------------------------------------------------------------
    // Foydalanuvchi amallari
    // ------------------------------------------------------------------
    async selectSection(code) {
        this.state.navOpen = false;
        if (this.state.section === code) {
            return;
        }
        this.state.section = code;
        this.closeDetail();
        await this.load();
    }

    async selectPeriod(code) {
        if (this.state.period === code) {
            return;
        }
        this.state.period = code;
        await this.load();
    }

    get dateFromValue() {
        return this.state.dateFrom ? deserializeDate(this.state.dateFrom) : false;
    }

    get dateToValue() {
        return this.state.dateTo ? deserializeDate(this.state.dateTo) : false;
    }

    onDateFromPicked(value) {
        if (value) {
            this.state.dateFrom = serializeDate(value);
        }
    }

    onDateToPicked(value) {
        if (value) {
            this.state.dateTo = serializeDate(value);
        }
    }

    async applyCustomRange() {
        if (!this.state.dateFrom || !this.state.dateTo) {
            return;
        }
        this.state.period = "custom";
        await this.load();
    }

    async refresh() {
        await this.load();
        if (this.state.detail.open) {
            await this._reloadDetail();
        }
    }

    /** Kartochka / qator / bo'lak bosilganda: avval tafsilot, bo'lmasa ro'yxat. */
    activate(item) {
        if (!item) {
            return;
        }
        if (item.detail) {
            this.openDetail(item.detail);
        } else if (item.open) {
            this.openRecord(item.open.res_model, item.open.res_id);
        } else if (item.action) {
            this.openAction(item.action);
        }
    }

    onScenePick(node) {
        if (!node) {
            return;
        }
        if (node.detail) {
            this.openDetail(node.detail);
        } else if (node.section) {
            this.selectSection(node.section);
        }
    }

    // ------------------------------------------------------------------
    // Tafsilot oynasi (drill-down)
    // ------------------------------------------------------------------
    get currentDetail() {
        const stack = this.state.detail.stack;
        return stack.length ? stack[stack.length - 1] : null;
    }

    async _fetchDetail(detail) {
        const payload = await this.orm.call("agronova.executive.dashboard", "get_detail", [
            detail.key,
            this.state.period,
            this.state.dateFrom || false,
            this.state.dateTo || false,
            detail.ref ?? false,
        ]);
        payload.request = detail;
        payload.page = 0;
        payload.pageSize = DETAIL_PAGE_SIZE;
        this._decorate([payload.chart, payload.split]);
        return payload;
    }

    async openDetail(detail) {
        if (!detail || !detail.key) {
            return;
        }
        const d = this.state.detail;
        d.open = true;
        d.loading = true;
        try {
            d.stack.push(await this._fetchDetail(detail));
        } catch (e) {
            if (!d.stack.length) {
                d.open = false;
            }
            throw e;
        } finally {
            d.loading = false;
        }
    }

    async _reloadDetail() {
        const d = this.state.detail;
        const current = this.currentDetail;
        if (!current) {
            return;
        }
        d.loading = true;
        try {
            d.stack[d.stack.length - 1] = await this._fetchDetail(current.request);
        } finally {
            d.loading = false;
        }
    }

    detailBack() {
        this.state.detail.stack.pop();
        if (!this.state.detail.stack.length) {
            this.closeDetail();
        }
    }

    closeDetail() {
        this.state.detail.open = false;
        this.state.detail.stack = [];
        this.state.detail.loading = false;
    }

    onDetailRow(row) {
        if (row.detail) {
            this.openDetail(row.detail);
        } else if (row.open) {
            this.openRecord(row.open.res_model, row.open.res_id);
        }
    }

    openDetailAction(action) {
        if (!action) {
            return;
        }
        if (action.res_id) {
            this.openRecord(action.res_model, action.res_id);
        } else {
            this.openAction(action);
        }
    }

    openRecord(resModel, resId) {
        if (!resModel || !resId) {
            return;
        }
        this.action.doAction({
            type: "ir.actions.act_window",
            res_model: resModel,
            res_id: resId,
            views: [[false, "form"]],
            target: "current",
        });
    }

    /** KPI kartochkasidagi domen bo'yicha tegishli Odoo ro'yxatini ochadi. */
    openAction(action) {
        if (!action || !action.res_model) {
            return;
        }
        this.action.doAction({
            type: "ir.actions.act_window",
            name: action.name,
            res_model: action.res_model,
            domain: action.domain || [],
            views: [
                [false, "list"],
                [false, "form"],
            ],
            target: "current",
        });
    }
}

registry.category("actions").add("agronova_executive_dashboard", AgroNovaExecutiveDashboard);
