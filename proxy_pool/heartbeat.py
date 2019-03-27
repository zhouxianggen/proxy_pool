# coding: utf8 
import os
import socket
import requests


ADMIN_HOST = 'http://114.55.31.211:8888/_add_proxy'
PROXY_PORT = 8899


def read_file(path):
    return open(path).read().strip() if os.path.isfile(path) else ''


def get_name():
    return read_file('/var/.name')


def get_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(('8.8.8.8', 53))
        n = s.getsockname()
        ip = n[0] if n else None
        s.close()
        return ip
    except Exception as e:
        return None


def run():
    ip = get_ip()
    print('current ip is [{}]'.format(ip))
    if not ip:
        return

    b = {'name': get_name(), 'ip': get_ip(), 'port': PROXY_PORT }
    print('send heartbeat to admin')
    requests.post(ADMIN_HOST, 
            data=json.dumps(data), timeout=2)
    print(r.status_code)


run()
