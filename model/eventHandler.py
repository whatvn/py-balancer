import os
import errno
import signal
import re
import time
from httpcompute import httpCompute, counts, constructed_cluster, dead_servers
from gevent.pool import Pool 
from gevent import socket, sleep, server
from gevent.monkey import patch_all; patch_all()
import _socket



"""
eventHandler.py
@author: hungnv 
@version: 1.0.1
handle http request
"""

ITIME = time.time() 
__version__ = 'py-balancer/1.0.1'
stats = 0 
computor = httpCompute()
startTime = time.ctime()



class HTTPServer(object):
    """py-balancer is just a balancer node, it should not do
    anything complicated, all of its function is showing statistic,
    redirect to destination server, we're trying to make it as simple
    as possible"""

    def send_header(self, sock, name, value = None):
        """Send headers as {key:value}"""
        if value is not None:
            value = value.strip() + '\r\n'
            sock.send(name + ': ' + value)

    def h_handle(self, sock, address):
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
        if request_headers.has_key('Host'):
            host   = request_headers['Host'].strip()
        else:
            sock.close()
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

    def serve_forever(self, listener, maxThread = 1000):
        """Libevent and greenlet take care all the rest"""
        connectionPool = Pool(maxThread)
        server.StreamServer(listener, self.h_handle).serve_forever()
        # listener = _tcp_listener((host, port))
        # listener
        # listen_sock    = socket.socket()
        # listen_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        # listen_sock.bind((host, port))
        # listen_sock.listen(500)
        while True:
             conn, addr = listener.accept()
             if conn:
                 connectionPool.wait_available()
                 connectionPool.spawn(self.h_handle, conn, addr)

def _tcp_listener(address, backlog=500, reuse_addr=1):
    """A shortcut to create a TCP socket, bind it and put it into listening state.

    The difference from :meth:`gevent.socket.tcp_listener` is that this function returns
    an unwrapped :class:`_socket.socket` instance.
    """
    sock = _socket.socket()
    if reuse_addr is not None:
        sock.setsockopt(_socket.SOL_SOCKET, _socket.SO_REUSEADDR, reuse_addr)
    try:
        sock.bind(address)
    except _socket.error, ex:
        strerror = getattr(ex, 'strerror', None)
        if strerror is not None:
            ex.strerror = strerror + ': ' + repr(address)
        raise
    sock.listen(backlog)
    sock.setblocking(0)
    return sock

def set_up_listener(host, port):
    listener = _tcp_listener((host, port))
    return listener
