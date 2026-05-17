# -*- coding: utf-8 -*-

from . import models
from . import views

from odoo import api, SUPERUSER_ID

def create_sequences(env):
    companies = env['res.company'].search([])
    
    for company in companies:
        # Crear la secuencia para Recibo de pagos
        env['ir.sequence'].create({
            'name': 'Recibo de pagos - ' + company.name,
            'code': 'recibo_de_pagos',
            'prefix': 'RP-',
            'padding': 8,
            'number_next': 1,
            'number_increment': 1,
            'company_id': company.id,
        })
        
        # Crear la secuencia para Reporte de Pagos
        env['ir.sequence'].create({
            'name': 'Reporte de Pagos - ' + company.name,
            'code': 'reporte_de_pagos',
            'prefix': 'OP-',
            'padding': 8,
            'number_next': 1,
            'number_increment': 1,
            'company_id': company.id,
        })

    server_action = env.ref('account-payment-group.action_create_payment_group_from_invoice', raise_if_not_found=False)
    if server_action:
        server_action.create_action()