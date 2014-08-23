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
import base64
from datetime import date, datetime
from calendar import monthrange

class reporte_mensual_wizard(osv.TransientModel):

    _name = 'cfdi.reporte.mensual.wizard'
    
    
    def _invoice_to_txt(self, invoice):
        campos = [
            invoice.partner_id.vat or '',
            invoice.serie or '',
            invoice.internal_number,
            str(invoice.anoAprobacion)+str(invoice.noAprobacion),
            invoice.date_invoice,
            "%.2f"%invoice.amount_total,
            "%.2f"%invoice.amount_tax,
            (invoice.state == 'cancel' and '0') or '1',
            (invoice.type == 'out_invoice' and 'I') or (invoice.type == 'out_refund' and 'E'),
            '',
            '',
            ''
        ]
        return '|' + '|'.join(campos) + '|'

    def action_reporte(self, cr, uid, ids, context=None):
        this = self.browse(cr, uid, ids)[0]
        txt = "hola"
        out = base64.encodestring(txt)
        vat = self.pool.get("res.users").browse(cr, uid, uid).partner_id.vat
        fname = "1%s%02d%4d"%(vat, this.mes, this.ano)
        fecha_inicio = "%d-%02d-01"%(this.ano, this.mes)
        ultimo_dia_mes = monthrange(this.ano, this.mes)[1]
        fecha_fin = "%d-%02d-%d"%(this.ano, this.mes, ultimo_dia_mes)
        invoices = self.pool.get('account.invoice').search(cr, uid, [
            ('date_invoice', '>=', fecha_inicio),
            ('date_invoice', '<=', fecha_fin),
            ('state', 'in', ['cancel','open','paid'])
            ])
        txt = ''
        for invoice in self.pool.get('account.invoice').browse(cr, uid, invoices):
            txt += self._invoice_to_txt(invoice) + "\n"
        out = base64.encodestring(txt)
        self.write(cr, uid, ids, {'state':'get', 'data':out, 'fname': fname}, context=context)
        return {
            'type': 'ir.actions.act_window',
            'name': 'Reporte mensual SAT',
            'res_model': 'cfdi.reporte.mensual.wizard',
            'view_mode': 'form',
            'view_type': 'form',
            'res_id': this.id,
            'views': [(False, 'form')],
            'target': 'new',
        }
        
    _columns = {
        'state': fields.selection((
          ('choose','choose'),  # escoger periodo
          ('get','get'),        # obtener archivo
        )),
        'mes': fields.selection([
            (1,'Enero'),
            (2,'Febrero'),
            (3,'Marzo'),
            (4,'Abril'),
            (5,'Mayo'),
            (6,'Junio'),
            (7,'Julio'),
            (8,'Agosto'),
            (9,'Septiembre'),
            (10,'Octubre'),
            (11,'Noviembre'),
            (12,'Diciembre'),
        ], string="Mes"),
        'ano': fields.integer("Año"),
        'data': fields.binary('Archivo', readonly=True),
        'fname': fields.char("Nombre", size=128)
    }
    
    _defaults = {
        'state' : 'choose',
        'mes': 1,
        'ano': lambda *a: int(date.today().strftime("%Y"))  
    }
    
    
