##################################
# Servicio de timbrado de Tralix #
##################################

import httplib
from lxml import etree
from openerp.osv import osv
 
def timbrar(xml_data, customer_key, hostname):  
    parser = etree.XMLParser(ns_clean=True, recover=True, encoding='utf-8')
    objroot = etree.fromstring(xml_data, parser=parser)
    NS = "http://schemas.xmlsoap.org/soap/envelope/"
    TREE = "{%s}" % NS
    NSMAP = {"soapenv": NS}
    soapobj = etree.Element(TREE + "Envelope", nsmap=NSMAP)
    header = etree.SubElement(soapobj, TREE + "Header")
    body = etree.SubElement(soapobj, TREE + "Body")
    body.append(objroot)
    sendstr = etree.tostring(soapobj, pretty_print=True, encoding="utf-8", xml_declaration=True)
    portnum = 7070
    conn = httplib.HTTPSConnection(hostname, portnum)
    conn.connect()
    conn.putrequest('POST', '/')
    conn.putheader("Content-Type", "text/xml;charset=UTF-8")
    conn.putheader("SOAPAction", '"urn:TimbradoCFD"')
    conn.putheader("CustomerKey", customer_key)
    conn.putheader("User-Agent", "Python httplib client")
    conn.putheader("Content-Length", str(len(sendstr)))
    conn.endheaders()
    conn.send(sendstr)
    respobj = etree.parse(conn.getresponse())
    envelope = respobj.getroot()
    body = envelope.getchildren()[0]
    if not "body" in body.tag.lower():
        raise osv.except_osv("Error", "Error en cuerpo de respuesta.")
    child = body.getchildren()[0]
    if "fault" in child.tag.lower():
        detail = child.getchildren()[0]
        error = detail.getchildren()[0]
        codigo = error.attrib["codigo"]
        desc = error.getchildren()[0].text.encode("iso-8859-1")
        print "Error %s:\n %s" %(codigo, desc)
        raise osv.except_osv("Error", "Error %s: %s" %(codigo, desc))
    timbre = etree.tostring(respobj.getroot())
    timbre = timbre[timbre.index("<tfd"):timbre.index("/>")+2]
    return xml_data.replace("</cfdi:Comprobante>", \
        "<cfdi:Complemento>"+timbre+"</cfdi:Complemento></cfdi:Comprobante>")\
        .decode("utf-8")
