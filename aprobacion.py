# -*- encoding: utf-8 -*-
############################################################################
#    Module for OpenERP, Open Source Management Solution
#
#    Copyright (c) 2013 Zenpar - http://www.zeval.com.mx/
#    All Rights Reserved.
############################################################################
#    Coded by: jsolorzano@zeval.com.mx
#    Manager: Orlando Zentella ozentella@zeval.com.mx
############################################################################
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU Affero General Public License as
#    published by the Free Software Foundation, either version 3 of the
#    License, or (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU Affero General Public License for more details.
#
#    You should have received a copy of the GNU Affero General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
##############################################################################


from openerp.osv import osv, fields

class ir_sequence(osv.Model):
    _inherit = 'ir.sequence'
    
    _columns = {
        'aprobacion_ids': fields.one2many("cfdi.aprobacion", 'sequence_id', 'Aprobaciones')
    }

class aprobacion(osv.Model):
    _name = 'cfdi.aprobacion'
    
    _columns = {
        'anoAprobacion': fields.integer("Año de aprobación", required=True),
        'noAprobacion': fields.char("No. de aprobación", required=True),
        'serie': fields.char("Serie", size=8),
        'del': fields.integer("Del", required=True),
        'al': fields.integer("Al", required=True),
        'sequence_id': fields.many2one("ir.sequence", "Secuencia", required=True)
    }
    
aprobacion()
