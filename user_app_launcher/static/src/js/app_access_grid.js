/** @odoo-module **/

import { Component, onWillStart, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { standardFieldProps } from "@web/views/fields/standard_field_props";

/**
 * res.users forma tabida ko'rsatiladigan vizual grid — barcha ilovalarni
 * Odoo Apps sahifasiga o'xshab ko'p ustunli katakchalarda ko'rsatadi.
 * Katakchani bosish shu foydalanuvchi uchun ilovani yoqadi/o'chiradi.
 */
class AppAccessGrid extends Component {
    static template = "user_app_launcher.AppAccessGrid";
    static props = { ...standardFieldProps };

    setup() {
        this.orm = useService("orm");
        this.notification = useService("notification");
        this.state = useState({
            apps: [],
            loading: true,
            saving: false,
            query: "",
        });
        onWillStart(async () => {
            await this.loadApps();
        });
    }

    get userId() {
        return this.props.record.resId;
    }

    async loadApps() {
        if (!this.userId) {
            this.state.apps = [];
            this.state.loading = false;
            return;
        }
        this.state.apps = await this.orm.call(
            "res.users", "get_app_access_grid", [[this.userId]]
        );
        this.state.loading = false;
    }

    /** Qidiruvga mos ilovalar (so'rov bo'sh bo'lsa — hammasi). */
    get visibleApps() {
        const q = (this.state.query || "").trim().toLowerCase();
        if (!q) {
            return this.state.apps;
        }
        return this.state.apps.filter((a) => (a.name || "").toLowerCase().includes(q));
    }

    get enabledCount() {
        return this.state.apps.filter((a) => a.has_access).length;
    }

    onSearch(ev) {
        this.state.query = ev.target.value;
    }

    clearSearch() {
        this.state.query = "";
    }

    getIconUrl(app) {
        return `/web/image/ir.ui.menu/${app.id}/web_icon_data`;
    }

    async onToggle(app) {
        if (!app.toggleable || this.state.saving) {
            return;
        }
        const newValue = !app.has_access;
        const oldValue = app.has_access;
        app.has_access = newValue;
        try {
            await this._save(app.id, newValue);
        } catch (e) {
            app.has_access = oldValue;
            this._error(e);
        }
    }

    /**
     * Ko'rinib turgan ilovalarning hammasini yoqadi/o'chiradi.
     * Qidiruv yoqilgan bo'lsa — FAQAT topilganlariga ta'sir qiladi, shunda
     * tugma ko'rinmayotgan ilovalarni kutilmaganda o'zgartirib yubormaydi.
     */
    async setAll(enable) {
        if (this.state.saving) {
            return;
        }
        const target = this.visibleApps.filter(
            (a) => a.toggleable && a.has_access !== enable
        );
        if (!target.length) {
            return;
        }
        this.state.saving = true;
        const oldValues = target.map((a) => a.has_access);
        target.forEach((a) => (a.has_access = enable));
        try {
            for (const app of target) {
                await this._save(app.id, enable);
            }
        } catch (e) {
            target.forEach((a, i) => (a.has_access = oldValues[i]));
            this._error(e);
        } finally {
            this.state.saving = false;
        }
    }

    _save(menuId, enable) {
        return this.orm.call(
            "res.users", "toggle_app_access", [[this.userId], menuId, enable]
        );
    }

    _error(e) {
        const msg =
            (e && e.data && e.data.message) || (e && e.message) || "Xatolik yuz berdi";
        this.notification.add(msg, { type: "danger" });
    }
}

registry.category("fields").add("app_access_grid", {
    component: AppAccessGrid,
});
