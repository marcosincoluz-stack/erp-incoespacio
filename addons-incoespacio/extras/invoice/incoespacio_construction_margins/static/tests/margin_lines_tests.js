/** @odoo-module **/

import { sectionColumnSums, sectionFigure } from "@incoespacio_construction_margins/js/margin_lines";

QUnit.module("construction margin lines");

QUnit.test("sectionColumnSums adds partidas, skips nested sections", (assert) => {
    const records = [
        { id: 1, data: { display_type: "line_section", name: "C01" } },
        { id: 2, data: { price_subtotal: 10, amount_planned: 8, amount_vendor_cost: 6 } },
        { id: 3, data: { display_type: "line_section", name: "C01A", bc3_level: 1 } },
        { id: 4, data: { price_subtotal: 5, amount_planned: 4, amount_vendor_cost: 3, bc3_level: 2 } },
        { id: 5, data: { display_type: "line_section", name: "C02" } },
        { id: 6, data: { price_subtotal: 3, amount_planned: 2, amount_vendor_cost: 1 } },
    ];
    const c01 = sectionColumnSums(records, 0, [
        "price_subtotal",
        "amount_planned",
        "amount_vendor_cost",
    ]);
    assert.strictEqual(c01.price_subtotal, 15);
    assert.strictEqual(c01.amount_planned, 12);
    assert.strictEqual(c01.amount_vendor_cost, 9);
    const c02 = sectionColumnSums(records, 4, ["price_subtotal"]);
    assert.strictEqual(c02.price_subtotal, 3);
});

QUnit.test("chapter percent is money over money, not the sum of percents", (assert) => {
    const records = [
        { id: 1, data: { display_type: "line_section" } },
        {
            id: 2,
            data: {
                price_subtotal: 1000,
                amount_margin_planned: 200,
                amount_cert_origin: 400,
                amount_margin: 100,
            },
        },
        { id: 3, data: { price_subtotal: 0, amount_margin_planned: 0, amount_cert_origin: 0, amount_margin: 0 } },
    ];
    assert.strictEqual(sectionFigure(records, 0, "price_subtotal"), 1000);
    assert.strictEqual(sectionFigure(records, 0, "margin_percent_planned"), 20);
    assert.strictEqual(sectionFigure(records, 0, "progress_percent"), 40);
    assert.strictEqual(sectionFigure(records, 0, "margin_percent"), 25);
});
