# coding: utf8 
import sys
import requests


url = 'https://www.cnblogs.com/dzqdzq/p/9822187.html'
if len(sys.argv) > 1:
    url = sys.argv[1]

host = 'localhost:8898'
#host = '183.164.234.225'
proxies = {'http': 'http://localhost:8898', 
        'https': 'http://localhost:8898'}
r = requests.get(url, proxies=proxies)
print(r.status_code)
print(len(r.content))
open('/data/share/x.html', 'wb').write(r.content)

