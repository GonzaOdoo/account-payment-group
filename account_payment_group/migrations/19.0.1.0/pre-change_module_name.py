# -*- coding: utf-8 -*-
from odoo.upgrade import util
from odoo import api, SUPERUSER_ID

import logging
_logger = logging.getLogger(__name__)


def migrate(cr, version):
    _logger.info(   "Running post-migration script for %s", version)
    util.rename_module(cr, 'account-payment-group', 'account_payment_group')