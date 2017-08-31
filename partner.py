# -*- encoding: utf-8 -*-
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

from openerp import api,models,fields
import re

class regimen(models.Model):
    _name = "cfdi.regimen"
    
    name = fields.Char(u"Descripción", size=128, required=True)
    code = fields.Char(u"Código", required=True)
    fisica = fields.Boolean(u"Aplica para física")
    moral = fields.Boolean(u"Aplica para moral")
    fecha_inicio = fields.Date("Fecha inicio vigencia")
    

class partner(models.Model):
    _inherit = 'res.partner'
    
    regimen_id = fields.Many2one('cfdi.regimen', "Regimen Fiscal")
    metodo_pago = fields.Many2one("cfdi.formapago", string="Metodo de pago")
    no_exterior = fields.Char("No. exterior")
    no_interior = fields.Char("No. interior")
    colonia = fields.Char("Colonia")
    municipio = fields.Char("Municipio")
    usocfdi_id = fields.Many2one("cfdi.c_usocfdi", "Uso CFDI")
    
    def _check_vat_unique(self, cr, uid, ids, context=None):
        for partner in self.browse(cr, uid, ids, context=context):
            res = self.search(cr, uid, [('vat', 'ilike', partner.vat)])
            if len(res) > 1:
                return False
        return True

    def _check_vat(self, cr, uid, ids, context=None):
        for partner in self.browse(cr, uid, ids, context=context):
            if not partner.vat:
                continue
            else:
                return re.match("[A-Z&]{3,4}[0-9]{6}[A-Z&0-9]{3}", partner.vat.upper()) and True or False
        return True


    _constraints = [
            (_check_vat_unique, "Error, el RFC ya existe", ["vat"]),
            (_check_vat, "Error en la estructura del RFC. El formato esperado es: 3 o 4 caracteres, 6 digitos, 3 caracteres", ["vat"])]
