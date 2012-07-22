#!/usr/bin/python

from twisted.internet import defer
from twisted.internet.task import LoopingCall
import json, time, datetime, re
import utils, opsview, txdbinterface, graph

log = utils.get_logger("SubscriberService")

date_format = utils.config.get('graph', 'date_format')
def_dur_len = utils.config.get('graph', 'duration_length')
def_dur_unit = utils.config.get('graph', 'duration_unit')

# the event display setting defines where the graphical display of an event occurs
# inclusive:
#   means the display will contain the start and end points of an event
#   which means the start time of the event will be set to the last data point before the start of the event
#   and the end time of the event will be set to the first data point after the end of the event
# exclusive:
#   means the display will not contain the start and end points of an event
#   which means the start time of the event will be set to the first data point after the start of the event
#   and the end time of the event will be set to the last data point before the end of the event

# if the subscriber doesn't do anything for x seconds, log them out
login_timeout = 600

# re-authenticate to opsview once an hour
reauth_timeout = 120

event_display = 'inclusive'
event_display_options = ['None', 'All', 'Events', 'Outages']
generalEventTypes = ['Outages', 'Events']
graph_engines = ['FusionCharts', 'HighCharts']
graph_types = {}
graph_types['FusionCharts'] = {'Zoom Chart': 'ZoomLine.swf',
                               'Column 2D': 'MSColumn2D.swf',
                               'Column 3D': 'MSColumn3D.swf',
                               'Line': 'MSLine.swf',
                               'Bar 2D': 'MSBar2D.swf',
                               'Bar 3D': 'MSBar3D.swf',
                               'Area 2D': 'MSArea.swf',
                               'Marimekko': 'Marimekko.swf'}
graph_types['HighCharts'] = {'Line': 'line',
                             'Spline': 'spline',
                             'Area': 'area',
                             'Area Spline': 'areaspline',
                             'Scatter': 'scatter'
                            }
graph_size = {}
graph_size['Small'] = ('600','400')
graph_size['Medium'] = ('800','600')
graph_size['Large'] = ('1000','800')
graph_size['Huge'] = ('1200','1000')
graph_privacy = {}
graph_privacy['Public'] = 0
graph_privacy['Private'] = 2

subscribers = {}

class subscriber(object):

    def __init__(self, username, password):
        self.username = username
        self.password = password
        self.auth_node_list = {}  # dictionary of node_name: [auth_token, cred_time]
        self.authed = False
        self.auth_count = 0
        self.auth_tkt = None
        self.web_session = None # this is the opsview web session, not the user's web session
        self.webSession = None # this is the users web session
        self.currentChart = None # describes a the current chart being edited 
        self.dbId = None
        self.chartList = []
        self.livePageList = []
        self._touchTime = int(time.time())
        self.timeoutChecker = LoopingCall(self._checkTimeout)
        self.timeoutChecker.start(5)
        d = txdbinterface.getUserData(self.username)
        d.addCallbacks(self.setDbId,self.onFailure)
        log.debug('subscriber %s added' % self.username)
        
    def onFailure(self, reason):
        log.error(reason)

    def _checkTimeout(self):
        currentTime = int(time.time())
        if (currentTime - self._touchTime) > login_timeout:
            log.info('%s logged out due to user timeout' % self.username)
            self.timeoutChecker.stop()
            self.logout()
        
    def logout(self):
        def onAllQuit(result):
            log.debug('all live elements closed')
            if self.webSession:
                try:
                    self.webSession.expire()
                except:
                    pass
                self.webSession = None
                tmp = subscribers.pop(self.username, None)
                return True
        def onQuit(result):
            log.debug('closed a live element')
            return True
        self.password = ''
        self.auth_node_list = {}
        self.authed = False
        self.selected_host = None
        # contact any live pages and force them to go away
        element = None
        dl = []
        if len(self.livePageList):
            while len(self.livePageList):
                element = self.livePageList.pop()
                d = element.pageQuit()
                d.addCallbacks(onQuit,onQuit)
                dl.append(d)
            d = defer.DeferredList(dl, consumeErrors=True)
            d.addCallbacks(onAllQuit,onAllQuit)
            return d
        else:
            return True

    def registerAvatarLogout(self, webSession):
        self.webSession = webSession
        
    def registerLiveElement(self, liveElement):
        if liveElement not in self.livePageList:
            self.livePageList.append(liveElement)
    
    def unregisterLiveElement(self, liveElement):
        if liveElement in self.livePageList:
            tmp = self.livePageList.remove(liveElement)
        
    def isAuthed(self):
        return self.authed

    def checkCredentials(self, selected_node):
        def onSuccess(result):
            log.debug('result: %s' % result)
            return result
        def onFailure(reason):
            log.error(reason)
            return False
        creds = {'X-Opsview-Username': self.username, 'X-Opsview-Token': token}
        token, cred_time = self.auth_node_list[selected_node]
        if (int(time.time()) - cred_time) > 50:
            d = self.authenticateNode(selected_node)
            d.addCallback(onSuccess).addErrback(onFailure)
            return d
        else:
            return True        
        
    def _setTouchTime_decorator(target_function):

        def wrapper(self, *args, **kwargs):
            lastTouched = int(time.time() - self._touchTime)
            self._touchTime = int(time.time())
            return target_function(self, *args, **kwargs)
        return wrapper

    @_setTouchTime_decorator
    def getDbId(self):
        return self.dbId
    
    @_setTouchTime_decorator
    def setCurrentChart(self, chart):
        self.currentChart = chart

    @_setTouchTime_decorator
    def editGraphInit(self):
        if not self.currentChart:
            self.currentChart = graph.chart(self)
        return self.currentChart
    
    @_setTouchTime_decorator
    def editSuiteInit(self, member_list):
        return graph.suite(self.dbId, members=member_list)
    
    @_setTouchTime_decorator
    def loadSuite(self, dbId, perms='ro'):
        log.debug(graph.suites)
        if int(dbId) in graph.suites:
            log.debug('returning a cached suite')
            # check for ownership and handle perms correctly
            # set permissions for myself (by myself) to perms
            return graph.suites[int(dbId)].setPermissions(self.dbId, self.dbId, perms)
        else:
            return graph.suite(self.dbId, dbId=dbId, perms=perms)
    
    @_setTouchTime_decorator
    def getSuiteMemberList(self, suite):
        log.debug('getting suite member list')
        return suite.getMemberList()
    
    @_setTouchTime_decorator
    def getSuiteColumns(self, suite):
        return suite.getColumns()
    
    @_setTouchTime_decorator
    def setSuiteColumns(self, suite, numcols):
        suite.setColumns(numcols)
        
    @_setTouchTime_decorator
    def getSuitePermissions(self, suite):
        return suite.getPermissions(self.dbId)
    
    @_setTouchTime_decorator
    def applySuiteOverrides(self, suite):
        return suite.applyOverrides(self)
    
    @_setTouchTime_decorator
    def saveSuite(self, suiteList, suite):
        return suite.saveSuite(suiteList)
    
    @_setTouchTime_decorator
    def addSuiteGraph(self, suite, chart, chart_id):
        suite.addGraphReference(chart, chart_id, self)
    
    @_setTouchTime_decorator
    def getSavedSuiteList(self):
        def onSuccess(result):
            suite_list = []
            for row in result:
                tmp = []
                # instead of converting the timestamp in the sql query, we should do it here so we can use the config based time formatting string
                for item in row:
                    tmp.append(unicode(item))
                suite_list.append(tmp)
            log.debug(suite_list)
            return suite_list
        def onFailure(reason):
            log.error(reason)
            return []
        d = txdbinterface.getSuiteList(self.username)
        d.addCallbacks(onSuccess,onFailure)
        return d
    
    @_setTouchTime_decorator
    def initializeGraphPage(self, chart):
        if not chart:
            self.currentChart = graph.chart(self)
            return self.currentChart
        if not chart.getSeriesCount():
            return () #False has no length, so we can't use it here, return an empty tuple instead
        else:
            return (chart.getSeriesHsmList(), chart.getChartObject())

    @_setTouchTime_decorator
    def getEventTypeList(self, chart):
        possibleEventTypes = opsview.event_type_list[:]
        event_types = ['All', 'None']
        # add opsview event types
        for e_type in possibleEventTypes:
            event_types.append(e_type)
        # add general event types
        #for e_type in generalEventTypes:
            #event_types.append(e_type)
        chart.setEventTypeList(event_types)
        return chart.getEventTypeList()
    
    @_setTouchTime_decorator
    def getSelectedEventType(self, chart):
        return chart.getEventsDisplay()
    
    @_setTouchTime_decorator
    def setDbId(self, result):
        log.debug('got db id %s' % result)
        self.dbId = result
        
    @_setTouchTime_decorator
    def getDbId(self):
        return self.dbId
    
    @_setTouchTime_decorator
    def authenticateNode(self, auth_node):
        def onLogin(result, auth_node):
            if result:
                log.debug('Got login result for user login: %s' % self.username)
                log.debug(result)
                token, cred_time, cj = result
                self.auth_node_list[auth_node] = [token, cred_time]
                log.debug('cred_time: %i, now: %i' % (cred_time, int(time.time())))
                if len(cj) == 2:
                    log.debug('Got web session and auth_tkt')
                    self.auth_tkt = cj['auth_tkt']
                    self.web_session = cj['opsview_web_session']
                log.debug('User %s authenticated on node %s' % (self.username, auth_node))
                log.debug('Auth Ticket: %s' % self.auth_tkt)
                log.debug('Web Session: %s' % self.web_session)
                log.debug('%s auth_node_list has %s entries' % (self.username, self.auth_node_list))
                return True
            else:
                log.debug('User %s failed to authenticate to node %s' % (self.username, auth_node))
                return False
        def onError(reason):
            log.error(reason)
        if auth_node in self.auth_node_list:
            old_token, old_cred_time = self.auth_node_list[auth_node]
            if int(time.time()) - int(old_cred_time) < 60:
                log.debug('re-auth attempted too soon, last auth: %i' % old_cred_time)
                login_result = False
            else:
                log.debug('attempting re-auth')
                login_result = opsview.node_list[auth_node].loginUser(self.username, self.password)
        else:
            log.debug('authenticating new node')
            login_result = opsview.node_list[auth_node].loginUser(self.username, self.password)
        return login_result.addCallback(onLogin, auth_node).addErrback(onError)
        
    @_setTouchTime_decorator
    def authenticateNodes(self):
        def onSuccess(result):
            log.debug('returning login request result: %s' % self.authed)
            return self.authed
        def onNodeSuccess(result):
            log.debug('result from node auth request: %s, node count: %s' % (result, self.auth_count))
            #log.debug(result)
            #log.debug(self.auth_node_list)
            if result:
                self.authed = True
                self.auth_count -= 1
            else:
                self.auth_count -= 1
            return self.authed
        def onFailure(reason):
            log.failure(reason)
        log.debug('Authenticating %s on nodes: %s' % (self.username, opsview.node_list))
        self.authed = False
        self.auth_count = 0
        ds = []
        for auth_node in opsview.node_list:
            self.auth_count += 1
            auth_result = self.authenticateNode(auth_node)
            auth_result.addCallback(onNodeSuccess).addErrback(onFailure)
            ds.append(auth_result)
        d = defer.DeferredList(ds, consumeErrors=True)
        d.addCallbacks(onSuccess,onFailure)
        return d
    
    @_setTouchTime_decorator
    def getUserName(self):
        return self.username
    
    @_setTouchTime_decorator
    def getAuthNodes(self):
        node_list = []
        log.debug('found auth list of length %s' % len(self.auth_node_list))
        for node in self.auth_node_list:
            node_list.append(node)
        log.debug('returning node list of length %s' % len(node_list))
        return node_list
    
    @_setTouchTime_decorator
    def getPreviousSeries(self, chart):
        return chart.getPreviousSeries()
    
    @_setTouchTime_decorator
    def resetPreviousSeries(self, chart):
        return chart.resetPreviousSeries()
    
    @_setTouchTime_decorator
    def getHostList(self, selected_node, chart):
        chart.setSelectedNode(str(selected_node))
        host_list = opsview.node_list[chart.getSelectedNode()].getHostList()
        host_list.sort()
        return host_list

    @_setTouchTime_decorator
    def getServiceList(self, selected_host, chart):
        chart.setSelectedHost(str(selected_host))
        domain = opsview.node_list[chart.getSelectedNode()]
        host = domain.getHostByName(chart.getSelectedHost())
        service_list = host.getServiceList()
        service_list.sort()
        return service_list

    
    @_setTouchTime_decorator
    def getMetricList(self, selected_service, chart):
        chart.setSelectedService(str(selected_service))
        domain = opsview.node_list[chart.getSelectedNode()]
        host = domain.getHostByName(chart.getSelectedHost())
        service = host.getServiceByName(str(selected_service))
        metric_list = service.getMetricList()
        new_metric_list = []
        for metric in metric_list:
            metric_series = [chart.getSelectedNode(),
                             chart.getSelectedHost(),
                             chart.getSelectedService(),
                             metric]
            log.debug("looking for %s in %s" % (metric_series, chart.getMetricSeries()))
            if metric_series in chart.getMetricSeries():
                log.debug('skipping metric that is already in the series selection')
                pass
            else:
                new_metric_list.append(metric)
        new_metric_list.sort()
        return new_metric_list

    @_setTouchTime_decorator
    def setMetric(self, selected_metric, chart):
        chart.setSelectedMetric(str(selected_metric))
        
    @_setTouchTime_decorator
    def setRegexp(self, chart, keyP, patt):
        if patt == '*':
            patt = '.*'
        try:
            tmp = re.compile(patt, re.I)
        except:
            return False
        chart.setRegexp(keyP, patt)
        return self.getRegexpMatchCount(chart)
        
    @_setTouchTime_decorator
    def getRegexpMatchCount(self, chart):
        tmp = chart.getRegexp()
        dPatt, hPatt, sPatt, mPatt = tmp
        regexpMatch = opsview.search(self.auth_node_list, dPatt, hPatt, sPatt, mPatt)
        dhsmList = self.getDhsmListFromDict(chart, regexpMatch)
        return (len(dhsmList),dhsmList[:])
    
    def getDhsmListFromDict(self, chart, domainDict):
        dhsmList = []
        selectedDhsm = chart.getMetricSeries()[:]
        for node in domainDict:
            for host in domainDict[node]:
                for service in domainDict[node][host]:
                    for metric in domainDict[node][host][service]:
                        tmpDhsm = [node, host, service, metric]
                        if tmpDhsm not in selectedDhsm:
                            dhsmList.append(tmpDhsm)
        return dhsmList[:]
            
    def addRegexpSelect(self, chart):
        dhsmCount, dhsm = self.getRegexpMatchCount(chart)
        dhsmIndexedList = []
        for row in dhsm:
            dhsmIndexed = chart.addUniqueSeries(row[:])
            dhsmIndexedList.append(dhsmIndexed)
        return dhsmIndexedList
            
    @_setTouchTime_decorator
    def addGraphSeries(self, chart):
        return chart.getCurrentSeries()

    @_setTouchTime_decorator
    def cancelSeriesId(self, series_id, chart):
        return chart.cancelSeriesId(series_id)
    
    @_setTouchTime_decorator
    def getEventList(self, time_values, chart):
        if not len(time_values):
            # no time values sent, return empty event object
            return {}
        log.debug('starting events building')
        chart.setEventList([])
        event_nodes = []
        for data_node in chart.getDataNodes():
            if data_node not in event_nodes:
                event_nodes.append(data_node)
                n_events = opsview.node_list[data_node].getEvents()
                log.debug('got events from node %s ' % data_node)
                log.debug(n_events)
                for event_type in n_events.keys():
                    if event_type in chart.getChartEventsDisplayList():
                        event_alpha = n_events[event_type]['alpha']
                        event_color = n_events[event_type]['color']
                        event_events = n_events[event_type]['events']
                        for record in event_events:
                            tmp = {'node': data_node,
                                   'alpha': event_alpha,
                                   'color': event_color,
                                   'type': event_type,
                                   'dbid': record[0],
                                   'name': record[1],
                                   'desc': record[2],
                                   'start': record[3],
                                   'end': record[4],
                                   'url': record[5]}
                            chart.addEvent(tmp)
        log.debug('looking through %i events' % len(chart.getEventList()))
        from bisect import bisect
        #get min and max values from time values
        t_min, t_max = int(time_values[0]), int(time_values[len(time_values)-1])
        graph_extents = (t_min, t_max)
        #find the outages that fit on our graph
        graphable_event_list = []
        for g_event in chart.getEventList():
            g_event_start_time = int(g_event['start'])
            g_event_end_time = int(g_event['end'])
            log.debug('event starts at: %i, graph starts at %i' % (g_event_start_time, t_min))
            log.debug('event ends at: %i, graph ends at %i' % (g_event_end_time, t_max))
            if (bisect(graph_extents, g_event_end_time) == 1 or bisect(graph_extents, g_event_start_time) == 1):
                log.debug('event starts %i seconds after graph' % (g_event_start_time - t_min))
                log.debug('event ends %i seconds before graph' % (t_max - g_event_end_time))
                g_event_start_index = bisect(time_values, g_event_start_time)
                g_event_end_index = bisect(time_values, g_event_end_time)
                if event_display == 'inclusive':
                    if g_event_start_index != 0:
                        g_event_start_index -= 1
                    if g_event_end_index != len(time_values)-1:
                        g_event_end_index += 1
                g_evnt = g_event.copy()
                g_evnt['s_index'] = g_event_start_index
                g_evnt['e_index'] = g_event_end_index
                g_evnt['start'] = g_event_start_time
                g_evnt['end'] = g_event_end_time
                graphable_event_list.append(g_evnt)
                log.debug('added an event for graphing')
            else:
                log.debug('processed an event that is out of range')
        # build the vTrendLines chart structure for the events
        events = {}
        events[unicode('line')] = []
        # events structure
        for event in graphable_event_list:
            evnt_record = {}
            evnt_record[unicode('startIndex')] = unicode(str(event['s_index']))
            evnt_record[unicode('endIndex')] = unicode(str(event['e_index']))
            evnt_record[unicode('color')] = unicode(str(event['color']))
            evnt_record[unicode('displayValue')] = unicode(event['desc'])
            evnt_record[unicode('alpha')] = unicode(event['alpha'])
            evnt_record[unicode('start')] = unicode(event['start'])
            evnt_record[unicode('end')] = unicode(event['end'])
            events[unicode('line')].append(evnt_record)
        return events

    @_setTouchTime_decorator
    def buildMultiSeriesTimeObject(self, chart, chart_cell, data={}):
        if data:
            time_values, data_series = chart.getTimeValues(data)
            if chart.getEventsDisplay() != 'None':
                events = self.getEventList(time_values, chart)
                log.debug('got events: %s' % events)
            else:
                log.debug('events set to None')
                events = None        
            if chart.getChartEngine() == 'FusionCharts':
                #log.debug('building a fusion charts graph from %s' % data)
                chart_object = chart.buildMultiSeriesTimeObject(time_values, data_series, events)
                return chart_object
            elif chart.getChartEngine() == 'HighCharts':
                #log.debug('building a high charts graph from %s' % data)
                chart_object = chart.buildHighChartsTimeObject(chart_cell, data_series, events)
                return chart_object
        else:
            return {}

    def _makeGraph(self, result, chart):
        """ called from makeGraph when authentication has failed during a graph build"""
        return self.makeGraph(chart)

    @_setTouchTime_decorator
    def makeGraph(self, chart):
        def onTotalSuccess(result):
            log.debug('got all results!')
            return chart.getSeriesData()
        def onSeriesSuccess(result, series_id):
            chart.setSeriesData(series_id, result)
        def onFailure(reason):
            log.error(reason)
            return False
        ds = []
        chart.setSeriesData()
        chart.setDataNodes([])
        log.debug('graphing the following series: %s' % chart.getSeries())
        for row in chart.getSeries():
            result = self._fetchMetricData(chart, row, returnData=True)
            result.addCallback(onSeriesSuccess, row)
            ds.append(result)
        d = defer.DeferredList(ds, consumeErrors=False)
        d.addCallbacks(onTotalSuccess, onFailure)
        return d

    def _fetchMetricData(self, chart, row, returnData=True):
        log.debug('trying to grab four items from %s' % chart.getSeriesTracker(row))
        log.debug('subscribers auth_list is %s' % self.auth_node_list)
        data_node, host, service, metric = chart.getSeriesTracker(row)
        try:
            cred_token, cred_time = self.auth_node_list[data_node]
        except:
            log.error("subscriber: makeGraph: Cannot get cred_token for data_node=%s"%data_node)
            continue
        if int(time.time()) > int(cred_time + reauth_timeout):
            # if we have exceeded our auth time, force a re-authentication.
            d = self.authenticateNode(data_node)
            log.debug('re-authentication requested')
            d.addCallback(self._makeGraph,chart).addErrback(self.onFailure)
            return d
        if data_node not in chart.getDataNodes():
            chart.addDataNode(data_node)
        creds = {'X-Opsview-Username': self.username, 'X-Opsview-Token': self.auth_node_list[data_node][0]}
        cookies = {'auth_tkt': self.auth_tkt}
        api_uri = '%s::%s::%s' % (host, service, metric)
        chart.setSeriesUri(row, data_node, api_uri)
        end_time,duration = chart.calculateGraphPeriod()
        #result = opsview.node_list[data_node].fetchData(api_uri, end_time, duration, creds, cookies, (host, service, metric))
        result = defer.maybeDeferred(opsview.node_list[data_node].fetchData, api_uri, end_time, duration, creds, cookies, (host, service, metric), (chart.getChartDurationModifier(), chart.getChartDurationLength(), chart.getChartDurationUnit()), returnData=returnData)
        return result

    @_setTouchTime_decorator
    def saveGraph(self, chart):
        return chart.saveGraph()

    @_setTouchTime_decorator
    def deleteGraphs(self, graphList):
        return txdbinterface.deleteGraphs(graphList)

    @_setTouchTime_decorator
    def getGraphEngineList(self):
        return graph_engines[:]
    
    @_setTouchTime_decorator
    def getGraphEngine(self, chart):
        return chart.getChartEngine()
    
    @_setTouchTime_decorator
    def getGraphType(self, chart):
        return chart.getChartType()
    
    @_setTouchTime_decorator
    def setGraphEngine(self, engine, chart):
        chart_engine = str(engine)
        chart.setChartEngine(chart_engine)
        if chart.getChartType() not in graph_types[chart_engine]:
            chart.setChartType(None)
        if chart_engine in graph_types:
            return graph_types[chart_engine].copy()
        else:
            return []

    @_setTouchTime_decorator
    def setGraphType(self, graph_type, chart):
        avail_types = graph_types[chart.getChartEngine()]
        if graph_type not in avail_types:
            return False
        else:
            chart.setChartType(graph_type)
            return True

    @_setTouchTime_decorator
    def getGraphSettings(self, chart):
        graph_settings = {}
        graph_settings['graph_type'] = graph_types[chart.getChartEngine()][chart.getChartType()]
        graph_settings['graph_width'] = chart.getChartWidth()
        graph_settings['graph_height'] = chart.getChartHeight()
        return graph_settings

    @_setTouchTime_decorator
    def getGraphSizes(self):
        return graph_size
    
    @_setTouchTime_decorator
    def getGraphName(self, chart):
        return chart.getChartName()
    
    @_setTouchTime_decorator
    def getGraphTitle(self, chart):
        return chart.getChartTitle()
    
    @_setTouchTime_decorator
    def getGraphSize(self, chart):
        return chart.getChartSize()
    
    @_setTouchTime_decorator
    def getGraphStartTime(self, chart):
        if chart.getChartStart() == 'Now':
            start_time = int(time.time())
        else:
            start_time = chart.getChartStart()
        date_time_object = datetime.datetime.fromtimestamp(start_time)
        return date_time_object.strftime("%m/%d/%Y %H:%M")
    
    @_setTouchTime_decorator
    def getGraphDuration(self, chart):
        dur = '%s%s%s' % (chart.getChartDurationModifier(),chart.getChartDurationLength(),chart.getChartDurationUnit())
        return dur
    
    @_setTouchTime_decorator
    def setGraphName(self, graph_name, chart):
        return chart.setChartName(graph_name)
        
    @_setTouchTime_decorator
    def setGraphTitle(self, graph_title, chart):
        return chart.setChartTitle(graph_title)
    
    @_setTouchTime_decorator
    def setGraphSize(self, size, chart):
        if size in graph_size:
            width, height = graph_size[size]
            return chart.setChartSize(size, width, height)
        else:
            return False
    
    @_setTouchTime_decorator
    def setGraphDuration(self, duration, chart):
        if len(duration) == 0:
            # missing duration, flag an error
            log.debug('duration of length 0 supplied')
            return False
        elif duration[:1] in ('+', '-'):
            dur_mod = duration[:1]
            dur_remainder = duration[1:]
        elif duration[:1] in ('1','2','3','4','5','6','7','8','9','0'):
            dur_mod = '-'
            dur_remainder = duration
        else:
            log.debug('invalid duration modifier: %s' % duration[:1])
            return False
        if duration[len(duration)-1:] in ('y','Y','m','M','w','W','d','D','h','H'):
            dur_units = duration[len(duration)-1:]
            dur_remainder = dur_remainder[:len(dur_remainder)-1]
        else:
            log.debug('invalid duration unit: %s' % duration[len(duration)-1:])
            return False
        try:
            log.debug('converting duration value %s to int' % dur_remainder)
            dur_len = int(dur_remainder)
        except:
            log.debug('invalid duration value: %s' % dur_len)
            return False
        chart.setChartDurationLength(str(dur_len))
        chart.setChartDurationUnit(dur_units)
        chart.setChartDurationModifier(dur_mod)
        return [str(dur_len), dur_units, dur_mod]
    
    @_setTouchTime_decorator
    def setGraphStartTime(self, date_time, chart):
        if type(date_time) == float:
            chart.setChartStart(date_time)
        elif type(date_time) == int:
            chart.setChartStart(date_time)
        else:
            date_time = date_time.strip(' ')
            log.debug('got start_time: %s' % date_time)
            if date_time == 'Now':
                start_time = time.time()
            elif date_time == '':
                start_time = time.time()
            else:
                # tear apart the date and time object into their component parts
                date,ttime = date_time.split(' ')
                month,day,year = date.split('/')
                hour,minute = ttime.split(':')
                start_time_object = datetime.datetime(int(year), int(month), int(day), int(hour), int(minute))
                start_time = time.mktime(start_time_object.timetuple())
            chart.setChartStart(start_time)
        return True
    
    @_setTouchTime_decorator
    def setGraphPrivacy(self, privacy, chart):
        if privacy not in graph_privacy:
            return False
        else:
            chart.setChartPrivacy(privacy)
            return true
        
    @_setTouchTime_decorator
    def getGraphPrivacy(self, chart):
        return chart.getChartPrivacy()
    
    @_setTouchTime_decorator
    def getGraphPrivacies(self):
        return graph_privacy.copy()
    
    @_setTouchTime_decorator
    def setGraphEventType(self, e_type, chart):
        chart.setChartEventsDisplay(e_type)
        log.debug('event display set to %s' % e_type)
        if e_type == 'None':
            chart.setChartEventsDisplayList([])
        elif e_type == 'All':
            chart.setChartEventsDisplayList(chart.getEventTypeList()[:])
        else:
            chart.setChartEventsDisplayList([e_type])
        log.debug('displaying events: %s' % chart.getChartEventsDisplayList())
        
    @_setTouchTime_decorator
    def getSavedGraphList(self):
        def onSuccess(result):
            log.debug(result)
            graph_list = []
            for row in result:
                tmp = []
                # instead of converting the timestamp in the sql query, we should do it here so we can use the config based time formatting string
                for item in row:
                    tmp.append(unicode(item))
                graph_list.append(tmp)
            return graph_list
        def onFailure(reason):
            log.error(reason)
            return []
        d = txdbinterface.getGraphList(self.username)
        d.addCallbacks(onSuccess,onFailure)
        return d
    
    @_setTouchTime_decorator
    def loadGraph(self, dbId):
        def onCompleteSuccess(result):
            log.debug('graph completely loaded!')
            log.debug(result)
            log.debug('Final result is %s' % finalResult)
            if finalResult:
                return chart
            else:
                return False
        def onDefinitionSuccess(result):
            log.debug('graph definition loaded')
            if result:
                return True
            else:
                finalResult = False
                return False
        def onSeriesSuccess(result):
            log.debug('graph series loaded')
            if result:
                return True
            else:
                finalResult = False
                return False
        def onParamSuccess(result):
            log.debug('graph parameters loaded')
            if result:
                return True
            else:
                finalResult = False
                return False
        def onFailure(reason):
            log.error(reason)
        finalResult = True
        chart = graph.chart(self)
        ds = []
        d = chart.loadGraphDescription(dbId)
        d.addCallbacks(onDefinitionSuccess,onFailure)
        ds.append(d)
        d = chart.loadGraphSeries(dbId)
        d.addCallbacks(onSeriesSuccess,onFailure)
        ds.append(d)
        d = chart.loadGraphParams(dbId)
        d.addCallbacks(onParamSuccess,onFailure)
        d = defer.DeferredList(ds, consumeErrors=False)
        d.addCallbacks(onCompleteSuccess,onFailure)
        return d

    @_setTouchTime_decorator
    def returnToLastChart(self):
        if len(self.chartList):
            self.currentChart = self.chartList.pop()
        else:
            self.currentChart = None
            
def addSubscriber(username, password):
    if username in subscribers:
        if subscribers[username].isAuthed():
            log.debug('User %s already logged in' % username)
            return False
        else:
            subscribers[username] = subscriber(username, password)
    else:
        subscribers[username] = subscriber(username, password)
    return subscribers[username]
        
        
        
