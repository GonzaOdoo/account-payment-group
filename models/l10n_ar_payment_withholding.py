from odoo import api, fields, models

class l10nArPaymentRegisterWithholding(models.Model):
    _inherit = 'l10n_ar.payment.withholding'
    
    currency_id = fields.Many2one(related='multiple_payment_id.currency_id',string ="Divisa")
    multiple_payment_id = fields.Many2one('account.payment.group', required=False, ondelete='cascade')
    payment_id = fields.Many2one('account.payment', required=False, ondelete='cascade')
