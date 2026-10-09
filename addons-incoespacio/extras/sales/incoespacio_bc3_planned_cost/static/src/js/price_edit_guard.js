/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import { ConfirmationDialog } from "@web/core/confirmation_dialog/confirmation_dialog";
import { _t } from "@web/core/l10n/translation";
import { Record } from "@web/model/relational_model/record";

const PRICE_FIELDS = {
    price_unit: "el precio unitario",
    price_planned: "el precio objetivo",
};

// Solo un campo, y solo si ya había precio: la primera cifra de una línea nueva no pregunta.
export function priceEditNeedsConfirm(resModel, changes, data) {
    if (resModel !== "sale.order.line" || !changes || data?.display_type) {
        return null;
    }
    const fields = Object.keys(changes);
    if (fields.length !== 1 || !PRICE_FIELDS[fields[0]]) {
        return null;
    }
    const field = fields[0];
    const prev = Number(data[field]) || 0;
    const next = Number(changes[field]) || 0;
    if (!prev || Math.abs(prev - next) < 1e-6) {
        return null;
    }
    return field;
}

patch(Record.prototype, {
    update(changes, options) {
        const field = priceEditNeedsConfirm(this.resModel, changes, this.data);
        if (!field) {
            return super.update(changes, options);
        }
        const label = PRICE_FIELDS[field];
        return new Promise((resolve, reject) => {
            this.model.dialog.add(ConfirmationDialog, {
                title: _t("Cambiar precio"),
                body: _t(
                    "¿Seguro que quieres cambiar %s? Casi nunca hay que modificarlo.",
                    label
                ),
                confirmLabel: _t("Cambiar"),
                cancelLabel: _t("Cancelar"),
                confirm: () =>
                    Promise.resolve(super.update(changes, options)).then(resolve, reject),
                cancel: () => {
                    this.model.notify();
                    resolve();
                },
            });
        });
    },
});
