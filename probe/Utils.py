#!/usr/bin/python
#
# mPlane QoE Probe
#
# (c) 2013-2014 mPlane Consortium (http://www.ict-mplane.eu)
#               Author: Marco Milanesio <milanesio.marco@gmail.com>
#
# This program is free software: you can redistribute it and/or modify it under
# the terms of the GNU Lesser General Public License as published by the Free
# Software Foundation, either version 3 of the License, or (at your option) any
# later version.
#
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
# FOR A PARTICULAR PURPOSE.  See the GNU Lesser General Public License for more
# details.
#
# You should have received a copy of the GNU General Public License along with
# this program.  If not, see <http://www.gnu.org/licenses/>.
#
import json

# quantile in (0,1)
def compute_quantile(data, quantile):
    if quantile < 0 or quantile > 1:
        print "Percentile value out of bounds!"
        return
    index = int((len(data) + 1) * quantile)
    return sorted(data)[index]


def add_wildcard_to_addr(addr):
    return '%'+addr.strip()+'%'

def __file_to_array(filename, separator):
    fileobj = open(filename, "r")
    str_ = fileobj.read()
    fileobj.close()
    return str_.split(separator)

#Read json formatted file.
def read_file(filename, separator):
    strarray = __file_to_array(filename, separator)
    rows = []
    for line in strarray:
        try:
            jsonstring = json.loads(line)
            rows.append(jsonstring)
        except ValueError:
            print line
            continue
    return rows
