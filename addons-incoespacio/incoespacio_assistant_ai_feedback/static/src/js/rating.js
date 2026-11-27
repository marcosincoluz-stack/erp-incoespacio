/** @odoo-module **/
// Valorar las respuestas de IncoBot desde el chat: los botones van en el
// mensaje (o_incobot_rate_up/down + o_incobot_q_<id>) y el servidor repinta.
import { Message } from "@mail/core/common/message";
import { patch } from "@web/core/utils/patch";

const QUESTION = /\bo_incobot_q_(\d+)\b/;
const RATE = /\bo_incobot_rate_(up|down)\b/;

patch(Message.prototype, {
  async onClick(ev) {
    const button = ev.target.closest(".o_incobot_rate");
    const question = button && button.className.match(QUESTION);
    const rate = button && button.className.match(RATE);
    if (question && rate) {
      ev.preventDefault();
      ev.stopPropagation();
      await this.env.services.orm.call("assistant.ai.question", "rate", [parseInt(question[1]), rate[1]]);
      return;
    }
    return super.onClick(ev);
  },
});
