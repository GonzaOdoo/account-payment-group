from odoo import models, fields, api
from odoo.exceptions import UserError

class AccountPaymentSelectionWizard(models.TransientModel):
    _name = 'account.payment.selection.wizard'
    _description = 'Seleccionar Pagos No Conciliados'

    payment_group_id = fields.Many2one('account.payment.group', string="Grupo de Pagos", required=True)
    payment_ids = fields.Many2many('account.payment', string="Pagos No Conciliados")

    @api.model
    def default_get(self, fields_list):
        """ Obtiene los pagos no conciliados del mismo partner para el wizard. """
        res = super().default_get(fields_list)
        payment_group_id = self.env.context.get('active_id')
        if not payment_group_id:
            return res
        
        payment_group = self.env['account.payment.group'].browse(payment_group_id)
        if not payment_group.partner_id:
            raise UserError("Debe seleccionar un contacto antes de agregar pagos.")

        payments = self.env['account.payment'].search([
            ('partner_id', '=', payment_group.partner_id.id),
            ('state', '!=', 'reconciled'),
            ('company_id', '=', payment_group.company_id.id),
            ('partner_type', '=', payment_group.partner_type),
            ('payment_type', '=', 'inbound' if payment_group.partner_type == 'customer' else 'outbound')
        ])

        res.update({'payment_ids': [(6, 0, payments.ids)], 'payment_group_id': payment_group.id})
        return res

    def confirm_selection(self):
        """ Agrega los pagos seleccionados al grupo de pagos """
        self.ensure_one()
        if not self.payment_ids:
            raise UserError("No ha seleccionado ningún pago.")

        self.payment_group_id.to_pay_payment_ids = [(4, payment.id) for payment in self.payment_ids]

        self.payment_group_id.message_post(
            body=f"Se han agregado {len(self.payment_ids)} pagos no conciliados a la lista.",
            subject="Pagos No Conciliados Agregados",
            message_type='comment',
            subtype_xmlid='mail.mt_comment'
        )

        return {'type': 'ir.actions.act_window_close'}
