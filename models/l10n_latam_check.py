from odoo import api, fields, models, _
from dateutil.relativedelta import relativedelta
from odoo.exceptions import RedirectWarning, UserError
import logging

_logger = logging.getLogger(__name__)
class l10nArPaymentRegisterWithholding(models.Model):
    _inherit = 'l10n_latam.check'

    is_echeck = fields.Boolean(string='Es electrónico?')

    def _get_validation_warnings(self):
        self.ensure_one()

        warnings = []

        # ---------------------------------------------------------
        # 1. Validación de fechas
        # ---------------------------------------------------------

        # Ajustar estos nombres a los campos reales del cheque
        issue_date = self.date
        payment_date = self.payment_date

        if issue_date and payment_date:
            days = (payment_date - issue_date).days

            if days < -30:
                warnings.append(
                    "La fecha de pago es anterior en más de 30 días "
                    "a la fecha de emisión."
                )

            if days > 360:
                warnings.append(
                    "La fecha de pago supera los 360 días "
                    "desde la fecha de emisión."
                )

        # ---------------------------------------------------------
        # 2. Número de cheque duplicado
        # ---------------------------------------------------------

        if self.name and self.original_journal_id:
            duplicate = self.search([
                ("id", "!=", self.id),
                ("name", "=", self.name),
                ("company_id", "=", self.company_id.id),
                ("original_journal_id", "=", self.original_journal_id.id),
            ], limit=1)
        
            if duplicate:
                warnings.append(
                    f"El número de cheque {self.name} ya existe "
                    f"en el diario '{self.original_journal_id.display_name}'."
                )

        return warnings


class L10n_LatamPaymentRegisterCheck(models.TransientModel):
    _inherit = 'l10n_latam.payment.register.check'

    is_echeck = fields.Boolean(string='Es electrónico?')