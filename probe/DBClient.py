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
import fpformat
import random
import datetime
import time

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

    def create_idtable(self):
	cursor = self.conn.cursor()	
	cursor.execute('''CREATE TABLE IF NOT EXISTS client_id (probe_id INT4, first_start TEXT)''')	
	self.conn.commit()

    def get_clientID(self):
	client_id = 0	
	query = "SELECT probe_id FROM client_id"
        res = self.execute_query(query)
	if res != []:
            client_id = int(res[0][0])
	else:
	    client_id = self.create_clientID()
        return client_id

    def create_clientID(self):
	cursor = self.conn.cursor()        
	client_id = fpformat.fix(random.random()*2147483647,0)		# int4 range in PgSQL: -2147483648 to +2147483647
	ts = time.time()
	st = datetime.datetime.fromtimestamp(ts).strftime('%Y-%m-%d %H:%M:%S')
	state = '''INSERT INTO client_id VALUES ('%s', '%s')'''% (client_id, st)
	cursor.execute(state)
        self.conn.commit()
	return client_id

    def create_plugin_table(self):
        #create a Table for the Firefox plugin
        cursor = self.conn.cursor()
        cursor.execute('''CREATE TABLE IF NOT EXISTS %s (host TEXT, uri TEXT, 
        request_ts TIMESTAMP, content_type TEXT, content_len INT4,  
        httpid INT8, session_start TIMESTAMP, session_url TEXT, cache INT4, 
        local_ip INET, local_port INT4, remote_ip INET, remote_port INT4, response_code INT4, get_bytes INT4, 
        header_bytes INT4, body_bytes INT4, cache_bytes INT4, dns_start TIMESTAMP, dns_time INT4, syn_start TIMESTAMP, 
        syn_time INT4, is_sent INT4, get_sent_ts TIMESTAMP, first_bytes_rcv TIMESTAMP, app_rtt INT4, end_time TIMESTAMP, 
        rcv_time INT4, full_load_time INT4, tab_id INT8,  
        cpu_percent TEXT, mem_percent TEXT, ping_gateway TEXT, ping_google TEXT, 
        annoy INT4, probe_id INT8, sid INT8)''' % self.dbconfig['rawtable']) 
        self.conn.commit()

    def create_activemeasurement_table(self):
        cursor = self.conn.cursor()
        # PSQL > 9.2 change TEXT to JSON
        cursor.execute('''CREATE TABLE IF NOT EXISTS %s (sid INT8, session_url TEXT, remoteAddress INET, ping TEXT, trace TEXT, sent BOOLEAN)''' % self.dbconfig['activetable'])
        self.conn.commit()
        
    def write_plugin_into_db(self, datalist, stats):
        #insert a directory into the db
        cursor = self.conn.cursor()
        for obj in datalist:
	    if obj.has_key("session_url"):
	    	mem_perc = stats[str(obj["session_url"])]['mem']
                cpu_perc = stats[str(obj["session_url"])]['cpu']
             	state = '''INSERT INTO %s VALUES ('%s', '%s', '%s', '%s', %d, %d, '%s', 
            	'%s', %d, '%s', %d, '%s', %d, %d, %d, %d, %d, %d, '%s', %d, '%s', %d, %d, '%s', '%s', %d, '%s', %d,
                    %d, %d, '%s', '%s', '%s', '%s', %d, %d)
                    ''' % (self.dbconfig['rawtable'], str(obj["host"]),\
                     str(obj["uri"]), str(obj["request_ts"]), str(obj["content_type"]), int(obj["content_len"]), \
                     int(obj["httpid"]), str(obj["session_start"]), str(obj["session_url"]), int(obj["cache"]), \
                     str(obj["local_ip"]), int(obj["local_port"]), str(obj["remote_ip"]), int(obj["remote_port"]), int(obj["response_code"]), int(obj["get_bytes"]), \
                     int(obj["header_bytes"]), int(obj["body_bytes"]), int(obj["cache_bytes"]), str(obj["dns_start"]), int(obj["dns_time"]), str(obj["syn_start"]), \
                     int(obj["syn_time"]), int(obj["is_sent"]), str(obj["get_sent_ts"]), str(obj["first_bytes_rcv"]), int(obj["app_rtt"]), str(obj["end_time"]), \
                     int(obj["rcv_time"]), int(obj["full_load_time"]), int(obj["tab_id"]), \
                     str(cpu_perc), str(mem_perc), str(obj["ping_gateway"]), \
                     str(obj["ping_google"]), int(obj["annoy"]), int(obj["probe_id"]))
	    	cursor.execute(state)
            	self.conn.commit()
        sid_inserted = self._generate_sid_on_table()        

    def load_to_db(self, stats, browser):
	if browser == 'firefox':
            datalist = Utils.read_file(self.dbconfig['pluginoutfile'], "\n")
	else:
	    self.create_idtable()
	    client_id = self.get_clientID()
	    datalist = Utils.read_tstatlog(self.dbconfig['tstatfile'], self.dbconfig['harfile'], "\n", client_id)
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
        query = "select distinct on (probe_id, session_start) probe_id, session_start from %s where sid is NULL order by session_start" % self.dbconfig['rawtable']
        res = self.execute_query(query)
        logger.debug('Found %d sessions to insert', len(res))
        for i in range(len(res)):
            clientid = res[i][0]
            session_start = res[i][1]
            max_sid += 1
            query = "update %s set sid = %d where session_start = \'%s\' and probe_id = \'%s\'" % (self.dbconfig['rawtable'], max_sid, session_start, clientid)
            self.execute_update(query)
        return max_sid

    def quit_db(self):
        self.conn.close()

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
        return {'raw': self.dbconfig['rawtable'] ,'active': self.dbconfig['activetable']}

    def force_update_full_load_time(self, sid):
        import datetime
        q = '''select session_start, end_time from %s where sid = %d''' % (self.dbconfig['rawtable'], sid)
        res = self.execute_query(q)
        session_start = list(set([x[0] for x in res]))[0]
        end_time = max(list(set([x[1] for x in res])))
        forced_load_time = int((end_time - session_start).total_seconds() * 1000)
        update = '''update %s set full_load_time = %d where sid = %d''' % (self.dbconfig['rawtable'], forced_load_time, sid)
        self.execute_update( update )
        return forced_load_time
        
