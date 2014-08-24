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
from helpers.files import TempFileTransaction
import helpers.openssl

class certificate(osv.Model):
    _name = 'cfdi.certificate'
    
    _columns = {
        'serial': fields.char("Número de serie", size=64, required=True),
        'cer': fields.binary('Certificado', filters='*.cer,*.certificate,*.cert', required=True),
        'key': fields.binary('Llave privada', filters='*.key', required=True),
        'key_password': fields.char('Password llave', size=64, invisible=False, required=True),
        'cer_pem': fields.binary('Certificado formato PEM', filters='*.pem,*.cer,*.certificate,*.cert'),
        'key_pem': fields.binary('Llave formato PEM', filters='*.pem,*.key'),
        'pfx': fields.binary('Archivo PFX', filters='*.pfx'),
        'pfx_password': fields.char('Password archivo PFX', size=64, invisible=False),
        'start_date': fields.date('Fecha inicio', required=False),
        'end_date': fields.date('Fecha expiración', required=True),
        'company_id': fields.many2one('res.company', 'Compañía', required=True),
    }
    
    def onchange_cer(self, cr, uid, id, cer, context=None):
        if not cer:
            return {}
        tmpfiles = TempFileTransaction()
        try:
           fname_cer = tmpfiles.decode_and_save(cer)
           serial = openssl.get_serial(fname_cer)
           start_date, end_date = openssl.get_dates(fname_cer)
        finally:
            tmpfiles.clean()
        return {'value': {'serial': serial, 'start_date': start_date, 'end_date': end_date}}
    
    def button_generate_pem(self, cr, uid, id, context=None):
        certificate = self.browse(cr, uid, id)[0]
        tmpfiles = TempFileTransaction()        
        try:
            cer = tmpfiles.decode_and_save(certificate.cer)
            key = tmpfiles.decode_and_save(certificate.key)
            cer_pem = openssl.cer_to_pem(cer)
            key_pem = openssl.key_to_pem(key, certificate.key_password)
            tmpfiles.add_file(cer_pem)
            tmpfiles.add_file(key_pem)
            cer_pem_b64 = tmpfiles.load_and_encode(cer_pem)
            key_pem_b64 = tmpfiles.load_and_encode(key_pem)
        finally:
            tmpfiles.clean()
        self.write(cr, uid, id, {
            'cer_pem': cer_pem_b64,
            'key_pem': key_pem_b64
        })
        return True
        
    def button_generate_pfx(self, cr, uid, id, context=None):
        certificate = self.browse(cr, uid, id)[0]
        if not certificate.cer_pem and certificate.key_pem:
            raise osv.except_osv('Error!', "No se han subido o creado los archivos PEM")
        if not certificate.pfx_password:
            raise osv.except_osv('Error!', "Se debe definir un password para el archivo pfx")
        tmpfiles = TempFileTransaction()
        try:
            cer_pem = tmpfiles.decode_and_save(certificate.cer_pem)
            key_pem = tmpfiles.decode_and_save(certificate.key_pem)
            pfx = openssl.cer_and_key_to_pfx(cer_pem, key_pem, certificate.pfx_password)
            tmpfiles.add_file(pfx)
            pfx_b64 = tmpfiles.load_and_encode(pfx)
        finally:
            tmpfiles.clean()
        self.write(cr, uid, id, {
            'pfx': pfx_b64,
        })
        return True
        
    def _get_default_company(self, cr, uid, id, context=None):
        return self.pool.get("res.users").browse(cr, uid, uid).company_id.id
    
    _defaults = {
        'company_id': _get_default_company
    }
