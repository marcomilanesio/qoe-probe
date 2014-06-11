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

import subprocess
import json
import re


class Measure(object):
    def __init__(self, host):
        self.target = host
        self.result = {}

    def get_result(self):
        return self.result


class Ping(Measure):
    def __init__(self, host):
        Measure.__init__(self, host)
        self.cmd = 'ping -c 3 %s ' % self.target

    def run(self):
        #logger.info('pinging %s' % self.target )
        print 'pinging %s ' % self.target
        ping = subprocess.Popen(self.cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True)
        out, error = ping.communicate()
        res = out.strip().split('\n')[-1].split(' = ')[1].split()[0]
        rttmin = rttavg = rttmax = rttmdev = -1.0
        try:
            rttmin, rttavg, rttmax, rttmdev = map(float, res.strip().split("/"))
            #logger.info('rtts - %.3f, %.3f, %.3f, %.3f' % (rttmin, rttavg, rttmax, rttmdev) )
            #print rttmin, rttavg, rttmax, rttmdev
        except ValueError:
            #logger.error('Unable to map float in do_ping [%s]' % out.strip())
            print '''logger.error('Unable to map float in do_ping [%s]' % out.strip())'''
        self.result = json.dumps({'min': rttmin, 'max':rttmax, 'avg':rttavg, 'std':rttmdev})


class Traceroute(Measure):
    HEADER_REGEXP = re.compile(r'traceroute to (\S+) \((\d+\.\d+\.\d+\.\d+)\)')

    def __init__(self, host, maxttl=32):
        Measure.__init__(self, host)
        self.cmd = 'traceroute -n -m %d %s ' % (maxttl, self.target)

    def run(self):
        print self.cmd
        fname = self.target + '.traceroute'
        outfile = open(fname, 'w')
        traceroute = subprocess.Popen(self.cmd, stdout=outfile, stderr=subprocess.PIPE, shell=True)
        _,  err = traceroute.communicate()
        if not err:
            print 'ok'
        outfile.close()
        self.parse_file(fname)

    def parse_file(self, outfile):
        f = open(outfile, 'r')
        arr = f.readlines()
        f.close()
        result = []
        for line in arr:
            if self.HEADER_REGEXP.match(line):  # header
                continue
            else:
                hop = Traceroute._parse_line(line)
                result.append(hop.__dict__)
        self.result = json.dumps(result)

    @staticmethod
    def _parse_line(line):
        hop = line.split()
        hop_nr = hop[0]
        hop.pop(0)
        remains = [x for x in hop if x != 'ms']
        t_hop = TracerouteHop(hop_nr)
        t_hop.add_measurement(remains)
        return t_hop


class TracerouteHop(object):
    IPADDR_REGEXP = re.compile(r'\d+\.\d+\.\d+\.\d+')

    def __init__(self, hop_nr):
        self.hop_nr = int(hop_nr)
        self.ip_addr = None
        self.rtt = 0.0
        self.endpoints = []

    def add_measurement(self, arr_data):
        _endpoints = [x for x in arr_data if self.IPADDR_REGEXP.match(x)]
        if len(_endpoints) == 0:  # no ip returned (3 packet drops)
            self.ip_addr = 'n.a.'
            self.rtt = -1
            return

        if len(_endpoints) > 1:  # more endpoints
            self.endpoints = _endpoints[1:]
        self.ip_addr = _endpoints[0]

        clean = [x for x in arr_data if x not in _endpoints and x != '*']

        if len(clean) > 0:
            self.rtt = min(map(float, clean))
        else:
            self.rtt = -1

    def __str__(self):
        return '%d: %s, %.3f %s' % (self.hop_nr, self.ip_addr, self.rtt, str(self.endpoints))

if __name__ == '__main__':
    t = '8.8.8.8'
    pi = Ping(t)
    tr = Traceroute(t)
    pi.run()
    tr.run()
    print pi.get_result()
    print tr.get_result()