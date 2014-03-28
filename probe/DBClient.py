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
        cursor.execute('''CREATE TABLE IF NOT EXISTS %s (log_reason TEXT, ff_version TEXT, method TEXT, host TEXT, uri TEXT, 
        request_event_ts TIMESTAMP, content_type TEXT, content_length INT4, AcceptEncoding TEXT, ContentEncoding TEXT, 
        server_cnxs TEXT, server_http TEXT, http_id INT8, session_start TIMESTAMP, session_url TEXT, if_complete_cache INT4, 
        localAddress INET, localPort INT4, remoteAddress INET, remotePort INT4, response_code INT4, http_request_bytes INT4, 
        http_header_bytes INT4, http_body_bytes INT4, http_cache_bytes INT4, dns_start TIMESTAMP, dns_time INT4, syn_start TIMESTAMP, 
        tcp_cnxting INT4, send_ts TIMESTAMP, send INT4, GET_sent TIMESTAMP, First_Bytes TIMESTAMP, app_rtt INT4, EndTime TIMESTAMP, 
        data_trans INT4, full_load_time INT4, content_load_time INT4, tabId INT8, current_wifi_quality TEXT, cpu_idle TEXT, 
        cpu_percent_ffx TEXT, mem_free TEXT, mem_used TEXT, mem_percent_ffx TEXT, ping_gw TEXT, ping_dns TEXT, ping_google TEXT, 
        nr_annoying INT4, location TEXT, obj_aborted INT4, clientID INT8, cmt TEXT, sid INT8)''' % self.dbconfig['rawtable']) 
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
            mem_perc = stats[str(obj["pageURL"])]['mem']
            cpu_perc = stats[str(obj["pageURL"])]['cpu']
            state = '''INSERT INTO %s VALUES ('%s', '%s', '%s', '%s', '%s', '%s', '%s', %d, '%s', '%s', '%s', '%s', %d, '%s', 
            '%s', %d, '%s', %d, '%s', %d, %d, %d, %d, %d, %d, '%s', %d, '%s', %d, '%s', %d, '%s', '%s', %d, '%s', %d,
                    %d, %d, %d, '%s', '%s', '%s', '%s', '%s', '%s', '%s', '%s', '%s', %d, '%s', %d, %d, '%s')
                    ''' % (self.dbconfig['rawtable'], str(obj["log"]), str(obj["ff_v"]), str(obj["method"]), str(obj["host"]),\
                     str(obj["uri"]), str(obj["ts"]), str(obj["type"]), int(obj["len"]), str(obj["C_Encode"]), str(obj["Encode"]), \
                     str(obj["s_cnxs"]), str(obj["s_http"]), int(obj["httpid"]), str(obj["pageStart"]), str(obj["pageURL"]), int(obj["cache"]), \
                     str(obj["cIP"]), int(obj["cPort"]), str(obj["sIP"]), int(obj["sPort"]), int(obj["status"]), int(obj["GET_Byte"]), \
                     int(obj["HeaderByte"]), int(obj["BodyByte"]), int(obj["CacheByte"]), str(obj["dns1"]), int(obj["dns"]), str(obj["tcp1"]), \
                     int(obj["tcp"]), str(obj["sendTS"]), int(obj["send"]), str(obj["http1"]), str(obj["http2"]), int(obj["http"]), str(obj["EndTS"]), \
                     int(obj["rcv"]), int(obj["onLoad"]), int(obj["onContent"]), int(obj["tabId"]), str(obj["wifi"]), str(obj["CPUidle"]), \
                     str(cpu_perc), str(obj["MEMfree"]), str(obj["MEMused"]), str(mem_perc), str(obj["pingGW"]), str(obj["pingDNS"]), \
                     str(obj["pingG"]), int(obj["AnnoyNr"]), str(obj["location"]), int(obj["IfAborted"]), int(obj["ID"]), str(obj["cmt"]))
	    print state
            cursor.execute(state)
            self.conn.commit()
        sid_inserted = self._generate_sid_on_table()
        

    def load_to_db(self, stats):
        #datalist = Utils.read_file(self.dbconfig['pluginoutfile'], "\n")
	datalist = Utils.read_tstatlog(self.dbconfig['tstatfile'], self.dbconfig['harfile'], "\n")
	#print datalist        	
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
        query = "select distinct on (clientID, session_start) clientID, session_start from %s where sid is NULL order by session_start" % self.dbconfig['rawtable']
        res = self.execute_query(query)
        logger.debug('Found %d sessions to insert', len(res))
        for i in range(len(res)):
            clientid = res[i][0]
            session_start = res[i][1]
            max_sid += 1
            query = "update %s set sid = %d where session_start = \'%s\' and clientID = \'%s\'" % (self.dbconfig['rawtable'], max_sid, session_start, clientid)
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
        q = '''select session_start, endtime from %s where sid = %d''' % (self.dbconfig['rawtable'], sid)
        res = self.execute_query(q)
        session_start = list(set([x[0] for x in res]))[0]
        end_time = max(list(set([x[1] for x in res])))
        forced_load_time = int((end_time - session_start).total_seconds() * 1000)
        update = '''update %s set full_load_time = %d where sid = %d''' % (self.dbconfig['rawtable'], forced_load_time, sid)
        self.execute_update( update )
        return forced_load_time
        
