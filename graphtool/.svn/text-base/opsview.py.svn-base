#!/usr/bin/python

from twisted.names import client as dns_client
from twisted.web import client as web_client
from twisted.internet import defer
from paste.auth import auth_tkt

import json, time, datetime, urllib
import utils, rest_api, txdbinterface

log = utils.get_logger("NodeService")
cfg_sections = utils.config.sections()

graph_duration = '%s%s' % (utils.config.get('graph', 'duration_length'), utils.config.get('graph', 'duration_unit'))
local_ip = utils.config.get('general', 'local_ip')
event_full_load_period = utils.config.get('events', 'full_load_period')
event_inc_load_period = utils.config.get('events', 'incremental_load_period')

node_list = {}
host_list = {}
metric_list = []
event_type_list = ['outage', 'event']

class opsview_node(object):
    
    def __init__(self, name, host, login, passwd, shared_secret, api_tool, rescan):
        self.name = name
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
        self.node_hosts = []
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
        
    def getHostList(self):
        tmp_list = []
        for host in self.node_hosts:
            if host_list[host].getMetricCount():
                tmp_list.append(host)
        return tmp_list
    
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
            
    def saveMetricData(self, result):
        if result:
            self.cred_time = int(time.time())
            if len(result):
                host_metric_list = result['list']
                log.debug('Metric list is %s records long' % len(host_metric_list))
                for row in host_metric_list:
                    metric_list.append(row)
                    host,service,metric = row.split('::')
                    host_list[str(host)].addServiceMetric(service, metric)
                    #log.debug('metrics: %i  - adding metric: %s' % (len(metric_list),row))
                log.info('Found %i graphable metrics for node %s' % (len(metric_list), self.name))
                log.info('Node initialization for node %s complete' % self.name)
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
                self.node_hosts.append(host_name)
                host_list[host_name] = host(host_alias,
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
                    svc_obj = service(svc_current_check_attempt,
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
                    host_list[host_name].addService(svc_name, svc_obj)
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

class host(object):
    
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
        self.alias = alias
        self.comments = comments
        self.current_check_attempt = current_check_attempt
        self.downtime = downtime
        self.icon = icon
        self.last_check = last_check
        self.max_check_attempts = max_check_attempts
        self.name = name
        self.num_interfaces = num_interfaces
        self.num_services = num_services
        self.output = output
        self.service_list = []
        self.service_metric = {}
        self.service_metric_count = {}
        self.metric_count = 0
        #log.debug('host %s added' % self.name)
        
    def addService(self, svc_name, svc_obj):
        self.service_list.append(svc_obj)
        perfdata = svc_obj.perfdata_available
        
    def addServiceMetric(self, service, metric=None):
        #log.debug('Adding service metric %s::%s to host %s' % (str(service), str(metric), self.name))
        service = str(service)
        if metric:
            metric = str(metric)
            self.metric_count += 1
            if service in self.service_metric:
                self.service_metric[service].append(metric)
                self.service_metric_count[service] += 1
            else:
                self.service_metric[service] = [metric]
                self.service_metric_count[service] = 1
        else:
            if service in self.service_metric:
                log.debug('adding a service metric that already exists')
            else:
                self.service_metric[service] = []
                self.service_metric_count[service] = 0
                
    def hasMetrics(self):
        return len(self.service_metric)
    
    def getMetricCount(self):
        return self.metric_count
    
    def getServiceList(self):
        log.debug('grabbing services from service dictionary: %s' % len(self.service_metric))
        service_list = []
        for service in self.service_metric.keys():
            if self.service_metric_count[service]:
                log.debug('appending %s to service list' % service)
                service_list.append(service)
            else:
                log.debug('service %s has no metrics - not appending to list' % service)
        return service_list
    
    def getMetricList(self, req_service):
        log.debug('grabbing metrics for service %s' % req_service)
        metric_list = []
        for metric in self.service_metric[req_service]:
            log.debug('appending %s to metric list' % metric)
            metric_list.append(metric)
        return metric_list
    
class service(object):
    
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
        self.current_check_attempt = current_check_attempt
        self.downtime = downtime
        self.last_check = last_check
        self.markdown = markdown
        self.max_check_attempts = max_check_attempts
        self.name = name
        self.output = output
        self.perfdata_available = perfdata_available
        self.service_object_id = service_object_id
        self.state = state
        self.state_type = state_type
        self.state_duration = state_duration
        self.unhandled = unhandled
        self.host = host
        
class metric(object):
    
    # we cache data for a metric here
    
    def __init__(self,
                 name):
        self.name = name
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
        node = opsview_node(server_name, server_host, server_login, server_password, server_tkt_shared, server_api_tool, server_rescan)
        node_list[server_name] = node
        node_uri = node_list[server_name].getUri()
        node_versions = rest_api.getInfo(node_uri, 'rest')
        node_versions.addCallback(saveVersionInfo, node=node).addErrback(errInfo)
        node = None
