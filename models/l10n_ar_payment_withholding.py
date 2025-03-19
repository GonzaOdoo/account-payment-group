from odoo import api, fields, models

class l10nArPaymentRegisterWithholding(models.Model):
    _inherit = 'l10n_ar.payment.withholding'
    
    currency_id = fields.Many2one(related='multiple_payment_id.currency_id',string ="Divisa")
    multiple_payment_id = fields.Many2one('account.payment.group', required=False, ondelete='cascade')
    payment_id = fields.Many2one('account.payment', required=False, ondelete='cascade')

class AccountMoveLine(models.Model):
    _inherit = 'account.move.line'

    payment_group_id = fields.Many2one(
        comodel_name='account.payment.group',  # Apunta al modelo 'account.payment.multiplemethods'
        string='Payment group',
        related='move_id.payment_id.multiple_payment_id',
        store=True,  # Opcional, solo si deseas almacenarlo en la base de datos para búsqueda y filtrado
        readonly=True,  # Opcional, evita modificaciones manuales
        help='Selecciona el registro de pago múltiple relacionado.'
    )