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
import logging
from DBClient import DBClient

logger = logging.getLogger('Active')


class Measure(object):
    def __init__(self, host):
        self.target = host
        self.result = {}
        self.cmd = ''

    def get_result(self):
        return self.result

    def get_cmd(self):
        return self.cmd


class Ping(Measure):
    def __init__(self, host):
        Measure.__init__(self, host)
        self.cmd = 'ping -c 3 %s ' % self.target

    def run(self):
        ping = subprocess.Popen(self.cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True)
        out, error = ping.communicate()
        res = out.strip().split('\n')[-1].split(' = ')[1].split()[0]
        rttmin = rttavg = rttmax = rttmdev = -1.0
        try:
            rttmin, rttavg, rttmax, rttmdev = map(float, res.strip().split("/"))
            logger.info('rtts - %.3f, %.3f, %.3f, %.3f' % (rttmin, rttavg, rttmax, rttmdev) )
        except ValueError:
            logger.error('Unable to map float in do_ping [%s]' % out.strip())
        self.result = json.dumps({'min': rttmin, 'max':rttmax, 'avg':rttavg, 'std':rttmdev})


class Traceroute(Measure):
    HEADER_REGEXP = re.compile(r'traceroute to (\S+) \((\d+\.\d+\.\d+\.\d+)\)')

    def __init__(self, host, maxttl=32):
        Measure.__init__(self, host)
        self.cmd = 'traceroute -n -m %d %s ' % (maxttl, self.target)

    def run(self):
        fname = self.target + '.traceroute'
        outfile = open(fname, 'w')
        traceroute = subprocess.Popen(self.cmd, stdout=outfile, stderr=subprocess.PIPE, shell=True)
        _,  err = traceroute.communicate()
        if err:
            logger.error('Error in %s' % self.cmd)
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


class Monitor(object):
    def __init__(self, config):
        self.config = config
        self.db = DBClient(config)
        self.inserted_sid = self.db.get_inserted_sid_addresses()
        logger.info('Started active monitor: %d session(s).' % len(self.inserted_sid))

    def run_active_measurement(self):
        tot = {}
        probed_ip = {}
        for sid, dic in self.inserted_sid.iteritems():
            if sid not in tot.keys():
                tot[sid] = []
            url = dic['url']
            ip_addrs = dic['address']
            for ip in ip_addrs:
                if ip not in probed_ip.keys():
                    probed_ip[ip] = []
                probed_ip[ip].append(sid)

                if len(probed_ip[ip]) > 1:
                    logger.debug('IP address [%s] already computed, skipping new ping/trace' % ip)
                    c_sid = probed_ip[ip][0]
                    logger.debug('First sid found for IP [%s] : %d' % (ip, c_sid))
                    logger.debug('Found %d measurements. ' % len(tot[c_sid]))
                    ping = tot[c_sid][0]['ping']
                    logger.debug('Ping for IP [%s] : %s' % (ip, str(ping)))
                    trace = tot[c_sid][0]['trace']
                    logger.debug('Trace for IP [%s] : %s' % (ip, str(trace)))
                else:
                    c_sid = sid
                    ping = Ping(ip)
                    trace = Traceroute(ip)
                    logger.info('Running: %s ' % ping.get_cmd())
                    ping.run()
                    logger.info('Running: %s ' % trace.get_cmd())
                    trace.run()

                logger.debug('current %d, inserted from %d' % (sid, c_sid))
                tot[sid].append({'url': url, 'ip': ip, 'ping': ping.get_result(), 'trace': trace.get_result()})
                probed_ip[ip].append(sid)
                logger.info('Computed Active Measurement for %s in session %d' % (ip, sid))

        self.db.insert_active_measurement(tot)
        logger.info('ping and traceroute saved into db.')


if __name__ == '__main__':
    t = '8.8.8.8'
    pi = Ping(t)
    tr = Traceroute(t)
    pi.run()
    tr.run()
    print pi.get_result()
    print tr.get_result()