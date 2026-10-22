/** @odoo-module **/

import { registry } from "@web/core/registry";
import { _t } from "@web/core/l10n/translation";

registry.category("actions").add("bc3_price_import_continue", async (env, action) => {
    const { wizard_id, done, total } = action.params;
    env.services.notification.add(_t("Importando partidas %s / %s", done, total), {
        type: "info",
    });
    const next = await env.services.orm.call("bc3.price.import.wizard", "action_import", [
        [wizard_id],
    ]);
    if (next && next.tag !== "bc3_price_import_continue") {
        env.services.notification.add(_t("Base de precios importada"), { type: "success" });
    }
    if (next) {
        await env.services.action.doAction(next);
    }
});
