from odoo import api, fields, models, _
from dateutil.relativedelta import relativedelta
from odoo.exceptions import RedirectWarning, UserError
import logging

_logger = logging.getLogger(__name__)
class l10nArPaymentRegisterWithholding(models.Model):
    _inherit = 'l10n_latam.check'

    is_echeck = fields.Boolean(string='Es electrónico?')


class L10n_LatamPaymentRegisterCheck(models.TransientModel):
    _inherit = 'l10n_latam.payment.register.check'

    is_echeck = fields.Boolean(string='Es electrónico?')