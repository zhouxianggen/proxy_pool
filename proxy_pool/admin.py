# coding: utf8 
""" vps代理服务
"""
import time
import threading
import tornado.ioloop
import tornado.web
from broker import Broker
from util import read_config, Runtime, LogObject


class Context(threading.Thread):
    def __init__(self):
        threading.Thread.__init__(self)
        self.daemon = True


    def init(self, config):
        self.proxies = {}
        self.proxy_pool_file = config.get('admin', 'proxy_pool_file')
    

    def run(self):
        while True:
            if self.proxy_pool_file:
                p = copy.copy(self.proxies)
                wlns = []
                for k,v in p.items():
                    wlns.append('{}:{}\n'.format(v[0], v[1]))
                codecs.open(self.proxy_pool_file, 'wb', 'utf8').writelines(wlns)
            time.sleep(1)


g_ctx = Context()


class BaseRequestHandler(LogObject, tornado.web.RequestHandler):
    def __init__(self, *args, **kwargs):
        LogObject.__init__(self)
        tornado.web.RequestHandler.__init__(self, *args, **kwargs)


class GetProxiesReqeustHandler(BaseRequestHandler):
    def get(self):
        self.finish(g_ctx.proxies)


class AddProxyRequestHandler(BaseRequestHandler):
    def post(self):
        self.log.info('[POST] [{}]'.format(self.request.body))
        d = json.loads(self.request.body)
        g_ctx['proxies'][d['name']] = (d['host'], d['port'], int(time.time()))


class DefaultReqeustHandler(BaseRequestHandler):
    def get(self):
        self.write('page inavailable')


class AdminService(tornado.web.Application):
    def __init__(self):
        handlers = [
                (r"/_add_proxy", AddProxyRequestHandler),
                (r"/_get_proxies", GetProxiesResponseHandler),
                (r"(.*)", DefaultRequestHandler)
        ]   
        settings = dict(
            debug=True,
        )   
        tornado.web.Application.__init__(self, handlers, **settings)


def main():
    runtime = Runtime()
    runtime.start()

    if runtime.is_running():
        print('admin service already running, exit ..')
        return

    parser = argparse.ArgumentParser()
    parser.add_argument('-c', '--config', default='proxy_pool.conf', 
            help="specify config file")
    args = parser.parse_args()
    config = read_config(args.config)
    g_ctx.init(config)

    broker = Broker()
    broker.init(config)
    broker.start()

    service = tornado.httpserver.HTTPServer(AdminService())
    service.listen(config.getint('admin', 'port'))
    tornado.ioloop.IOLoop.current().start()


if __name__ == "__main__":
    main()


