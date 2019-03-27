# coding: utf8 
import os
import sys
import logging
import threading


PY3 = sys.version_info[0] == 3
if PY3: 
    import configparser as ConfigParser
else:
    import ConfigParser


def read_config(config):
    cfg = ConfigParser.ConfigParser()
    cfg.read(config)
    return cfg


class LogObject(object):
    def __init__(self, log_path=None, log_level=logging.INFO):
        self.log_path = log_path
        self.log_level = log_level
        self.log = logging.getLogger(self.__class__.__name__)
        if not self.log.handlers:
            if log_path:
                handler = logging.handlers.RotatingFileHandler(
                        log_path, maxBytes=1024*1024*500, backupCount=10)
            else:
                handler = logging.StreamHandler()
            handler.setFormatter(logging.Formatter(
                    '[%(name)-18s %(threadName)-10s %(levelname)-8s '
                    '%(asctime)s] %(message)s'))
            self.log.addHandler(handler)
        self.log.setLevel(log_level)


class Runtime(threading.Thread):
    def __init__(self, interval=1):
        threading.Thread.__init__(self)
        self.daemon = True
        self.interval = interval
        self.runtime_path = os.path.join(
                os.path.dirname(os.path.abspath(__file__)), '.runtime')


    def run(self):
        while 1:
            open(self.runtime_path, 'wb').write(str(int(time.time())))
            time.sleep(self.interval)
    
    
    def is_running(self):
        if os.path.isfile(self.runtime_path):
            c = open(self.runtime_path, 'rb').read()
            if c.isdigit():
                return int(c) + self.interval + 1 > int(time.time())
        return False

