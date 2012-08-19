#!/usr/bin/env python
import random 
import sys 
import logging 
import re 
from socket import gaierror, error  
import threading 
from os import getcwd, mkdir
from os.path import isdir 
from time import time, ctime 
from ConfigParser import SafeConfigParser
from httplib import HTTPConnection 

initTime = ctime() 
config_file = getcwd() + '/conf/production.ini' 
counts = {}
start_time = last_check = time() 
 

LOG_DIR = getcwd() +  '/logs'
LOG_FILENAME = LOG_DIR + '/httpserver.log'
if not isdir(LOG_DIR): mkdir(LOG_DIR)
logger = logging.getLogger('httpserver')
logger.setLevel(logging.INFO)
dead_servers = []


def parseConfig(f):
	"""Use configparser module to parse configuration file
	   config file must be in right format, otherwise, server cannot start
	   This function returns 2 dictionaries:
			- handle_servers stores requested server, handles server and weight
			- constructed_cluster store requested server and handle server 
	   This thing is ugly but it works :-)
	"""
	print 'Reading configuration file....'
	cluster = {} 
	group = {}
	constructed_cluster = {} 
	parser = SafeConfigParser()
	parser.read(f)
	if parser.has_section('farms'):
		farm_list = [value for name, value in parser.items('farms')] 
		for item in farm_list[0].split(','):
			if parser.has_section(item):
				cluster[item] = {name:value for name, value in parser.items(item)}  
	else:
		sys.stderr.write("Configuration file error, no item 'farms' defined\n") 
		sys.stderr.write("Exit!\n") 
		sys.exit(2) 
	
	for i in parser.get('farms','list').split(','):
		list_redirect_domain = [parser.get(parser.get(i, 'list').split(',')[j], 'domain') for j in range(len(parser.get(i, 'list').split(','))) ]
		constructed_cluster[parser.get(i, 'domain')]  = list_redirect_domain 
	for server_group, server_list in cluster.iteritems():
		temporary_list = [] 
		origin_domain_name = server_list['domain']
		servers = [server for server in server_list['list'].split(',')]
		for s in servers: 
			temporary_list.append([v for k, v in parser.items(s) if v != 'on']) 
		group[origin_domain_name] = temporary_list 
	return (group, constructed_cluster) 


handle_servers, constructed_cluster = parseConfig(config_file) 


class httpCompute(object):
	"""
	- Based on global variable last_check, computeServer function will
	perform health check on servers list using health_check() function 
	- computeServer() function constructer dead_server list and return 
	which server will serve http request from client using random_weighted 
	function.
	- random_weighted function using random algo to return server based on
	weight number defined in configuration file.
	"""
	 
	def health_check(self, target):  
		global dead_servers 
		is_alive = 0
		beaten = 0
		p    = re.compile("[a-z0-9-.]*?\.[a-z]+$")
		domain_tld = p.findall(target)[0]   
		accepted_responses = (404, 302, 304, 301, 200) 
		#logger.error('perform health check on ' + domain_tld) 
		try:
			conn = HTTPConnection(domain_tld) 
			conn.request('HEAD', '/') 
			response = conn.getresponse() 
			if response.status in accepted_responses:
				is_alive = 1 
			else:
				logger.error(ctime() + ': ' + target + ' is down, HTTP error code is: ' + response.status )
		# FIXME
		# Bypass dns resolving errors exception, don't know why it always fail after running for about 1 hours. 
		except gaierror:
			#logger.error(ctime() + ' ' + target + ' : Error: Name or service does not known' ) 
			is_alive = 1 
		except error:
			logger.error(ctime() + ' ' + target + ' : Connection refused' )  
		finally:
			conn.close() 
		if is_alive == 0 and target not in dead_servers: 
			dead_servers.append(target)
		if is_alive == 1 and target in dead_servers: 
			dead_servers.pop(dead_servers.index(target)) 
		
	
	def random_weighted(self, d):
		"""Random based on weight defined"""
		offset = random.randint(0, sum(d.itervalues())-1)
		for k, v in d.iteritems():
			if offset < v:
				#print "%s < %s: return %s" %(offset, v, v)
				return k
			offset -= v
			
	def computeServer(self, request_server): 
		"""
		   Main function: get values from configuration
		   redirect request to right servers
		"""
		servers = {}
		global last_check  
		global dead_servers 
		if handle_servers.has_key(request_server):
			balance_list = handle_servers[request_server]
			for i in range(0, len(balance_list)):
				# Remove server marked as 'off' in config file 
				if len(balance_list[i]) > 2 :
					continue 
				servers[balance_list[i][0]] = int(balance_list[i][1])
			check_list = servers.copy() 
			if (time() - last_check) > 30:
				for k, v in check_list.iteritems():
					t = threading.Thread(target=self.health_check, args=(k,)) 
					t.start() 
				last_check += 30
			for k in range(len(dead_servers)):
				if servers.has_key(dead_servers[k]): servers.pop(dead_servers[k]) 
			if len(servers.values()) < 1:
				# When all servers on cluster went down, decrease last_check time to check more frequent.
				# Disable logging to prevent CPU mad usage.
				# logger.error('No server available to serve request for ' + self.request.host) 
				last_check = last_check - 30 
				raise tornado.web.HTTPError(502, 'No available server') 
			server = self.random_weighted(servers) 
			try:
				counts[server] = counts[server] + 1
			except KeyError:
				counts[server] = 1 
		else:
			server = None
		return server 
