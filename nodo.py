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

class Nodo:
    def __init__(self, nombre, atributos={}, padre=None, valor=None):
        self.nombre = nombre
        self.atributos = atributos or {}
        self.hijos = []
        if padre:
            padre.append(self)
        if not valor is None:
            self.hijos.append(valor)
        
    def append(self, *hijos):
        for hijo in hijos:
            self.hijos.append(hijo)
        return self
                
    def __getitem__(self, key):
        return self.atributos[key]
        
    def __setitem__(self, key, value):
        self.atributos[key] = value
        
    def xml_escape(self, cadena):
        cadena = cadena.replace("&", "--ampersand--")
        cadena = cadena.replace('"', "&quot;")
        cadena = cadena.replace('<', "&lt;")
        cadena = cadena.replace('>', "&gt;")
        cadena = cadena.replace("'", "&apos;")
        cadena = cadena.replace('--ampersand--', "&amp;")
        return cadena
    
    def toxml(self, header=True):
        if len(self.hijos) == 0 and len(self.atributos) == 0:
            return ""
        texto = "<"+self.nombre
        for atributo,valor in self.atributos.iteritems():
            try:
                valor = str(valor)
            except:
                pass
            if valor:
                texto += " "+atributo+"="+'"'+self.xml_escape(valor)+'"'
        if not self.hijos:
            texto += "/>"
        else:
            texto += ">"
            for hijo in self.hijos:
                if isinstance(hijo, Nodo):
                    hijo = hijo.toxml(header=False)
                elif type(hijo) != unicode:
                    try:
                        hijo = str(hijo)
                        hijo = self.xml_escape(hijo)
                    except:
                        print "******hijo malo",type(hijo)
                else:
                    hijo = self.xml_escape(hijo)
                texto += hijo
            texto += "</"+self.nombre+">"
        if header:
            texto = '<?xml version="1.0" encoding="UTF-8"?>' + texto
        return texto
        
        
