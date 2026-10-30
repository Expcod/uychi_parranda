/** @odoo-module **/
import { registry } from "@web/core/registry";
import { AgroNovaExecutiveDashboard } from "@agronova_dashboard/dashboard/dashboard";

const SECTIONS = [
    { code: "overview", label: "Umumiy ko'rinish", icon: "fa-th-large", group: "Yem zavodi" },
    { code: "production", label: "Ishlab chiqarish va reja", icon: "fa-industry", group: "Jarayonlar" },
    { code: "stock", label: "Xomashyo va tarozi", icon: "fa-cubes", group: "Jarayonlar" },
    { code: "quality", label: "Yo'qotish va to'xtashlar", icon: "fa-exclamation-triangle", group: "Jarayonlar" },
    { code: "dispatch", label: "Qadoqlash va jo'natma", icon: "fa-truck", group: "Jarayonlar" },
    { code: "energy", label: "Energiya va tannarx", icon: "fa-bolt", group: "Moliyaviy tahlil" },
];

export class FeedManagerDashboard extends AgroNovaExecutiveDashboard {
    get visibleSections() { return SECTIONS; }
    get currentSection() { return SECTIONS.find(s => s.code === this.state.section) || SECTIONS[0]; }
    get brandName() { return "Rahbar paneli"; }
    _restoreState() { return {}; }
    _forcedSection() { return null; }
    _persistState() {}
    async loadMeta() {
        this.state.meta = await this.orm.call("agronova.executive.dashboard", "get_feed_manager_meta", []);
    }
    async load() {
        this.state.loading = true;
        this.state.error = false;
        try {
            const data = await this.orm.call("agronova.executive.dashboard", "get_feed_manager_data", [
                this.state.section, this.state.period, this.state.dateFrom || false, this.state.dateTo || false,
            ]);
            this._decorate(data.panels || []);
            this.state.data = data;
            this.state.dateFrom = data.date_from;
            this.state.dateTo = data.date_to;
            this.state.period = data.period || this.state.period;
            this.state.loadSeq++;
            this.state.updatedAt = new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
        } catch (e) {
            this.state.error = true;
            throw e;
        } finally { this.state.loading = false; }
    }
}
registry.category("actions").add("agronova_feed_manager_dashboard", FeedManagerDashboard);
