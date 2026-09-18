/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import { useState } from "@odoo/owl";
import { FormController } from "@web/views/form/form_controller";

export const CHATTER_FOLD_KEY = "incoespacio.chatter.folded";

export function readChatterFolded() {
    return localStorage.getItem(CHATTER_FOLD_KEY) === "1";
}

export function writeChatterFolded(folded) {
    localStorage.setItem(CHATTER_FOLD_KEY, folded ? "1" : "0");
}

patch(FormController.prototype, {
    setup() {
        super.setup();
        this.chatterFold = useState({ folded: readChatterFolded() });
    },
    get hasChatter() {
        return Boolean(this.model?.root?.fields?.message_ids);
    },
    get className() {
        const result = super.className;
        if (this.hasChatter && this.chatterFold.folded) {
            result.o_chatter_folded = true;
        }
        return result;
    },
    toggleChatterFold() {
        this.chatterFold.folded = !this.chatterFold.folded;
        writeChatterFolded(this.chatterFold.folded);
    },
});
