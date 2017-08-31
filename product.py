# -*- coding: utf-8 -*-
from openerp import api,fields,models

class product_category(models.Model):
    _inherit = "product.category"

    code_sat = fields.Many2one("cfdi.c_claveprodserv", string=u"Catálogo SAT")

class product_template(models.Model):
    _inherit = "product.template"

    code_sat = fields.Many2one("cfdi.c_claveprodserv", string=u"Catálogo SAT")

class product_uom(models.Model):
    _inherit = "product.uom"

    code_sat = fields.Many2one("cfdi.c_claveunidad", string=u"Catálogo SAT")
