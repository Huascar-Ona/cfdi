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
{
    'name' : 'Factura Electronica (CFDI)',
    'version' : '1.0',
    'author' : 'Zenpar',
    'website' : 'http://www.zeval.com.mx',
    'category' : 'Invoicing',
    'depends' : ['account', 'sale', 'document'],
    'description': """

    """,
    'init_xml': [
        'security/cfdi_groups.xml',
        'security/ir.model.access.csv'
    ],
    'data': [
        'res_company_view.xml',
        'certificate_view.xml',
        'invoice_view.xml',
        'partner_view.xml',
        'account_journal_view.xml',
        #'aprobacion_view.xml',
        'wizard/reporte_mensual_wizard_view.xml',
        'account_view.xml'
    ],
    'demo': [],
    'test': [],
    'installable': True,
    'auto_install': False,
    'images': [],
}
