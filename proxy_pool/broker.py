# coding: utf8 
""" python proxy server
refer: https://github.com/abhinavsingh/proxy.py
"""
import os
import sys
import time
import argparse
import threading
import socket
import select
import codecs
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

    def __init__(self, what, log_path=''):
        LogObject.__init__(self, log_path)
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
    def __init__(self, conn, addr, log_path=''):
        super(Server, self).__init__('server', log_path)
        self.conn = conn
        self.addr = addr


class Client(Connection):
    def __init__(self, conn, addr, log_path=''):
        super(Client, self).__init__('client', log_path)
        self.conn = conn
        self.addr = addr


class LogThread(threading.Thread, LogObject):
    def __init__(self, log_path=''):
        threading.Thread.__init__(self)
        LogObject.__init__(self, log_path=log_path)
        self.daemon = True


class Tunnel(LogThread):
    """ act as a tunnel between client and server.
    """

    def __init__(self, client, server, client_recvbuf_size=8192, 
            server_recvbuf_size=8192, log_path=''):
        LogThread.__init__(self, log_path=log_path)

        self.start_time = time.time()
        self.last_activity = self.start_time
        self.client = client
        self.client_recvbuf_size = client_recvbuf_size
        self.server = server
        self.server_recvbuf_size = server_recvbuf_size


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
    

class Broker(LogThread):
    def __init__(self, config):
        self.init(config)
        LogThread.__init__(self, log_path=self.log_path)
        

    def init(self, cfg):
        self.hostname = cfg.get('broker', 'hostname')
        self.port = cfg.getint('broker', 'port')
        self.backlog = cfg.getint('broker', 'backlog')
        self.client_recvbuf_size = cfg.getint('broker', 'client_recvbuf_size')
        self.server_recvbuf_size = cfg.getint('broker', 'server_recvbuf_size')
        self.open_file_limit = cfg.getint('broker', 'open_file_limit')
        self.proxy_pool_file = cfg.get('broker', 'proxy_pool_file')
        self.log_path = cfg.get('broker', 'log_path')
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
                client = Client(conn, addr, self.log_path)
                self.log.info('request from client [{}]'.format(client.addr))
                server = self.select_server()
                if not server:
                    self.log.warning('can not select server')
                    client.close()
                    continue
                self.log.info('select server [{}]'.format(server.addr))
                self.handle(client, server)
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


    def select_server(self):
        if not os.path.isfile(self.proxy_pool_file):
            return None
        pool = []
        for ln in codecs.open(self.proxy_pool_file, 'r', 'utf8').readlines():
            t = ln.split(':')
            if len(t) == 2:
                pool.append((t[0], int(t[1])))
        if not pool:
            return None
        start = random.randint(0, len(pool)-1)
        for i in range(len(pool)):
            addr = pool[(start + i) % len(pool)]
            try:
                conn = socket.create_connection(addr)
                return Server(conn, addr, log_path=self.log_path)
            except Exception as e:
                self.log.exception(e)
                self.log.warning('try connect [{}] failed'.format(addr))
        return None


    def handle(self, client, server):
        self.log.info('handle request from [{}]'.format(client.addr))
        tunnel = Tunnel(client, server, 
                      server_recvbuf_size=self.server_recvbuf_size,
                      client_recvbuf_size=self.client_recvbuf_size, 
                      log_path=self.log_path)
        tunnel.start()

