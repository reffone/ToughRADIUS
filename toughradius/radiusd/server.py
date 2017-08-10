#!/usr/bin/env python
#coding:utf-8
import os
from gevent.server import DatagramServer
from gevent.threadpool import ThreadPool
from gevent import socket
from toughradius.txradius.radius import dictionary
from toughradius.common import cache
import gevent
from . import authenticate
from . import accounting
import click
import logging
import logging.config 
import importlib



class RudiusServer(DatagramServer):

    def __init__(self, address, config):
        DatagramServer.__init__(self,address)
        self.logger = logging.getLogger(__name__)
        self.config = config
        self.dictionary = dictionary.Dictionary(self.config.radiusd.dictionary)
        self.clients = self.config.clients
        self.modules = self.config.modules
        self.address = (self.config.radiusd.host,self.config.radiusd.auth_port)
        self.module_cache = cache.Mcache()
        self.cache = cache.Mcache()
        self.load_modules()
        self.pool = ThreadPool(self.config.radiusd.pool_size)
        self.start()

    def load_modules(self):
        self.logger.info('starting load authentication modules')
        for module_cls in self.config.modules.authentication:
            self.logger.info("enable module %s" % module_cls)
            mod = self.get_module(module_cls)

        self.logger.info('starting load authorization modules')
        for module_cls in self.config.modules.authorization:
            self.logger.info("enable module %s" % module_cls)
            mod = self.get_module(module_cls)

        self.logger.info('starting load acctounting modules')
        for name in ['parse','start','stop','update','on','off','acct_post']:
            for module_cls in self.config.modules.acctounting[name]:
                self.logger.info("enable module %s" % module_cls)
                mod = self.get_module(module_cls)        
    

    def get_module(self,module_class):
        modobj = self.module_cache.get(module_class)
        if modobj:
            return modobj
        try:
            mdobj = importlib.import_module(module_class)
            if hasattr(mdobj, 'handle_radius'):
                self.module_cache.set(module_class,mdobj)
                return mdobj
        except:
            self.logger.exception("load module <%s> error" % module_class)



class RudiusAuthServer(RudiusServer):

    def __init__(self, address, config):
        RudiusServer.__init__(self,address,config)
        self.radius_handler = authenticate.Handler(self)

    def handle(self,data, address):
        self.pool.spawn(self.radius_handler.handle,data,address)


class RudiusAcctServer(RudiusServer):

    def __init__(self, address, config):
        RudiusServer.__init__(self,address,config)
        self.radius_handler = accounting.Handler(self)

    def handle(self,data, address):
        self.pool.spawn(self.radius_handler.handle,data,address)




















