#!/usr/bin/python

from twisted.names import client as dns_client
from twisted.web import client as web_client
from twisted.internet import defer, reactor
from paste.auth import auth_tkt

import json, time, datetime, urllib, exceptions
import utils, rest_api, txdbinterface
import re, copy

log = utils.get_logger("NodeService")
cfg_sections = utils.config.sections()

graph_duration = '%s%s' % (utils.config.get('graph', 'duration_length'), utils.config.get('graph', 'duration_unit'))
local_ip = utils.config.get('general', 'local_ip')
event_full_load_period = int(utils.config.get('events', 'full_load_period'))
event_inc_load_period = int(utils.config.get('events', 'incremental_load_period'))
timeRoundBase = int(utils.config.get('graph', 'round_time'))

node_list = {}
event_type_list = ['outage', 'event']
loginTimeout = 10
dataTimeout = 20
cacheLife = 3600 # dump any cache that hasn't been used in 60 mins
cacheLatency = 300 # don't fetch new data if newest data in cache is less than 5 mins old

class OdwError(exceptions.Exception):
    """ Error received while attempting fetch ODW Data """
    def __repr__(self):
        return 'OdwError'
    
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
    
    def getChild(self, child):
        if child in self.children:
            return self.children[child]
        else:
            return False

class Domain(Node):
    
    def __init__(self, name, host, login, passwd, shared_secret, api_tool, rescan, odwHost, odwDb, odwUser, odwPass):
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
        self.rescan_sched = 0
        self.odwHost = odwHost
        self.odwDb = odwDb
        self.odwUser = odwUser
        self.odwPass = odwPass
        self.loadEvents()
        
    def getOdw(self):
        if self.odwHost:
            return (self.odwHost, self.odwDb, self.odwUser, self.odwPass)
        else:
            return None
        
    def loadEvents(self):
        def onTypeSuccess(result):
            log.debug('Got Event Types result for Node %s: ' % self.name)
            log.debug(result)
            self.event_type_list = []
            if result and type(result) != type(bool()):            
                for item in result:
                    if item[0] not in event_type_list:
                        event_type_list.append(item[0])
                    self.event_type_list.append(item[0])
            else:
                log.debug("onTypeSuccess: Got no event types")
  
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
            #log.debug(result)
            #schedule the next full event load for the event timeout
            log.debug("scheduling an event rescan for %s in %i seconds" % (self.host, event_full_load_period))
            reactor.callLater(event_full_load_period, self.loadEvents)
        def onFailure(reason):
            log.error(reason)
        def onCompleteFailure(reason):
            # we got an error loading events, reschedule a new event load in one minute
            reactor.callLater(60, self.loadEvents)
        ds = []
        d1 = txdbinterface.getEventTypes()
        d1.addCallbacks(onTypeSuccess,onFailure)
        ds.append(d1)
        d2 = txdbinterface.getEventData(self.name)
        d2.addCallbacks(onEventsSuccess,onFailure)
        ds.append(d2)
        d = defer.DeferredList(ds, consumeErrors=False)
        d.addCallbacks(onCompleteSuccess,onCompleteFailure)
        
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
        log.error(reason)
        
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
        d = rest_api.postData(self.uri, 'rest/login', postData, timeout=loginTimeout)
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
            #d = web_client.getPage(self.uri, headers, method='GET', cookies=cj)
            d = rest_api.getInfo(self.uri, '', headers, cookies=cj, timeout=loginTimeout)
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
            l = reason.trap(rest_api.LoginError)
            if l == rest_api.LoginError:
                pass
            else:
                log.error(reason)
            return False
        cj = {}
        cj['auth_tkt'] = self._makeTicket(userid=username, remote_addr=local_ip)
        postData = {'username': username, 'password': password}
        d = rest_api.postData(self.uri, 'rest/login', postData, headers={}, cookies=cj, timeout=loginTimeout)
        d.addCallbacks(onSuccess,onFail)
        return d
    
    def initialize(self, result=None):
        self.rescan_sched = 0
        # if we don't have a token, we need to get one
        if not self.masterLoginToken:
            log.info('Initializing opsview node %s' % self.name)
            d = self.loginMaster()
            return d.addCallback(self.initialize).addErrback(self.onErr)
        else:
            self.creds = {'X-Opsview-Username': self.login, 'X-Opsview-Token': self.masterLoginToken}
            d = rest_api.getInfo(self.uri, 'rest/status/service', headers=self.creds, timeout=loginTimeout)
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
                #schedule a rescan based on the rescan timer
                if not self.rescan_sched:
                    log.debug('scheduling a node rescan in %i seconds' % self.rescan)
                    reactor.callLater(self.rescan, self.initialize)
                    self.rescan_sched = int(time.time()) + self.rescan
                else:
                    log.debug('a rescan is already scheduled for this node in %i seconds' % rescan_time)
                    rescan_time = self.rescan_sched - int(time.time())
                return True
            else:
                if self.rescan_sched:
                    if (self.rescan_sched - int(time.time())) > 120:
                        log.debug('initialize failed, scheduling a rescan for in one minute')
                        reactor.callLater(60, self.initialize)
                        self.rescan_sched = int(time.time()) + 60
                    else:
                        log.debug('initialize failed, rescan already scheduled within the next two minutes')
                return False
        else:
            log.debug('No result')
            if self.rescan_sched:
                if (self.rescan_sched - int(time.time())) > 120:
                    log.debug('initialize failed, scheduling a rescan for in one minute')
                    reactor.callLater(60, self.initialize)
                    self.rescan_sched = int(time.time()) + 60
                else:
                    log.debug('initialize failed, rescan already scheduled within the next two minutes')
            return False
            
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
            #remove the old children set
            log.debug("Reloading Domain %s" % self.host)
            self.initialized = False
            self.children = {}
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
            perfmetrics = rest_api.getInfo(self.uri, 'rest/runtime/performancemetric', headers=self.creds, timeout=dataTimeout)
            perfmetrics.addCallbacks(self.saveMetricData,self.onErr)
            return perfmetrics
                
    def getName(self):
        return self.name
    
    def getUri(self):
        return self.uri
    
    def getApi(self):
        return api_tool
    
    def fetchData(self, h_s_m, end_time=None, duration=None, creds={}, cookies={}, hsm=None, durSet=(), timeout=dataTimeout, retry=0):
        if not duration:
            duration = graph_duration
        if not end_time:
            end_time = int(time.time())
        if len(creds) == 0:
            creds = self.creds
        if hsm:
            host, service, metric = hsm
            m_host = self.getChild(host)
            if m_host:
                m_service = m_host.getChild(service)
                if m_service:
                    m_metric = m_service.getChild(metric)
                    if m_metric:
                        # the host, service, metric is valid, request the data
                        result =  m_metric.getData(self.uri, self.api_tool, h_s_m, end_time, durSet, headers=creds, cookies=cookies, timeout=timeout)
                        return result
                    else:
                        log.error('no valid metric found')
                        return None
                else:
                    log.error('no valid service found')
                    return None
            else:
                log.error('no valid host found')
                return None
        else:
            log.error('invalid hsm (no hsm) supplied')
            return None

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
        self.dataCache = {}
        self.touched = int(time.time())
        self.cacheLastHit = 0
        self.cacheExpire = None
        self.live = None
        
    def _ackCacheHit(self):
        """ called whenever we need to mark the cache as freshened """
        self.cacheLastHit = int(time.time())
        if self.cacheExpire:
            self.cacheExpire.cancel()
        self.cacheExpire = reactor.callLater(cacheLife, self._expireCache)

    def _expireCache(self):
        log.debug('cache has expired for metric')
        self.cacheExpire = self.dataCache = None
        
    def _cacheAndReturnData(self, data, start, end, returnData=True):
        """ add fetched data to cache """
        if not data:
            log.debug('No data to add to cache')
            return {}
        if 'list' not in data:
            log.debug('unknown data set, not caching')
            return {}
        elif not data['list']:
            log.debug('no values in data set, not caching')
            return {}
        else:
            resultSet = data['list'][0]
            if 'data' not in resultSet:
                log.debug('no data in the result set, not caching')
                return {}
            else:
                log.debug('adding data to cache')
                dataSet = resultSet['data']
                description = resultSet['description']
                log.debug('description: %s' % description)
                #dataMin = description['Min']
                #dataMax = description['Max']
                #dataAvg = description['Average']
                dataUom = resultSet['uom']
                dataLabel = resultSet['label']
                
                if self.dataCache == None:
                    self.dataCache = {}

                if not 'data' in self.dataCache:
                    self.dataCache['data'] = self._normalizeData(dataSet, timeRoundBase)
                    self.dataCache['label'] = dataLabel
                    self.dataCache['uom'] = dataUom
                else:
                    newData = self._normalizeData(dataSet, timeRoundBase)
                    self.dataCache['data'].update(newData)
                if returnData:
                    return self._getCachedData(start, end)
                else:
                    return False

    def _normalizeData(self, dataSet, roundBase):
        #convert x,y pairs in the dataSet into a dictionary
        minX = maxX = minY = maxY = 0        
        normalizedData = {}
        for x,y in dataSet:
            if str(y) == '':
                y = None # this is not correct, need to check fusionchart/highcharts how to handle this
            if timeRoundBase:
                # round all x values to the nearest timeRoundBase (from round_time value in the config file)
                x = int(timeRoundBase * round(float(x)/timeRoundBase))
            else:
                x = int(x)
                if x < minX: minX = x
                if x > maxX: maxX = x
            if y:
                y = float(y)
                if y < minY: minY = y
                if y > maxY: maxY = y
            else:
                y = '' # this allows fusioncharts and highcharts to recognize this is missing data
            normalizedData[x] = y
        return normalizedData
    
    def _getCachedData(self, start, end):
        log.debug('returning cached data')
        if not self.dataCache:
            return {}
        data = self.dataCache['data']
        dataRange = data.keys()
        dataRange.sort()
        # we now have a sorted list of all the x values in the cached data
        # use bisect to get a set that contains only the requested range
        # bisect doesn't include exactly matched values, so make our bisect values 1 larger/smaller
        bStart = int(start) - 1
        bEnd = int(end) + 1
        from bisect import bisect
        rangeStart = bisect(dataRange, bStart)
        rangeEnd = bisect(dataRange, bEnd)
        # build the requested data object
        reqRange = dataRange[rangeStart:rangeEnd]
        returnSet = {}
        # we were returning a list that we then turned back into a dict, return a dict instead
        #dataSet = []
        #for valX in reqRange:
        #    dataSet.append([valX, data[valX]])
        #returnSet['data'] = dataSet
        dataSet = {str(key): data[key] for key in reqRange}
        returnSet['cacheData'] = dataSet
        returnSet['label'] = self.dataCache['label']
        returnSet['uom'] = self.dataCache['uom']
        log.debug('returning cached data with %s records' % len(dataSet))
        return {'list': [returnSet]}

    def _calcBeginEnd(self, end_time, durSet):
        """ return min and max x for requested time period"""
        durMod = durSet[0]
        durLen = durSet[1]
        durUnit = durSet[2]
        if durUnit in ('y', 'Y'):
            durUval = 365.25 * 24 * 60 * 60
        elif durUnit in ('m', 'M'):
            durUval = 30.4375 * 24 * 60 * 60
        elif durUnit in ('w', 'W'):
            durUval = 7 * 24 * 60 * 60
        elif durUnit in ('d', 'D'):
            durUval = 24 * 60 * 60
        elif durUnit in ('h', 'H'):
            durUval = 60 * 60
        else:
            durUval = 60 * 60
        if durMod == '+':
            start = end_time
            end = start + int(durLen) * durUval
        else:
            end = end_time
            start = end_time - int(durLen) * durUval
        return start, end


            
    def _fetchRestData(self, uri, api_tool, h_s_m, headers, cookies, timeout, reqStart, reqEnd, retry=0, returnData=True):
        def onSuccess(result, reqStart, reqEnd):
            #we got back a result from our data fetch request - add it to our cache and set our timestamp
            #return the result to the calling function
            log.debug('got metric api request back')
            return self._cacheAndReturnData(result, reqStart, reqEnd, returnData)
        def onFailure(result, uri=None, api_tool=None, headers=None, cookies=None, reqStart=None, reqEnd=None, timeout=dataTimeout, retry=0):
            #trap possible errors here
            l = result.trap(rest_api.ApiError, defer.CancelledError)
            if l == rest_api.ApiError:
                retry += 1
                if uri:
                    if retry < 3:
                        log.debug('got api error, retrying')
                        return self.fetchRestData(uri, api_tool, headers, cookies, reqStart, reqEnd, timeout, retry)
                    else:
                        log.debug('too many retries')
                        return result
                else:
                    log.debug ('missing uri')
                    return result
            elif l == defer.CancelledError:
                log.debug('got timeout error')
                return result
            else:
                log.debug('got error: %s' % result)
                return result
        #url = '%s?hsm=%s&end=%s&duration=%s' % (api_tool, urllib.quote_plus(uri), end_time, duration)
        url = '%s?hsm=%s&start=%s&end=%s' % (api_tool, urllib.quote_plus(h_s_m), reqStart, reqEnd)
        log.debug('requesting %s from %s' % (url, uri))        
        d = rest_api.getInfo(uri, str(url), headers=headers, cookies=cookies, timeout=timeout)
        d.addCallback(onSuccess, reqStart, reqEnd).addErrback(onFailure, uri, api_tool, headers, cookies, reqStart, reqEnd, timeout, retry)
        return d
    
    def _fetchOdwData(self, odwHost, odwDb, odwUser, odwPass, hsm, reqStart, reqEnd, uri=None, api_tool=None, headers=None, cookies=None, timeout=None, retry=0):
        def onSuccess(result, reqStart, reqEnd, hsm):
            log.debug('got metric odw request back')
            metricResult = result[0]
            unitResult = result[1][0]
            if len(result):
                log.debug('got result of lenght: %s' % len(result))
                uom = unitResult
                label = hsm
                dataSet = {}
                dataSet['list'] =[]
                data = {}
                data['data'] = metricResult
                data['uom'] = uom
                data['label'] = label
                data['description'] = None
                dataSet['list'].append(data)
                return self._cacheAndReturnData(dataSet, reqStart, reqEnd)
            else:
                log.debug('failed to retreive odw data')
                if not uri:
                    log.debug('missing uri, unable to fall back to rest request')
                    return None
                else:
                    log.debug('falling back to rest request')
                    return self._fetchRestData(uri, api_tool, hsm, headers, cookies, timeout, reqStart, reqEnd, retry)
        def onFailure(reason):
            #log.error("KEV: opsview: _fetchOdwData: onFailure: reason = %s"%str(reason))
            log.debug('got db error')
            if not uri:
                log.debug('missing uri, unable to fall back to rest request')
                return reason
            else:
                log.debug('falling back to rest request')
                return self._fetchRestData(uri, api_tool, hsm, headers, cookies, timeout, reqStart, reqEnd, retry)
        host, service, metric = hsm.split('::')
        if int(time.time() - reqEnd) < 1000:
            if uri:
                tmpReqStart = int(time.time() - 1200)
                tmpReqEnd = int(time.time())
                log.debug('getting lastest 15 minutes of data via rest api')
                tmp = self._fetchRestData(uri, api_tool, hsm, headers, cookies, timeout, tmpReqStart, tmpReqEnd, retry, False)
        d = txdbinterface.loadOdwData(odwHost, odwDb, odwUser, odwPass, host, service, metric, reqStart, reqEnd)
        d.addCallback(onSuccess, reqStart, reqEnd, hsm).addErrback(onFailure)
        return d
    
    def _getLiveData(self, uri, api_tool, h_s_m, end_time, durSet, headers, cookies, timeout):
        self.live = self.reactor.callLater(cacheLatency, self._getLiveData, uri, api_tool, h_s_m, int(time.time()), ('-', 1, 'h'), headers, cookies, timeout)
        return self.getData(uri, api_tool, h_s_m, end_time, durSet, headers, cookies, timeout)
    
    def getData(self, uri, api_tool, h_s_m, end_time, durSet, headers, cookies, timeout, retry=0, start=None, end=None):
        log.debug('get maybe cached data called')
        if (start and end):
            reqStart = start
            reqEnd = end
        else:
            reqStart, reqEnd = self._calcBeginEnd(end_time, durSet)
        # check to see if the cache contains all the data we need
        if (self.dataCache == None) or ('data' not in self.dataCache):
            # nothing in the cache!
            log.debug('cache is empty')
            cacheResult = None
        else:
            log.debug('checking cache contents ')
            dataKeys = self.dataCache['data'].keys()
            dataKeys.sort()
            from bisect import bisect
            inStart = bisect(dataKeys, reqStart+cacheLatency)
            inEnd = bisect(dataKeys, reqEnd-cacheLatency)
            log.debug('inStart: %i' % inStart)
            log.debug('inEnd: %i' % inEnd)
            if (inStart and inEnd < len(dataKeys)):
                #we have a valid cache hit
                log.debug('valid full cache hit')
                cacheResult = self._getCachedData(reqStart, reqEnd)
            else:
                maxX = dataKeys[-1]
                minX = dataKeys[0]
                log.debug('cache does not cover request range')
                log.debug('requested start %i is %i less than cache min %i' % (reqStart, minX-reqStart, minX))
                log.debug('request end %i is %i more than cache max %i' % (reqEnd, reqEnd-maxX, maxX))
                cacheResult = None
                # we don't have a valid cache hit
        if cacheResult:
            log.debug('returning cached data')
            self._ackCacheHit()
            return cacheResult
        else:
            # figure out source of data
            dbi = self.parent.parent.parent.getOdw()
            if dbi:
                odwHost, odwDb, odwUser, odwPass = dbi
                #hasOdw = False # TODO: odw fetch code doesn't exist
                hasOdw = True
            else:
                hasOdw = False
            if hasOdw:
                log.debug('fetching data from ODW')
                d = self._fetchOdwData(odwHost, odwDb, odwUser, odwPass, h_s_m, reqStart, reqEnd, uri, api_tool, headers, cookies, timeout, retry=0)
                return d
            else:
                log.debug('fetching data from API')
                return self._fetchRestData(uri, api_tool, h_s_m, headers, cookies, timeout, reqStart, reqEnd, retry=0)
            

    def makeLive(self, uri, api_tool, h_s_m, headers, cookies, timeout):
        if self.live:
            self.live.cancel()
        if (self.dataCache == None) or ('data' not in self.dataCache):
            # we have no cache, grab the last two days of data and turn live on
            now = int(time.time())
            tmp = self.getData(uri, api_tool, h_s_m, now, ('-',2,'d'), headers, cookies, timeout)
        else:
            # we have cache data, find the last time entry and grab all data more recent than it
            data = self.dataCache.keys()
            data.sort()
            maxX = data[-1]
            now = int(time.time())
            if now - maxX > cacheLatency:
                # TODO: if we don't have odw, then we should grab api data in blocks that match rrd's resolution
                tmp = self.getData(uri, api_tool, h_s_m, now, ('-', 2, 'd'), headers, cookies, timeout, start=maxX, end=now)
        self.live = self.reactor.callLater(cacheLatency, self._getLiveData, uri, api_tool, h_s_m, int(time.time()), ('-', 1, 'h'), headers, cookies, timeout)
        
    def cancelLive(self):
        if self.live:
            self.live.cancel()
            
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
    for key in domainlist:
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
        try:
            odw_host = utils.config.get(section, "odw_host")
            odw_db = utils.config.get(section, "odw_db")
            odw_user = utils.config.get(section, "odw_user")
            odw_pass = utils.config.get(section, "odw_pass")
        except:
            odw_host = odw_db = odw_user = odw_pass = None
            log.info('Found no or invalid odw data for node %s' % server_name)
        node = Domain(server_name, server_host, server_login, server_password, server_tkt_shared, server_api_tool, server_rescan, odw_host, odw_db, odw_user, odw_pass)
        node_list[server_name] = node
        node_uri = node_list[server_name].getUri()
        node_versions = rest_api.getInfo(node_uri, 'rest', timeout=dataTimeout)
        node_versions.addCallback(saveVersionInfo, node=node).addErrback(errInfo)
        node = None
