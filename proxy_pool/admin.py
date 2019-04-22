# coding: utf8 
""" vps代理服务
"""
import time
import json
import copy
import argparse
import threading
import tornado.ioloop
import tornado.web
from broker import Broker
from util import is_addr_used, read_config, LogObject


class Context(threading.Thread):
    def __init__(self):
        threading.Thread.__init__(self)
        self.daemon = True
        self.lock = threading.Lock()


    def init(self, config):
        self.proxies = {}
        self.proxy_file = config.get('admin', 'proxy_file')
        self.log_file = config.get('admin', 'log_file')
    

    def add_proxy(self, proxy):
        proxy['timestamp'] = int(time.time())
        k = proxy['name']
        self.lock.acquire()
        self.proxies[k] = proxy
        self.lock.release() 


    def run(self):
        while True:
            deletes = []
            for k,v in self.proxies.items():
                if time.time() - v['timestamp'] > 66:
                    deletes.append(k)
            self.lock.acquire()
            for k in deletes:
                self.proxies.pop(k, '')
            self.lock.release() 

            if self.proxy_file:
                p = copy.copy(self.proxies)
                wlns = []
                for k,v in p.items():
                    wlns.append('{} {} {}\n'.format(','.join(v['schemes']), 
                            v['ip'], v['port']))
                open(self.proxy_file, 'w').writelines(wlns)
            time.sleep(1)


g_ctx = Context()


class BaseRequestHandler(LogObject, tornado.web.RequestHandler):
    def __init__(self, *args, **kwargs):
        LogObject.__init__(self, log_file=g_ctx.log_file)
        tornado.web.RequestHandler.__init__(self, *args, **kwargs)


class GetProxiesRequestHandler(BaseRequestHandler):
    def get(self):
        for k,v in g_ctx.proxies.items():
            v['active'] = int(time.time()) - int(v['timestamp'])
        self.finish(g_ctx.proxies)


class AddProxyRequestHandler(BaseRequestHandler):
    def post(self):
        self.log.info('[POST] [{}]'.format(self.request.body))
        proxy = json.loads(self.request.body)
        g_ctx.add_proxy(proxy)


class DefaultRequestHandler(BaseRequestHandler):
    def get(self, option):
        self.write('page inavailable')


class AdminService(tornado.web.Application):
    def __init__(self):
        handlers = [
                (r"/_add_proxy", AddProxyRequestHandler),
                (r"/_get_proxies", GetProxiesRequestHandler),
                (r"(.*)", DefaultRequestHandler)
        ]   
        settings = dict(
            debug=True,
        )   
        tornado.web.Application.__init__(self, handlers, **settings)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('-c', '--config', default='proxy_pool.conf', 
            help="specify config file")
    args = parser.parse_args()
    config = read_config(args.config)
    g_ctx.init(config)
    g_ctx.start()

    broker = Broker()
    broker.init(config)
    if is_addr_used(broker.hostname, broker.port):
        print('broker already run. exit ..')
        return
    broker.start()

    port = config.getint('admin', 'port')
    if is_addr_used('localhost', port):
        print('admin already run. exit ..')
        return
    service = tornado.httpserver.HTTPServer(AdminService())
    service.listen(port)
    tornado.ioloop.IOLoop.current().start()


if __name__ == "__main__":
    main()


