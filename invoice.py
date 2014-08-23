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
from nodo import Nodo
import os
import inspect
from files import TempFileTransaction
import openssl
import codecs
import base64
from datetime import date, datetime
from amount_to_text_es_MX import amount_to_text
import suds
import zipfile
import logging
import qrcode
import re
from pytz import timezone
import tempfile
import tralix
import finkok

class addendas(osv.Model):
    _name = 'cfdi.conf_addenda'
    
    _columns = {
        'partner_ids': fields.many2many('res.partner', string="Clientes"),
        'model': fields.char('Modelo de la addenda')
    }

class formapago(osv.Model):
    _name = 'cfdi.formapago'
    
    _columns = {
        'name': fields.char("Descripcion", size=64, required=True),
        'banco': fields.boolean("Banco"),
        'pos_metodo': fields.many2one('account.journal',
            domain=[('journal_user','=',1)], string="Metodo de pago del TPV")
    }
   

class account_invoice(osv.Model):
    _inherit = 'account.invoice'
    
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
            'mandada_cancelar': False,
            'mensaje_pac': False,
        })
        return new_id
    
    def onchange_partner_id(self, cr, uid, ids, type, partner_id,\
            date_invoice=False, payment_term=False, partner_bank_id=False, company_id=False):
        res = super(account_invoice, self).onchange_partner_id(cr, uid, ids, type, partner_id,\
            date_invoice, payment_term, partner_bank_id, company_id)
        metodo = self.pool.get("res.partner").browse(cr, uid, partner_id).metodo_pago
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
            'value': {'cuentaBanco': cuenta}
        })
        return res
        
    def _format_uuid(self, uuid):
        return uuid[0:8]+'-'+uuid[8:12]+'-'+uuid[12:16]+'-'+uuid[16:20]+'-'+uuid[20:32]   
        
    _columns = {
        'cuentaBanco': fields.char('Ultimos 4 digitos cuenta', size=4),
        'anoAprobacion': fields.integer("Año de aprobación"),
        'noAprobacion': fields.char("No. de aprobación"),
        'serie': fields.char("Serie", size=8),
        'formapago_id': fields.many2one('cfdi.formapago','Método de Pago'),
        'sello': fields.char("Sello", size=256),
        'cadena': fields.text("Cadena original"),
        'noCertificado': fields.char("No. de serie del certificado", size=64),
        'cantLetra': fields.char("Cantidad en letra", size=256),
        'hora': fields.char("Hora", size=8),
        'uuid': fields.char('Timbre fiscal', size=32),
        'hora_factura': fields.char('Hora', size=16),
        'qrcode': fields.binary("Codigo QR"),
        'test': fields.boolean("Timbrado en modo de prueba"),
        'sello_sat': fields.char("Sello del SAT", size=64),
        'certificado_sat': fields.char("No. Certificado del SAT", size=64),
        'fecha_timbrado': fields.char("Fecha de Timbrado", size=32),
        'cadena_sat': fields.text("Cadena SAT"),
        'mandada_cancelar': fields.boolean('Mandada cancelar'),
        'tipo_cambio': fields.float("Tipo de cambio"),
        'mensaje_pac': fields.text('Ultimo mensaje del PAC'),
    }
    
    _defaults = {
        'cuentaBanco': '',
        'mandada_cancelar': False
    }

    def _make_qrcode(self, invoice, uuid):
        total = invoice.amount_total
        integer, decimal = str(total).split('.')
        padded_total = integer.rjust(10, '0') + '.' + decimal.ljust(6, '0')
        data = '?re=%s&rr=%s&tt=%s&id=%s'%(invoice.company_id.vat, invoice.partner_id.vat,\
                                           padded_total, uuid)
        img = qrcode.make(data)
        fp, tmpfile = tempfile.mkstemp()
        img.save(tmpfile, 'PNG')
        res = base64.b64encode(open(tmpfile, 'rb').read())
        os.unlink(tmpfile)
        return res

    
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
        certificate_id = certificate_obj.search(cr, uid, [('serial', '=', invoice.noCertificado)])
        if certificate_id:
            certificate =  certificate_obj.browse(cr, uid, certificate_id[0])
            pfx_data_b64 = certificate.pfx
            pfx_password = certificate.pfx_password
            cer_file = certificate.cer_pem
            key_file = certificate.key_pem
        else:
            raise osv.except_osv("Error", "El certificado %s no existe"%invoice.noCertificado)
        #--------------------------------------------------------------------------
        if invoice.company_id.cfdi_pac == 'zenpar':
        #--------------------------------------------------------------------------
            config_obj = self.pool.get('ir.config_parameter')
            password = config_obj.get_param(cr, uid, 'cfdi.password')
            url =   config_obj.get_param(cr, uid, 'cfdi.host')
            client = client = suds.client.Client(url)
            res = client.service.cancelar(rfc, uuid, pfx_data_b64, pfx_password, password)
        #--------------------------------------------------------------------------
        elif invoice.company_id.cfdi_pac == 'finkok':
        #--------------------------------------------------------------------------
            if not invoice.test and not invoice.company_id.cfdi_finkok_host_cancel:
                raise osv.except_osv("Error", "No se ha definido la direccion para la cancelacion de Finkok")
            if invoice.test and not invoice.company_id.cfdi_finkok_host_cancel_test:
                raise osv.except_osv("Error", "No se ha definido la direccion para la cancelacion de Finkok modo pruebas")
            if not invoice.company_id.cfdi_finkok_user or not invoice.company_id.cfdi_finkok_key:
                raise osv.except_osv("Error", "No se ha definido user y password de Finkok")
            hostname = invoice.company_id.cfdi_finkok_host_cancel if not invoice.test else invoice.company_id.cfdi_finkok_host_cancel_test
            username = invoice.company_id.cfdi_finkok_user
            password = invoice.company_id.cfdi_finkok_key
            invoices = [self._format_uuid(uuid)]
            res = finkok.cancelar(hostname, invoices, username, password, rfc, cer_file, key_file)
        else:
            raise osv.except_osv("No se puede cancelar con el PAC seleccionado")
        self.write(cr, uid, invoice.id, {'mandada_cancelar': True, 'mensaje_pac': res})
        return True

    def _sign_cfdi(self, cr, uid, invoice, xml_data_b64, test):
        #--------------------------------------------------------------------------
        if invoice.company_id.cfdi_pac == 'zenpar':
        #--------------------------------------------------------------------------
            test = test and 1 or 0
            rfc = invoice.company_id.partner_id.vat
            config_obj = self.pool.get('ir.config_parameter')
            password = config_obj.get_param(cr, uid, 'cfdi.password')
            url =   config_obj.get_param(cr, uid, 'cfdi.host')
            client = suds.client.Client(url)
            return client.service.timbrar(xml_data_b64, test, rfc, password)
        #--------------------------------------------------------------------------
        elif invoice.company_id.cfdi_pac == 'tralix':
        #--------------------------------------------------------------------------
            if not invoice.company_id.cfdi_tralix_key:
                raise osv.except_osv("Error", "No se ha definido el customer key para el timbrado de Tralix")
            if not test and not invoice.company_id.cfdi_tralix_host:
                raise osv.except_osv("Error", "No se ha definido la direccion para el timbrado de Tralix")
            if test and not invoice.company_id.cfdi_tralix_host_test:
                raise osv.except_osv("Error", "No se ha definido la direccion para el timbrado de Tralix modo pruebas")
            hostname = invoice.company_id.cfdi_tralix_host if not test else invoice.company_id.cfdi_tralix_host_test
            xml_data = xml_data_b64.decode('base64').decode('utf-8').encode('utf-8')
            return tralix.timbrar(xml_data, invoice.company_id.cfdi_tralix_key, hostname)  
        #--------------------------------------------------------------------------
        elif invoice.company_id.cfdi_pac == 'finkok':
        #--------------------------------------------------------------------------
            if not test and not invoice.company_id.cfdi_finkok_host:
                raise osv.except_osv("Error", "No se ha definido la direccion para el timbrado de Finkok")
            if test and not invoice.company_id.cfdi_finkok_host_test:
                raise osv.except_osv("Error", "No se ha definido la direccion para el timbrado de Finkok modo pruebas")
            if not invoice.company_id.cfdi_finkok_user or not invoice.company_id.cfdi_finkok_key:
                raise osv.except_osv("Error", "No se ha definido user y password de Finkok")
            hostname = invoice.company_id.cfdi_finkok_host if not test else invoice.company_id.cfdi_finkok_host_test
            username = invoice.company_id.cfdi_finkok_user
            password = invoice.company_id.cfdi_finkok_key
            return finkok.timbrar(hostname, username, password, xml_data_b64)
        #--------------------------------------------------------------------------
        else:
            raise osv.except_osv("Error", "PAC '%s' no es valido"%invoice.partner_id.cfd_pac)
      
    def _get_certificate(self, cr, uid, id, invoice):
        certificate_obj = self.pool.get("cfdi.certificate")
        certificate_id = certificate_obj.search(cr, uid, ['&', 
            ('company_id','=', invoice.company_id.id), 
            ('end_date', '>', date.today().strftime("%Y-%m-%d"))
        ])
        if not certificate_id:
            raise osv.except_osv("Error", "No tiene certificados vigentes")
        certificate = certificate_obj.browse(cr, uid, certificate_id)[0]
        if not certificate.cer_pem or not certificate.key_pem:
            raise osv.except_osv("Error", "No esta el certificado y la llave en formato PEM")
        return certificate
    
    
    def _get_aprobacion(self, cr, uid, id, invoice):
        if not invoice.journal_id.sequence_id:
            raise osv.except_osv("Error", "No hay definida una secuencia en el diario");
        try:
            number = int(invoice.number)
        except ValueError:
            raise osv.except_osv("Error", "El folio no debe contener letras");
        aprobacion_ids = self.pool.get("cfdi.aprobacion").search(cr, uid, ['&','&', 
                ('sequence_id','=', invoice.journal_id.sequence_id.id),
                ('del', '<=', number),
                ('al', '>=', number)])
        if not aprobacion_ids:
            raise osv.except_osv("Error", "Este folio no esta aprobado (%s)"%number);
        if len(aprobacion_ids) != 1:
            raise osv.except_osv("Error", "Este folio tiene mas de un numero de aprobacion");
        return self.pool.get("cfdi.aprobacion").browse(cr, uid, aprobacion_ids)[0]
    
        
      
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

        version = invoice.company_id.cfdi_version
        test = invoice.company_id.cfdi_test
        dp = self.pool.get('decimal.precision').precision_get(cr, uid, 'Account')
        ns = version == '3.2' and 'cfdi:' or ''
        if version == '2.2':
            comprobante = Nodo(ns+'Comprobante', {
                'version': '2.2',
                'xmlns': "http://www.sat.gob.mx/cfd/2",
                'xmlns:xsi': "http://www.w3.org/2001/XMLSchema-instance",
                'xsi:schemaLocation': "http://www.sat.gob.mx/cfd/2 http://www.sat.gob.mx/sitio_internet/cfd/2/cfdv22.xsd" 
            })
        elif version == '3.2':
            comprobante = Nodo(ns+'Comprobante', {
                'version': '3.2',
                'xmlns:cfdi': "http://www.sat.gob.mx/cfd/3",
                'xmlns:xsi': "http://www.w3.org/2001/XMLSchema-instance",
                'xsi:schemaLocation': "http://www.sat.gob.mx/cfd/3  http://www.sat.gob.mx/sitio_internet/cfd/3/cfdv32.xsd" 
            })
        else:
            raise osv.except_osv("Error!", "Versión de CFD no valida")
        
        if version == '2.2':    
            aprobacion = self._get_aprobacion(cr, uid, id, invoice)
            comprobante.atributos.update({
                'noAprobacion': aprobacion.noAprobacion,
                'anoAprobacion': aprobacion.anoAprobacion,
                'serie': aprobacion.serie or '',
            })
        
        #Hora de la factura en zona horaria del usuario
        tz = self.pool.get("res.users").browse(cr, uid, uid).tz
        hora_factura_utc =  datetime.now(timezone("UTC"))
        hora_factura_local = hora_factura_utc.astimezone(timezone(tz)).strftime("%H:%M:%S")
        print "****HORA", hora_factura_utc.strftime("%H:%M:%S"), hora_factura_local, tz

        #Tipo de cambio
        #--------------
        #Si es pesos poner 1 directo
        if invoice.currency_id.name == 'MXN':
            rate = 1.0
        #Si no, obtener el tipo de cambio
        #Esto funciona aunque la moneda base no sea el peso
        else:
            model_data = self.pool.get("ir.model.data")
            mxn_rate = model_data.get_object(cr, uid, 'base', 'MXN').rate
            rate = (1.0 / invoice.currency_id.rate) * mxn_rate

        comprobante.atributos.update({
            'serie': invoice.journal_id.serie or '',
            'Moneda': invoice.currency_id.name,
            'TipoCambio': round(rate, 4), #De acuerdo al diario oficial de la federacion son 4 decimales
            'NumCtaPago': invoice.cuentaBanco,
            'LugarExpedicion': invoice.journal_id and invoice.journal_id.lugar or "",
            'metodoDePago': invoice.formapago_id and invoice.formapago_id.name or "No identificado",
            'formaDePago': "Pago en una sola exhibicion",
            'fecha': str(invoice.date_invoice) + "T" + hora_factura_local,
            'folio': invoice.internal_number,
            'tipoDeComprobante': (invoice.type == 'out_invoice' and 'ingreso') or (invoice.type == 'out_refund' and 'egreso'),
            'subTotal': round((invoice.amount_untaxed or 0.0), dp),
            'total': round((invoice.amount_total or 0.0), dp),
        })

        if invoice.discount_type:
            comprobante.atributos.update({'descuento': round(invoice.discount, dp)})
        
        emisor = Nodo(ns+'Emisor', {
            'rfc': invoice.company_id.partner_id.vat or "",
            'nombre': invoice.company_id.partner_id.name or "",
        }, comprobante)
        
        domicilioFiscal = Nodo(ns+'DomicilioFiscal', {
            'calle': invoice.company_id.partner_id.street  or "",
            'noExterior': invoice.company_id.partner_id.noExterior  or "",  
            'noInterior': invoice.company_id.partner_id.noInterior  or "",
            'localidad': invoice.company_id.partner_id.ciudad_id and invoice.company_id.partner_id.ciudad_id.name or "",
            'colonia': invoice.company_id.partner_id.colonia_id and invoice.company_id.partner_id.colonia_id.name or "",
            'municipio': invoice.company_id.partner_id.municipio_id and invoice.company_id.partner_id.municipio_id.name or "",
            'estado': invoice.company_id.partner_id.state_id and invoice.company_id.partner_id.state_id.name or "",
            'pais': invoice.company_id.partner_id.country_id and invoice.company_id.partner_id.country_id.name or "",
            'codigoPostal': invoice.company_id.partner_id.zip or "",
        }, emisor)
        
        regimenFiscal = Nodo(ns+'RegimenFiscal', {
            'Regimen': invoice.company_id.partner_id.regimen_id and invoice.company_id.partner_id.regimen_id.name or ""
        }, emisor)
        
        receptor = Nodo(ns +'Receptor', {
            'rfc': invoice.partner_id.vat or "",
            'nombre': invoice.partner_id.name or "",
        }, comprobante)
        
        domicilio = Nodo(ns+'Domicilio', {
            'calle': invoice.partner_id.street or "",
            'noExterior': invoice.partner_id.noExterior or "",
            'noInterior': invoice.partner_id.noInterior or "",
            'localidad': invoice.partner_id.ciudad_id and invoice.partner_id.ciudad_id.name  or "",
            'colonia': invoice.partner_id.colonia_id and invoice.partner_id.colonia_id.name  or "",
            'municipio': invoice.partner_id.municipio_id and invoice.partner_id.municipio_id.name or "",
            'estado': invoice.partner_id.state_id and invoice.partner_id.state_id.name or "",
            'pais': invoice.partner_id.country_id and invoice.partner_id.country_id.name or "",
            'codigoPostal': invoice.partner_id.zip or ""
        }, receptor)
        
        conceptos = Nodo(ns+'Conceptos', padre=comprobante)
        
        impuestos_traslados = {}
        impuestos_retenidos = {}
        tasas = {}
        cfdi_impuestos = {}
        tax_obj = self.pool.get("account.tax")
        for line in invoice.invoice_line:
            #if line.product_id:
            #    unidad = line.product_id.uos_id and line.product_id.uos_id.name or ""
            #else:
            #    unidad = line.uos_id and line.uos_id.name or ""
            concepto = Nodo(ns+'Concepto', {
                'descripcion': line.name  or "",
                'importe': round(line.price_subtotal, dp),
                'valorUnitario': round(line.price_unit, dp),
                'cantidad': round(line.quantity, dp),
                'unidad': line.uos_id and line.uos_id.name or "",
                'noIdentificacion': line.product_id and line.product_id.default_code or ""
            }, conceptos)
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
                    raise osv.except_osv("Error", "El impuesto %s no tiene categoria CFD"%tax.name)
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
            
        impuestos = Nodo(ns+'Impuestos', padre=comprobante)
        retenciones = Nodo(ns+'Retenciones', padre=impuestos)
        traslados = Nodo(ns+'Traslados', padre=impuestos)
        
        totalImpuestosTrasladados = 0
        totalImpuestosRetenidos = 0
        if len(invoice.tax_line) == 0:
            traslado = Nodo(ns+'Traslado', {
                  'impuesto':'IVA',
                  'tasa': '0.00',
                  'importe': '0.00'},
                traslados)
                
        for impuesto in impuestos_retenidos:
            importe = abs(sum(impuestos_retenidos[impuesto]))
            Nodo(ns+'Retencion', {
                    'impuesto': impuesto,
                    'importe': importe
                }, retenciones)
            totalImpuestosRetenidos += importe

        for impuesto in impuestos_traslados:
            importe = sum(impuestos_traslados[impuesto])
            Nodo(ns+'Traslado', {
                    'impuesto': impuesto,
                    'importe': importe,
                    'tasa': tasas[impuesto]
                }, traslados)
            totalImpuestosTrasladados += importe        
                
        impuestos.atributos.update({
            'totalImpuestosTrasladados': totalImpuestosTrasladados,
            'totalImpuestosRetenidos': totalImpuestosRetenidos
        })
        
        #Nombre largo de la moneda. Si es MXN poner 'pesos' a menos que se haya puesto algo en el campo de nombre largo
        #Si no es MXN poner lo que está en el campo de nombre largo o en su defecto el código de la moneda
        if invoice.currency_id.name == 'MXN':
            nombre = invoice.currency_id.nombre_largo or 'pesos'
            siglas = 'M.N.'
        else:
            nombre = invoice.currency_id.nombre_largo or invoice.currency_id.name
            siglas = ''
        invoice.cantLetra = amount_to_text().amount_to_text_cheque(float(invoice.amount_total), nombre, siglas).capitalize()
                
        # *********************** Sellado del XML ************************
        tmpfiles = TempFileTransaction()
           
        xml = comprobante.toxml()
        fname_xml = tmpfiles.save(xml, 'xml_sin_sello')

        current_path = os.path.dirname(os.path.abspath(inspect.getfile(inspect.currentframe())))
        if version == '2.2':
            fname_xslt = current_path+'/SAT/cadenaoriginal_2_2.xslt'
        elif version == '3.2':
            fname_xslt = current_path+'/SAT/cadenaoriginal_3_2.xslt'
        fname_cadena = tmpfiles.create("cadenaori")
        os.system("xsltproc --output %s %s %s"%(fname_cadena, fname_xslt, fname_xml))
        
        certificate = self._get_certificate(cr, uid, id, invoice)
        fname_cer_pem = tmpfiles.decode_and_save(certificate.cer_pem)
        fname_key_pem = tmpfiles.decode_and_save(certificate.key_pem)
        
        sello = openssl.sign_and_encode(fname_cadena, fname_key_pem)
        certificado = ''.join(open(fname_cer_pem).readlines()[1:-1])
        certificado = certificado.replace('\n', '')
        comprobante.atributos.update({
            'sello': sello,
            'certificado': certificado,
            'noCertificado': certificate.serial
        })
        
        # ************************ Addenda *********************************
        nodo_addenda = False
        conf_addenda_obj = self.pool.get('cfdi.conf_addenda')
        conf_addenda_ids = conf_addenda_obj.search(cr, uid, [('partner_ids','in',invoice.partner_id.id)])
        if conf_addenda_ids:
            conf_addenda = conf_addenda_obj.browse(cr, uid, conf_addenda_ids[0])
            addenda_obj = self.pool.get(conf_addenda.model)
            addenda = addenda_obj.create_addenda(Nodo, invoice)
            if conf_addenda.model == "cfdi.addenda_detallista":
                nom_nodo = "Complemento"
            else:
                nom_nodo = "Addenda"
            nodo_addenda = Nodo(ns+nom_nodo).append(addenda)
            addenda_obj.set_namespace(comprobante, nodo_addenda)
            
        # *************** Guardar XML y timbrarlo en su caso ***************
        cfd = comprobante.toxml()
        if version == '3.2':
            cfd_b64 = base64.b64encode(cfd.encode("utf-8"))
            res = self._sign_cfdi(cr, uid, invoice, cfd_b64, test)
            if res.startswith('ERROR'):
                m = re.search('text = "(.*?)"', res, re.DOTALL)
                error = m and m.group(1) or res
                raise osv.except_osv("Error", error)
            cfd = res
            uuid = re.search('UUID="(.*?)"', cfd).group(1)
            fecha_timbrado = re.search('FechaTimbrado="(.*?)"', cfd).group(1)
            sello_sat = re.search('selloSAT="(.*?)"', cfd).group(1)
            certificado_sat = re.search('noCertificadoSAT="(.*?)"', cfd).group(1)
        if nodo_addenda:
            xml_add = nodo_addenda.toxml(header=False)
            end_tag = "</"+ns+"Comprobante>"
            cfd = cfd.replace(end_tag, xml_add + end_tag)    
        cfd_b64 = base64.b64encode(cfd.encode("utf-8"))
        fname = "cfd_"+invoice.number + ".xml"
        attachment_values = {
            'name': fname,
            'datas': cfd_b64,
            'datas_fname': fname,
            'description': 'Comprobante Fiscal Digital',
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
            'noCertificado': certificate.serial,
            'cantLetra': invoice.cantLetra,
            'tipo_cambio': rate,
        }
        if version == '2.2':
            values.update({
                'serie': aprobacion.serie,
                'noAprobacion': aprobacion.noAprobacion,
                'anoAprobacion': aprobacion.anoAprobacion
            })
        elif version == '3.2':
            values.update({
                'uuid': uuid.replace('-',''),
                'serie': invoice.journal_id.serie or '',
                'qrcode': self._make_qrcode(invoice, uuid),
                'test': test,
                'sello_sat': sello_sat,
                'certificado_sat': certificado_sat,
                'fecha_timbrado': fecha_timbrado,
                'cadena_sat': re.sub("(.{80})", "\\1\n", '||1.0|%s|%s|%s|%s||'%(uuid.lower(), fecha_timbrado,
                    sello_sat, certificado_sat), 0, re.DOTALL)
            })

        self.pool.get('account.invoice').write(cr, uid, invoice.id, values)

        tmpfiles.clean() 
        
account_invoice()    


#Para que tambien se mande el xml

class mail_compose_message(osv.TransientModel):
    _inherit = 'mail.compose.message'
    
    def onchange_template_id(self, cr, uid, ids, template_id, composition_mode, model, res_id, context=None):
        print "******onchange_template_id", context
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
       
