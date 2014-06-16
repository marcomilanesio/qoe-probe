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
from DBClient import DBClient
import logging

logger = logging.getLogger('LocalDiagnosisManager')


class LocalDiagnosisManager():
    def __init__(self, dbconn, clientid, sids):
        self.dbconn = dbconn
        self.sids = sids
        self.clientid = clientid
    
    def do_local_diagnosis(self):
        res = {}
        for sid in self.sids:
            session_start, idletime = self._get_client_idle_time(sid)
            print 'session_start, idletime: ', session_start, idletime
            httpresp = self._get_http_response_time(sid)
            print 'httpresp: ', httpresp
            pagedown = self._get_page_downloading_time(sid)
            dnsresp = self._get_dns_response_time(sid)
            tcpresp = self._get_tcp_response_time(sid)
            pagedim = self._get_page_dimension(sid)
            osstats = self._get_os_stats(sid)
            res[str(sid)] = {'idle': idletime, 'http': httpresp, 'tcp': tcpresp, 'tot': pagedown,
                             'dns': dnsresp, 'dim': pagedim, 'osstats': osstats, 'start': session_start}
        return res
         
    def _execute_obj_start_end_query(self, sid, full_load_time=True):
        q = '''select session_start, obj_start, obj_end, httpid, host,
            extract(minute from obj_start-session_start)*60*1000+extract(millisecond from obj_start-session_start) as relative_start, 
            extract(minute from obj_end-session_start)*60*1000+extract(millisecond from obj_end-session_start) as relative_end 
            from 
            (SELECT session_start, 
            case when dns_start>'1970-01-01 12:00:00' and dns_start<syn_start and dns_start<get_sent_ts then dns_start
            when syn_start>'1970-01-01 12:00:00' and syn_start<get_sent_ts then syn_start
            when get_sent_ts>'1970-01-01 12:00:00' then get_sent_ts else request_ts end as obj_start,
            case when end_time>'1970-01-01 12:00:00' then end_time
            when first_bytes_rcv>'1970-01-01 12:00:00' then first_bytes_rcv else request_ts end as obj_end,
            httpid, host from %s where sid=%d and cache is FALSE
            ''' % (self.dbconn.get_table_names()['raw'], sid)
        
        if full_load_time:
            q += ' and full_load_time > -1)t'
        else:
            q += ')t'
        
        res = self.dbconn.execute_query(q)
        return res
    
    def _get_client_idle_time(self, sid):
        found_zero = self.dbconn.check_for_zero_full_load_time()
        if len(found_zero) > 0:
            logger.warning('Found full_load_time = 0 in sessions %s. Updated.' % str(found_zero))
        res = self._execute_obj_start_end_query(sid)
        if len(res) == 0:
            logger.warning('sid %d, probe %d : full_load_time = -1' % (sid, self.clientid))
            res = self._execute_obj_start_end_query(sid, full_load_time=False)
            logger.warning('sid %d, probe %d : with no check on full_load_time, found %d objects' % (sid, self.clientid, len(res)))
            new_full_load_time = self.dbconn.force_update_full_load_time(sid)
            logger.warning('sid %d, probe %d : forced full_load_time = %d ' % (sid, self.clientid, new_full_load_time))
        session_start = str(res[0][0]) # convert datetime to string for being json-serializable
        rel_starts = [r[5] for r in res]
        rel_ends = [r[6] for r in res]
        
        idle_time = 0.0
        end = rel_ends[0]
        for i in range(1, len(rel_starts)):
            if rel_starts[i] > end:
                idle_time += rel_starts[i] - end
            end = rel_ends[i]
        
        return session_start, idle_time #msec
    
    def _get_http_response_time(self, sid):
        q = 'select app_rtt from %s where sid = %d and full_load_time > -1' % (self.dbconn.get_table_names()['raw'], sid)
        res = self.dbconn.execute_query(q)
        app_rtts = [r[0] for r in res]
        if len(app_rtts) == 0:
            return -1
        else:
            #print Utils.computeQuantile(app_rtts, 0.5)
            return sum(app_rtts)/float(len(app_rtts))

    def _get_page_downloading_time(self, sid):
        q = 'select distinct full_load_time from %s where sid = %d and full_load_time > -1 group by full_load_time' % (self.dbconn.get_table_names()['raw'], sid)
        res = self.dbconn.execute_query(q)
        if len(res) == 0:
            return -1
        else:
            return float(res[0][0]) #msec

    def _get_dns_response_time(self, sid):
        q = 'select remoteaddress, dns_time from %s where sid = %d and dns_time > 0 and full_load_time > -1' % (self.dbconn.get_table_names()['raw'], sid)
        res = self.dbconn.execute_query(q)
        #resolved_ips = [r[0] for r in res]
        dns_times = [float(r[1]) for r in sorted(res, key=lambda time: time[1])]
        return sum(dns_times) #msec

    def _get_tcp_response_time(self, sid):
        q = 'select tcp_cnxting from %s where sid = %d and full_load_time > -1' % (self.dbconn.get_table_names()['raw'], sid)
        res = self.dbconn.execute_query(q)
        tcp_times = [r[0] for r in res]
        if len(tcp_times) == 0:
            return -1
        else:
            return sum(tcp_times) / float(len(tcp_times)) #msec


    def _get_page_dimension(self, sid):
        q =  'SELECT sum(http_header_bytes+http_body_bytes) as netw_bytes, count(*) as nr_netw_obj from %s where sid = %d and full_load_time > -1' % (self.dbconn.get_table_names()['raw'], sid)
        res = self.dbconn.execute_query(q)
        assert len(res) == 1
        if res[0][0] != None:
            tot_bytes = int(res[0][0])
            nr_obj = int(res[0][1])
        else:
            tot_bytes = 0
        return tot_bytes

    def _get_os_stats(self,sid):
        q = "select distinct on(cpu_percent_ffx, mem_percent_ffx) cpu_percent_ffx, mem_percent_ffx from %s where sid = %d" % (self.dbconn.get_table_names()['raw'], sid)
        res = self.dbconn.execute_query(q)
        if len(res) != 1:
            logger.error('multiple sessions with sid = %d' % sid)
            return (-1,-1)
        else:
            if res[0] != (None,):
                return (float(res[0][0]), float(res[0][1]))
            else:
                return (-1,-1)
