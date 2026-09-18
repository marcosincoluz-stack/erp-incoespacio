/** @odoo-module **/

import {
    foldedHiddenIds,
    lineAmount,
    sectionTotal,
} from "@incoespacio_section_fold/js/section_fold";

QUnit.module("section fold");

QUnit.test("lineAmount prefers price_subtotal then amount_origin", (assert) => {
    assert.strictEqual(lineAmount({ display_type: "line_section", price_subtotal: 99 }), 0);
    assert.strictEqual(lineAmount({ price_subtotal: 10.5 }), 10.5);
    assert.strictEqual(lineAmount({ amount_origin: 7 }), 7);
    assert.strictEqual(lineAmount({ price_unit: 2, product_uom_qty: 4 }), 8);
});

QUnit.test("fold C01 hides partidas, not C02; total is the sum", (assert) => {
    const records = [
        { id: 1, data: { display_type: "line_section", name: "C01" } },
        { id: 2, data: { price_subtotal: 10 } },
        { id: 3, data: { price_subtotal: 5 } },
        { id: 4, data: { display_type: "line_section", name: "C02" } },
        { id: 5, data: { price_subtotal: 3 } },
    ];
    assert.strictEqual(sectionTotal(records, 0), 15);
    assert.strictEqual(sectionTotal(records, 3), 3);
    const hidden = foldedHiddenIds(records, { 1: true }, false);
    assert.ok(hidden.has(2) && hidden.has(3));
    assert.notOk(hidden.has(4) || hidden.has(5) || hidden.has(1));
    assert.strictEqual(foldedHiddenIds(records, { 1: true }, true).size, 0);
});

QUnit.test("nested C01A folds inside C01; sibling partida stays", (assert) => {
    const records = [
        { id: 1, data: { display_type: "line_section", name: "C01", bc3_level: 0 } },
        { id: 2, data: { display_type: "line_section", name: "C01A", bc3_level: 1 } },
        { id: 3, data: { price_subtotal: 10, bc3_level: 2 } },
        { id: 4, data: { price_subtotal: 8, bc3_level: 1 } },
        { id: 5, data: { display_type: "line_section", name: "C02", bc3_level: 0 } },
        { id: 6, data: { price_subtotal: 3, bc3_level: 1 } },
    ];
    assert.strictEqual(sectionTotal(records, 0), 21);
    assert.strictEqual(sectionTotal(records, 1), 10);
    const hideParent = foldedHiddenIds(records, { 1: true }, false);
    assert.ok(hideParent.has(2) && hideParent.has(3) && hideParent.has(4));
    assert.notOk(hideParent.has(5) || hideParent.has(6));
    const hideSub = foldedHiddenIds(records, { 2: true }, false);
    assert.ok(hideSub.has(3));
    assert.notOk(hideSub.has(4) || hideSub.has(2) || hideSub.has(5));
});
