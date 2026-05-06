# -*- coding: utf-8 -*-

from odoo import api, SUPERUSER_ID
import logging
_logger = logging.getLogger(__name__)

OLD_NAME = 'account-payment-group'
NEW_NAME = 'account_payment_group'


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})

    # 1. Renombrar en ir_module_module
    cr.execute("""
        UPDATE ir_module_module
        SET name = %s
        WHERE name = %s
    """, (NEW_NAME, OLD_NAME))

    # 2. Renombrar en ir_model_data (CLAVE para no romper xml_ids)
    cr.execute("""
        UPDATE ir_model_data
        SET module = %s
        WHERE module = %s
    """, (NEW_NAME, OLD_NAME))

    # 3. (Opcional pero recomendado) logs para validar
    env.cr.execute("""
        SELECT COUNT(*) FROM ir_model_data WHERE module = %s
    """, (NEW_NAME,))
    count = env.cr.fetchone()[0]

    _logger.info(f"[MIGRATION] Renamed module '{OLD_NAME}' -> '{NEW_NAME}'")
    _logger.info(f"[MIGRATION] Updated {count} xml_ids")