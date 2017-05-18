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

import tempfile
import base64
import os
import codecs

class TempFileTransaction:
    def __init__(self):
        self.tempfiles = []
        self.fds = []
        
    def _get_prefix(self, prefix):
        return "openerp_cfd_mx_"+prefix+"_"
        
    def create(self, prefix=""):
        fd, fname = tempfile.mkstemp(prefix=self._get_prefix(prefix))
        self.add_file(fname)
        self.fds.append(fd)
        return fname

    def decode_and_save(self, b64str, prefix=""):
        fname = self.create(prefix)
        f = open(fname, "wb")
        f.write(base64.b64decode(b64str))
        f.close()
        return fname
        
    def save(self, txt, prefix=""): 
        fname = self.create(prefix)
        f = open(fname, "w")
        f.write(txt)
        f.close()
        return fname
        
    def load_and_encode(self, fname):
        f = open(fname, "r")
        return base64.b64encode(f.read())
        
    def load(self, fname):
        f = open(fname, "r")
        return f.read()
        
    def add_file(self, fname):
        self.tempfiles.append(fname)
        
    def clean(self):
        for fd in self.fds:
            try:
                os.close(fd)
                #print "cerrando", fd
            except:
                pass
        for fname in self.tempfiles:
            os.unlink(fname)
