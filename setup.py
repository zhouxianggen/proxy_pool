#!/usr/bin/env python
#coding=utf8

try:
    from  setuptools import setup, find_packages
except ImportError:
    from distutils.core import setup

setup(
        name = 'proxy_pool',
        version = '1.0',
        install_requires = [], 
        description = 'proxy pool',
        url = 'https://github.com/zhouxianggen/proxy_pool', 
        author = 'zhouxianggen',
        author_email = 'zhouxianggen@gmail.com',
        classifiers = [ 'Programming Language :: Python :: 3.7',],
        packages = ['proxy_pool'],
        data_files = [ ], 
        )

