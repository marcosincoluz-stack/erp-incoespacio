/** @odoo-module **/

import {
    addedLineLevel,
    createContext,
    foldedHiddenIds,
    cumulativeSalePercent,
    formatShare,
    lineAmount,
    sectionDisplayColumns,
    sectionFieldTotal,
    sectionTotal,
} from "@incoespacio_section_fold/js/section_fold";

QUnit.module("section fold");

QUnit.test("lineAmount prefers price_subtotal then amount_origin", (assert) => {
    assert.strictEqual(lineAmount({ display_type: "line_section", price_subtotal: 99 }), 0);
    assert.strictEqual(lineAmount({ price_subtotal: 10.5 }), 10.5);
    assert.strictEqual(lineAmount({ amount_origin: 7 }), 7);
    assert.strictEqual(lineAmount({ price_unit: 2, product_uom_qty: 4 }), 8);
});

QUnit.test("chapter row puts sale and invoiced under those columns", (assert) => {
    const active = [
        { widget: "handle", name: "sequence", type: "field" },
        { name: "product_id", type: "field" },
        { name: "name", type: "field" },
        { name: "product_uom_qty", type: "field" },
        { name: "price_subtotal", type: "field" },
        { name: "amount_cert_origin", type: "field" },
        { name: "price_total", type: "field" },
    ];
    const cols = sectionDisplayColumns(active, "name");
    const span = cols.reduce((n, col) => n + (col.colspan || 1), 0);
    assert.strictEqual(span, active.length);
    assert.strictEqual(cols[1].name, "name");
    assert.strictEqual(cols[1].colspan, 3);
    assert.strictEqual(cols[2].sumField, "price_subtotal");
    assert.strictEqual(cols[3].sumField, "amount_cert_origin");
    assert.strictEqual(cols[4].id, "section_pad_6");
    const records = [
        { data: { display_type: "line_section", bc3_level: 0 } },
        { data: { price_subtotal: 100, amount_cert_origin: 40, bc3_level: 1 } },
        { data: { display_type: "line_section", bc3_level: 1 } },
        { data: { price_subtotal: 50, amount_cert_origin: 10, bc3_level: 2 } },
    ];
    assert.strictEqual(sectionFieldTotal(records, 0, "amount_cert_origin"), 50);
    assert.strictEqual(sectionFieldTotal(records, 2, "amount_cert_origin"), 10);
    assert.strictEqual(sectionFieldTotal(records, 0, "price_subtotal"), 150);
});

QUnit.test("sorted sale share accumulates partidas and chapters to 100", (assert) => {
    const records = [
        { id: 1, data: { display_type: "line_section", bc3_level: 0, sequence: 1 } },
        { id: 2, data: { price_subtotal: 200, sequence: 2, bc3_level: 1 } },
        { id: 3, data: { display_type: "line_section", bc3_level: 1, sequence: 3 } },
        { id: 4, data: { price_subtotal: 50, sequence: 4, bc3_level: 2 } },
        { id: 5, data: { display_type: "line_section", bc3_level: 0, sequence: 5 } },
        { id: 6, data: { price_subtotal: 750, sequence: 6, bc3_level: 1 } },
    ];
    const shown = [records[5], records[1], records[3], records[0], records[4], records[2]];
    const pct = cumulativeSalePercent(shown);
    assert.strictEqual(pct.get(6), 75);
    assert.strictEqual(pct.get(2), 95);
    assert.strictEqual(pct.get(4), 100);
    assert.strictEqual(pct.get(1), 25);
    assert.strictEqual(pct.get(5), 100);
    assert.strictEqual(pct.get(3), 5);
    assert.strictEqual(formatShare(20), "20%");
    assert.strictEqual(formatShare(12.5), "12.5%");
    const active = [
        { widget: "handle", name: "sequence", type: "field" },
        { name: "name", type: "field" },
        { name: "price_subtotal", type: "field" },
        { name: "amount_cert_origin", type: "field" },
        { id: "sale_share", name: "display_type", type: "field" },
    ];
    const cols = sectionDisplayColumns(active, "name");
    const span = cols.reduce((n, col) => n + (col.colspan || 1), 0);
    assert.strictEqual(span, active.length);
    assert.strictEqual(cols[cols.length - 1].id, "sale_share");
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

QUnit.test("new partida nests under the open section", (assert) => {
    const chapter = [{ data: { display_type: "line_section", bc3_level: 0 } }];
    assert.strictEqual(addedLineLevel(chapter, {}), 1);
    const sub = chapter.concat([{ data: { display_type: "line_section", bc3_level: 1 } }]);
    assert.strictEqual(addedLineLevel(sub, {}), 2);
    assert.strictEqual(addedLineLevel([], {}), null);
    assert.strictEqual(
        addedLineLevel(chapter, { default_display_type: "line_section", default_bc3_level: 1 }),
        1
    );
    assert.strictEqual(addedLineLevel(chapter, { default_display_type: "line_note" }), null);
});

QUnit.test("subchapter button context stays a section", (assert) => {
    const ctx = createContext(
        "{'default_display_type': 'line_section', 'default_bc3_level': 1}"
    );
    assert.strictEqual(ctx.default_display_type, "line_section");
    assert.strictEqual(ctx.default_bc3_level, 1);
    assert.strictEqual(addedLineLevel([], ctx), 1);
});
