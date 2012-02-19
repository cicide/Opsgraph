#!/usr/bin/python

from twisted.names import client as dns_client
from twisted.web import client as web_client
from twisted.internet import defer
from paste.auth import auth_tkt

import json, time, datetime, urllib
import utils, rest_api, txdbinterface
import re, copy

log = utils.get_logger("NodeService")
cfg_sections = utils.config.sections()

graph_duration = '%s%s' % (utils.config.get('graph', 'duration_length'), utils.config.get('graph', 'duration_unit'))
local_ip = utils.config.get('general', 'local_ip')
event_full_load_period = utils.config.get('events', 'full_load_period')
event_inc_load_period = utils.config.get('events', 'incremental_load_period')

node_list = {}
event_type_list = ['outage', 'event']

class Node(object):
    def __init__(self, name, type):
        self.name = name
        self.parent = None
        self.children = {}
        self.type = type
         
    def addChild(self, node):
        self.children[node.name] = node
        node.parent = self

    def removeChild(self, name):
        if children.get(name):
            del self.children[name]

    def getChildren(self):
        return self.children 

    def searchChildren(self, pattern):
        returnList = {}
        pat = re.compile(pattern, re.I)
        for key in self.children:
            if pat.search(key) is not None:
                returnList[key] = self.children[key]
        return returnList

class Domain(Node):
    
    def __init__(self, name, host, login, passwd, shared_secret, api_tool, rescan):
        Node.__init__(self, name, "Domain")
        self.host = host.split('//')[1]
        self.uri = host
        self.login = login
        self.password = passwd
        self.shared_secret = shared_secret
        self.api_tool = api_tool
        self.rescan = int(rescan)
        self.masterLoginToken = None
        self.easyxdm_version = None
        self.api_min_version = None
        self.api_version = None
        self.creds = None
        self.initialized = False
        self.cred_time = 0
        self.ip_address = None
        self.last_event_id = 0
        self.last_full_event_load = 0
        self.do_dns_lookup(self.host)
        self.event_type_list = []
        self.eventList = []
        self.loadEvents()
        
    def loadEvents(self):
        def onTypeSuccess(result):
            log.debug('Got Event Types result for Node %s: ' % self.name)
            log.debug(result)
            self.event_type_list = []
            for item in result:
                if item[0] not in event_type_list:
                    event_type_list.append(item[0])
                self.event_type_list.append(item[0])
        def onEventsSuccess(result):
            log.debug('Got Event List result for Node %s: ' % self.name)
            log.debug(result)
            event_list = {}
            if result:
                for event in result:
                    e_dbid = event[0]
                    e_node = event[1]
                    et_name = event[2]
                    et_desc = event[3]
                    et_color = event[4]
                    et_alpha = event[5]
                    e_name = event[6]
                    e_desc = event[7]
                    e_start = event[8]
                    e_end = event[9]
                    e_url = event[10]
                    log.debug('processing event %s for node %s ' % (e_name, self.name))
                    if et_name not in event_list:
                        event_list[et_name] = {}
                        event_list[et_name]['color'] = et_color
                        event_list[et_name]['alpha'] = et_alpha
                        event_list[et_name]['events'] = []
                    event_list[et_name]['events'].append([e_dbid, e_name, e_desc, e_start, e_end, e_url])
                self.eventList = event_list
            log.debug('Parsed event list for node %s: %s' % (self.name, event_list))
        def onCompleteSuccess(result):
            log.debug('Got Complete result for Node %s: ' % self.name)
            log.debug(result)
        def onFailure(reason):
            log.error(reason)
        ds = []
        d1 = txdbinterface.getEventTypes()
        d1.addCallbacks(onTypeSuccess,onFailure)
        ds.append(d1)
        d2 = txdbinterface.getEventData(self.name)
        d2.addCallbacks(onEventsSuccess,onFailure)
        ds.append(d2)
        d = defer.DeferredList(ds, consumeErrors=False)
        d.addCallbacks(onCompleteSuccess,onFailure)
        
    def getHostList(self):
        host_list = []
        for i in self.children:
           host_list.append(i)
        return host_list

    def getEvents(self):
        return self.eventList.copy()
    
    def getUri(self):
        return self.uri
    
    def do_dns_lookup(self, domain):
        def onSuccess(result, domain):
            log.debug('got ip address %s for domain %s' %(result, domain))
            self.ip_address = result
        def onFailure(reason):
            log.error(reason)
        d = dns_client.getHostByName(self.host)
        d.addCallback(onSuccess, domain).addErrback(onFailure)
        return d
        
    def onErr(self, reason):
        log.debug(reason)
        
    def setVersions(self, easyxdm, api_min, api):
        self.easyxdm_version = easyxdm
        self.api_min_version = api_min
        self.api_version = api
        log.debug('versions set: %s, %s, %s' % (self.easyxdm_version, self.api_min_version, self.api_version))
        return 1
    
    def loginMaster(self):
        def onSuccess(result):
            if 'token' not in result:
                log.debug('got login response without token')
                return 0
            else:
                self.masterLoginToken = str(result['token'])
                self.cred_time = int(time.time())
                log.debug('logged in with token %s' % self.masterLoginToken)
                return 1
        def onFail(reason):
            log.error(reason)
        postData = {'username': self.login, 'password': self.password}
        d = rest_api.postData(self.uri, 'rest/login', postData)
        d.addCallbacks(onSuccess,onFail)
        return d
    
    def loginUser(self, username, password):
        def get_auth_tkt(result):
            def onTktSuccess(result, token_result):
                log.debug('got token result: %s' % token_result)
                log.debug('got auth_tkt response for %s: %s' % (self.name, cj))
                return token_result, cj
            def onTktFail(reason, token_result):
                log.debug('got token result')
                log.debug(token_result)
                log.error('auth_tkt request failed')
                log.error(reason)
                return False, token_result
            token_result = result
            cj = {}
            headers = []
            cj['auth_tkt'] = self._makeTicket(userid=username, remote_addr=local_ip)
            log.debug('requesting web auth with ticket: %s' % cj)
            d = web_client.getPage(self.uri,headers,method='GET',cookies=cj)
            d.addCallback(onTktSuccess, token_result).addErrback(onTktFail, token_result)
            return d
        def onSuccess(result):
            if 'token' not in result:
                log.debug('got user login response without token')
                return False
            else:
                token = str(result['token'])
                cred_time = int(time.time())
                log.debug('cookies: %s' % cj)
                log.debug('user logged in with token %s' % token)
                return (token, cred_time, cj)
        def onFail(reason):
            log.error(reason)
            return False
        cj = {}
        cj['auth_tkt'] = self._makeTicket(userid=username, remote_addr=local_ip)
        postData = {'username': username, 'password': password}
        d = rest_api.postData(self.uri, 'rest/login', postData, headers={}, cookies=cj)
        d.addCallbacks(onSuccess,onFail)
        #d.addBoth(get_auth_tkt)
        return d
    
    def initialize(self, result=None):
        # if we don't have a token, we need to get one
        if not self.masterLoginToken:
            log.info('Initializing opsview node %s' % self.name)
            d = self.loginMaster()
            return d.addCallback(self.initialize).addErrback(self.onErr)
        else:
            self.creds = {'X-Opsview-Username': self.login, 'X-Opsview-Token': self.masterLoginToken}
            d = rest_api.getInfo(self.uri, 'rest/status/service', headers=self.creds)
            return d.addCallbacks(self.addServices,self.onErr)
            
    def getHostByName(self, name):
        return self.children.get(name, None)

    def saveMetricData(self, result):
        if result:
            self.cred_time = int(time.time())
            if len(result):
                host_metric_list = result['list']
                log.debug('Metric list is %s records long' % len(host_metric_list))
                for row in host_metric_list:
                    host,service,metric = row.split('::')
                    if( service and metric):
                        host = self.getHostByName(str(host))
                        if host:
                            host.addServiceMetric(service, metric)
                        else:
                            log.error("Host doesn't exist %s for row %s" % (host, row))
                    else:
                        log.info('skipping row: %s  - as something is wrong' % row)
                log.info('Found %i graphable metrics for domain %s' % (len(host_metric_list), self.name))
                log.info('Domain initialization for domain %s complete' % self.name)
                self.initialized = True
                return 1
            else:
                return 0
        else:
            log.debug('No result')
            return 0
            
    def addServices(self, result=None):
        self.cred_time = int(time.time())
        if not result:
            log.debug('No services to add')
            return 0
        else:
            services = result
            service_list = services['list']
            service_sum = services['summary']
            host_count = 0
            for item in service_list:
                host_count += 1
                item_services = item['services']
                host_name = item['name']
                host_alias = item['alias']
                if 'comments' in item:
                    host_comments = item['comments']
                else:
                    host_comments = ''
                host = Host(host_alias,
                               host_comments,
                               item['current_check_attempt'],
                               item['downtime'],
                               item['icon'],
                               item['last_check'],
                               item['max_check_attempts'],
                               host_name,
                               item['num_interfaces'],
                               item['num_services'],
                               item['output'])
                self.addChild(host)
                for svc in item_services:
                    svc_host = host_name
                    svc_name = svc['name']
                    svc_current_check_attempt = svc['current_check_attempt']
                    svc_downtime = svc['downtime']
                    svc_last_check = svc['last_check']
                    svc_markdown = svc['markdown']
                    svc_max_check_attempts = svc['max_check_attempts']
                    svc_output = svc['output']
                    svc_perfdata_available = svc['perfdata_available']
                    svc_service_object_id = svc['service_object_id']
                    svc_state = svc['state']
                    svc_state_type = svc['state_type']
                    svc_state_duration = svc['state_duration']
                    svc_unhandled = svc['unhandled']
                    svc_obj = Service(svc_current_check_attempt,
                                      svc_downtime,
                                      svc_last_check,
                                      svc_markdown,
                                      svc_max_check_attempts,
                                      svc_name,
                                      svc_output,
                                      svc_perfdata_available,
                                      svc_service_object_id,
                                      svc_state,
                                      svc_state_type,
                                      svc_state_duration,
                                      svc_unhandled,
                                      svc_host)
                    host.addChild(svc_obj)
            log.info('found %s hosts for node %s' % (host_count, self.name))
            perfmetrics = rest_api.getInfo(self.uri, 'rest/runtime/performancemetric', headers=self.creds)
            perfmetrics.addCallbacks(self.saveMetricData,self.onErr)
            return 1
                
    def getName(self):
        return self.name
    
    def getUri(self):
        return self.uri
    
    def getApi(self):
        return api_tool
    
    def fetchData(self, uri, end_time=None, duration=None, creds={}, cookies={}):
        def onSuccess(result):
            return result
        def onFailure(result):
            return result
        if not duration:
            duration = graph_duration
        if not end_time:
            end_time = int(time.time())
        if len(creds) == 0:
            creds = self.creds
        #url = '%s?hsm=%s&end_time=%s&duration=%s' % (api_tool, urllib.quote_plus(uri), end_time, duration)
        url = '%s?hsm=%s&end=%s&duration=%s' % (self.api_tool, urllib.quote_plus(uri), end_time, duration)
        log.debug('requesting %s from %s' % (url, self.uri))
        d = rest_api.getInfo(self.uri, str(url), headers=creds, cookies=cookies)
        return d.addCallbacks(onSuccess,onFailure)

    def _makeTicket(self, 
                    userid='userid', 
                    remote_addr='0.0.0.0',
                    tokens = [], 
                    userdata='userdata',
                    cookie_name='auth_tkt', 
                    secure=False,
                    time=None):
        log.debug('creating ticket with shared: %s and remote_ip: %s' % (self.shared_secret, remote_addr))
        ticket = auth_tkt.AuthTicket(
            self.shared_secret,
            userid,
            remote_addr,
            tokens=tokens,
            user_data=userdata,
            time=time,
            cookie_name=cookie_name,
            secure=secure)
        return ticket.cookie_value()

class Host(Node):
    
    def __init__(self, 
                 alias, 
                 comments, 
                 current_check_attempt, 
                 downtime, 
                 icon,
                 last_check,
                 max_check_attempts,
                 name,
                 num_interfaces,
                 num_services,
                 output):
        Node.__init__(self, name, "Host")
        self.alias = alias
        self.comments = comments
        self.current_check_attempt = current_check_attempt
        self.downtime = downtime
        self.icon = icon
        self.last_check = last_check
        self.max_check_attempts = max_check_attempts
        self.num_interfaces = num_interfaces
        self.num_services = num_services
        self.output = output
        self.metric_count = 0
        #log.debug('host %s added' % self.name)
        
    def addServiceMetric(self, serviceName, metric=None):
        #log.debug('Adding service metric %s::%s to host %s' % (str(service), str(metric), self.name))
        serviceName = str(serviceName)
        service = self.getServiceByName(serviceName)
        if metric:
            metric = str(metric)
            if service:
                met = Metric(metric)
                self.metric_count += 1
                service.addChild(met)
            else:
                log.debug('adding a metric without service So skipping Metric %s')
        else:
            if service:
                log.debug('adding a service without metric so skipping')
                
    def hasMetrics(self):
        return self.metric_count!=0;
    
    def getMetricCount(self):
        return self.metric_count
    
    def getMetricList(self, req_service):
        log.debug('grabbing metrics for service %s' % req_service)
        metric_list = []
        for child in self.children:
            log.debug('appending %s to metric list' % metric)
            metric_list.extend(child.getMetricList())
        return metric_list

    def getServiceList(self):
        return self.children.keys()
    def getServiceByName(self, name):
        return self.children.get(name, None)
    
class Service(Node):
    
    def __init__(self,
                 current_check_attempt,
                 downtime,
                 last_check,
                 markdown,
                 max_check_attempts,
                 name,
                 output,
                 perfdata_available,
                 service_object_id,
                 state,
                 state_type,
                 state_duration,
                 unhandled,
                 host):
        Node.__init__(self, name, "Service")
        self.current_check_attempt = current_check_attempt
        self.downtime = downtime
        self.last_check = last_check
        self.markdown = markdown
        self.max_check_attempts = max_check_attempts
        self.output = output
        self.perfdata_available = perfdata_available
        self.service_object_id = service_object_id
        self.state = state
        self.state_type = state_type
        self.state_duration = state_duration
        self.unhandled = unhandled
        self.host = host

    def getMetricList(self):
        metric_list = []
        for child in self.children.values():
            metric_list.append(child.name)
        return metric_list

class Metric(Node):
    # we cache data for a metric here
    def __init__(self, name):
        Node.__init__(self, name, "Metric")
        self.data = {}
        self.touched = int(time.time()) 
    
def saveVersionInfo(result, node):
    if 'easyxdm_version' not in result:
        easyxdm = 0
    else:
        easyxdm = result['easyxdm_version']
    if 'api_min_version' not in result:
        api_min = 0
    else:
        api_min = result['api_min_version']
    if 'api_version' not in result:
        api = 0
    else:
        api = result['api_version']
    node.setVersions(easyxdm, api_min, api)
    node.initialize()

def search(domainlist, dpattern=None, hpattern=None, spattern=None, mpattern=None):
    returnList = {}
    if not dpattern:
        dpattern= "" 
    if not hpattern:
        hpattern= "" 
    if not spattern:
        spattern= "" 
    if not mpattern:
        mpattern= "" 
    dpat = re.compile(dpattern, re.I)

    for key in node_list:
        hList = {}
        if dpat.search(key):
            hList = node_list[key].searchChildren(hpattern)
        for i,j in hList.items():
            sList = j.searchChildren(spattern)
            for a,b in sList.items():
                mList = b.searchChildren(mpattern)
                if len(mList):
                    #found something to return
                    # find if the node exists in return list
                    node = returnList.get(key, None)
                    if not node:
                        node = {}
                        returnList[key] = node
                    # get the host from this list
                    host = node.get(i, None)
                    if not host:
                        host = {}
                        node[i] = host
                    # get the service from this list 
                    service = host.get(a, None)
                    if not service:
                        service = {}
                        host[a] = service
                    for x,y in mList.items():
                        service[x] = y
    return returnList

def errInfo(reason):
    log.error(reason)
    
for section in cfg_sections:
    if section[:14] == 'opsview_server':
        server_name = utils.config.get(section, "name")
        server_host = utils.config.get(section, "host")
        server_login = utils.config.get(section, "login")
        server_password = utils.config.get(section, "password")
        server_tkt_shared = utils.config.get(section, "shared_secret")
        server_api_tool = utils.config.get(section, "api_tool")
        server_rescan = utils.config.get(section, "rescan")
        node = Domain(server_name, server_host, server_login, server_password, server_tkt_shared, server_api_tool, server_rescan)
        node_list[server_name] = node
        node_uri = node_list[server_name].getUri()
        node_versions = rest_api.getInfo(node_uri, 'rest')
        node_versions.addCallback(saveVersionInfo, node=node).addErrback(errInfo)
        node = None
