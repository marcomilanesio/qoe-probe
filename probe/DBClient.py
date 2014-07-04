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
import psycopg2
import Utils
import sys
from Configuration import Configuration
import logging
import json

logger = logging.getLogger('DBClient')


class DBClient:
    def __init__(self, config):
        #connect to the database
        self.dbconfig = config.get_database_configuration()
        try:
            self.conn = psycopg2.connect(database=self.dbconfig['dbname'], user=self.dbconfig['dbuser'])
            logger.debug('DB connection established')
        except psycopg2.DatabaseError, e:
            print 'Unable to connect to DB. Error %s' % e
            logger.error('Unable to connect to DB. Error %s' % e)
            sys.exit(1)

    def create_tables(self):
        self.create_plugin_table()
        self.create_activemeasurement_table()

    def create_plugin_table(self):
        #create a Table for the Firefox plugin
        cursor = self.conn.cursor()

        cursor.execute('''CREATE TABLE IF NOT EXISTS %s (
        row_id SERIAL,
        uri TEXT,
        host TEXT,
        request_ts TIMESTAMP,
        content_type TEXT,
        content_len INT,
        keep_alive BOOLEAN,
        httpid INT,
        session_start TIMESTAMP,
        session_url TEXT,
        cache INT,
        local_ip TEXT,
        local_port INT,
        remote_ip TEXT,
        remote_port INT,
        response_code INT,
        get_bytes INT,
        header_bytes INT,
        body_bytes INT,
        cache_bytes INT,
        dns_start TIMESTAMP,
        dns_time INT,
        syn_start TIMESTAMP,
        syn_time INT,
        get_sent_ts TIMESTAMP,
        first_bytes_rcv TIMESTAMP,
        app_rtt INT,
        end_time TIMESTAMP,
        rcv_time INT,
        full_load_time INT,
        annoy INT,
        tab_id TEXT,
        cpu_percent INT,
        mem_percent INT,
        ping_gateway TEXT,
        ping_google TEXT,
        probe_id INT,
        sid INT,
        is_sent BOOLEAN
        )
        ''' % self.dbconfig['rawtable'])
        self.conn.commit()

    def create_activemeasurement_table(self):
        cursor = self.conn.cursor()
        # PSQL > 9.2 change TEXT to JSON
        cursor.execute('''CREATE TABLE IF NOT EXISTS %s (sid INT8, session_url TEXT,
        remote_ip INET, ping TEXT, trace TEXT, sent BOOLEAN)''' % self.dbconfig['activetable'])
        self.conn.commit()

    @staticmethod
    def _unicode_to_ascii(item):
        return item.encode('ascii', 'ignore')

    @staticmethod
    def _convert_to_ascii(arr):
        res = []
        for i in arr:
            res.append(DBClient._unicode_to_ascii(i))
        return res

    def write_plugin_into_db(self, datalist, stats):
        #read json objects from each line of the plugin file
        cursor = self.conn.cursor()
        table_name = self.dbconfig['rawtable']
        insert_query = 'INSERT INTO ' + table_name + ' (%s) values %r RETURNING row_id'
        update_query = 'UPDATE ' + table_name + ' SET mem_percent = %s, cpu_percent = %s where row_id = %d'
        for obj in datalist:
            url = DBClient._unicode_to_ascii(obj['session_url'])
            cols = ', '.join(obj)
            to_execute = insert_query % (cols, tuple(DBClient._convert_to_ascii(obj.values())))
            #print to_execute
            cursor.execute(to_execute)
            self.conn.commit()
            row_id = cursor.fetchone()[0]
            to_update = update_query % (stats[url]['mem'], stats[url]['cpu'], row_id)
            cursor.execute(to_update)
            self.conn.commit()

        self._generate_sid_on_table()
        
    def load_to_db(self, stats):
        datalist = Utils.read_file(self.dbconfig['pluginoutfile'], "\n")
        if len(datalist) > 0:
            self.write_plugin_into_db(datalist, stats)

    def execute_query(self, query):
        cur = self.conn.cursor()
        cur.execute(query)
        res = cur.fetchall()
        return res

    def execute_update(self, query):
        cur = self.conn.cursor()
        cur.execute(query)
        self.conn.commit()
        
    def _select_max_sid(self):
        query = "select max(sid) from %s" % self.dbconfig['rawtable']
        res = self.execute_query(query)
        max_sid = 0
        if res[0] != (None,):
            max_sid = int(res[0][0])
        return max_sid

    def _generate_sid_on_table(self):
        max_sid = self._select_max_sid()
        query = '''select distinct on (probe_id, session_start) probe_id, session_start from %s where sid is NULL
        order by session_start''' % self.dbconfig['rawtable']
        res = self.execute_query(query)
        logger.debug('Found %d sessions to insert', len(res))
        for i in range(len(res)):
            clientid = res[i][0]
            session_start = res[i][1]
            max_sid += 1
            query = '''update %s set sid = %d where session_start = \'%s\' and probe_id = \'%s\'''' \
                    % (self.dbconfig['rawtable'], max_sid, session_start, clientid)
            self.execute_update(query)
        return max_sid

    def quit_db(self):
        self.conn.close()

    def get_inserted_sid_addresses(self):
        result = {}
        q = '''select distinct on (sid, session_url, remote_ip) sid, session_url, remote_ip
        FROM %s where sid not in (select distinct sid from active)''' % self.dbconfig['rawtable']
        res = self.execute_query(q)
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
                result[cur_sid] = {'url': cur_url, 'address': [cur_addr]}
        #print 'result _get_inserted_sid_addresses', result
        return result


    def insert_active_measurement(self, tot_active_measurement):
        #data['ping'] = json obj
        #data['trace'] = json obj
        cur = self.conn.cursor()
        for sid, data in tot_active_measurement.iteritems():
            for dic in data:
                url = dic['url']
                ip = dic['ip']
                ping = dic['ping']
                trace = dic['trace']
                query = '''INSERT into %s values ('%d','%s','%s','%s','%s','%s')
                ''' % (self.dbconfig['activetable'], sid, url, ip, ping, trace, 'f') #false as not sent yet
                cur.execute(query)
            logger.info('inserted active measurements for sid %s: ' % sid)
        self.conn.commit()
    
    def get_table_names(self):
        return {'raw': self.dbconfig['rawtable'],'active': self.dbconfig['activetable']}

    def force_update_full_load_time(self, sid):
        import datetime
        q = '''select session_start, end_time from %s where sid = %d''' % (self.dbconfig['rawtable'], sid)
        res = self.execute_query(q)
        session_start = list(set([x[0] for x in res]))[0]
        end_time = max(list(set([x[1] for x in res])))
        forced_load_time = int((end_time - session_start).total_seconds() * 1000)
        update = '''update %s set full_load_time = %d where sid = %d''' \
                 % (self.dbconfig['rawtable'], forced_load_time, sid)
        self.execute_update(update)
        return forced_load_time
        
    def check_for_zero_full_load_time(self):
        res = []
        q = '''select sid from %s where full_load_time = 0''' % self.dbconfig['rawtable']
        res = self.execute_query(q)
        sids = [int(x[0]) for x in res]
        if len(sids) > 0:
            for s in sids:
                self.force_update_full_load_time(s)
                res.append(s)
        return res
