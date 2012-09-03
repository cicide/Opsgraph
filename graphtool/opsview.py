#!/usr/bin/python

from twisted.names import client as dns_client
from twisted.web import client as web_client
from twisted.internet import defer, reactor
from paste.auth import auth_tkt
from bisect import bisect

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
loginTimeout = 10  # how long should we wait for a login attempt to succeed
maxLoginTimeout = 300 # what is the absolutely longest period we should wait?
dataTimeout = 20
cacheDict = {} # dictionary of cache objects name: object
cacheLife = 28800 # dump any cache that hasn't been used in 8 hours
cacheLatency = 300 # don't fetch new data if newest data in cache is less than 5 mins old

class TimelineCache(object):
    
    """ General data cache.  Cache is referenced by name and contains x,y data sets in a dictionary"""
    
    def __init__(self, name, normalize=False):
        self.name = name
        self.data = {}
        self.newData = {}   # consists of a timestamp key and a x, y value dictionary of data added
        self.defaultNormalize = normalize # a value in seconds
        self.normalizedData = {} # dictionary storing normalized
        if self.defaultNormalize:
            self.normalizedData[self.defaultNormalize] = {}
        self.label = None
        self.uom = None
        self.createTime = self.usageTime = int(time.time())
    
    def _expire(self):
        self._ackTouch()
        self.data = {}
        self.label = self.uom = None
        self.normalizedData = {}
        
    def _ackTouch(self):
        self.usageTime = int(time.time())
    
    def _normalizeData(self, dataSet, roundBase=0):
        maxX = maxY = minX = minY = 0 
        normalizeData = {}
        for x in dataSet:
            y = dataSet[x]
            if str(y) == '':
                y = None # 
            if roundBase:
                # round all x values to the nearest roundBase
                x = int(roundBase * round(float(x)/roundBase))
            else:
                x = int(x)
            if x < minX: minX = x
            if x > maxX: maxX = x
            if y:
                y = float(y)
                if y < minY: minY = y
                if y > maxY: maxY = y
            else:
                y = '' #this allows fusion and high charts to recognize this as missing data
            normalizeData[x] = y
        return normalizeData
    
    def getCacheTimeValueRange(self):
        self._ackTouch()
        if len(self.data):
            return int(min(self.data.keys())),int(max(self.data.keys()))
        else:
            return 0,0
        
    def addData(self, label, uom, data):
        self._ackTouch()
        newDataTime = int(time.time())
        if not data:
            log.error('cache add with no supplied data')
        else:
            flushBeforeAdd = False
            if self.label:
                if self.label != label:
                    log.warning('previous label %s does not match new label: %s, flushing old data' % (self.label, label))
                    flushBeforeAdd = True
                    self.label = label
            else:
                self.label = label
            if self.uom:
                if self.uom != uom:
                    log.warning('previous uom %s does not match new uom: %s, flushing old data' % (self.uom, uom))
                    flushBeforeAdd = True
                    self.uom = uom
            else:
                self.uom = uom
            # If the supplied data had a different uom or label, then we need to flush the old 
            # data which is most likely invalid
            if flushBeforeAdd:
                self.data = {}
                if len(self.normalizedData):
                    for normalize in self.normalizedData:
                        self.normalizedData[normalize] = {}
            # if the data is handed to us as a list, then convert it to a dict
            if type(data) == list:
                data = {a: b for a,b in data}
            # remove any trailing data with no y value
            tv = data.keys()
            tv.sort()
            while len(data):
                timeVal = tv[len(data)-1]
                if data[timeVal] in (None, ''):
                    log.debug('removing a null value from the end of the data for %s' % timeVal)
                    data.pop(timeVal)
                else:
                    log.debug('done trimming null values')
                    break
            # the new data with the same x values should have identical y values.
            # we should validate the new data and throw an error if it doesn't match
            valListNew = set(data.keys())
            valListOld = self.data.keys()
            valCheckList = valListNew.intersection(valListOld)
            invalidData = []
            for value in valCheckList:
                if data[value] != self.data[value]:
                    invalidData.append(value)
            if len(invalidData):
                log.error('Invalid data detected in %i of %i matching records' % (len(invalidData), len(valCheckList)))
            # get the time values from the supplied data that are not currently in the cache
            addList = list(set(data.keys())-set(self.data.keys()))
            if len(invalidData):
                pass
            elif addList:
                self.newData[newDataTime] = {}
                for tv in addList:
                    self.data[tv] = self.newData[newDataTime][tv] = data[tv]
                log.debug('added %i items to cache' % len(addList))
            else:
                log.debug('cache already has all supplied data')
            if len(self.normalizedData):
                # we have normalized data in the cache, add newly supplied data for normalization
                for normalizeValue in self.normalizedData.keys():
                    addList = list(set(data.keys()) - set(self.normalizedData[normalizeValue]))
                    if len(addList) == len(data):
                        normData = self._normalizeData(data, normalizeValue)
                    else:
                        preNorm = {}
                        for tv in addList:
                            preNorm[tv] = data[tv]
                        normData = self._normalizeData(preNorm, normalizeValue)
                    self.normalizedData[normalizeValue].update(normData)

    def getData(self, start, end, normalize=None):
        self._ackTouch()
        if normalize:
            # if normalized data is requested, return the normalized data
            if normalize in self.normalizedData:
                dataSet = self.normalizedData[normalize]
            elif len(self.data):
                # the normalize value requested isn't calculated, so we must calculate it
                #dataSet = self.normalizedData[normalize] = self._normalizeData(self.data, roundBase=normalize)
                dataSet = self._normalizeData(self.data, roundBase=normalize)
                self.normalizedData[normalize] = dataSet
            else:
                dataSet = None
        elif len(self.data):
            dataSet = self.data
        else:
            dataSet = None
        if not dataSet:
            return {'list': [{'label': self.label, 'uom': self.uom, 'cacheData': {}}]}
        else:
            dataRange = dataSet.keys()
            dataRange.sort()
            # we now have a sorted list of all the x values in the cached data
            # use bisect to get a set that contains only the requested range
            # bisect doesn't include exactly matched values, so make our bisect values 1 larger/smaller
            bStart = int(start) - 1
            bEnd = int(end) + 1
            rangeStart = bisect(dataRange, bStart)
            rangeEnd = bisect(dataRange, bEnd)
            reqRange = dataRange[rangeStart:rangeEnd]
            returnSet = {}
            returnData = {str(key): dataSet[key] for key in reqRange}
            returnSet['cacheData'] = returnData
            returnSet['label'] = self.label
            returnSet['uom'] = self.uom
            return {'list': [returnSet]}
            
    def isCached(self, start, end):
        # start time is the oldest time, and end is the youngest
        isInCache = True
        if len(self.data) == 0:
            return False, start, end
        timeValues = [int(i) for i in self.data.keys()]
        timeValues.sort()
        cacheLow = timeValues[0] - cacheLatency
        cacheHigh = timeValues[len(timeValues)-1] + cacheLatency
        #log.debug('checking cache values')
        #log.debug('requested start: %s' % start)
        #log.debug('cache start: %s' % timeValues[0])
        #log.debug('cache low w/latency: %s' % cacheLow)
        #log.debug('requested end: %s' % end)
        #log.debug('cache end: %s' % timeValues[len(timeValues)-1])
        #log.debug('cache high w/latency: %s' % cacheHigh)
        if start < cacheLow:
            log.debug('end falls outside of cache')
            # requesting data earlier than cacheStart
            fetchEnd = end
            isInCache = False
        else:
            # end is within cache limits
            log.debug('end within cache range')
            fetchEnd = cacheHigh + 1
        if end > cacheHigh:
            log.debug('start outside of cache range')
            # request data later than cacheStart
            fetchStart = start
            isInCache = False
        else:
            log.debug('start inside of cache range')
            fetchStart = start
        return isInCache, fetchStart, fetchEnd

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

    def getParent(self):
        return self.parent
    
    def getName(self):
        return self.name
    
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
        self.name = name
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
        self.eventList = {}
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
        
    def onErr(self, reason, timeout=None):
        log.debug("opsview: onErr() called")
        log.error(reason)
        if reason and type(reason) != type(bool()):
            de = reason.trap(defer.CancelledError)
            if de == defer.CancelledError:
                log.debug("Cancelled request error. Need to schedule rescan")
                if not timeout:
                    newTimeout = loginTimeout
                    scan_retry = 60
                    scan_check = scan_retry * 2
                    log.debug("no data on timeout attempted received, using default of %s" % loginTimeout)
                else:
                    newTimeout = timeout
                    if newTimeout > 60:
                        scan_retry = 60
                    else:
                        scan_retry = timeout
                    scan_check = scan_retry * 2
                    log.debug("retrying initialize after failure with %s timeout" % newTimeout)
                if self.rescan_sched:
                    if (self.rescan_sched - int(time.time())) > scan_check:
                        log.debug('cancelled error, scheduling a rescan in %i seconds' % scan_retry)
                        reactor.callLater(scan_retry, self.initialize, None, newTimeout)
                        self.rescan_sched = int(time.time()) + scan_retry
                    else:
                        log.debug('cancelled error, rescan already scheduled within the next %i seconds' % scan_check)
                else:
                    log.debug('cancelled error, scheduling a Fresh rescan for in %i seconds' % scan_retry)
                    reactor.callLater(scan_retry, self.initialize, None, newTimeout)
                    self.rescan_sched = int(time.time()) + scan_retry
        
    def onInitErr(self, reason, attemptedTimeout=None):
        log.error(reason)
        if reason.getErrorMessage() == '401 Unauthorized':
            # Re login to opsview server
            log.debug("Relogging in into opsview server")
            self.masterLoginToken = None
            log.debug('OnInitErr: Scheduling a rescan for ten seconds')
            reactor.callLater(10, self.initialize)
            self.rescan_sched = int(time.time()) + 10
            #return False
        else:
            #log.debug('Node INIT Error Reason: %s') % reason.getErrorMessage()
            reactor.callLater(3, self.initialize, None, attemptedTimeout)
            log.debug('OnInitErr: Scheduling a rescan for three seconds')
            self.rescan_sched = int(time.time()) + 3

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
    
    def initialize(self, result=None, lastTimeout=None):
        self.rescan_sched = 0
        if lastTimeout:
            newTimeout = lastTimeout * 2
            if newTimeout > maxLoginTimeout:
                newTimeout = maxLoginTimeout
        else:
            newTimeout = loginTimeout
        # if we don't have a token, we need to get one
        if not self.masterLoginToken:
            log.info('Initializing opsview node %s' % self.name)
            d = self.loginMaster()
            return d.addCallback(self.initialize).addErrback(self.onInitErr, newTimeout)
        else:
            self.creds = {'X-Opsview-Username': self.login, 'X-Opsview-Token': self.masterLoginToken}
            d = rest_api.getInfo(self.uri, 'rest/status/service', headers=self.creds, timeout=newTimeout)
            return d.addCallback(self.addServices, newTimeout).addErrback(self.onInitErr, newTimeout)
            
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
                    metricUniqueId = 'opsview::%s::%s' % (self.name, row)
                    if( service and metric):
                        host = self.getHostByName(str(host))
                        if host:
                            host.addServiceMetric(service, metric, metricUniqueId)
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
            
    def addServices(self, result=None, curTimeout=None):
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
            perfmetrics.addCallback(self.saveMetricData).addErrback(self.onErr, curTimeout)
            return perfmetrics
                
    def getName(self):
        return self.name
    
    def getUri(self):
        return self.uri
    
    def getApi(self):
        return api_tool
    
    def getMaxCacheTimeValue(self, host, service, metric):
        m_host = self.getChild(host)
        if m_host:
            m_service = m_host.getChild(service)
            if m_service:
                m_metric = m_service.getChild(metric)
                if m_metric:
                    result = m_metric.getMaxCacheTimeValue()
                    log.debug('got max cache value of %s' % result)
                    return result
                else:
                    return None
            else:
                return None
        else:
            return None
        
    def fetchData(self, api_uri, end_time, creds={}, cookies={}, hsm=None, durSet=(), timeout=dataTimeout, endTime=None, startTime=None, returnData=True, skipODW=False, retry=0, dataSubscriber=None):
        log.debug('node data fetch request with timeout of %s' % timeout)
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
                        log.debug('start Time: %s' % startTime)
                        log.debug('end Time: %s' % endTime)
                        result =  m_metric.getData(self.uri, self.api_tool, api_uri, end_time, durSet, headers=creds, cookies=cookies, timeout=timeout, end=endTime, start=startTime, returnData=returnData, skipODW=skipODW, retry=retry, dataSubscriber=dataSubscriber)
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
        
    def addServiceMetric(self, serviceName, metric=None, metricUniqueId=None):
        #log.debug('Adding service metric %s::%s to host %s' % (str(service), str(metric), self.name))
        serviceName = str(serviceName)
        service = self.getServiceByName(serviceName)
        if metric:
            metric = str(metric)
            if service:
                met = Metric(metric, metricUniqueId)
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
    def __init__(self, name, uniqueId):
        Node.__init__(self, name, "Metric")
        #self.dataCache = {}
        self.uniqueId = uniqueId
        if self.uniqueId in cacheDict:
            self.dataCache = cacheDict[self.uniqueId]
        else:
            self.dataCache = cacheDict[self.uniqueId] = TimelineCache(uniqueId)
        self.touched = int(time.time())
        self.cacheLastHit = 0
        self.cacheExpire = None
        self.live = None
        
    def getMaxCacheTimeValue(self):
        minValue,maxValue = self.dataCache.getCacheTimeValueRange()
        return maxValue

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
                dataUom = resultSet['uom']
                dataLabel = resultSet['label']
                self.dataCache.addData(dataLabel, dataUom, dataSet)
                if returnData:
                    log.debug('returning cached data')
                    return self.dataCache.getData(start, end, timeRoundBase)
                else:
                    log.debug('not returning any data')
                    return False

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
        log.debug('calculating start and end time from end_time and duration.')
        log.debug(end_time)
        log.debug(durSet)
        log.debug('calculated start: %s, calculated end: %s' % (start,end))
        return start, end


            
    def _fetchRestData(self, uri, api_tool, h_s_m, headers, cookies, timeout, reqStart, reqEnd, retry=0, returnData=True, missStart=None, missEnd=None):
        def onSuccess(result, reqStart, reqEnd):
            #we got back a result from our data fetch request - add it to our cache and set our timestamp
            #return the result to the calling function
            log.debug('got metric api request back')
            return self._cacheAndReturnData(result, reqStart, reqEnd, returnData)
        def onFailure(result, uri=None, api_tool=None, headers=None, cookies=None, reqStart=None, reqEnd=None, timeout=dataTimeout, retry=0, returnData=True, missStart=None, missEnd=None):
            #trap possible errors here
            l = result.trap(rest_api.ApiError, defer.CancelledError)
            if l == rest_api.ApiError:
                retry += 1
                if uri:
                    if retry < 3:
                        log.debug('got api error, retrying')
                        return self.fetchRestData(uri, api_tool, headers, cookies, reqStart, reqEnd, timeout, retry=retry, returnData=returnData, missStart=missStart, missEnd=missEnd)
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
        if missStart is not None:
            fetchStart = missStart
        else:
            fetchStart = reqStart
        if missEnd is not None:
            fetchEnd = missEnd
        else:
            fetchEnd = reqEnd
        url = '%s?hsm=%s&start=%s&end=%s' % (api_tool, urllib.quote_plus(h_s_m), fetchStart, fetchEnd)
        log.debug('requesting %s from %s' % (url, uri))        
        d = rest_api.getInfo(uri, str(url), headers=headers, cookies=cookies, timeout=timeout)
        d.addCallback(onSuccess, reqStart, reqEnd).addErrback(onFailure, uri, api_tool, headers, cookies, reqStart, reqEnd, timeout, retry=retry, returnData=returnData, missStart=missStart, missEnd=missEnd)
        return d
    
    def _fetchOdwData(self, odwHost, odwDb, odwUser, odwPass, hsm, reqStart, reqEnd, uri=None, api_tool=None, headers=None, cookies=None, timeout=None, retry=0, returnData=True, missStart=None, missEnd=None):
        def onSuccess(result, reqStart, reqEnd, hsm):
            log.debug('got metric odw request back')
            metricResult = result[0]
            unitResult = result[1][0]
            if len(result):
                log.debug('got result of length: %s' % len(result))
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
                return self._cacheAndReturnData(dataSet, reqStart, reqEnd, returnData)
            else:
                log.debug('failed to retreive odw data')
                if not uri:
                    log.debug('missing uri, unable to fall back to rest request')
                    return None
                else:
                    log.debug('falling back to rest request')
                    return self._fetchRestData(uri, api_tool, hsm, headers, cookies, timeout, reqStart, reqEnd, retry=retry, returnData=returnData, missStart=missStart, missEnd=missEnd)
        def onFailure(reason):
            log.debug('got db error: %s' % reason)
            if not uri:
                log.debug('missing uri, unable to fall back to rest request')
                return reason
            else:
                log.debug('falling back to rest request')
                #return self._fetchRestData(uri, api_tool, hsm, headers, cookies, timeout, reqStart, reqEnd, retry=retry, returnData=returnData, missStart=missStart, missEnd=missEnd)
        host, service, metric = hsm.split('::')
        if missStart is not None:
            fetchStart = missStart
        else:
            fetchStart = reqStart
        if missEnd is not None:
            fetchEnd = missEnd
        else:
            fetchEnd = reqEnd
        if int(time.time() - fetchEnd) < 1000:
            if uri:
                tmpReqStart = int(time.time() - 1200)
                tmpReqEnd = int(time.time())
                #log.debug('getting lastest 15 minutes of data via rest api')
                #tmp = self._fetchRestData(uri, api_tool, hsm, headers, cookies, timeout, tmpReqStart, tmpReqEnd, retry, False)
        d = txdbinterface.loadOdwData(odwHost, odwDb, odwUser, odwPass, host, service, metric, fetchStart, fetchEnd)
        d.addCallback(onSuccess, reqStart, reqEnd, hsm).addErrback(onFailure)
        return d
    
    def _getLiveData(self, uri, api_tool, h_s_m, end_time, durSet, headers, cookies, timeout):
        self.live = self.reactor.callLater(cacheLatency, self._getLiveData, uri, api_tool, h_s_m, int(time.time()), ('-', 1, 'h'), headers, cookies, timeout)
        return self.getData(uri, api_tool, h_s_m, end_time, durSet, headers, cookies, timeout)
    
    def getData(self, uri, api_tool, h_s_m, end_time, durSet, headers, cookies, timeout, returnData=True, skipODW=False, retry=0, start=None, end=None, dataSubscriber=None):
        def onErr(reason):
            log.debug('opsview::Metric::getData got error: %s' % reason)
        log.debug('get maybe cached data called with timeout of %s' % timeout)
        if (start and end):
            reqStart = start
            reqEnd = end
        else:
            reqStart, reqEnd = self._calcBeginEnd(end_time, durSet)
        # check to see if the cache contains all the data we need
        isCached, missStart, missEnd = self.dataCache.isCached(reqStart, reqEnd)
        if isCached:
            return self.dataCache.getData(reqStart, reqEnd, normalize=timeRoundBase)
        else:
            # figure out source of data
            if skipODW:
                dbi = False
            else:
                dbi = self.parent.parent.parent.getOdw()
            if dbi:
                odwHost, odwDb, odwUser, odwPass = dbi
                hasOdw = True
            else:
                hasOdw = False
            if hasOdw:
                log.debug('fetching missing data from ODW')
                #d = self._fetchOdwData(odwHost, odwDb, odwUser, odwPass, h_s_m, reqStart, reqEnd, uri, api_tool, headers, cookies, timeout, retry=retry, returnData=returnData, missStart=missStart, missEnd=missEnd)
                #return d
                # queue up an odw request, but don't wait on it
                d = self._fetchOdwData(odwHost, odwDb, odwUser, odwPass, h_s_m, reqStart, reqEnd, uri, api_tool, headers, cookies, timeout, retry=retry, returnData=True, missStart=missStart, missEnd=missEnd)
                if dataSubscriber:
                    d.addCallback(dataSubscriber.cacheAddNotify).addErrback(onErr)
            #else:
                #log.debug('fetching missing data from API')
                #return self._fetchRestData(uri, api_tool, h_s_m, headers, cookies, timeout, reqStart, reqEnd, retry=retry, returnData=returnData, missStart=missStart, missEnd=missEnd)
            return self._fetchRestData(uri, api_tool, h_s_m, headers, cookies, timeout, reqStart, reqEnd, retry=retry, returnData=returnData, missStart=missStart, missEnd=missEnd)

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
        try:
            server_tkt_shared = utils.config.get(section, "shared_secret")
        except:
            server_tkt_shared = None
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
