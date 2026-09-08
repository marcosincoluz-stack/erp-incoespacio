/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import { UserMenu } from "@web/webclient/user_menu/user_menu";
import { browser } from "@web/core/browser/browser";
import { _t } from "@web/core/l10n/translation";
import { registry } from "@web/core/registry";

const userMenuRegistry = registry.category("user_menuitems");

// Personalizar el Menú de Usuario idéntico a Incoluz
patch(UserMenu.prototype, {
    setup() {
        super.setup();
        // Eliminar 'Mi cuenta Odoo.com' de forma segura en la inicialización
        if (userMenuRegistry.contains("odoo_account")) {
            userMenuRegistry.remove("odoo_account");
        }
        if (userMenuRegistry.contains("account")) {
            userMenuRegistry.remove("account");
        }
    },

    getElements() {
        // account/odoo_account ya se eliminan del registro en setup()
        const filtered = super.getElements();

        // Adaptar nombres y secuencias según el estándar Incoluz
        for (const item of filtered) {
            if (item.id === "settings" || item.id === "profile") {
                item.description = _t("Mi perfil");
                item.sequence = 40;
            } else if (item.id === "logout") {
                item.description = _t("Cerrar sesión");
                item.sequence = 50;
            }
        }

        // Añadir 'Documentación IT' (estándar Incoluz)
        if (!filtered.some((el) => el.id === "documentation_it")) {
            filtered.push({
                type: "item",
                id: "documentation_it",
                description: _t("Documentación IT"),
                callback: () => {
                    browser.open("/documentation/index.html", "_blank");
                },
                sequence: 15,
            });
        }

        // Fijar separador entre atajos y perfil
        for (const el of filtered) {
            if (el.type === "separator") {
                el.sequence = 30;
            }
        }

        filtered.sort((a, b) => (a.sequence || 100) - (b.sequence || 100));
        return filtered;
    },
});

