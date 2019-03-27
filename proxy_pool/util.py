# coding: utf8 
import os
import sys
import time
import socket
import logging
import logging.handlers
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
    def __init__(self, log_file=None, log_level=logging.INFO):
        self.set_log(log_file, log_level)


    def set_log(self, log_file=None, log_level=logging.INFO):
        self.log_file = log_file
        self.log_level = log_level
        self.log = logging.getLogger(self.__class__.__name__)
        if self.log.handlers:
            for h in self.log.handlers:
                self.log.removeHandler(h)
        if log_file:
            handler = logging.handlers.RotatingFileHandler(
                    log_file, maxBytes=1024*1024*500, backupCount=10)
        else:
            handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter(
                '[%(name)-18s %(threadName)-10s %(levelname)-8s '
                '%(asctime)s] %(message)s'))
        self.log.addHandler(handler)
        self.log.setLevel(log_level)


def is_addr_used(host, port):
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    result = sock.connect_ex((host, port))
    sock.close()
    return True if result == 0 else False

