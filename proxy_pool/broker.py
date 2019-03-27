# coding: utf8 
""" python proxy server
refer: https://github.com/abhinavsingh/proxy.py
"""
import os
import sys
import re
import time
import argparse
import threading
import socket
import select
import random
from util import LogObject
if os.name != 'nt':
    import resource


PY3 = sys.version_info[0] == 3
if PY3: 
    from urllib import parse as urlparse
else:
    import urlparse


class Connection(LogObject):
    """TCP server/client connection abstraction."""

    def __init__(self, what, log_file=''):
        LogObject.__init__(self, log_file)
        self.conn = None
        self.buffer = b''
        self.closed = False
        self.what = what  # server or client


    def send(self, data):
        # TODO: Gracefully handle BrokenPipeError exceptions
        return self.conn.send(data)


    def recv(self, bufsiz=8192):
        try:
            data = self.conn.recv(bufsiz)
            self.log.info('rcvd [{}] bytes from [{}]'.format(
                    len(data), self.what))
            if len(data) == 0:
                return None
            return data
        except Exception as e:
            self.log.exception(e)
            return None


    def close(self):
        self.conn.close()
        self.closed = True


    def buffer_size(self):
        return len(self.buffer)


    def has_buffer(self):
        return self.buffer_size() > 0


    def queue(self, data):
        self.buffer += data


    def flush(self):
        sent = self.send(self.buffer)
        self.buffer = self.buffer[sent:]


class Server(Connection):
    def __init__(self, conn, addr, log_file=''):
        super(Server, self).__init__('server', log_file)
        self.conn = conn
        self.addr = addr


class Client(Connection):
    def __init__(self, conn, addr, log_file=''):
        super(Client, self).__init__('client', log_file)
        self.conn = conn
        self.addr = addr


class LogThread(threading.Thread, LogObject):
    def __init__(self, log_file=''):
        threading.Thread.__init__(self)
        LogObject.__init__(self, log_file=log_file)
        self.daemon = True


class Tunnel(LogThread):
    """ act as a tunnel between client and server.
    """

    def __init__(self, client, client_recvbuf_size=8192, 
            server_recvbuf_size=8192, proxy_file='proxies', log_file=''):
        LogThread.__init__(self, log_file=log_file)

        self.start_time = time.time()
        self.last_activity = self.start_time
        self.client = client
        self.client_recvbuf_size = client_recvbuf_size
        self.server_recvbuf_size = server_recvbuf_size
        self.proxy_file = proxy_file
        self.server = None


    def _is_inactive(self):
        return (time.time() - self.last_activity) > 30


    def run(self):
        try:
            self._process()
        except Exception as e:
            self.log.exception(e)
        finally:
            self.log.info('close client connection')
            self.client.close()
            if self.server:
                self.server.close()
    
    
    def _process(self):
        while True:
            self.log.debug('_process')
            rlist, wlist, xlist = self._get_waitable_lists()
            r, w, x = select.select(rlist, wlist, xlist, 1)

            self._process_wlist(w)
            if self._process_rlist(r):
                break


    def _get_waitable_lists(self):
        rlist, wlist, xlist = [self.client.conn], [], []
        if self.client.has_buffer():
            wlist.append(self.client.conn)
        if self.server and not self.server.closed:
            rlist.append(self.server.conn)
        if self.server and not self.server.closed and self.server.has_buffer():
            wlist.append(self.server.conn)
        return rlist, wlist, xlist


    def _process_wlist(self, w):
        if self.client.conn in w:
            self.log.info('client is ready for writes, flushing client buffer')
            self.client.flush()

        if self.server and not self.server.closed and self.server.conn in w:
            self.log.info('server is ready for writes, flushing server buffer')
            self.server.flush()
    
    
    def _process_rlist(self, r):
        """Returns True if connection to client must be closed."""
        if self.client.conn in r:
            self.log.info('client is ready for reads')
            self.last_activity = time.time()
            data = self.client.recv(self.client_recvbuf_size)
            if not data:
                self.log.info('client closed connection')
                return True
            if not self.server:
                m = re.match(r'(GET|CONNECT|POST|HEAD)\s+(\S+)\s+HTTP', 
                        data.decode('utf8'), re.I)
                if not m:
                    self.log.error('can not match first line')
                    return True

                self.log.info('select server for [{}]'.format(m.group(1)))
                self.server = self.select_server(m.group(1).upper())
                if not self.server:
                    self.log.warning('can not select server')
                    return True
                self.log.info('get server [{}]'.format(self.server.addr))
            self.server.queue(data)

        if self.server.conn in r:
            self.log.info('server is ready for reads')
            self.last_activity = time.time()
            data = self.server.recv(self.server_recvbuf_size)
            if not data:
                self.log.info('server closed connection')
                return True
            self.client.queue(data)
        return False
 
 
    def select_server(self, method):
        if not os.path.isfile(self.proxy_file):
            return None
        pool = []
        for ln in open(self.proxy_file, 'r').readlines():
            t = ln.split()
            if len(t) != 3:
                continue
            schemes = [x.upper().strip() for x in t[0].split(',')]
            ip, port = t[1], int(t[2])
            if method == 'CONNECT':
                if 'HTTPS' not in schemes:
                    continue
            else: 
                if 'HTTP' not in schemes:
                    continue
            pool.append((t[1], int(t[2])))
        if not pool:
            return None
        start = random.randint(0, len(pool)-1)
        for i in range(len(pool)):
            addr = pool[(start + i) % len(pool)]
            try:
                conn = socket.create_connection(addr)
                return Server(conn, addr, log_file=self.log_file)
            except Exception as e:
                self.log.exception(e)
                self.log.warning('try connect [{}] failed'.format(addr))
        return None
   

class Broker(LogThread):
    def __init__(self):
        LogThread.__init__(self)
        

    def init(self, cfg):
        self.hostname = cfg.get('broker', 'hostname')
        self.port = cfg.getint('broker', 'port')
        self.backlog = cfg.getint('broker', 'backlog')
        self.client_recvbuf_size = cfg.getint('broker', 'client_recvbuf_size')
        self.server_recvbuf_size = cfg.getint('broker', 'server_recvbuf_size')
        self.open_file_limit = cfg.getint('broker', 'open_file_limit')
        self.proxy_file = cfg.get('broker', 'proxy_file')
        self.log_file = cfg.get('broker', 'log_file')
        self.set_log(log_file=self.log_file)
        self.socket = None


    def run(self):
        self.set_open_file_limit(self.open_file_limit)
        try:
            self.log.info('Starting broker on port %d' % self.port)
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.socket.bind((self.hostname, self.port))
            self.socket.listen(self.backlog)
            while True:
                conn, addr = self.socket.accept()
                client = Client(conn, addr, self.log_file)
                self.log.info('request from client [{}]'.format(client.addr))
                self.handle(client)
        except Exception as e:
            self.log.exception(e)
        finally:
            self.log.info('closing server socket')
            self.socket.close()


    def set_open_file_limit(self, limit):
        if os.name != 'nt': 
            soft_limit, hard_limit = resource.getrlimit(resource.RLIMIT_NOFILE)
            if soft_limit < limit < hard_limit:
                resource.setrlimit(resource.RLIMIT_NOFILE, (limit, hard_limit))


    

    def handle(self, client):
        self.log.info('handle request from [{}]'.format(client.addr))
        tunnel = Tunnel(client,  
                      server_recvbuf_size=self.server_recvbuf_size,
                      client_recvbuf_size=self.client_recvbuf_size, 
                      proxy_file=self.proxy_file,
                      log_file=self.log_file)
        tunnel.start()

