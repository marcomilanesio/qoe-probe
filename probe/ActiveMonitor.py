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
import threading
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
        self.session_dic = self._get_inserted_sid_addresses()
        logger.debug('Loaded %d sessions.' % len(self.session_dic.keys()))
        
    def _get_inserted_sid_addresses(self):
        result = {}
        q = "select distinct on (sid, session_url, remote_ip) sid, session_url, remote_ip FROM %s where sid not in (select distinct sid from active)" % (self.raw_table_name)
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
        #print 'result _get_inserted_sid_addresses', result
        return result


    # build trace object from trace files
    # tracefile = traceroute files
    # mtrfname = mtr file 
    def build_trace(self, target, tracefile, mtrfile):
        result = {}
        t = TracerouteParser(target)
        t.parse_traceroutefile(tracefile)
	try:
            os.remove(tracefile) # remove packed trace file as root
        except OSError, e:
            logger.error('Error in removing packed tracefile %s' % tracefile)
        #t.parse_mtrfile(mtrfile)
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
    
    
    def _execute(self, c, outfilename):
        outfile = open(outfilename, 'w')
	traceroute = subprocess.Popen(c, stdout=outfile, stderr=subprocess.PIPE)
        _, err = traceroute.communicate()
        if err:
            logger.error( "Error in: %s" % c )
        logger.debug('command executed [%s]' % c)
        outfile.close()
    
    def do_traceroute(self, target, maxttl=32):
        trace_udp = "traceroute -n -m %d %s" % (maxttl, target)
        trace_tcpsyn = "traceroute -n -T -m %d %s" % (maxttl, target)
        trace_icmp = "traceroute -n -I -m %d %s" % (maxttl, target)
        trace_mtr = "mtr -n --report --report-cycles 20 %s" % target
        #cmds = [trace_udp,trace_tcpsyn,trace_icmp,trace_mtr]
	cmds = [trace_icmp]        
	traceroute_fnames = []
        mtrfilename = '%s.mtr' % target
        thread_list = []
        i = 0
        for cmd in cmds:
            cmdline = cmd.split(" ")
            i += 1
            if cmdline[0] == 'traceroute':
                if re.match('-T', cmdline[2]):
                    protocol = 'tcpsyn'
                elif re.match('-I', cmdline[2]):
                    protocol = 'icmp'
                else:
                    protocol = 'udp'
                fname = '%s.trace_%s' % (target, protocol)
                traceroute_fnames.append(fname)
            else:
                fname = mtrfilename
                
            t = threading.Thread(target=self._execute, args=(cmdline,fname,))
            thread_list.append(t)
            
        for thread in thread_list:
            thread.start()

        for thread in thread_list:
            logger.debug(thread.join())

        logger.info('Traceroute to %s terminated' % target)
        tracefilename = Utils.pack_files( traceroute_fnames, target + '.trace')
        return self.build_trace(target, tracefilename, mtrfilename)
        
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
