import os
import errno
import signal
import socket
import re
import time 
from httpcompute import httpCompute, counts, constructed_cluster, dead_servers
"""
httputil.py
@author: hungnv 
@version: 1.0.0 
core module, fork tcp server socket
handle http request
"""

ITIME = time.time() 
BACKLOG = 5
__version__ = 'py-balancer/1.0.0'
stats = 0 
computor = httpCompute()
startTime = time.ctime()

	
class HTTPServer(object):
	
	def send_header(self, sock, name, value):
		value = value.strip() + '\r\n'
		#print name + ': ' + value 
		try:
			sock.send(name + ': ' + value)
		# bypass broken Pipe 
		except socket.error: 
			pass 
	def handle(self, sock):
		try:
			request_headers = {}
			bytes = sock.recv(1024)
			bytes = bytes.split('\r\n')
			try:
				path = bytes[0].split(' ')[1] 
				for element in bytes[1:]:
					request_headers[element.split(':')[0]] = element.split(':')[1]
			except IndexError: 
				pass
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
					total = 0
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
				else: 
					server = server + path 
					sock.send('HTTP/1.1 302 Move Temporary\r\n')
					self.send_header(sock, "Content-Type", 'text/html')
					self.send_header(sock, 'Server', __version__)
					self.send_header(sock, 'Location', server) 
					sock.send('\r\n')
					
			else:
				sock.send("HTTP/1.1 403 you're doing something wrong, aren't you?\r\n")
				sock.send("\r\n")
				sock.send("Forbidden")
		except KeyError: 
			pass 
		except socket.error: 
			pass 
		finally:
			sock.close() 

		
	def child_loop(self, index, listen_sock):
		"""Main child loop."""
		while True:
			# block waiting for connection to handle
			try:
				conn, client_address = listen_sock.accept()
			except IOError as e:
				code, msg = e.args
				if code == errno.EINTR:
					continue
				else:
					raise
			self.handle(conn)
			
			# close handled socket connection and off to handle another request
			conn.close()
	
	def create_child(self, index, listen_sock):
		pid = os.fork()
		if pid > 0: # parent
			return pid
		#print 'Child started with PID: %s' % os.getpid()
		# child never returns
		self.child_loop(index, listen_sock)
	
	
	def _cleanup(self, signum, frame):
		"""SIGTERM signal handler"""
		# terminate all children
		for pid in PIDS:
			try:
				os.kill(pid, signal.SIGTERM)
			except:
				pass
	
        # wait for all children to finish
		while True:
			try:
				pid, status = os.wait()
			except OSError as e:
				if e.errno == errno.ECHILD:
					break
				else:
					raise
			if pid == 0:
				break
			os._exit(0)


	def serve_forever(self, host, port, childnum):
		# create, bind, listen
		listen_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
		# re-use the port
		listen_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
		listen_sock.bind((host, port))
		listen_sock.listen(BACKLOG)

		print 'Listening on port %d ...' % port
		# prefork children
		global PIDS
		PIDS = [self.create_child(index, listen_sock) for index in range(childnum)]
		# setup SIGTERM handler - in case the parent is killed
		signal.signal(signal.SIGTERM, self._cleanup)
		
		# parent never calls 'accept' - children do all the work
		# all parent does is sleeping :)
		signal.pause()
		
		
	
