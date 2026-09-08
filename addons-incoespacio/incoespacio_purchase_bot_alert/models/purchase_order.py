# -*- coding: utf-8 -*-

from odoo import models, fields, api
from markupsafe import Markup


class PurchaseOrder(models.Model):
    _inherit = 'purchase.order'

    @api.model_create_multi
    def create(self, vals_list):
        purchase_orders = super().create(vals_list)

        group = self.env.ref('incoespacio_purchase_bot_alert.purchase_bot_alert_group_user', raise_if_not_found=False)
        if not group or not group.users:
            return purchase_orders

        # Identificar órdenes creadas por IncoBot (superusuario ID 1 o cron/su)
        for order in purchase_orders:
            if order.create_uid.id == 1 or self.env.su:
                partner_ids = [user.partner_id.id for user in group.users if user.partner_id]
                supplier_name = order.partner_id.name if order.partner_id else "Sin asignar"

                # 1. Mensaje en el chatter de la orden de compra con formato enriquecido
                order.message_post(
                    body=Markup(
                        f"🤖 <b>IncoBot</b>: He generado automáticamente la orden de compra "
                        f"<b>{order.name}</b> para el proveedor <b>{supplier_name}</b>."
                    ),
                    partner_ids=partner_ids,
                    subtype_xmlid='mail.mt_comment',
                )

                # 2. Programar actividad 'Por hacer' en Odoo 17 para el equipo de compras
                for user in group.users:
                    try:
                        order.activity_schedule(
                            act_type_xmlid='mail.mail_activity_data_todo',
                            summary=f"Revisar orden automática {order.name}",
                            note=f"Pedido generado automáticamente por IncoBot ({order.name}). Por favor, revisar líneas y confirmar con proveedor.",
                            user_id=user.id,
                        )
                    except Exception:
                        pass

        return purchase_orders
