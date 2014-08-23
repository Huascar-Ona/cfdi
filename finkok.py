###################################
# Servicio de timbrado de Finkok  #
###################################

from openerp.osv import osv
import suds
import tempfile
import os
import base64

def timbrar(host, user, password, xml):
    client = suds.client.Client(host, cache=None)
    soapresp = client.service.stamp(xml, user, password)
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

    result = client.service.cancel(invoices_list, username, password, taxpayer_id, cer_file, key_file_b64)
    #print client.last_sent()
    #print result
    return result
