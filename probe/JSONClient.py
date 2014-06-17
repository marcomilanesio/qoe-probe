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
import socket
import json
import numpy
from DBClient import DBClient
from Configuration import Configuration 
from LocalDiagnosisManager import LocalDiagnosisManager
import logging

logger = logging.getLogger('JSONClient')


class JSONClient():
    def __init__(self, config):
        self.activetable = config.get_database_configuration()['activetable']
        self.rawtable = config.get_database_configuration()['rawtable']
        self.srv_ip = config.get_jsonserver_configuration()['ip']
        self.srv_port = int(config.get_jsonserver_configuration()['port'])
        self.db = DBClient(config)
        self.probeid = self._get_client_id_from_db()
    
    def _get_client_id_from_db(self):
        q = 'select distinct on (probe_id) probe_id from %s ' % self.rawtable
        r = self.db.execute_query(q)
        assert len(r) == 1
        return int(r[0][0])
        
    def prepare_and_send(self):
        query = 'select * from %s where not sent' % self.activetable
        res = self.db.execute_query(query)
        sids = list(set([r[0] for r in res]))
        local_data = {'clientid': self.probeid, 'local': self._prepare_local_data(sids)}
        str_to_send = "local: " + json.dumps(local_data)
        logger.info('sending local data... %s' % self.send_to_srv(str_to_send, is_json=True))
        for row in res:
            active_data = {'clientid': self.probeid, 'ping': None, 'trace': []}
            count = 0
            sid = int(row[0])
            session_url = row[1]
            remoteaddress = row[2]
            ping = json.loads(row[3])
            trace = json.loads(row[4])
            for steps in trace:
                if len(steps) > 1:
                    empty_targets = [t for t in steps if t[0] == '???' or t[1] == []]
                    for empty in empty_targets:
                        steps.remove(empty)
                        count += 1
            active_data['ping'] = {'sid': sid, 'session_url': session_url, 'remoteaddress': remoteaddress, 'min': ping['min'], 'max': ping['max'], 'avg': ping['avg'], 'std': ping['std']}

            for step in trace:
                step_nr = step['hop_nr']
                step_addr = step['ip_addr']
                step_rtt = step['rtt']
                step_alias = step['endpoints']
                '''
                @TODO
                Consider different endpoints
                '''
                active_data['trace'].append({'sid': sid, 'remoteaddress': remoteaddress, 'step': step_nr,
                                             'step_address': step_addr, 'rtt': step_rtt})

            #logger.debug('Removed %d empty step(s) from secondary path to %s.' % (count, remoteaddress))
            logger.info('sending ping/trace data about [%s]: %s ' % (remoteaddress,  self.send_to_srv(active_data)))


        for sent_sid in sids:
            update_query = '''update %s set sent = 't' where sid = %d''' % ( self.activetable, int(sent_sid) )
            self.db.execute_update(update_query)
            logger.info('updated sent sid on %s' % self.activetable)

    def _prepare_local_data(self, sids):
        l = LocalDiagnosisManager(self.db, self.probeid, sids)
        return l.do_local_diagnosis()
        
    def send_to_srv(self, data, is_json=False):
        print data
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.connect((self.srv_ip, self.srv_port))
        if not is_json:
            s.sendall(json.dumps(data) + "\n")
        else:
            s.sendall(data + "\n")
        result = json.loads(s.recv(1024))
        s.close()
        return result

    def send_request_for_diagnosis(self, url, time_range=6):
        data = {'clientid': self.probeid, 'url': url, 'time_range': time_range}
        str_to_send = 'check: ' + json.dumps(data)
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.connect((self.srv_ip, self.srv_port))
        s.send(str_to_send + "\n")
        result = json.loads(s.recv(1024))
        s.close()
        return result

        
if __name__ == '__main__':
    import sys
    conf_file = sys.argv[1]
    url = sys.argv[2]
    #conf_file='../probe.conf'
    #url = 'www.google.com'
    c = Configuration(conf_file)
    j = JSONClient(c)
    print j.send_request_for_diagnosis(url, 6)

