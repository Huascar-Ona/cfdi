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

import files
import os
import base64
import re

def get_serial(fname_cer):
    h = os.popen("openssl x509 -in %s -serial -inform DER -noout"%(fname_cer)).read().split("=")[1]
    return ''.join([h[i] for i in range(1,len(h),2)])
    
def get_dates(fname_cer):
    res = os.popen("openssl x509 -in %s -inform DER -dates -noout"%(fname_cer)).read()
    start = re.search("notBefore=(\\w{3}) +(\\d{1,2}) +\\d{1,2}:\\d{2}:\\d{2} (\\d{4}) GMT", res)
    end = re.search("notAfter=(\\w{3}) +(\\d{1,2}) +\\d{1,2}:\\d{2}:\\d{2} (\\d{4}) GMT", res)
    months = {
        'Jan': '01',
        'Feb': '02',
        'Mar': '03',
        'Apr': '04',
        'May': '05',
        'Jun': '06',
        'Jul': '07',
        'Aug': '08',
        'Sep': '09',
        'Oct': '10',
        'Nov': '11',
        'Dec': '12'        
    }
    start_date = start.group(3) + "-" + months[start.group(1)] + "-" + start.group(2).rjust(2,'0')
    end_date = end.group(3) + "-" + months[end.group(1)] + "-" + end.group(2).rjust(2,'0')
    return start_date, end_date

def cer_to_pem(fname_cer):
    fname_cer_pem = fname_cer + ".pem"
    os.system("openssl x509 -inform DER -outform PEM -in %s -pubkey -out %s"%(fname_cer, fname_cer_pem))
    return fname_cer_pem

def key_to_pem(fname_key, password):
    fname_key_pem  = fname_key + ".pem"
    os.system("openssl pkcs8 -inform DER -in %s -passin pass:%s -out %s"%(fname_key, password, fname_key_pem))
    return fname_key_pem
    
def cer_and_key_to_pfx(fname_cer_pem, fname_key_pem, password):
    fname_pfx = fname_cer_pem + ".pfx"
    os.system("openssl pkcs12 -export -out %s -inkey %s -in %s -passout pass:%s"%(fname_pfx, fname_key_pem, fname_cer_pem, password))
    return fname_pfx
    
def sign_and_encode(fname_plaintext, fname_key_pem, func="sha1"):
     return base64.b64encode(os.popen("openssl dgst -%s -sign %s %s"%(func, fname_key_pem, fname_plaintext)).read())
