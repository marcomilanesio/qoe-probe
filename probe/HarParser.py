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


# usage: 
#   ./python har_print.py '/harfolder/'


path = sys.argv[1]


global threshold_dns_bug
threshold_dns_bug=10 # 10ms



global cdn_list
cdn_list = [ ".akamai.net" , ".akamaiedge.net", ".llnwd.net", "edgecastcdn.net", 
	      "hwcdn.net", ".panthercdn.com", ".simplecdn.net", ".instacontent.net", 
	      ".footprint.net", ".ay1.b.yahoo.com", ".yimg.", ".google.", "googlesyndication.", 
	      "youtube.", ".googleusercontent.com", ".internapcdn.net", ".cloudfront.net", ".netdna-cdn.com", 
	      ".netdna-ssl.com", ".netdna.com", ".cotcdn.net", ".cachefly.net", "bo.lt", ".cloudflare.com", 
	      ".afxcdn.net", ".lxdns.com", ".att-dsa.net", ".vo.msecnd.net", ".voxcdn.net", 
	      ".bluehatnetwork.com", ".swiftcdn1.com", ".cdngc.net", ".fastly.net", ".gslb.taobao.com", 
	      ".gslb.tbcache.com", ".mirror-image.net", ".yottaa.net", ".cubecdn.net", "END_MARKER"]


global cdn_company_list
cdn_company_list = [ "Akamai", "Akamai", "Limelight", "Edgecast", "Highwinds", "Panther", "Simple CDN", 
		      "Mirror Image", "Level 3", "Yahoo", "Yahoo", "Google", "Google", "Google", "Google", 
		      "Internap", "Amazon CloudFront", "MaxCDN", "MaxCDN", "MaxCDN", "Cotendo CDN", 
		      "Cachefly", "BO.LT", "Cloudflare", "afxcdn.net", "lxdns.com", "AT&T", "Windows Azure", 
		      "VoxCDN", "Blue Hat Network", "SwiftCDN", "CDNetworks", "Fastly", "Taobao", "Alimama", 
		      "Mirror Image", "Yottaa", "cubeCDN", "END_MARKER" ]




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



listing = os.listdir(path)

for jsonfile in listing:
    
    try:
	x=os.path.splitext( jsonfile )
	if not x[1]==".har": continue #  jsonfile is the HAR filename

	file = str(path) + str(jsonfile)

        json_data=open(file)
	data = json.load(json_data)

        page_url = jsonfile.split('+')[0] 
	
	# filename contains the Page_URL
        session_start = data["log"]["pages"][0]["startedDateTime"].replace('T', ' ')[0:-1]
	session_id = data["log"]["pages"][0]["id"]
        onContentLoad = data["log"]["pages"][0]["pageTimings"]["onContentLoad"]
	onLoad = data["log"]["pages"][0]["pageTimings"]["onLoad"]


        #obj_start_time_list=[]
        #obj_end_time_list=[]
        dns_resolved_time_list={}
        
        
        num_obj = 0
        
        
        for entry in data["log"]["entries"]:
            
            cdn_host_alias = 'null'
            cdn_company = 'null'


            start_ts=entry["startedDateTime"].replace('T', ' ')[0:-1] #human readable time
            relative_start_ts=(parseDateTime(start_ts)-parseDateTime(session_start)).microseconds/1000+(parseDateTime(start_ts)-parseDateTime(session_start)).seconds*1000
            for field in entry["request"]["headers"]: 
		if field["name"] == "httpid":
		    http_id = field["value"]
		else: 
		    http_id = 'null'
            #http_id = [field["value"] for field in entry["request"]["headers"] if field["name"] == "httpid"][0]
            #print http_id
            relative_end_ts=relative_start_ts+entry["timings"]["blocked"]+entry["timings"]["dns"]+entry["timings"]["connect"]+entry["timings"]["send"]+entry["timings"]["wait"]+entry["timings"]["receive"]
            #obj_start_time_list.append(relative_start_ts)
            #obj_end_time_list.append(relative_end_ts)

            request_host = entry["request"]["url"].split('/')[2]

	  


##########################################################
# The followings are used to revise DNS problem of firebug 1.6.x, as bug reported in:
#   http://groups.google.com/group/firebug/browse_thread/thread/33d1739064de61d5?tvc=2&pli=1
#   http://code.google.com/p/fbug/issues/detail?id=3809
#   http://fbug.googlecode.com/issues/attachment?aid=38090005000&name=blocked-as-dns.jpg&token=v7DAetR1LyqifeHzK1-hnyDQz9U%3A1333023639111&inline=1
#   http://www.1stwave.com/firebug_dns_ve

            if entry["timings"]["dns"] > 0 :
                if dns_resolved_time_list.has_key(request_host):
                    if relative_start_ts+entry["timings"]["blocked"]+entry["timings"]["dns"]> dns_resolved_time_list.get(request_host)+threshold_dns_bug:
                    ## current DNS resolve finish.time is larger than 10ms of the 1st DNS query for current host
                        entry["timings"]["blocked"]+=entry["timings"]["dns"]
                        entry["timings"]["dns"]=0
                else:
                    dns_resolved_time_list.update({request_host:relative_start_ts+entry["timings"]["blocked"]+entry["timings"]["dns"]})

##########################################################

	    request_url = entry["request"]["url"]
            request_ts = entry["startedDateTime"].replace('T', ' ')[0:-1]


            response_size = entry["response"]["headersSize"] + entry["response"]["bodySize"]            # including response header
            cnt_type = entry["response"]["content"]["mimeType"]
            dns = entry["timings"]["dns"]
            connect = entry["timings"]["connect"]
            blocked = entry["timings"]["blocked"]
            send = entry["timings"]["send"]
            wait = entry["timings"]["wait"]
            receive = entry["timings"]["receive"]


            #request_host='www.google-analytics.com'
	    #request_host='gzip.static.woot.com:9090'
	    #request_host='hs-ac.tynt.com.'
            request_host=request_host.split(':')[0] # e.g. 'gzip.static.woot.com:9090'

            cdn_index=-1
            try:
                cdn_index = cdn_list.index([x for x in cdn_list if x in request_host][0])
		#print [x for x in cdn_list]
                cdn_host_alias = cdn_list[cdn_index]
                cdn_company = cdn_company_list[cdn_index]
            except:
                cdn_index=-1

            if cdn_index==-1:
            # if the obj-URL does NOT contain the key-words in the alias-list. DNS query to get alias.
                cmd_host_query = 'host -t ns ' + request_host

                dns_query_results = os.popen(cmd_host_query)
                #print dns_query_results
		
                for line in dns_query_results.readlines():
                    
                    try:
                        alias = line.rstrip('\n').split(' is an alias for ')[1]

			cdn_index = cdn_list.index([x for x in cdn_list if x in alias][0])
                        #if alias in cdn_list:
			#print [x for x in cdn_list if x in alias][0], cdn_index
			
                        #cdn_index = cdn_list.index(alias)
                        cdn_host_alias = cdn_list[cdn_index]
                        cdn_company = cdn_company_list[cdn_index]
                        break
                    except: # e.g. in the case of NXDOMAIN...or only provide IP addresses
                        pass


            
            num_obj = num_obj +1
            
            #output_str = str(page_url) + '^' + str(session_start) + '^' + str(session_id) + '^' + str(onContentLoad) + '^' + str(onLoad) + '^' + str(http_id) + '^' +  str(request_url) + '^' + str(request_ts) + '^' + str(request_host) + '^' + str(cnt_type) + '^' + str(cdn_host_alias) + '^' + str(cdn_company) + '^' + str(response_size) + '^' + str(blocked) + '^' + str(dns) + '^' + str(connect) + '^' + str(send) + '^' + str(wait) + '^' + str(receive)
	    
	    #output_str = str(page_url) + '^' + str(onLoad) + '^' + str(request_host) 
            output_str = str(http_id)
            print output_str
	    out_file = open("taobao.host","a")
	    out_file.write(str(request_host) + "\n")
	    out_file.close()
	    #out_file2 = open("ebay.loadtime","w")
	    #out_file2.write(str(onLoad) + ',' + str(num_obj) + "\n")
	    #out_file2.close()

	    

	    
	    
            #print request_host, cdn_host_alias, cdn_company


	
	json_data.close()
	out_file2 = open("taobao.loadtime","a")
	out_file2.write(str(onLoad) + ',' + str(num_obj) + "\n")
	out_file2.close()
	
	
    except:
	##print '??'
	pass




