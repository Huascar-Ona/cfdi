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

class regimen(osv.Model):
    _name = "cfdi.regimen"
    
    _columns = {
        'name': fields.char("Regimen Fiscal", size=128),
    }
    
regimen()

class partner(osv.Model):

    _inherit = 'res.partner'
    
    _columns = {
        'regimen_id': fields.many2one('cfdi.regimen', "Regimen Fiscal"),
        'metodo_pago': fields.many2one("cfdi.formapago", string="Metodo de pago"),
    }
    
partner()
