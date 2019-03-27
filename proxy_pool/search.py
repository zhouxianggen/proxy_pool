# coding: utf8 
import json
import asyncio
import requests
from proxybroker import Broker


ADMIN_HOST = 'http://114.55.31.211:8888/_add_proxy'


async def add(proxies):
    while True:
        proxy = await proxies.get()
        if proxy is None: break
        print('Found proxy: %s' % proxy)
        b = {'name': proxy.host, 'schemes': proxy.schemes, 'ip': proxy.host, 
                'port': proxy.port or 80 }
        print('send heartbeat to admin')
        r = requests.post(ADMIN_HOST, 
                data=json.dumps(b), timeout=2)
        print(r.status_code)


proxies = asyncio.Queue()
broker = Broker(proxies)
tasks = asyncio.gather(
    broker.find(types=['HTTP', 'HTTPS'], limit=10),
    add(proxies))


loop = asyncio.get_event_loop()
loop.run_until_complete(tasks)

