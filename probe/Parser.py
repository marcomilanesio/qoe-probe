#!/usr/bin/python
#
# mPlane QoE Probe
#
# (c) 2013-2014 mPlane Consortium (http://www.ict-mplane.eu)
#               Author: Salvatore Balzano <balzano@eurecom.fr>
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
from pprint import pprint
import os
import glob
import sys
import os
import re
import datetime
import time
import re
import fpformat



def parseTstat(filename,separator, client_id):
    # Read tstat log
    log = open(filename, "r")
    lines = log.readlines()
    log.close()
    rows = []
    for line in lines:
        line = line[:-1]
        rows.append(line.split(" "))
    # Create json file from tstat metrics
    jsonmetrics = ""
    for line in rows:
        if line[59] is not "":		#avoid HTTPS sessions
	    line[59] = line[59][:-1]
	    httpids = line[59].split(",")
	    #print httpids
	    for elem in httpids:
            	metrics = {'cIP': line[0], 'cPort': line[1], 'ID': client_id, 'tcp': fpformat.fix(line[13],0), 
				'sIP': line[30], 'sPort': line [31],'httpid': elem}
	    	jsonmetrics = jsonmetrics + json.dumps(metrics) + "\n"
    return jsonmetrics.split(separator)


def parseDateTime(s):
	if s is None:
	    return None
	m = re.match(r'(.*?)(?:\.(\d+))?(([-+]\d{1,2}):(\d{2}))?$', str(s))
	datestr, fractional, tzname, tzhour, tzmin = m.groups()
	if tzname is None:
	    tz = None
	else:
	    tzhour, tzmin = int(tzhour), int(tzmin)
	    if tzhour == tzmin == 0:
		tzname = 'UTC'
	    tz = FixedOffset(timedelta(hours=tzhour, minutes=tzmin), tzname)
	# Convert the date/time field into a python datetime
	# object.
	x = datetime.datetime.strptime(datestr, "%Y-%m-%d %H:%M:%S")
	# Convert the fractional second portion into a count
	# of microseconds.
	if fractional is None:
	    fractional = '0'
	fracpower = 6 - len(fractional)
	fractional = float(fractional) * (10 ** fracpower)	
	# Return updated datetime object with microseconds and
	# timezone information.
	return x.replace(microsecond=int(fractional), tzinfo=tz)


def updatebyHar(tstatdata,filename):
    try:
        json_data=open(filename)
	data = json.load(json_data)
	
	# Global metrics of the session
	version = data["log"]["creator"]["version"]
	page_url = data["log"]["entries"][0]["request"]["url"]	# pageURL is the url of the first request
	session_start = data["log"]["pages"][0]["startedDateTime"].replace('T', ' ')[0:-1]
	onContentLoad = data["log"]["pages"][0]["pageTimings"]["onContentLoad"]
	onLoad = data["log"]["pages"][0]["pageTimings"]["onLoad"]
  	
       	# Parsing each object
        for entry in data["log"]["entries"]:            
            request_ts=entry["startedDateTime"].replace('T', ' ')[0:-1] #human readable time
	    firstByte = entry["TimeToFirstByte"].replace('T', ' ')[0:-1]
            endTS = entry["endtimeTS"].replace('T', ' ')[0:-1]
	    # Finding httpid of the object
	    for field in entry["request"]["headers"]: 
		if field["name"] == "httpid":
		    http_id = field["value"]
		else: 
		    http_id = "null"            
            request_host = entry["request"]["url"].split('/')[2]
	    request_host=request_host.split(':')[0] # e.g. 'gzip.static.woot.com:9090'
	    method = entry["request"]["method"]
	    httpVersion = entry["request"]["httpVersion"]
	    status = entry["response"]["status"]
	    request_url = entry["request"]["url"]
            response_header_size = entry["response"]["headersSize"]	  
	    responde_body_size = entry["response"]["bodySize"]     
            cnt_type = entry["response"]["content"]["mimeType"].split(';')[0]  # e.g. 'text/javascript; charset=UTF-8'
	    # Timing
	    blocked = entry["timings"]["blocked"]
            dns = entry["timings"]["dns"]
            connect = entry["timings"]["connect"]
            send = entry["timings"]["send"]
            wait = entry["timings"]["wait"]
            receive = entry["timings"]["receive"]

            # Matching tstatdata
	    for line in tstatdata:			
		if line["httpid"] == http_id:
			#fields_to_add = {'log'.decode('utf-8'): "null".decode('utf-8')}
			fields_to_add = {'log': "null", 'pageURL': page_url,'onLoad': str(onLoad), 'onContent': str(onContentLoad), 
					'ff_v': str(version), 'method': str(method), 'host': str(request_host), 'uri': str(request_url),
					'ts': "1970-01-01 12:00:00", 'type': str(cnt_type), 'len': "0", 'C_Encode': "null", 
					'Encode': "null", 's_cnxs': "null", 's_http': str(httpVersion), 'pageStart': str(session_start),
					'cache': "0", 'status': str(status), 'GET_Byte': "-1", 'HeaderByte': "-1", 
					'BodyByte': str(responde_body_size), 'CacheByte': "0", 'dns1': "1970-01-01 12:00:00", 
					'dns': str(dns), 'tcp1': "1970-01-01 12:00:00", 'sendTS': "1970-01-01 12:00:00", 
					'send': str(send), 'http1': str(request_ts), 'http2': str(firstByte), 'http': str(wait), 
					'EndTS': str(endTS),'rcv': str(receive), 'tabId': "0", 'wifi': "0;0", 'CPUidle': "-1;-1", 
					'MEMfree': "-1;-1", 'MEMused': "-1;-1", 'pingGW': "null", 'pingDNS': "null", 
					'pingG': "null", 'AnnoyNr': "0", 'location': "null", 'IfAborted': "0", 'cmt': "null"}
						
			line.update(fields_to_add)
			#print line
	    # End for cicle (matching tstatdata)

	# End for clicle (each object)
	json_data.close()	
	
    except:
	#print tstatdata
	pass
    return tstatdata


