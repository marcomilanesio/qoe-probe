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
import subprocess
import sys
import socket
import struct
import re
import os
from TracerouteParser import TracerouteParser
import json
from DBClient import DBClient
import Utils
from Configuration import Configuration
from JSONClient import JSONClient
import logging
import logging.config


class ActiveMonitor():
    def __init__(self, config):
        self.raw_table_name = config.get_database_configuration()['rawtable']
        self.db = DBClient(config)
        self.session_dic = self.__get_inserted_sid_addresses()
        logger.debug('Loaded %d sessions.' % len(self.session_dic.keys()))
        
    def __get_inserted_sid_addresses(self):
        result = {}
        q = "select distinct on (sid, session_url, remoteaddress) sid, session_url, remoteaddress FROM %s where sid not in (select distinct sid from active)" % (self.raw_table_name)
        res = self.db.execute_query(q)
        for tup in res:
            cur_sid = tup[0]
            cur_url = tup[1]
            cur_addr = tup[2]
            if cur_addr == '0.0.0.0':
                continue
            if cur_sid in result.keys():
                if result[cur_sid]['url'] == cur_url:
                    result[cur_sid]['address'].append(cur_addr)
                else:
                    result[cur_sid]['url'] = cur_url
                    result[cur_sid]['address'].append(cur_addr)
            else:
                result[cur_sid] = {'url': cur_url, 'address' : [cur_addr]}
        #print 'result __get_inserted_sid_addresses', result
        return result


    # build trace object from trace files
    # tracefile = traceroute files
    # mtrfname = mtr file 
    def build_trace(self, target, tracefile, mtrfile):
        result = {}
        t = TracerouteParser(target)
        t.parse_traceroutefile(tracefile)
        t.parse_mtrfile(mtrfile)
        return json.dumps(t.get_results())

    def do_ping(self, host):
        result = {}
        cmdline = ["./probe/ping_activeprobe.sh", host]
        logger.info('pinging %s' % host )
        ping = subprocess.Popen(cmdline, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        out, error = ping.communicate()
        rttmin = rttavg = rttmax = rttmdev = -1.0
        try:
            rttmin, rttavg, rttmax, rttmdev = map(float, out.strip().split("/"))
            logger.info('rtts - %.3f, %.3f, %.3f, %.3f' % (rttmin, rttavg, rttmax, rttmdev) )
        except ValueError:
            logger.error('Unable to map float in do_ping [%s]' % out.strip())
            #print 'Error in Active monitor: unable to map float in do_ping: ', out
        return json.dumps({'min': rttmin, 'max':rttmax, 'avg':rttavg, 'std':rttmdev})

    def do_traceroute(self, target, maxttl=32):
        trace_udp = "traceroute -n -m %d %s" % (maxttl, target)
        trace_tcpsyn = "traceroute -n -T -m %d %s" % (maxttl, target)
        trace_icmp = "traceroute -n -I -m %d %s" % (maxttl, target)
        trace_mtr = "mtr -n --report --report-cycles 20 %s" % target
        
        if os.geteuid() != 0:
            logger.warning("You're not root - Using only UDP traceroute.")
            cmds = [trace_udp]
        else:
            cmds = [trace_udp, trace_tcpsyn, trace_icmp]
        tracefile = target + ".trace"
        outfile = open(tracefile, "w")
        
        for cmd in cmds:
            cmdline = cmd.split(" ")
            traceroute = subprocess.Popen(cmdline, stdout=outfile, stderr=subprocess.PIPE)
            _, err = traceroute.communicate()
            if err:
                logger.error("Error in: %s" % cmd)
                continue
            logging.info('traceroute executed [%s]' % cmd)
        
        outfile.write("\n")
        outfile.close()
        
        mtrfile = target + ".mtr"
        mtroutfile = open(mtrfile, 'w')
        mtr = subprocess.Popen(trace_mtr.split(" "), stdout=mtroutfile, stderr=subprocess.PIPE)
        _, err = mtr.communicate()
        if err:
            logger.error("Error in: %s" % trace_mtr)
        logging.info('traceroute executed [%s]' % trace_mtr)
        
        mtroutfile.close()
        return self.build_trace(target, tracefile, mtrfile)

    def do_probe(self):
        tot_active_measurement = {}
        for sid, url_addr in self.session_dic.iteritems():
            if sid not in tot_active_measurement.keys():
                tot_active_measurement[sid] = []
            url = url_addr['url']
            ip_addrs = url_addr['address']
            for ip in ip_addrs:
                ping = self.do_ping(ip)
                trace = self.do_traceroute(ip)
                tot_active_measurement[sid].append({'url' : url, 'ip': ip, 'ping' : ping, 'trace' : trace})
                logger.info('Computed Active Measurement for %s in session %d' % (ip, sid))
        self.db.insert_active_measurement(tot_active_measurement)
        logger.info('ping and traceroute saved into db.') 
            
        
        
def main(conf_file):
    config = Configuration(conf_file)
    a = ActiveMonitor(config)
    a.do_probe()
    logger.info('Probing ended...')
    cli = JSONClient(config)
    cli.prepare_and_send()

if __name__ == "__main__":
    if len(sys.argv) != 2:
        exit("%s: You MUST specify a config file" % sys.argv[0])
    logging.config.fileConfig('logging.conf')
    logger = logging.getLogger('ActiveMonitor')
    conf_file = sys.argv[1]
    main(conf_file)
