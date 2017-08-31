# -*- coding: utf-8 -*-
from openerp import api,fields,models

class c_Aduana(models.Model):
    _name = "cfdi.c_aduana"
    
    name = fields.Char(u"Descripción", required=True)
    code = fields.Char(u"Código", required=True)


class c_ClaveProdServ(models.Model):
    _name = "cfdi.c_claveprodserv"
    
    name = fields.Char(u"Descripción", required=True)
    code = fields.Char(u"Código", required=True)
    incluir_iva = fields.Selection([('si','Sí'),('no','No'),('opcional','Opcional')], "Incluir IVA trasladado")
    incluir_ieps = fields.Selection([('si','Sí'),('no','No'),('opcional','Opcional')], "Incluir IEPS trasladado")
    complemento = fields.Char("Complemento que debe incluir")
    fecha_inicio = fields.Date("Fecha inicio vigencia")
    fecha_fin = fields.Date("Fecha fin vigencia")  
  
class c_ClaveUnidad(models.Model):
    _name = "cfdi.c_claveunidad"
    
    name = fields.Char(u"Nombre", required=True)
    code = fields.Char(u"Código SAT", required=True)
    symbol = fields.Char(u"Símbolo")
    desc = fields.Text(u"Descripción")
    fecha_inicio = fields.Date("Fecha inicio vigencia")
    fecha_fin = fields.Date("Fecha fin vigencia")  

    
class c_Impuesto(models.Model):
    _name = "cfdi.c_impuesto"

    name = fields.Char(u"Descripción", required=True)
    code = fields.Char(u"Código", required=True)
    retencion = fields.Boolean(u"Retención")
    traslado = fields.Boolean(u"Traslado")
    local_o_federal = fields.Selection([('local','Local'),('federal','Federal')],string="Local o Federal")
    entidad = fields.Many2one("res.country.state", string="Entidad en la que aplica")


class c_MetodoPago(models.Model):
    _name = "cfdi.c_metodopago"

    name = fields.Char(u"Descripción", required=True)
    code = fields.Char(u"Código", required=True)


class c_NumPedimentoAduana(models.Model):
    _name = "cfdi.c_numpedimentoaduana"

    name = fields.Char(u"Patente", required=True)
    code = fields.Char(u"Código", required=True)
    ejercicio = fields.Integer(u"Ejercicio", required=True)
    cantidad = fields.Char(u"Cantidad", required=True)


class c_PatenteAduanal(models.Model):
    _name = "cfdi.c_patenteaduanal"

    name = fields.Char("Pantente aduanal")
    fecha_inicio = fields.Date("Fecha inicio vigencia")     
    fecha_fin = fields.Date("Fecha fin vigencia")     

class c_TasaOCuota(models.Model):
    _name = "cfdi.c_tasaocuota"

    rango_o_fijo = fields.Selection([('rango','Rango'),('fijo','Fijo')], string="Rango o Fijo")
    valor_minimo = fields.Float(u"Valor mínimo")
    valor_maximo = fields.Float(u"Valor máximo")
    impuesto = fields.Char("Impuesto")
    factor = fields.Many2one("cfdi.c_tipofactor", "Factor")
    retencion = fields.Boolean(u"Retención")
    traslado = fields.Boolean(u"Traslado")


class c_TipoDeComprobante(models.Model):
    _name = "cfdi.c_tipodecomprobante"

    name = fields.Char(u"Patente", required=True)
    code = fields.Char(u"Código", required=True)
    valor_maximo = fields.Float(u"Valor máximo")        


class c_TipoFactor(models.Model):
    _name = "cfdi.c_tipofactor"

    name = fields.Char(u"Descripción", required=True)


class c_TipoRelacion(models.Model):
    _name = "cfdi.c_tiporelacion"

    name = fields.Char(u"Descripción", required=True)
    code = fields.Char(u"Código", required=True)


class c_UsoCFDI(models.Model):
    _name = "cfdi.c_usocfdi"

    name = fields.Char(u"Patente", required=True)
    code = fields.Char(u"Código", required=True)
    fisica = fields.Boolean(u"Aplica para física")
    moral = fields.Boolean(u"Aplica para moral")
    fecha_inicio = fields.Date("Fecha inicio vigencia")
    fecha_fin = fields.Date("Fecha fin vigencia")

