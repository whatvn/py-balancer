import os
import errno
import signal
import re
import time 
from httpcompute import httpCompute, counts, constructed_cluster, dead_servers
from gevent.pool import Pool 
from gevent import socket, sleep 

"""
httputil.py
@author: hungnv 
@version: 1.0.0 
core module, fork tcp server socket
handle http request
"""

ITIME = time.time() 
__version__ = 'py-balancer/1.0.0'
stats = 0 
computor = httpCompute()
startTime = time.ctime()

	
class HTTPServer(object):
	"""py-balancer is just a balancer node, it should not do
	anything complicated, so all of its function is show statistic,
	redirect to destination server, so we're trying to make it as simple
	as possible"""
	
	def send_header(self, sock, name, value = None):
		"""Send headers as {key:value}"""
		if value is not None:
			value = value.strip() + '\r\n'
			sock.send(name + ': ' + value)
			
	def _handle(self, sock):
		"""Main handler for HTTP request"""
		request_headers = {}
		bytes = sock.recv(1024)
		bytes = bytes.split('\r\n')
		if len(bytes) >= 2:
			path = bytes[0].split(' ')[1] 
			for element in bytes[1:-2]:
				if element:
					request_headers[element.split(':')[0]] = element.split(':')[1]
		else:
			sock.close()
		host   = request_headers['Host'].strip()
		server = computor.computeServer(host)
		if server:  
			if path == '/stats': 
				sock.send('HTTP/1.1 200 OK\r\n')
				self.send_header(sock, "Content-Type", 'text/html')
				self.send_header(sock, 'Server', __version__)  
				sock.send('\r\n')
				data = '<br><br>Domain: <b>' + host + ' </b><br> + Started: '\
						+ startTime + '<br> Balance list: </br>'
				total = 1
				for key, value in counts.iteritems():
					if key not in constructed_cluster[host]: 
						continue 
					total += value 
					data  += ' -' +key+ ':' + '<b>' + str(value) + '</b><br>' 
				sock.send('<meta http-equiv="refresh" content="5" > \
				 <title> Stats </title> \
				 Total requests: ' + '<b>' + str(total) + '</b><br>' \
				'Request/s: ' + str(total/(int(time.time() - ITIME))) + '<br')
				sock.send(data)  
				if len(dead_servers) > 0:
					ddata = '<br> Down: '
					for i in dead_servers:
						if i in constructed_cluster[host]:
							ddata += '<br>' + i + '<br>'
						else: ddata = '<br>Down: 0'
				else: 
					ddata = '<br>Down: 0'
				sock.send(ddata)
				sock.close() 
			elif path == '/favicon.ico':
				sock.send("HTTP/1.1 404 Not Found\r\n")
				sock.close() 
			else: 
				server = server + path 
				sock.send('HTTP/1.1 302 Move Temporary\r\n')
				self.send_header(sock, "Content-Type", 'text/html')
				self.send_header(sock, 'Server', __version__)
				self.send_header(sock, 'Location', server) 
				sock.send('\r\n')
				sock.close()
		else:
			sock.send("HTTP/1.1 403 you're doing something wrong, aren't you?\r\n")
			sock.send("\r\n")
			sock.send("Forbidden")
			sock.close()

	def serve_forever(self, host, port, maxThread = 1000):
		"""Libevent and greenlet take care all the rest"""
		connectionPool = Pool(maxThread)
		listen_sock    = socket.socket() 
		listen_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
		listen_sock.bind((host, port)) 
		listen_sock.listen(500) 
		while True:
			conn, addr = listen_sock.accept() 
			if conn:
				connectionPool.wait_available() 
				connectionPool.spawn(self._handle,conn) 
			
	
