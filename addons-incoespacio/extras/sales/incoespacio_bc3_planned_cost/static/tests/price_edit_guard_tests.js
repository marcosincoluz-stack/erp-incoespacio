/** @odoo-module **/

import { priceEditNeedsConfirm } from "@incoespacio_bc3_planned_cost/js/price_edit_guard";

QUnit.module("price edit guard");

QUnit.test("asks only when an existing line price changes", (assert) => {
    const data = { price_unit: 10, price_planned: 8 };
    assert.strictEqual(
        priceEditNeedsConfirm("sale.order.line", { price_unit: 12 }, data),
        "price_unit"
    );
    assert.strictEqual(
        priceEditNeedsConfirm("sale.order.line", { price_planned: 9 }, data),
        "price_planned"
    );
    assert.strictEqual(
        priceEditNeedsConfirm("sale.order.line", { price_unit: 10 }, data),
        null
    );
    assert.strictEqual(
        priceEditNeedsConfirm("sale.order.line", { price_unit: 12 }, { price_unit: 0 }),
        null
    );
    assert.strictEqual(
        priceEditNeedsConfirm(
            "sale.order.line",
            { price_unit: 12 },
            { price_unit: 10, display_type: "line_section" }
        ),
        null
    );
    assert.strictEqual(
        priceEditNeedsConfirm("sale.order.line", { product_uom_qty: 2 }, data),
        null
    );
    assert.strictEqual(
        priceEditNeedsConfirm("sale.order.line", { price_unit: 12, price_planned: 9 }, data),
        null
    );
    assert.strictEqual(
        priceEditNeedsConfirm("purchase.order.line", { price_unit: 12 }, data),
        null
    );
});
