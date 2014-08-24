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

from openerp.osv import osv, fields

class company(osv.Model):

    _inherit = 'res.company'
    
    _columns = {
        "cfdi_version": fields.selection([('3.2', 'CFDI 3.2')], 'Versión', required=True),
        "cfdi_test": fields.boolean('Timbrar en modo de prueba'),
        'cfdi_pac': fields.selection([('tralix','Tralix'), ('finkok', 'Finkok')], string="PAC"),
        "cfdi_tralix_key": fields.char("Tralix Customer Key", size=64),
        "cfdi_tralix_host": fields.char("Tralix Host", size=256),
        "cfdi_tralix_host_test": fields.char("Tralix Host Modo Pruebas", size=256),
        "cfdi_finkok_user": fields.char("Finkok user", size=64),
        "cfdi_finkok_key": fields.char("Finkok password", size=64),
        "cfdi_finkok_host": fields.char("Finkok URL Stamp", size=256),
        "cfdi_finkok_host_cancel": fields.char("Finkok URL Cancel", size=256),
        "cfdi_finkok_host_test": fields.char("Finkok URL Stamp Modo Pruebas", size=256),
        "cfdi_finkok_host_cancel_test": fields.char("Finkok URL Cancel Modo Pruebas", size=256),
        "cfdi_journal_ids": fields.many2many("account.journal", string="Diarios"),
    }
    
    _defaults = {
        'cfdi_version': '3.2',
        'cfdi_test': True,
        'cfdi_pac': 'finkok',
    }
