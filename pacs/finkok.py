# -*- coding: utf-8 -*-
###################################
# Servicio de timbrado de Finkok  #
###################################

from openerp.osv import osv
from suds.client import Client
import tempfile
import os
import base64

finkok_errors = {
    '201' : "UUID Cancelado exitosamente",
    '202' : "UUID Previamente cancelado",
    '203' : "UUID No corresponde el RFC del Emisor y de quien solicita la cancelación",
    '205' : "UUID No existe",
    '300' : "Usuario y contraseña inválidos",
    '301' : "XML mal formado",
    '302' : "Sello mal formado o inválido",
    '303' : "Sello no corresponde a emisor",
    '304' : "Certificado Revocado o caduco",
    '305' : "La fecha de emisión no esta dentro de la vigencia del CSD del Emisor",
    '306' : "El certificado no es de tipo CSD",
    '307' : "El CFDI contiene un timbre previo",
    '308' : "Certificado no expedido por el SAT",
    '401' : "Fecha y hora de generación fuera de rango",
    '402' : "RFC del emisor no se encuentra en el régimen de contribuyentes",
    '403' : "La fecha de emisión no es posterior al 01 de enero de 2012",
    '501' : "Autenticación no válida",
    '703' : "Cuenta suspendida",
    '704' : "Error con la contraseña de la llave Privada",
    '705' : "XML estructura inválida",
    '706' : "Socio Inválido",
    '707' : "XML ya contiene un nodo TimbreFiscalDigital",
    '708' : "No se pudo conectar al SAT",
}

def timbrar(host, user, password, xml):
    client = Client(host, cache=None)
    soapresp = client.service.stamp(xml, user, password)
    print client.last_sent()
    print soapresp
    if soapresp["xml"]:
        return soapresp["xml"]
    else:
        error = ""
        for incidencia in soapresp["Incidencias"]:
            for x in incidencia[1]:
                error += x["MensajeIncidencia"] + "\n"
        raise osv.except_osv("Error", error)

def cancelar(host, invoices, username, password, taxpayer_id, cer_file, key_file):
    client = Client(host, cache=None)

    # The next lines are needed by the python suds library
    invoices_list = client.factory.create("cancel.UUIDS")
    invoices_list.uuids.string = invoices

    #encriptar llave
    fd, fname = tempfile.mkstemp(prefix="openerp_cfd_mx_finkok")
    #print fname
    with open(fname, "w") as f:
        f.write(base64.decodestring(key_file))
    enc = os.popen("openssl rsa -in %s -des3 -passout pass:%s"%(fname, password)).read()
    #print enc
    os.unlink(fname)
    
    #Codificar pem en b64
    key_file_b64 = base64.encodestring(enc)

    result = client.service.cancel(invoices_list, username, password, taxpayer_id, cer_file, key_file_b64)
    with open("/tmp/debug_cancel", "w") as f:
        f.write(str(client.last_sent()))
    #print client.last_received()
    #print result
    return result
