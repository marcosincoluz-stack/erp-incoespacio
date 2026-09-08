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
        return this.menuService.getApps();
    }

    isCurrentApp(app) {
        const currentApp = this.menuService.getCurrentApp();
        return Boolean(currentApp && app && currentApp.id === app.id);
    }

    onAppClick(app) {
        if (app) {
            this.menuService.selectMenu(app);
        }
    }
}

registry.category("main_components").add("IncoespacioAppSidebar", {
    Component: IncoespacioAppSidebar,
});
