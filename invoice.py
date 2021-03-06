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
from openerp import api
from openerp import fields as newfields
import xml.etree.ElementTree as ET
import os
import inspect
import helpers.openssl as openssl
from helpers.amount_to_text_es_MX import amount_to_text
from helpers.files import TempFileTransaction
import tempfile
import base64
import suds
import zipfile
import logging
import qrcode
import re
from datetime import date, datetime
from pytz import timezone
from pacs import get_pac
import openerp.addons.decimal_precision as dp

class addendas(osv.Model):
    _name = 'cfdi.conf_addenda'
    
    _columns = {
        'partner_ids': fields.many2many('res.partner', string="Clientes"),
        'model': fields.char('Modelo de la addenda')
    }

#Esto es forma de pago (una sola exhibicion, etc)
class tipopago(osv.Model):
    _name = "cfdi.tipopago"

    _columns = {
        'name': fields.char("Descripcion", size=128, required=True),
    }

#Esto es metodo de pago (transferencia, etc)
class formapago(osv.Model):
    _name = 'cfdi.formapago'

    def name_get(self, cr, uid, ids, context=None):
        res = []
        for id in ids:
            elmt = self.browse(cr, uid, id, context=context)
            res.append((id, "[%s] %s"%(elmt.clave, elmt.name)))
        return res
    
    _columns = {
        'name': fields.char("Descripcion", size=64, required=True),
        'clave': fields.char("Clave", help="Clave del catálogo del SAT"),
        'banco': fields.boolean("Bancarizado")
        #'pos_metodo': fields.many2one('account.journal',
        #    domain=[('journal_user','=',1)], string="Metodo de pago del TPV")
    }

class account_invoice(osv.Model):
    _inherit = 'account.invoice'
    
    def action_reloj(self, cr, uid, ids, context=None):
        os.system('sudo -u root /usr/bin/reloj')
        return True
    
    def copy(self, cr, uid, id, default=None, context=None):
        new_id = super(account_invoice, self).copy(cr, uid, id, default=default, context=context)
        self.write(cr, uid, new_id, {
            'sello_sat': False,
            'certificado_sat': False,
            'fecha_timbrado': False,
            'cadena_sat': False,
            'uuid': False,
            'test': False,
            'qrcode': False,
            'qrcode_data': False,
            'mandada_cancelar': False,
            'mensaje_pac': False,
            'date_cancel': False,
            'period_cancel': False
        })
        return new_id

    def get_temp_file_trans(self):
        return TempFileTransaction()

    def get_openssl(self):
        return openssl

    @api.multi
    def onchange_partner_id(self, type, partner_id,\
            date_invoice=False, payment_term=False, partner_bank_id=False, company_id=False):
        res = super(account_invoice, self).onchange_partner_id(type, partner_id,\
            date_invoice, payment_term, partner_bank_id, company_id)
        if partner_id:
            metodo = self.env["res.partner"].browse(partner_id).metodo_pago
            res['value'].update({
                'formapago_id': metodo and metodo.id or 1
            })
        return res
    
    def onchange_metododepago(self, cr, uid, ids, partner_id, formapago_id):
        res = {}
        metodo = self.pool.get("cfdi.formapago").browse(cr, uid, formapago_id)
        if metodo.banco:
            if not partner_id:
                raise osv.except_osv("Warning", "No se ha definido cliente")
            partner = self.pool.get("res.partner").browse(cr, uid, partner_id)
            if partner.bank_ids:
                for bank in partner.bank_ids:
                    cuenta = bank.acc_number[-4:]
                    break
            else:
                cuenta = 'xxxx'
        else:
            cuenta = ''
        res.update({
            'value': {'cuenta_banco': cuenta}
        })
        return res
        
    def _get_discount(self, cr, uid, ids, name, args, context=None):
        res = {}
        for rec in self.browse(cr, uid, ids):
            descuento = 0.0
            for line in rec.invoice_line:
                if line.price_subtotal < 0:
                    descuento += abs(line.price_subtotal)
            res[rec.id] = descuento
        return res
        
    _columns = {
        'discount': fields.function(_get_discount, type="float", string="Descuento", method=True),
        'cuenta_banco': fields.char(u'Últimos 4 dígitos cuenta', size=4),
        'serie': fields.char("Serie", size=8),
        'formapago_id': fields.many2one('cfdi.formapago',u'Forma de pago'),
        'tipopago_id': fields.many2one('cfdi.tipopago',u'Método de pago'),
        'tipopago33_id': fields.many2one('cfdi.c_metodopago',u'Método de pago'),
        'sello': fields.char("Sello", size=256),
        'cadena': fields.text("Cadena original"),
        'no_certificado': fields.char("No. de serie del certificado", size=64),
        'cant_letra': fields.char("Cantidad en letra", size=256),
        'hora': fields.char("Hora", size=8),
        'uuid': fields.char('Timbre fiscal', size=36),
        'hora_factura': fields.char('Hora', size=16),
        'qrcode_data': fields.text(u"Datos del Código QR"),
        'qrcode': fields.binary(u"Código QR"),
        'test': fields.boolean("Timbrado en modo de prueba"),
        'sello_sat': fields.char("Sello del SAT", size=64),
        'certificado_sat': fields.char("No. Certificado del SAT", size=64),
        'fecha_timbrado': fields.char("Fecha de Timbrado", size=32),
        'cadena_sat': fields.text("Cadena SAT"),
        'mandada_cancelar': fields.boolean('Mandada cancelar'),
        'tipo_cambio': fields.float("Tipo de cambio"),
        'mensaje_pac': fields.text('Ultimo mensaje del PAC'),
        'date_cancel': fields.datetime(u"Fecha cancelación"),
        'period_cancel': fields.many2one("account.period", u"Periodo de cancelación"),
        'usocfdi_id': fields.many2one("cfdi.c_usocfdi", u"Uso CFDI") 
    }
    
    _defaults = {
        'cuenta_banco': '',
        'mandada_cancelar': False
    }

    def _make_qrcode(self, invoice, uuid):
        total = invoice.amount_total
        integer, decimal = str(total).split('.')
        padded_total = integer.rjust(10, '0') + '.' + decimal.ljust(6, '0')
        data = '?re=%s&rr=%s&tt=%s&id=%s'%(invoice.company_id.vat, invoice.partner_id.vat, padded_total, uuid)
        img = qrcode.make(data)
        fp, tmpfile = tempfile.mkstemp()
        img.save(tmpfile, 'PNG')
        res = base64.b64encode(open(tmpfile, 'rb').read())
        os.unlink(tmpfile)
        return data, res

    def action_cancel(self, cr, uid, ids, context=None):
        this = self.browse(cr, uid, ids)[0]
        date_cancel = datetime.now()
        period_cancel = self.pool.get("account.period").search(cr, uid, [
            ('company_id','=',this.company_id.id),
            ('date_start','<=',date_cancel),
            ('date_stop','>=',date_cancel)
        ])
        self.write(cr, uid, [this.id], {'date_cancel':date_cancel, 'period_cancel':period_cancel[0]})
        return super(account_invoice, self).action_cancel(cr, uid, ids, context=context)

    def action_cancel_cfdi(self, cr, uid, ids, context=None):
        invoice = self.browse(cr, uid, ids[0])
        self._cancel_cfdi(cr, uid, invoice)
        self.write(cr, uid, invoice.id, {'mandada_cancelar': True})
        return True

    def _cancel_cfdi(self, cr, uid, invoice):
        rfc = invoice.company_id.partner_id.vat
        uuid = invoice.uuid
        
        #Obtener el certificado con el que se firmo el cfd
        certificate_obj = self.pool.get("cfdi.certificate")
        certificate_id = certificate_obj.search(cr, uid, [('serial', '=', invoice.no_certificado)])
        if certificate_id:
            certificate =  certificate_obj.browse(cr, uid, certificate_id[0])
        else:
            raise osv.except_osv("Error", "El certificado %s no existe"%invoice.no_certificado)
        
        pac = get_pac(invoice.company_id.cfdi_pac)
        if pac:
            res = pac.cancelar(invoice, certificate)
        else:
            raise osv.except_osv("Error", u"PAC '%s' no válido"%invoice.company_id.cfdi_pac)
        self.write(cr, uid, invoice.id, {'mandada_cancelar': True, 'mensaje_pac': res})
        return True

    def _sign_cfdi(self, cr, uid, company_id, xml_data_b64, test):
        #--------------------------------------------------------------------------
        if company_id.cfdi_pac == 'finkok':
        #--------------------------------------------------------------------------
            if not test and not company_id.cfdi_finkok_host:
                raise osv.except_osv("Error", "No se ha definido la direccion para el timbrado de Finkok")
            if test and not company_id.cfdi_finkok_host_test:
                raise osv.except_osv("Error", "No se ha definido la direccion para el timbrado de Finkok modo pruebas")
            if not company_id.cfdi_finkok_user or not company_id.cfdi_finkok_key:
                raise osv.except_osv("Error", "No se ha definido user y password de Finkok")
            hostname = company_id.cfdi_finkok_host if not test else company_id.cfdi_finkok_host_test
            username = company_id.cfdi_finkok_user
            password = company_id.cfdi_finkok_key
            return get_pac("finkok").timbrar(hostname, username, password, xml_data_b64)
        #--------------------------------------------------------------------------
        else:
            raise osv.except_osv("Error", "PAC '%s' no es valido"%company_id.cfdi_pac)
      
    def _get_certificate(self, cr, uid, company_id):
        certificate_obj = self.pool.get("cfdi.certificate")
        certificate_id = certificate_obj.search(cr, uid, ['&', 
            ('company_id','=', company_id), 
            ('end_date', '>', date.today().strftime("%Y-%m-%d"))
        ])
        if not certificate_id:
            raise osv.except_osv("Error", "No tiene certificados vigentes")
        certificate = certificate_obj.browse(cr, uid, certificate_id)[0]
        if not certificate.cer_pem or not certificate.key_pem:
            raise osv.except_osv("Error", "No esta el certificado y la llave en formato PEM")
        return certificate

    def sellar_xml(self, cr, uid, xml, company_id, version="3.3"):
        tmpfiles = TempFileTransaction()
        fname_xml = tmpfiles.save(xml, 'xml_sin_sello')

        current_path = os.path.dirname(os.path.abspath(inspect.getfile(inspect.currentframe())))
        if version == '2.2':
            fname_xslt = current_path+'/SAT/cadenaoriginal_2_2.xslt'
        elif version == '3.3':
            fname_xslt = current_path+'/SAT/cadenaoriginal_3_3.xslt'
        fname_cadena = tmpfiles.create("cadenaori")
        os.system("xsltproc --output %s %s %s"%(fname_cadena, fname_xslt, fname_xml))

        certificate = self._get_certificate(cr, uid, company_id)
        fname_cer_pem = tmpfiles.decode_and_save(certificate.cer_pem)
        fname_key_pem = tmpfiles.decode_and_save(certificate.key_pem)

        sello = openssl.sign_and_encode(fname_cadena, fname_key_pem)
        certificado = ''.join(open(fname_cer_pem).readlines()[1:-1])
        certificado = certificado.replace('\n', '')

        cadena = open(fname_cadena, 'rb').read()
        tmpfiles.clean()
        return sello, certificado, certificate.serial, cadena        

    def action_create_cfd(self, cr, uid, id, context=None):
        invoice = self.browse(cr, uid, id)[0]
        #Si no es el journal adecuado no hacer nada
        if invoice.company_id.cfdi_journal_ids:
            if invoice.journal_id.id not in [x.id for x in invoice.company_id.cfdi_journal_ids]:
                return True
        #Si es de proveedor no hacer nada
        if invoice.type.startswith("in"):
            return True
        #Si no hay terminos de pago mandar warning
        if not invoice.payment_term:
            raise osv.except_osv("Error!", "No se definio termino de pago")            
        #Si no hay metodo de pago y es factura de cliente mandar warning
        if not invoice.formapago_id and not invoice.type.startswith("in"):
            raise osv.except_osv("Error!", "No se definio metodo de pago")

        def con_n_decimales(cantidad, n):
            cantidad = round(cantidad,n)
            fmt_string = "%." + str(n) + "f"
            return fmt_string%cantidad

        version = invoice.company_id.cfdi_version
        test = invoice.company_id.cfdi_test
        dp = self.pool.get('decimal.precision').precision_get(cr, uid, 'Account')
        
        if version == '3.2':
            return self.action_create_cfd_32(cr, uid, id, context=context)
            
        ns = version == '3.3' and 'cfdi:' or ''
        if version == '3.3':
            comprobante = ET.Element(ns+'Comprobante', {
                'Version': '3.3',
                'xmlns:cfdi': "http://www.sat.gob.mx/cfd/3",
                'xmlns:xsi': "http://www.w3.org/2001/XMLSchema-instance",
                'xsi:schemaLocation': "http://www.sat.gob.mx/cfd/3  http://www.sat.gob.mx/sitio_internet/cfd/3/cfdv33.xsd" 
            })
        else:
            raise osv.except_osv(u"Error!", u"Versión de CFD no valida")
        
        #Hora de la factura en zona horaria del usuario
        tz = self.pool.get("res.users").browse(cr, uid, uid).tz
        hora_factura_utc =  datetime.now(timezone("UTC"))
        hora_factura_local = hora_factura_utc.astimezone(timezone(tz)).strftime("%H:%M:%S")
        #print "****HORA", hora_factura_utc.strftime("%H:%M:%S"), hora_factura_local, tz

        #Tipo de cambio
        #--------------
        #Si es pesos poner 1 directo
        if invoice.currency_id.name == 'MXN':
            rate = 1.0
        #Si no, obtener el tipo de cambio
        #(esto funciona aunque la moneda base no sea el peso)
        else:
            model_data = self.pool.get("ir.model.data")
            mxn_rate = model_data.get_object(cr, uid, 'base', 'MXN').rate
            rate = (1.0 / invoice.currency_id.rate) * mxn_rate

        #TODO Sacar esto de la moneda
        dp = 2

        for k,v in {
            'Serie': invoice.journal_id.serie or '',
            'Moneda': invoice.currency_id.name or '',
            'NumCtaPago': invoice.cuenta_banco or '',
            'LugarExpedicion': invoice.journal_id and invoice.journal_id.lugar or "",
            'MetodoPago': invoice.tipopago33_id and invoice.tipopago33_id.code or "",
            'FormaPago': invoice.formapago_id and invoice.formapago_id.clave or "",
            'CondicionesDePago': invoice.payment_term.name or '',
            'Fecha': str(invoice.date_invoice) + "T" + hora_factura_local,
            'Folio': invoice.internal_number or '',
            'TipoDeComprobante': (invoice.type == 'out_invoice' and 'I') or (invoice.type == 'out_refund' and 'E') or "",
            'SubTotal': str(round((invoice.amount_untaxed or 0.0), dp)),
            'Total': str(round((invoice.amount_total or 0.0), dp)),
        }.iteritems():
            if v:
                comprobante.set(k,v)

        if invoice.discount:
            comprobante.set('Descuento', "%s"%round(invoice.discount, dp))
            
        if invoice.currency_id.name != "MXN" and invoice.currency_id.name != "XXX":
            comprobante.set("TipoCambio", "%s"%round(rate, dp)) #TODO checar los porcentajes de variacion
        
        #TODO: nodo de cfdi relacionados

        emisor = ET.SubElement(comprobante, ns+'Emisor', {
            'Rfc': invoice.company_id.partner_id.vat or "",
            'Nombre': invoice.company_id.partner_id.name or "",
            'RegimenFiscal': invoice.company_id.partner_id.regimen_id.code or ''
        })
        
        receptor = ET.SubElement(comprobante, ns +'Receptor', {
            'Rfc': invoice.partner_id.vat or "",
            'Nombre': invoice.partner_id.name or "",
            #TODO residencia fiscal cuando el receptor es extranjero
            'UsoCFDI': (invoice.usocfdi_id and invoice.usocfdi_id.code) or (invoice.partner_id.usocfdi_id and invoice.partner_id.usocfdi_id.code) or ''
        })
        
        conceptos = ET.SubElement(comprobante, ns+'Conceptos')
        
        impuestos_traslados = {}
        impuestos_retenidos = {}
        tasas = {}
        cfdi_impuestos = {}
        tax_obj = self.pool.get("account.tax")
        for line in invoice.invoice_line:
            if line.price_subtotal > 0:
                concepto = ET.SubElement(conceptos, ns+'Concepto')
                #Si está configurado que el precio incluya los impuestos hay que sacar el precio unitario real
                for tax in line.invoice_line_tax_id:
                    if tax.price_include:
                        print "incluye ipuesto!!!"
                        precio_unitario = line.price_unit / (1 + tax.amount)
                        break
                else:
                    precio_unitario = line.price_unit
                for k,v in {
                    'ClaveProdServ': (line.product_id.code_sat and line.product_id.code_sat.code) or (line.product_id.categ_id.code_sat and line.product_id.categ_id.code_sat.code) or '',
                    'NoIdentificacion': line.product_id and line.product_id.default_code or "",  
                    'ClaveUnidad': line.uos_id.code_sat and line.uos_id.code_sat.code or '',
                    'Descripcion': line.name or "",
                    'Importe': con_n_decimales(line.price_subtotal, dp),
                    'ValorUnitario': con_n_decimales(precio_unitario, dp),
                    'Cantidad': str(round(line.quantity or 0.0, dp)),
                    'Unidad': line.uos_id and line.uos_id.name or "",
                }.iteritems():
                    if v:
                        concepto.set(k,v)
                #Si está instalado el modulo de pedimentos ver si lleva pedimentos el concepto
                if self.pool.get("ir.module.module").search(cr, uid, [('state','=','installed'),('name','=','pedimentos')]):
                    for pedimento in line.pedimentos:
                        infoadu = ET.SubElement(concepto, ns+"InformacionAduanera")
                        for k,v in {
                            'numero': pedimento.name,
                            'fecha': pedimento.fecha,
                            'aduana': pedimento.aduana.name if pedimento.aduana else False
                        }.iteritems():
                            if v:
                                infoadu.set(k,v)

            #Por cada partida poner impuestos
            #Estos impuestos tienen que tener un tipo (IVA, IEPS, ISR) y si es retención o no
            if line.invoice_line_tax_id:
                concepto_impuestos = ET.SubElement(concepto, ns+"Impuestos")
                concepto_traslados = None
                concepto_retenciones = None
                for tax in line.invoice_line_tax_id:
                    if not tax.tipo_impuesto or not tax.tipo_factor:
                        raise osv.except_osv(u"Error", u"El impuesto %s no tiene configurado los dos campos Tipo Impuesto y Tipo Factor"%tax.name)
                    impuesto = tax.tipo_impuesto.code
                    comp = tax_obj.compute_all(cr, uid, [tax], line.price_unit, line.quantity, line.product_id, invoice.partner_id)
                    importe = comp['total_included'] - comp['total']
                    importe = round(importe, dp)
                    if tax.type == 'percent':
                        tasas[impuesto] = round(abs(tax.amount * 100), dp)
                    #Traslados
                    if not tax.retencion:
                        if concepto_traslados is None:
                            concepto_traslados = ET.SubElement(concepto_impuestos, ns+"Traslados")
                        key = (impuesto, tax.tipo_factor, tax.amount)
                        impuestos_traslados.setdefault(key, []).append(importe)
                        tras = ET.SubElement(concepto_traslados, ns+"Traslado")
                        for k,v in {
                            'Base': con_n_decimales(precio_unitario * line.quantity, dp),
                            'Impuesto': impuesto,
                            'TipoFactor': tax.tipo_factor.name,
                        }.iteritems():
                            if v:
                                tras.set(k, v)
                        if tras.attrib.get("TipoFactor") != 'Exento':
                            tras.set('TasaOCuota', str(abs(tax.amount)))
                            tras.set("Importe", con_n_decimales(importe, dp))
                    #Retenciones
                    else:
                        if concepto_retenciones is None:
                            concepto_retenciones = ET.SubElement(concepto_impuestos, ns+"Retenciones")
                        impuestos_retenidos.setdefault(impuesto, []).append(importe)
                        ret = ET.SubElement(concepto_retenciones, ns+"Retencion")
                        for k,v in {
                            'Base': con_n_decimales(precio_unitario * line.quantity, dp),
                            'Impuesto': impuesto,
                            'TipoFactor': tax.tipo_factor.name,
                            'TasaOCuota': str(abs(tax.amount)),
                            'Importe': con_n_decimales(importe, dp)
                        }.iteritems():
                            if v:
                                ret.set(k, v)

            
        impuestos = ET.SubElement(comprobante, ns+'Impuestos')
        if impuestos_retenidos:
            retenciones = ET.SubElement(impuestos, ns+'Retenciones')
        for key in impuestos_traslados:
            impuesto, tipo_factor, tasa_o_cuota = key
            if tipo_factor.name != 'Exento':
                solo_exentos = False
                break
        else:
            solo_exentos = True
        if impuestos_traslados and not solo_exentos:
            traslados = ET.SubElement(impuestos, ns+'Traslados')
        
        totalImpuestosTrasladados = 0
        totalImpuestosRetenidos = 0
        for impuesto in impuestos_retenidos:
            importe = abs(sum(impuestos_retenidos[impuesto]))
            ET.SubElement(retenciones, ns+'Retencion', {
                'Impuesto': impuesto,
                'Importe': con_n_decimales(importe or 0.0, dp)
            })
            totalImpuestosRetenidos += importe
        if not solo_exentos:
            for key in impuestos_traslados:
                importe = sum(impuestos_traslados[key])
                impuesto, tipo_factor, tasa_o_cuota = key
                if tipo_factor.name == 'Exento':
                    continue
                ET.SubElement(traslados, ns+'Traslado', {
                    'Impuesto': impuesto,
                    'Importe': con_n_decimales(importe or 0.0, dp),
                    'TipoFactor': tipo_factor.name,
                    'TasaOCuota': str(tasa_o_cuota)
                })
                totalImpuestosTrasladados += importe
        
        if totalImpuestosTrasladados:
            impuestos.set('TotalImpuestosTrasladados', con_n_decimales(totalImpuestosTrasladados, dp))
        if totalImpuestosRetenidos:
            impuestos.set('TotalImpuestosRetenidos', con_n_decimales(totalImpuestosRetenidos, dp))
        
        #Nombre largo de la moneda. Si es MXN poner 'pesos' a menos que se haya puesto algo en el campo de nombre largo
        #Si no es MXN poner lo que está en el campo de nombre largo o en su defecto el código de la moneda
        if invoice.currency_id.name == 'MXN':
            nombre = invoice.currency_id.nombre_largo or 'pesos'
            siglas = 'M.N.'
        else:
            nombre = invoice.currency_id.nombre_largo or invoice.currency_id.name
            siglas = ''
        invoice.cant_letra = amount_to_text().amount_to_text_cheque(float(invoice.amount_total), nombre, siglas).capitalize()
                
        # *********************** Sellado del XML ************************
        tmpfiles = TempFileTransaction()

        certificate = self._get_certificate(cr, uid, invoice.company_id.id)
        comprobante.set("NoCertificado", certificate.serial)

        xml = '<?xml version="1.0" encoding="utf-8"?>' + ET.tostring(comprobante, encoding="utf-8")
        fname_xml = tmpfiles.save(xml, 'xml_sin_sello')
        current_path = os.path.dirname(os.path.abspath(inspect.getfile(inspect.currentframe())))

        if version == '3.3':
            fname_xslt = current_path+'/SAT/cadenaoriginal_3_3.xslt'
        fname_cadena = tmpfiles.create("cadenaori")
        os.system("xsltproc --output %s %s %s"%(fname_cadena, fname_xslt, fname_xml))
        
        fname_cer_pem = tmpfiles.decode_and_save(certificate.cer_pem)
        fname_key_pem = tmpfiles.decode_and_save(certificate.key_pem)
        
        sello = openssl.sign_and_encode(fname_cadena, fname_key_pem)
        certificado = ''.join(open(fname_cer_pem).readlines()[1:-1])
        certificado = certificado.replace('\n', '')
        for k,v in {
            'Sello': sello,
            'Certificado': certificado,
        }.iteritems():
            comprobante.set(k,v)
            
        #Validar xml resultante contra xsd
        xml = '<?xml version="1.0" encoding="utf-8"?>' + ET.tostring(comprobante, encoding="utf-8")
        fname_xml = tmpfiles.save(xml, 'xml_con_sello')
        res_validar = os.popen("xmllint --schema %s/SAT/cfdv33.xsd %s --noout 2>&1"%(current_path, fname_xml)).read()
        if not res_validar.strip().endswith("validates"):
            raise osv.except_osv("Error en la estructura del xml", res_validar)
        
        # ************************ Addenda *********************************
        nodo_addenda = False
        conf_addenda_obj = self.pool.get('cfdi.conf_addenda')
        conf_addenda_ids = conf_addenda_obj.search(cr, uid, [('partner_ids','in',invoice.partner_id.id)])
        if conf_addenda_ids:
            conf_addenda = conf_addenda_obj.browse(cr, uid, conf_addenda_ids[0])
            addenda_obj = self.pool.get(conf_addenda.model)
            addenda = addenda_obj.create_addenda(Nodo, invoice)
            if conf_addenda.model == "cfdi.addenda_detallista" or 'complemento' in conf_addenda.model:
                nom_nodo = "Complemento"
            else:
                nom_nodo = "Addenda"
            nodo_addenda = ET.SubElement(addenda, ns+nom_nodo)
            addenda_obj.set_namespace(comprobante, nodo_addenda)
            
        # *************** Guardar XML y timbrarlo en su caso ***************
        cfd = '<?xml version="1.0" encoding="utf-8"?>' + ET.tostring(comprobante, encoding="utf-8")
        print cfd
        if version == '3.3':
            res = self._sign_cfdi(cr, uid, invoice.company_id, base64.b64encode(cfd), test)
            cfd = res
            uuid = re.search('UUID="(.*?)"', cfd).group(1)
            fecha_timbrado = re.search('FechaTimbrado="(.*?)"', cfd).group(1)
            sello_sat = re.search('SelloSAT="(.*?)"', cfd).group(1)
            certificado_sat = re.search('NoCertificadoSAT="(.*?)"', cfd).group(1)
        if nodo_addenda:
            xml_add = ET.tostring(nodo_addenda, encoding="utf-8")
            end_tag = "</"+ns+"Comprobante>"
            cfd = cfd.replace(end_tag, xml_add + end_tag)    
        cfd_b64 = base64.b64encode(cfd.encode("utf-8"))
        fname = uuid + ".xml"
        attachment_values = {
            'name': fname,
            'datas': cfd_b64,
            'datas_fname': fname,
            'description': uuid,
            'res_model': self._name,
            'res_id': invoice.id,
        }
        self.pool.get('ir.attachment').create(cr, uid, attachment_values, context=context)
        
        # *************** Guardar datos CFD en la base del Open ***************
        sello = re.sub("(.{100})", "\\1\n", sello, 0, re.DOTALL) #saltos de linea cada 100 caracteres
        values = {
            'hora_factura': hora_factura_local,       
            'sello': sello,
            'cadena': open(fname_cadena, 'rb').read(),
            'no_certificado': certificate.serial,
            'cant_letra': invoice.cant_letra,
            'tipo_cambio': rate,
        }
        if version == '3.3':
            qrcode_data, qrcode = self._make_qrcode(invoice, uuid)
            values.update({
                'uuid': uuid,
                'serie': invoice.journal_id.serie or '',
                'qrcode_data': qrcode_data,
                'qrcode': qrcode,
                'test': test,
                'sello_sat': sello_sat,
                'certificado_sat': certificado_sat,
                'fecha_timbrado': fecha_timbrado,
                'cadena_sat': re.sub("(.{80})", "\\1\n", '||1.0|%s|%s|%s|%s||'%(uuid.lower(), fecha_timbrado,
                    sello_sat, certificado_sat), 0, re.DOTALL)
            })

        self.pool.get('account.invoice').write(cr, uid, invoice.id, values)

        tmpfiles.clean()

    def action_create_cfd_32(self, cr, uid, id, context=None):
        invoice = self.browse(cr, uid, id)[0]
        #Si no es el journal adecuado no hacer nada
        if invoice.company_id.cfdi_journal_ids:
            if invoice.journal_id.id not in [x.id for x in invoice.company_id.cfdi_journal_ids]:
                return True
        #Si es de proveedor no hacer nada
        if invoice.type.startswith("in"):
            return True
        #Si no hay terminos de pago mandar warning
        if not invoice.payment_term:
            raise osv.except_osv("Error!", "No se definio termino de pago")            
        #Si no hay metodo de pago y es factura de cliente mandar warning
        if not invoice.formapago_id and not invoice.type.startswith("in"):
            raise osv.except_osv("Error!", "No se definio metodo de pago")

        version = invoice.company_id.cfdi_version
        test = invoice.company_id.cfdi_test
        dp = self.pool.get('decimal.precision').precision_get(cr, uid, 'Account')
        ns = version == '3.2' and 'cfdi:' or ''
        if version == '3.2':
            comprobante = ET.Element(ns+'Comprobante', {
                'version': '3.2',
                'xmlns:cfdi': "http://www.sat.gob.mx/cfd/3",
                'xmlns:xsi': "http://www.w3.org/2001/XMLSchema-instance",
                'xsi:schemaLocation': "http://www.sat.gob.mx/cfd/3  http://www.sat.gob.mx/sitio_internet/cfd/3/cfdv32.xsd" 
            })
        else:
            raise osv.except_osv(u"Error!", u"Versión de CFD no valida")
        
        #Hora de la factura en zona horaria del usuario
        tz = self.pool.get("res.users").browse(cr, uid, uid).tz
        hora_factura_utc =  datetime.now(timezone("UTC"))
        hora_factura_local = hora_factura_utc.astimezone(timezone(tz)).strftime("%H:%M:%S")
        #print "****HORA", hora_factura_utc.strftime("%H:%M:%S"), hora_factura_local, tz

        #Tipo de cambio
        #--------------
        #Si es pesos poner 1 directo
        if invoice.currency_id.name == 'MXN':
            rate = 1.0
        #Si no, obtener el tipo de cambio
        #(esto funciona aunque la moneda base no sea el peso)
        else:
            model_data = self.pool.get("ir.model.data")
            mxn_rate = model_data.get_object(cr, uid, 'base', 'MXN').rate
            rate = (1.0 / invoice.currency_id.rate) * mxn_rate

        for k,v in {
            'serie': invoice.journal_id.serie or '',
            'Moneda': invoice.currency_id.name or '',
            'TipoCambio': str(round(rate or 0.0, 4)), #De acuerdo al diario oficial de la federacion son 4 decimales
            'NumCtaPago': invoice.cuenta_banco or '',
            'LugarExpedicion': invoice.journal_id and invoice.journal_id.lugar or "",
            'metodoDePago': invoice.formapago_id and invoice.formapago_id.clave or "99",
            'formaDePago': invoice.tipopago_id and invoice.tipopago_id.name or "Pago en una sola exhibicion",
            'fecha': str(invoice.date_invoice) + "T" + hora_factura_local,
            'folio': invoice.internal_number or '',
            'tipoDeComprobante': (invoice.type == 'out_invoice' and 'ingreso') or (invoice.type == 'out_refund' and 'egreso') or "",
            'subTotal': str(round((invoice.amount_untaxed or 0.0), dp)),
            'total': str(round((invoice.amount_total or 0.0), dp)),
        }.iteritems():
            if v:
                comprobante.set(k,v)

        if invoice.discount:
            comprobante.set('descuento', "%s"%round(invoice.discount, dp))
        
        emisor = ET.SubElement(comprobante, ns+'Emisor', {
            'rfc': invoice.company_id.partner_id.vat or "",
            'nombre': invoice.company_id.partner_id.name or "",
        })
        
        domicilioFiscal = ET.SubElement(emisor, ns+'DomicilioFiscal')
        for k,v in {
            'calle': invoice.company_id.partner_id.street or "",
            'noExterior': invoice.company_id.partner_id.no_exterior or "",  
            'noInterior': invoice.company_id.partner_id.no_interior or "",
            'localidad': invoice.company_id.partner_id.city or "",
            'colonia': invoice.company_id.partner_id.colonia or "",
            'municipio': invoice.company_id.partner_id.municipio or "",
            'estado': invoice.company_id.partner_id.state_id and invoice.company_id.partner_id.state_id.name or "",
            'pais': invoice.company_id.partner_id.country_id and invoice.company_id.partner_id.country_id.name or "",
            'codigoPostal': invoice.company_id.partner_id.zip or "",
        }.iteritems():
            if v:
                domicilioFiscal.set(k, v)
        
        regimenFiscal = ET.SubElement(emisor, ns+'RegimenFiscal', {
            'Regimen': invoice.company_id.partner_id.regimen_id and invoice.company_id.partner_id.regimen_id.name or ""
        })
        
        receptor = ET.SubElement(comprobante, ns +'Receptor', {
            'rfc': invoice.partner_id.vat or "",
            'nombre': invoice.partner_id.name or "",
        })
        
        domicilio = ET.SubElement(receptor, ns+'Domicilio')
        for k,v in {
            'calle': invoice.partner_id.street or "",
            'noExterior': invoice.partner_id.no_exterior or "",
            'noInterior': invoice.partner_id.no_interior or "",
            'localidad': invoice.partner_id.city or "",
            'colonia': invoice.partner_id.colonia or "",
            'municipio': invoice.partner_id.municipio or "",
            'estado': invoice.partner_id.state_id and invoice.partner_id.state_id.name or "",
            'pais': invoice.partner_id.country_id and invoice.partner_id.country_id.name or "",
            'codigoPostal': invoice.partner_id.zip or ""
        }.iteritems():
            if v:
                domicilio.set(k,v)
        
        conceptos = ET.SubElement(comprobante, ns+'Conceptos')
        
        impuestos_traslados = {}
        impuestos_retenidos = {}
        tasas = {}
        cfdi_impuestos = {}
        tax_obj = self.pool.get("account.tax")
        for line in invoice.invoice_line:
            if line.price_subtotal > 0:
                concepto = ET.SubElement(conceptos, ns+'Concepto')
                for k,v in {
                    'descripcion': line.name or "",
                    'importe': str(round(line.price_subtotal or 0.0, dp)),
                    'valorUnitario': str(round(line.price_unit or 0.0, dp)),
                    'cantidad': str(round(line.quantity or 0.0, dp)),
                    'unidad': line.uos_id and line.uos_id.name or "",
                    'noIdentificacion': line.product_id and line.product_id.default_code or ""
                }.iteritems():
                    if v:
                        concepto.set(k,v)
                #Si está instalado el modulo de pedimentos ver si lleva pedimentos el concepto
                if self.pool.get("ir.module.module").search(cr, uid, [('state','=','installed'),('name','=','pedimentos')]):
                    for pedimento in line.pedimentos:
                        infoadu = ET.SubElement(concepto, ns+"InformacionAduanera")
                        for k,v in {
                            'numero': pedimento.name,
                            'fecha': pedimento.fecha,
                            'aduana': pedimento.aduana.name if pedimento.aduana else False
                        }.iteritems():
                            if v:
                                infoadu.set(k,v)
            nombres_impuestos = {
                'iva': 'IVA',
                'ieps': 'IEPS',
                'iva_ret': 'IVA',
                'isr_ret': 'ISR'
            }
            #Por cada partida ver que impuestos lleva.
            #Estos impuestos tienen que tener una de las 4 categorias (iva, ieps, retencion iva, retencion isr)
            for tax in line.invoice_line_tax_id:
                if not tax.categoria:
                    raise osv.except_osv(u"Error", u"El impuesto %s no tiene categoria CFDI"%tax.name)
                impuesto = nombres_impuestos[tax.categoria]
                comp = tax_obj.compute_all(cr, uid, [tax], line.price_unit, line.quantity, line.product_id, invoice.partner_id)
                importe = comp['total_included'] - comp['total']
                importe = round(importe, dp)
                if tax.type == 'percent':
                    tasas[impuesto] = round(abs(tax.amount * 100), dp)
                #Traslados
                if tax.categoria in ('iva', 'ieps'):
                    impuestos_traslados.setdefault(impuesto, []).append(importe)
                #Retenciones
                else:
                    impuestos_retenidos.setdefault(impuesto, []).append(importe)
            
        impuestos = ET.SubElement(comprobante, ns+'Impuestos')
        if impuestos_retenidos:
            retenciones = ET.SubElement(impuestos, ns+'Retenciones')
        traslados = ET.SubElement(impuestos, ns+'Traslados')
        
        totalImpuestosTrasladados = 0
        totalImpuestosRetenidos = 0
        if len(invoice.tax_line) == 0:
            ET.SubElement(traslados, ns+'Traslado', {
                'impuesto':'IVA',
                'tasa': '0.00',
                'importe': '0.00'
            })
        for impuesto in impuestos_retenidos:
            importe = abs(sum(impuestos_retenidos[impuesto]))
            ET.SubElement(retenciones, ns+'Retencion', {
                'impuesto': str(impuesto or 0.0),
                'importe': str(importe or 0.0)
            })
            totalImpuestosRetenidos += importe
        for impuesto in impuestos_traslados:
            importe = sum(impuestos_traslados[impuesto])
            ET.SubElement(traslados, ns+'Traslado', {
                'impuesto': str(impuesto or 0.0),
                'importe': str(importe or 0.0),
                'tasa': str(tasas.get(impuesto, 0.0))
            })
            totalImpuestosTrasladados += importe        
                
        impuestos.set('totalImpuestosTrasladados', str(totalImpuestosTrasladados))
        impuestos.set('totalImpuestosRetenidos', str(totalImpuestosRetenidos))
        
        #Nombre largo de la moneda. Si es MXN poner 'pesos' a menos que se haya puesto algo en el campo de nombre largo
        #Si no es MXN poner lo que está en el campo de nombre largo o en su defecto el código de la moneda
        if invoice.currency_id.name == 'MXN':
            nombre = invoice.currency_id.nombre_largo or 'pesos'
            siglas = 'M.N.'
        else:
            nombre = invoice.currency_id.nombre_largo or invoice.currency_id.name
            siglas = ''
        invoice.cant_letra = amount_to_text().amount_to_text_cheque(float(invoice.amount_total), nombre, siglas).capitalize()
                
        # *********************** Sellado del XML ************************
        tmpfiles = TempFileTransaction()
           
        xml = '<?xml version="1.0" encoding="utf-8"?>' + ET.tostring(comprobante, encoding="utf-8")
        fname_xml = tmpfiles.save(xml, 'xml_sin_sello')
        current_path = os.path.dirname(os.path.abspath(inspect.getfile(inspect.currentframe())))

        if version == '3.2':
            fname_xslt = current_path+'/SAT/cadenaoriginal_3_2.xslt'
        fname_cadena = tmpfiles.create("cadenaori")
        os.system("xsltproc --output %s %s %s"%(fname_cadena, fname_xslt, fname_xml))
        
        certificate = self._get_certificate(cr, uid, invoice.company_id.id)
        fname_cer_pem = tmpfiles.decode_and_save(certificate.cer_pem)
        fname_key_pem = tmpfiles.decode_and_save(certificate.key_pem)
        
        sello = openssl.sign_and_encode(fname_cadena, fname_key_pem)
        certificado = ''.join(open(fname_cer_pem).readlines()[1:-1])
        certificado = certificado.replace('\n', '')
        for k,v in {
            'sello': sello,
            'certificado': certificado,
            'noCertificado': certificate.serial
        }.iteritems():
            comprobante.set(k,v)
            
        #Validar xml resultante contra xsd
        xml = '<?xml version="1.0" encoding="utf-8"?>' + ET.tostring(comprobante, encoding="utf-8")
        fname_xml = tmpfiles.save(xml, 'xml_con_sello')
        res_validar = os.popen("xmllint --schema %s/SAT/cfdv32.xsd %s --noout 2>&1"%(current_path, fname_xml)).read()
        if not res_validar.strip().endswith("validates"):
            raise osv.except_osv("Error en la estructura del xml", res_validar)
        
        # ************************ Addenda *********************************
        nodo_addenda = False
        conf_addenda_obj = self.pool.get('cfdi.conf_addenda')
        conf_addenda_ids = conf_addenda_obj.search(cr, uid, [('partner_ids','in',invoice.partner_id.id)])
        if conf_addenda_ids:
            conf_addenda = conf_addenda_obj.browse(cr, uid, conf_addenda_ids[0])
            addenda_obj = self.pool.get(conf_addenda.model)
            addenda = addenda_obj.create_addenda(Nodo, invoice)
            if conf_addenda.model == "cfdi.addenda_detallista" or 'complemento' in conf_addenda.model:
                nom_nodo = "Complemento"
            else:
                nom_nodo = "Addenda"
            nodo_addenda = ET.SubElement(addenda, ns+nom_nodo)
            addenda_obj.set_namespace(comprobante, nodo_addenda)
            
        # *************** Guardar XML y timbrarlo en su caso ***************
        cfd = '<?xml version="1.0" encoding="utf-8"?>' + ET.tostring(comprobante, encoding="utf-8")
        if version == '3.2':
            res = self._sign_cfdi(cr, uid, invoice, cfd, test)
            cfd = res
            uuid = re.search('UUID="(.*?)"', cfd).group(1)
            fecha_timbrado = re.search('FechaTimbrado="(.*?)"', cfd).group(1)
            sello_sat = re.search('selloSAT="(.*?)"', cfd).group(1)
            certificado_sat = re.search('noCertificadoSAT="(.*?)"', cfd).group(1)
        if nodo_addenda:
            xml_add = ET.tostring(nodo_addenda, encoding="utf-8")
            end_tag = "</"+ns+"Comprobante>"
            cfd = cfd.replace(end_tag, xml_add + end_tag)    
        cfd_b64 = base64.b64encode(cfd.encode("utf-8"))
        fname = "cfd_"+invoice.number + ".xml"
        attachment_values = {
            'name': fname,
            'datas': cfd_b64,
            'datas_fname': fname,
            'description': uuid,
            'res_model': self._name,
            'res_id': invoice.id,
        }
        self.pool.get('ir.attachment').create(cr, uid, attachment_values, context=context)
        
        # *************** Guardar datos CFD en la base del Open ***************
        sello = re.sub("(.{100})", "\\1\n", sello, 0, re.DOTALL) #saltos de linea cada 100 caracteres
        values = {
            'hora_factura': hora_factura_local,       
            'sello': sello,
            'cadena': open(fname_cadena, 'rb').read(),
            'no_certificado': certificate.serial,
            'cant_letra': invoice.cant_letra,
            'tipo_cambio': rate,
        }
        if version == '3.2':
            qrcode_data, qrcode = self._make_qrcode(invoice, uuid)
            values.update({
                'uuid': uuid,
                'serie': invoice.journal_id.serie or '',
                'qrcode_data': qrcode_data,
                'qrcode': qrcode,
                'test': test,
                'sello_sat': sello_sat,
                'certificado_sat': certificado_sat,
                'fecha_timbrado': fecha_timbrado,
                'cadena_sat': re.sub("(.{80})", "\\1\n", '||1.0|%s|%s|%s|%s||'%(uuid.lower(), fecha_timbrado,
                    sello_sat, certificado_sat), 0, re.DOTALL)
            })

        self.pool.get('account.invoice').write(cr, uid, invoice.id, values)

        tmpfiles.clean()
        
#Para que tambien se mande el xml al elegir un template de email
class mail_compose_message(osv.TransientModel):
    _inherit = 'mail.compose.message'
    
    def onchange_template_id(self, cr, uid, ids, template_id, composition_mode, model, res_id, context=None):
        if context is None: context = {}
        res = super(mail_compose_message, self).onchange_template_id(cr, uid, ids, template_id, composition_mode, model, res_id, context=context)       
        if context.get('active_model', False) == 'account.invoice':
            invoice = self.pool.get("account.invoice").browse(cr, uid, context['active_id'])
            if not invoice.internal_number:
                return res
            xml_name = "cfd_" + invoice.internal_number + ".xml"
            att_obj = self.pool.get("ir.attachment")
            xml_id = self.pool.get("ir.attachment").search(cr, uid, [('name', '=', xml_name)])
            if xml_id:
                res['value'].setdefault('attachment_ids', []).append(xml_id[0])
        return res
