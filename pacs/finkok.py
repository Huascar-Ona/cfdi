###################################
# Servicio de timbrado de Finkok  #
###################################

from openerp.osv import osv
import suds
import tempfile
import os
import base64

def timbrar(invoice, xml, test):
    if not test and not invoice.company_id.cfdi_finkok_host:
       raise osv.except_osv("Error", "No se ha definido la direccion para el timbrado de Finkok")
    if test and not invoice.company_id.cfdi_finkok_host_test:
       raise osv.except_osv("Error", "No se ha definido la direccion para el timbrado de Finkok modo pruebas")
    if not invoice.company_id.cfdi_finkok_user or not invoice.company_id.cfdi_finkok_key:
        raise osv.except_osv("Error", "No se ha definido user y password de Finkok")
    host = invoice.company_id.cfdi_finkok_host if not test else invoice.company_id.cfdi_finkok_host_test
    user = invoice.company_id.cfdi_finkok_user
    password = invoice.company_id.cfdi_finkok_key

    client = suds.client.Client(host, cache=None)
    xml = base64.b64encode(xml)
    soapresp = client.service.stamp(xml, user, password)
    #print soapresp
    if soapresp["xml"]:
        return soapresp["xml"]
    else:
        error = ""
        for incidencia in soapresp["Incidencias"]:
            for x in incidencia[1]:
                error += x["MensajeIncidencia"] + "\n"
        raise osv.except_osv("Error Finkok", error)

def cancelar(invoice, certificate):
    rfc = invoice.company_id.partner_id.vat
    uuid = invoice.uuid
    pfx_data_b64 = certificate.pfx
    pfx_password = certificate.pfx_password
    cer_file = certificate.cer_pem
    key_file = certificate.key_pem

    if not invoice.test and not invoice.company_id.cfdi_finkok_host_cancel:
        raise osv.except_osv("Error", "No se ha definido la direccion para la cancelacion de Finkok")
    if invoice.test and not invoice.company_id.cfdi_finkok_host_cancel_test:
        raise osv.except_osv("Error", "No se ha definido la direccion para la cancelacion de Finkok modo pruebas")
    if not invoice.company_id.cfdi_finkok_user or not invoice.company_id.cfdi_finkok_key:
        raise osv.except_osv("Error", "No se ha definido user y password de Finkok")
    host = invoice.company_id.cfdi_finkok_host_cancel if not invoice.test else invoice.company_id.cfdi_finkok_host_cancel_test
    user = invoice.company_id.cfdi_finkok_user
    password = invoice.company_id.cfdi_finkok_key
    invoices = [uuid]

    client = suds.client.Client(host, cache=None)

    # The next lines are needed by the python suds library
    invoices_list = client.factory.create("cancel.UUIDS")
    invoices_list.uuids.string = invoices

    #encriptar llave
    fd, fname = tempfile.mkstemp(prefix="openerp_cfdi_finkok")
    #print fname
    with open(fname, "w") as f:
        f.write(base64.decodestring(key_file))
    enc = os.popen("openssl rsa -in %s -des3 -passout pass:%s"%(fname, password)).read()
    #print enc
    os.unlink(fname)
    
    #Codificar pem en b64
    key_file_b64 = base64.encodestring(enc)

    result = client.service.cancel(invoices_list, user, password, rfc, cer_file, key_file_b64)
    #print client.last_sent()
    #print result
    return result
