/** @odoo-module **/

import { Component } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

export class IncoespacioAppSidebar extends Component {
    static template = "incoespacio_theme.AppSidebar";

    setup() {
        this.menuService = useService("menu");
    }

    get apps() {
        try {
            return this.menuService?.getApps?.() || [];
        } catch (e) {
            return [];
        }
    }

    isCurrentApp(app) {
        try {
            const currentApp = this.menuService?.getCurrentApp?.();
            return Boolean(currentApp && app && currentApp.id === app.id);
        } catch (e) {
            return false;
        }
    }

    onAppClick(app) {
        try {
            if (app) {
                this.menuService.selectMenu(app);
            }
        } catch (e) {
            console.error("Error selecting app:", e);
        }
    }
}

registry.category("main_components").add("IncoespacioAppSidebar", {
    Component: IncoespacioAppSidebar,
});
