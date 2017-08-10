#!/usr/bin/env python
#coding:utf-8

import gevent
import logging
import six
from toughradius.txradius.radius import dictionary
from toughradius.common import cache
from toughradius.txradius import message
from toughradius.txradius.radius import packet
from toughradius.radiusd.basworker import BasicWorker
import importlib

class Handler(BasicWorker):

    def __init__(self,config):
        self.load_auth_modules()

    def createAuthPacket(self, datagram,(host,port)):
        if host in self.clients.ips:
            client = self.clients.ips[host]
            auth_message = message.AuthMessage(packet=datagram, 
                dict=self.dictionary,secret=str(client['secret']))
            auth_message.vendor_id=self.clients.vendors.get(client['vendor'])
        elif self.clients.ids:
            auth_message = message.AuthMessage(packet=datagram, 
                dict=self.dictionary, secret=six.b(''))
            nas_id = auth_message.get_nas_id()
            if nas_id in self.clients.ids:
                client = self.clients.ids[nas_id]
                auth_message.vendor_id = self.clients.vendors.get(client['vendor'])
                auth_message.secret = six.b(client['secret'])
            else:
                raise packet.PacketError("Unauthorized Radius Access Device [%s] (%s:%s)"%(nas_id,host,port))
        else:
            raise packet.PacketError("Unauthorized Radius Access Device (%s:%s) "%(host,port))

        auth_message.source = (host,port)
        return auth_message

    def freeReply(self,req):
        reply = req.CreateReply()
        reply.vendor_id = req.vendor_id
        reply['Reply-Message'] = u'User:%s (Free)Authenticate Success' % req.get_user_name()
        reply.code = packet.AccessAccept        
        reply_attrs = {'attrs':{}}
        reply_attrs['input_rate'] = self.config.radiusd.get("free_auth_input_limit",1048576)
        reply_attrs['output_rate'] = self.config.radiusd.get("free_auth_output_limit",4194304)
        reply_attrs['rate_code'] = self.config.radiusd.get("free_auth_limit_code","")
        reply_attrs['domain'] = self.config.radiusd.get("free_auth_limit_code","")
        reply_attrs['attrs']['Session-Timeout'] = self.config.radiusd.get("max_session_timeout",86400)
        reply.resp_attrs = reply_attrs
        with gevent.Timeout(5, True) as timeout:
            for module_cls in self.modules.authorization:
                mod = self.get_module(module_cls)
                if mod: 
                    reply = mod.handle_radius(req,reply)
            return reply

    def rejectReply(self,req,errmsg=''):
        reply = req.CreateReply()
        reply.vendor_id = req.vendor_id
        reply['Reply-Message'] = errmsg
        reply.code = packet.AccessReject
        return reply

    def sendReply(self,reply, (host,port)):
        self.logger.info("send reply to %s:%s"%(host,port))
        self.socket.sendto(reply.ReplyPacket(), (host,port))     


    def handle(self,data, (host,port)):
        req = self.createAuthPacket(data,(host,port))
        # pass user and password
        if self.config.radiusd.pass_userpwd:
            reply = self.freeReply(req)
            self.pool.spawn(self.sendReply,reply,(host,port))
            return
            
        reply = req.CreateReply()
        reply.vendor_id = req.vendor_id
        with gevent.Timeout(self.config.radiusd.request_timeout, True) as timeout:
            # process radius access request
            for module_cls in self.modules.authentication:
                mod = self.get_module(module_cls)
                if mod: 
                    try:
                        req = mod.handle_radius(req)       
                    except:
                        errmsg = "server handle radius authentication error"
                        self.logger.exception(errmsg)
                        reply = self.rejectReply(req,errmsg)
                        self.pool.spawn(self.sendReply,reply,(host,port))
                        return

            for module_cls in self.modules.authorization:
                mod = self.get_module(module_cls)
                if mod: 
                    try:
                        reply = mod.handle_radius(req,reply)       
                    except:
                        errmsg = "server handle radius authorization error"
                        self.logger.exception(errmsg)
                        reply = self.self.rejectReply(req,errmsg)
                        self.pool.spawn(self.sendReply,reply,(host,port))
                        return

        if reply is None:
            self.logger.error("radius authentication message discarded")
            return

        if not req.VerifyReply(reply):
            errstr = u'[User:%s] The authentication message failed to check. \
            Check that the shared key is consistent'% username
            self.logger.error(errstr)
            return

        self.pool.spawn(self.sendReply,reply,(host,port))

        



















