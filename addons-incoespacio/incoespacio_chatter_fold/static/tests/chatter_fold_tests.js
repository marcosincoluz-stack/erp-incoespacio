/** @odoo-module **/

import {
    CHATTER_FOLD_KEY,
    readChatterFolded,
    writeChatterFolded,
} from "@incoespacio_chatter_fold/js/chatter_fold";

QUnit.module("chatter fold", {
    afterEach() {
        localStorage.removeItem(CHATTER_FOLD_KEY);
    },
});

QUnit.test("read/write localStorage", (assert) => {
    localStorage.removeItem(CHATTER_FOLD_KEY);
    assert.strictEqual(readChatterFolded(), false);
    writeChatterFolded(true);
    assert.strictEqual(readChatterFolded(), true);
    writeChatterFolded(false);
    assert.strictEqual(readChatterFolded(), false);
});
