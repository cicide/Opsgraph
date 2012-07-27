#!/usr/bin/python

import time, datetime
import utils, fusioncharts, highcharts, txdbinterface
from itertools import chain
from twisted.internet import defer
from twisted.internet.task import LoopingCall


log = utils.get_logger("GraphService")

date_format = utils.config.get('graph', 'date_format')
def_dur_len = utils.config.get('graph', 'duration_length')
def_dur_unit = utils.config.get('graph', 'duration_unit')

suites = {}
loadOnSelect = True

class suite(object):
    
    """ a suite of charts """
    
    def __init__(self, owner_id, members=None, dbId=None, perms=None):
        self.name = 'Default Suite Name'
        self.title = 'Default Suite Title'
        self.start = 'Now'
        self.durLen = def_dur_len
        self.durUnit = def_dur_unit
        self.durMod = '-'
        self.dbId = dbId
        self.owner = owner_id
        self.member_dict = {}
        self.columns = '3'
        self.subscribers = []  # web page subscribers (not a reference to a subscriber)
        self.changeList = []
        self.override = False
        self.loading = False
        self.loading_reqs = []
        self.perms = {}  #permission dict user_id: permissions
        if members:
            self.member_list = members
            self.perms[owner_id] = 'rw'
        elif dbId:
            # we have a database key id, load the suite from the database
            self.member_list = []
            self.perms[owner_id] = perms
            log.debug("permissions for %s set to %s" % (owner_id, self.perms[owner_id]))
            self.loading = True
            if int(dbId) in suites:
                log.error('oops, we already exist, why are we being created again?')
                suites[int(dbId)] = self
            else:
                suites[int(dbId)] = self
            tmp = self.loadFromDatabase()
        else:
            self.perms[owner_id] = 'rw'
            self.member_list = []
        log.debug('permissions on suite init: %s' % self.perms)
        log.debug('I am %s' % self)
        
    def destroy(self):
        log.debug('Destroy requested for suite %s' % self.name)
        if self.dbId:
            suites.pop(int(self.dbId))
    
    def loadFromDatabase(self):
        def loadComplete():
            self.loading = False
            log.debug('database load complete, notifying interested parties')
            for requester in self.loading_reqs:
                log.debug('Notifying caller we are initialized')
                requester.callback(self.member_list)
            return True
        def onDatabaseLoad(result):
            if result:
                self.owner = result[0]
                self.name = result[1]
                self.title = result[2]
                self.durMod = result[3]
                self.durLen = result[4]
                self.durUnit = result[5]
                if result[6] == 0:
                    self.start = 'Now'
                else:
                    self.start = result[6]
                self.member_list = result[7]
                self.columns = str(result[8])
                if int(result[9]):
                    self.override = True
                else:
                    self.override = False
                reply = True
            else:
                reply = False
            tmp = loadComplete()
            return reply
        def onDatabaseError(reason):
            self.loading = False
            log.error('onDbError: %s' % reason)
            loadComplete()
            return False
        log.debug('loading suite id: %s' % self.dbId)
        d = txdbinterface.loadSuite(self.dbId)
        d.addCallbacks(onDatabaseLoad,onDatabaseError)
        return d
        
    def registerSubscriber(self, subscriber):
        """ register for updates """
        self.subscribers.append(subscriber)
        
    def unregisterSubscriber(self, subscriber):
        if subscriber in self.subscribers:
            self.subscribers.remove(subscriber)
        log.debug('there are %i subscribers to suite %s' % (len(self.subscribers), self.name))
        if not len(self.subscribers):
            self.destroy()
            
    def addGraphReference(self, chart, chart_id, subscriber):
        self.member_dict[chart_id] = chart
        if self.override:
            suiteDuration = '%s%s%s' % (self.durMod, self.durLen, self.durUnit)
            log.debug('-----------------------------------------------------------------------------')
            log.debug('Applying Suite overrides to chart %s' % chart_id)
            log.debug('-----------------------------------------------------------------------------')
            tmp = subscriber.setGraphStartTime(self.start, chart)
            tmp = subscriber.setGraphDuration(suiteDuration, chart)

    def applyOverrides(self, subscriber):
        self.override = True
        suiteDuration = '%s%s%s' % (self.durMod, self.durLen, self.durUnit)
        # we probably want to make this a deferred list.....
        chartList = []
        for chart_id in self.member_dict:
            chart = self.member_dict[chart_id]
            result = (subscriber.setGraphStartTime(self.start, chart), subscriber.setGraphDuration(suiteDuration, chart))
            if result:
                chartList.append([chart_id, chart])
        if chartList:
            return chartList
        else:
            return False
    
    def setPermissions(self, user_id, requestor_id, perms):
        if int(requestor_id) != int(self.owner):
            # the requestor isn't the owner, and doesn't have rights to give someone rw access
            # if the requested access is ro, go ahead and set it
            if perms == 'ro':
                self.perms[user_id] = 'ro'
            elif user_id in self.perms:
                # requested perms is rw, if user_id is already permissioned, don't do anything
                pass
            else:
                # requested perms is rw, unknown user, so set to ro
                self.perms[user_id] = 'ro'
        else:
            # owner is changing user_id permissions, immediately affect the change
            # we should immediately update the affected web session.....
            self.perms[user_id] = perms
        log.debug(self.perms)
        return self
        
    def getPermissions(self, dbId):
        log.debug('*********************************************************************************')
        log.debug(self.perms)
        log.debug('I am %s' % self)
        if int(self.owner) == int(dbId):
            # the person requesting permissions is the owner, so they have rw perms
            # however if this was called from view ('ro' perms request, we should return 'ro')
            log.debug('stored perms is %s for user %s' % (self.perms[dbId], self.owner))
            if self.perms[dbId] == 'ro':
                return 'ro'
            else:
                return 'rw'
        else:
            log.debug('we are not the graph owner, setting permissions to read only, unless otherwise specified')
            # the requestor is not the owner, return read only
            if dbId in self.perms:
                return self.perms[dbId]
            else:
                return 'ro'
        
    def saveSuite(self, suiteList):
        def onSaveComplete(result):
            self.dbId = result
            if int(self.dbId) not in suites:
                suites[int(self.dbId)] = self
            else:
                log.debug('we were already in the suites dictionary, maybe this was an update?')
            return self.dbId
        def onFailure(reason):
            log.error('savesuite %s' % reason)
            return False
        suite_def = {}
        if self.override:
            suite_def['override'] = 1
        else:
            suite_def['override'] = 0
        suite_def['owner_id'] = self.owner
        suite_def['name'] = self.name
        suite_def['title'] = self.title
        suite_def['dur_mod'] = self.durMod
        suite_def['dur_len'] = self.durLen
        suite_def['dur_unit'] = self.durUnit
        if self.start == 'Now':
            suite_def['start'] = 0
        else:
            suite_def['start'] = suite.start
        suite_def['numCols'] = int(self.columns)
        # if we already have a dbId, we should do an update instead of an insert
        if self.dbId:
            # do a suite update here instead of a save
            d = txdbinterface.updateSuite(suite_def, self.member_list)
        else:
            d = txdbinterface.saveSuite(suite_def, self.member_list)
        d.addCallbacks(onSaveComplete,onFailure)
        return d
    
    def noteChanges(self, item, value):
        self.changeList.append({item: value})
        
    def updateSubscribers(self, item, value):
        self.changeList.reverse()
        while len(self.changeList):
            change = self.changeList.pop()
            for changeTarget in change:
                for sub in self.subscribers:
                    sub.updateSuite(changeTarget, change[changeTarget])
            
    def getMemberList(self):
        # check to see if we are loading data from the database, if so hand back a deferred
        # that can be calles with the member list when the database load is complete, else
        # hand back a fired deferred with the member list.
        if not self.loading:
            log.debug('returning member list - triggered deferred')
            return defer.succeed(self.member_list)
        else:
            log.debug('returning deferred while loading from database')
            d = defer.Deferred()
            self.loading_reqs.append(d)
            return d
    
    def setColumns(self, columns):
        self.columns = int(columns)
        self.noteChanges('columns', columns)
        
    def getColumns(self):
        return self.columns

    def setChartName(self, name):
        self.name = name
        self.noteChanges('name', name)
        
    def getChartName(self):
        return self.name
    
    def setChartTitle(self, title):
        self.title = title
        self.noteChanges('title', title)
        
    def getChartTitle(self):
        return self.title
    
    def setChartStart(self, start):
        self.start = start
        self.noteChanges('start', start)
        
    def getChartStart(self):
        return self.start

    def setChartDurationModifier(self, durMod):
        self.durMod = durMod
        self.noteChanges('durMod', durMod)
        
    def getChartDurationModifier(self):
        return self.durMod
    
    def setChartDurationLength(self, durLen):
        self.durLen = durLen
        self.noteChanges('durLen', durLen)
        
    def getChartDurationLength(self):
        return self.durLen
    
    def setChartDurationUnit(self, durUnit):
        self.durUnit = durUnit
        self.noteChanges('durUnit', durUnit)
        
    def getChartDurationUnit(self):
        return self.durUnit
    
    
class chart(object):
    
    """ a single chart either in development or developed"""
    
    def __init__(self, creator, copy_master=None):
        self.owner = creator #subscriber object - possible memory leak area
        self.domRegexp = self.hostRegexp = self.svcRegexp = self.metRegexp = None
        if copy_master:
            self.name = copy_master.name
            self.title = copy_master.title
            self.privacy = copy_master.privacy
            self.engine = copy_master.engine
            self.ctype = copy_master.ctype
            self.dbId = None
            self.size = copy_master.size
            self.width = copy_master.width
            self.height = copy_master.height
            self.durLen = copy_master.durLen
            self.durUnit = copy_master.durUnit
            self.durMod = copy_master.durMod
            self.start = copy_master.start
            self.eventsDisplay = copy_master.eventsDisplay
            self.possibleEventTypes = copy_master.possibleEventTypes
            self.eventsDisplayList = copy_master.eventsDisplayList
            self.eventList = copy_master.eventList
            self.dataNodes = copy_master.dataNodes
            self.series = copy_master.series
            self.seriesTracker = copy_master.seriesTracker
            self.seriesCounter = copy_master.seriesCounter
            self.metricSeries = copy_master.metricSeries
            self.seriesUri = copy_master.seriesUri
            self.seriesData = copy_master.seriesData
            self.chartObject = copy_master.chartObject
            self.selected_node = copy_master.selected_node
            self.selected_host = copy_master.selected_host
            self.selected_service = copy_master.selected_service
            self.selected_metric = copy_master.selected_metric
            self.previousSeries = copy_master.previousSeries
            self.liveElements = copy_master.liveElements
            self.liveUpdater = copy_master.liveUpdater
        else:
            self.name = 'Default Graph Name'
            self.title = 'Default Graph Title'
            self.privacy = 'Public' # Public, ACL, Private
            self.engine = 'HighCharts'
            self.ctype = 'Line'
            self.dbId = None
            self.size = 'Large'
            self.width = '800'
            self.height = '600'
            self.durLen = def_dur_len
            self.durUnit = def_dur_unit
            self.durMod = '-'
            self.start = 'Now'
            self.eventsDisplay = 'None'
            self.possibleEventTypes = ['outage', 'event']
            self.eventsDisplayList = []
            self.eventList = [] # entry: {'node': node, 
            #                                         'type': type, 
            #                                         'color': color, 
            #                                         'alpha': alpha, 
            #                                         'dbid': id, 
            #                                         'name': name, 
            #                                         'desc': description, 
            #                                         'start': start_time,
            #                                         'end': end_time, 
            #                                         'url': url }
            self.dataNodes = []
            self.series = []
            self.seriesTracker = {}
            self.seriesCounter = 0
            self.metricSeries = []
            self.seriesUri = {}
            self.seriesData = {}
            self.chartObject = {}
            self.selected_node = None
            self.selected_host = None
            self.selected_service = None
            self.selected_metric = None
            self.previousSeries = None
            self.liveElements = {}
            self.liveUpdater = None
        
    def addLiveElement(self, element, chartId):
        if element not in self.liveElements:
            log.debug('adding a live element to my list to be updated')
            self.liveElements[element] = [chartId]
        else:
            if chartId not in self.liveElements[element]:
                log.debug('adding chartId %s to live element with %i chart ids' % (chartId, len(self.liveElements[element])))
                self.liveElements[element].append(chartId)
            else:
                log.debug('chartId %s is already being live updated for this element' % chartId)
        if self.start == 'Now':
            log.debug('enable live updates for chart')
            self.liveUpdate(True, 180)
        elif (time.time() - self.start) < 301:
            log.debug('enable live updates for chart with start time within five minutes')
            self.liveUpdate(True, 180)
        else:
            log.debug('graph end time is too old to be made live')
            
    def cancelLiveElement(self, element):
        if element in self.liveElements:
            log.debug('removing live element from chart')
            tmp = self.liveElements.pop(element)
            tmp = None
        else:
            log.debug('got a live element removal request for an element that was not live')
        if not len(self.liveElements):
            self.liveUpdate(False)
            
    def liveUpdate(self, active, interval=300):
        # enable or disable liveUpdates - looping call
        log.debug('liveUpdate request: %s, interval: %s' % (active, interval))
        if active:
            self.liveUpdater = LoopingCall(self.runLiveUpdates)
            self.liveUpdater.start(interval)
        else:
            if self.liveUpdater:
                if self.liveUpdater.running:
                    log.debug('Stopping live updates')
                    self.liveUpdater.stop()
                    self.liveUpdater = None
        
    def runLiveUpdates(self):
        self.owner._touchTime = int(time.time())
        log.debug('running Live update for %s' % self.name)
        # Check for new data
        for row in self.getSeries():
            result = self.owner._fetchMetricData(self, row, returnData=True, end_time=int(time.time()), extendCache=True, skipODW=True)
        
    def updateLiveElements(self, liveData, seriesId):
        if len(self.liveElements):
            # send the update to each element viewing this graph
            for element in self.liveElements:
                #we will need to pass the graph element id, as well as the series being updated with the
                #actual live data 
                for chart in self.liveElements[element]:
                    element.liveUpdate(chartId, seriesId, liveData)
        else:
            log.debug('got a liveUpdate for a graph with no listeners')
            self.liveUpdate(False)
        
    def getDataNodes(self):
        return self.dataNodes

    def setDataNodes(self, nodes):
        self.dataNodes = nodes

    def addDataNode(self, node):
        self.dataNodes.append(node)

    def getSeriesCount(self):
        return len(self.series)

    def getSeriesTracker(self, key_id=None):
        if key_id:
            return self.seriesTracker[key_id]
        else:
            return self.seriesTracker.copy()
    
    def getSeriesHsmList(self):
        res_series = []
        for row in self.series:
            series = self.seriesTracker[row][:]
            series.append(row)
            res_series.append(series)
        return res_series

    def getSeriesData(self):
        log.debug('Series data is %i long' % len(self.seriesData))
        return self.seriesData
    
    def setSeriesData(self, key_id=None, data=None):
        if key_id:
            self.seriesData[key_id] = data
        else:
            self.seriesData = {}
        
    def setSeriesUri(self, key_id, data_node, api_uri):
        self.seriesUri[key_id] = [data_node, api_uri]
        
    def getSeries(self):
        return self.series
    
    def getChartObject(self):
        return self.chartObject
    
    def getChartEngine(self):
        log.debug('returning graph engine: %s' % self.engine)
        return self.engine
    
    def setChartEngine(self, engine):
        log.debug('Setting graph engine to: %s' % engine)
        self.engine = str(engine)
        log.debug('Graph engine set to: %s' % engine)
    
    def getChartType(self):
        return self.ctype
    
    def setChartType(self, c_type):
        self.ctype = c_type
    
    def getChartWidth(self):
        return self.width
    
    def getChartHeight(self):
        return self.height
    
    def getChartSize(self):
        return self.size
    
    def setChartSize(self, size_name, size_width, size_height):
        self.size = size_name
        self.height = size_height
        self.width = size_width
        return True
        
    def getChartPrivacy(self):
        return self.privacy
    
    def setChartPrivacy(self, privacy):
        self.privacy = privacy
        
    def getChartName(self):
        return self.name
    
    def setChartName(self, name):
        self.name = name
        return True
        
    def getChartTitle(self):
        return self.title
    
    def setChartTitle(self, title):
        self.title = title
        return True
        
    def getChartStart(self):
        return self.start
    
    def setChartStart(self, time):
        self.start = time
    
    def getChartDurationModifier(self):
        return self.durMod
    
    def setChartDurationModifier(self, durMod):
        self.durMod = durMod
        
    def getChartDurationLength(self):
        return self.durLen
    
    def setChartDurationLength(self, durLen):
        self.durLen = durLen
        
    def getChartDurationUnit(self):
        return self.durUnit
    
    def setChartDurationUnit(self, durUnit):
        self.durUnit = durUnit
    
    def getChartEventsDisplay(self):
        return self.eventsDisplay
    
    def setChartEventsDisplay(self, ed):
        self.eventsDisplay = ed
        
    def getChartEventsDisplayList(self):
        log.debug('returning event display list: %s' % self.eventsDisplayList)
        return self.eventsDisplayList
    
    def setChartEventsDisplayList(self, edl):
        self.eventsDisplayList = edl
        
    def addEvent(self, event):
        self.eventList.append(event)
        
    def getEventTypeList(self):
        return self.possibleEventTypes
    
    def setEventTypeList(self, event_types):
        self.possibleEventTypes = event_types[:]
    
    def getEventsDisplay(self):
        return self.eventsDisplay

    def getEventList(self):
        return self.eventList
    
    def setEventList(self, event_list):
        self.eventList = event_list

    def getPreviousSeries(self):
        return self.previousSeries
    
    def resetPreviousSeries(self):
        self.previousSeries = None
        return None
    
    def setSelectedNode(self, node):
        self.selected_node = node
        
    def getSelectedNode(self):
        return self.selected_node
    
    def setSelectedHost(self, host):
        self.selected_host = host
        
    def getSelectedHost(self):
        return self.selected_host
    
    def setSelectedService(self, service):
        self.selected_service = service
        
    def getSelectedService(self):
        return self.selected_service

    def setSelectedMetric(self, metric):
        self.selected_metric = metric

    def getMetricSeries(self):
        return self.metricSeries
    
    def getCurrentSeries(self):
        def onSuccess(result):
            log.debug('completed pre-load')
        def onFail(reason):
            log.debug('preload failed: %s' % reason)
        graphSeries = [self.selected_node, self.selected_host, self.selected_service, self.selected_metric]
        self.previousSeries = graphSeries
        self.seriesCounter += 1
        series_index = str(self.seriesCounter)
        self.series.append(series_index)
        self.seriesTracker[series_index] = graphSeries
        self.selected_node = self.selected_host = self.selected_service = self.selected_metric = None
        self.metricSeries = []
        for sel_series in self.series:
            self.metricSeries.append(self.seriesTracker[sel_series][:])
        res_graphSeries = graphSeries[:]
        res_graphSeries.append(series_index)
        if loadOnSelect:
            d = self.owner._fetchMetricData(self, series_index, returnData=False)
            d.addCallback(onSuccess).addErrback(onFail)
        return res_graphSeries
    
    def addUniqueSeries(self, dhsm):
        def onSuccess(result):
            log.debug('completed pre-load')
        def onFail(reason):
            log.debug('preload failed: %s' % reason)
        self.seriesCounter += 1
        series_index = str(self.seriesCounter)
        self.series.append(series_index)
        self.seriesTracker[series_index] = dhsm[:]
        self.metricSeries = []
        for sel_series in self.series:
            self.metricSeries.append(self.seriesTracker[sel_series][:])
        res_dhsm = []
        for item in dhsm[:]:
            res_dhsm.append(unicode(item))
        res_dhsm.append(unicode(series_index))
        if loadOnSelect:
            d = self.owner._fetchMetricData(self, series_index, returnData=False)
            d.addCallback(onSuccess).addErrback(onFail)            
        return res_dhsm
        
    def cancelSeriesId(self, seriesId):
        try:
            series_index = str(seriesId)
            series = self.seriesTracker[series_index]
            self.series.remove(series_index)
            self.metricSeries.remove(series)
            return True
        except:
            log.debug('Unable to remove series')
            return False
        
    def normalizeData(self, data):
        #detect format of data and normalize
        if not data:
            log.debug('no data retrieved')
            return []
        key_list = []
        for key in data.keys():
            if data[key]:
                key_list.append(key)
        if not key_list:
            return []
        # if this is rrdfetch data, the first object per series is a ResultSet object
        # if this is rest/graph data, the first object is a list
        if 'ResultSet' in data[key_list[0]]:
            #do data normalization
            data_series = []
            data_record_dict = {}
            log.debug('received data for graph object creation')
            #log.debug(data)
            for series in data:
                log.debug('Working on series: %s' % series)
                # to-do: Handle Series with value None
                data_dict = {}
                log.debug('grabbing series from series list')
                series_record = data[series]
                #log.debug(series_record)
                log.debug('grabbing resultset from series')
                result_set = series_record['ResultSet']
                #log.debug(result_set)
                log.debug('grabbing lines from resultset')
                lines = result_set['lines'][0]
                #log.debug(lines)
                log.debug('grabbing data list from lines')
                data_record = lines['data']
                #log.debug(data_record)
                for record in data_record:
                    data_dict[str(record[0])] = record[1]
                #log.debug(data_dict)
                lines['data'] = data_dict
                data_series.append(lines)
            return data_series
        else:
            # do rest/api data normalization
            data_series = []
            data_record_dict = {}
            #log.debug('received data for graph object creation - rest/api')
            #log.debug(data)
            for series in data:
                log.debug('Working on series: %s' % series)
                data_dict = {}
                log.debug('grabbing data dictionary from series')
                if len(data[series]['list']):
                    series_list = data[series]['list'][0]
                    if 'data' in series_list:
                        log.debug('grabbing raw data from list (lines)')
                        data_record = series_list['data']
                        for record in data_record:
                            data_dict[str(record[0])] = record[1]
                    elif 'cacheData' in series_list:
                        log.debug('grabbing cached data from list (dict)')
                        data_dict = series_list['cacheData']
                    else:
                        log.debug('unknown series data type')
                    #log.debug(data_dict)
                    series_list['data'] = data_dict
                else:
                    series_list['data'] = {}
                data_series.append(series_list)
            return data_series
        
    
    def calculateGraphPeriod(self):
        # Calculate the end_time and duration from the start_time and duration provided by the user
        if self.start in ('Now', 0):
            start_time = int(time.time())
            log.debug('setting start time to Now')
        else:
            try:
                start_time = int(self.start)
                log.debug('setting start time to %s' % datetime.datetime.fromtimestamp(self.start).strftime('%Y-%m-%d %H:%M'))
            except:
                log.debug('setting start time to Now')
                start_time = int(time.time())
        if self.durMod == '-':
            end_time = start_time
            duration = "%s%s" % (self.durLen,self.durUnit)
            log.debug('setting selected start time with negative modifier')
            return end_time, duration
        else:
            dt = datetime.datetime.fromtimestamp(start_time)
            log.debug('initial start time calculated as %s' % dt.strftime('%Y-%m-%d %H:%M'))
            dt_unit = self.durUnit
            dt_value = int(self.durLen)
            if dt_unit in ('y','Y'):
                et_year = dt.year + dt_value
                end_time = datetime.datetime(et_year, dt.month, dt.day, dt.hour, dt.minute)
                log.debug('setting end time year to %i ' % et_year)
            elif dt_unit in ('m','M'):
                et_month = dt.month + dt_value
                et_year = dt.year
                while et_month > 12:
                    et_year += 1
                    et_month -= 12
                end_time = datetime.datetime(et_year, et_month, dt.day, dt.hour, dt.minute)
                log.debug('setting end time year to %i and month to %i' % (et_year, et_month))
            elif dt_unit in ('w','W'):
                dt_diff = datetime.timedelta(weeks=dt_value)
                end_time = dt + dt_diff
                log.debug('modified start time by %i weeks' % dt_value)
            elif dt_unit in ('d','D'):
                dt_diff = datetime.timedelta(days=dt_value)
                end_time = dt + dt_diff
                log.debug('modified start time by %i days' % dt_value)
            elif dt_unit in ('h','H'):
                dt_diff = datetime.timedelta(hours=dt_value)
                end_time = dt + dt_diff
                log.debug('modified start time by %i hours' % dt_value)
            else:
                log.debug('unknown unit type, setting end date to Now')
                end_time = datetime.datetime.fromtimestamp(int(time.time()))
            end_time_timestamp = int(time.mktime(end_time.timetuple()))
            log.debug('final end time calculated as %s' % end_time.strftime('%Y-%m-%d %H:%M'))
            duration = "%s%s" % (self.durLen,self.durUnit)
            return end_time_timestamp,duration

    def getTimeValues(self, data):
        if len(data):
            # create a list and store each series in the list separately
            # We will need to package up the series data into dictionaries with time: value format
            data_series = self.normalizeData(data)
            # We should now have a list with a dictionary for each series
            # The dictionary should have the keys data, description, uom, and label
            # inside the data item, we have a list of [time, value] lists
            # We need to build a list of all the time values in order, as the 
            #   different series might not have data for the same time values
            # To do: make sure x axis data has equal increments for valid graph display
            time_values = []
            log.debug('figuring out time values')
            #for series in data_series:
                #for time_value in series['data']:
                    #if int(time_value) not in time_values:
                        #time_values.append(int(time_value))
            tvList = []
            for series in data_series:
                tvList.append(series['data'].keys())
            # chain the lists of series x values into a single list
            # set gives us in unordered set of objects, removing duplicates
            # convert it back to a list for our use
            time_values = list(iter(set(chain(*tvList))))
            if not len(time_values):
                log.error('got no time values')
            else:
                log.debug('sorting time values')
                #order the time values sequentially
                time_values.sort()
                #log.debug('data_series: %s' % data_series)
            log.debug('returning time values')
            return time_values, data_series
        else:
            return None
    
    def buildMultiSeriesTimeObject(self, time_values=[], data_series=[], events=None, caption=None, length=800, width=600):
        if not caption:
            caption = self.title
        if len(time_values):
            # we now have the x-axis time values in the time_values list
            # if this list is longer than some defined length depending on the width of the graph,
            #   we should limit the intervals which are printed on the x-axis
            log.debug('time values is %i long' % len(time_values))
            if self.engine == 'FusionCharts':
                x_axis_name = "Time"
                chart_object = fusioncharts.getMsObject(date_format, time_values, data_series, caption, x_axis_name, events)
                self.chartObject[unicode('chart_engine')] = unicode('FusionCharts')
                self.chartObject[unicode('chart_object')] = chart_object
                return chart_object
            elif self.engine == 'HighCharts':
                return self.buildHighChartsTimeObject(data_series, events)
            else:
                log.error('Unknown chart engine selected')
                return False
        else:
            log.error('No data to graph!')
            return False
        
    def buildHighChartsTimeObject(self, chart_cell, data_series = {}, events=None, caption=None):
        if not caption:
            caption = self.title
        if len(data_series):
            x_axis_name = "Time"
            graph_settings = self.owner.getGraphSettings(self)
            chart_object = highcharts.getLineChartObject(date_format, graph_settings, data_series, caption, x_axis_name, events, chart_cell)
            self.chartObject[unicode('chart_engine')] = unicode('HighCharts')
            self.chartObject[unicode('chart_object')] = chart_object
            return chart_object

    def saveGraph(self):
        log.debug('saving chart')
        # in the future we should detect whether or not this graph has been saved already
        if not self.chartObject:
            log.debug('no chartObject')
            return False
        #elif str(self.chartObject['chart_engine']) == 'FusionCharts':
        elif str(self.chartObject['chart_engine'] in ('FusionCharts', 'HighCharts')):
            # build a list of series in the graph
            chart_series = []
            for row in self.series:
                data_node, host, service, metric = self.seriesTracker[row]
                chart_series.append((data_node, host, service, metric))
            #build the chart definition object
            chart_def = {}
            chart_def['owner_id'] = self.owner.getDbId()
            chart_def['graph_name'] = self.name
            chart_def['graph_engine'] = self.engine
            chart_def['graph_title'] = self.title
            chart_def['graph_privacy'] = self.privacy
            chart_def['graph_type'] = self.ctype
            chart_def['graph_event'] = self.eventsDisplay
            if self.start == 'Now':
                chart_def['graph_start'] = 0
            else:
                chart_def['graph_start'] = int(self.start)
            chart_def['graph_dur_mod'] = self.durMod
            chart_def['graph_dur_len'] = self.durLen
            chart_def['graph_dur_unit'] = self.durUnit
            #get the chart object
            chart_obj = self.chartObject['chart_object']
            #determine if we are updating an existing graph, or saving a new one
            if self.dbId:
                #update the graph - for the mean time, save a new one
                #this should be a callback, or we suffer the chance of blocking here
                chartId = txdbinterface.saveGraph(chart_def, chart_obj, chart_series)
                self.dbId = chartId
                return True
            else:
                #save the new graph - this should be a callback, or we suffer the chance of blocking here
                chartId = txdbinterface.saveGraph(chart_def, chart_obj, chart_series)
                self.dbId = chartId
                return True
        else:
            return False
    
    def loadGraphDescription(self, dbId):
        def onLoadDefinitionSuccess(result):
            log.debug('loaded graph definition')
            log.debug(result)
            if result:
                self.g_owner = int(result[0])
                self.engine = result[1]
                self.name = result[2]
                self.title = result[3]
                self.privacy = result[4]
                self.ctype = result[5]
                self.durMod = result[6]
                self.durLen = result[7]
                self.durUnit = result[8]
                if int(result[9]) == 0:
                    self.start = 'Now'
                else:
                    self.start = int(result[9])
                self.owner.setGraphEventType(result[10], self)
                return True
            else:
                return False
        def onFailure(reason):
            log.error('onloadgraph: %s' % reason)
            return False
        # loads graph description from the database
        self.dbId = int(dbId)
        d = txdbinterface.loadGraphDefinition(self.dbId)
        d.addCallbacks(onLoadDefinitionSuccess,onFailure)
        return d
    
    def loadGraphSeries(self, dbId):
        def onLoadSeriesSuccess(result):
            log.debug('loaded graph series')
            log.debug(result)
            if result:
                for row in result:
                    data_node, host, service, metric = row
                    self.previousSeries = graphSeries = [data_node, host, service, metric]
                    self.seriesCounter += 1
                    series_index = str(self.seriesCounter)
                    self.series.append(series_index)
                    self.seriesTracker[series_index] = graphSeries
                    self.selected_node = self.selected_host = self.selected_service = self.selected_metric = None
                    self.metricSeries = []
                for sel_series in self.series:
                    self.metricSeries.append(self.seriesTracker[sel_series][:])            
                return True
            else:
                return False
        def onFailure(reason):
            log.error('loadgraphseries: %s' % reason)
            return False
        dbId = int(dbId)
        d = txdbinterface.loadGraphSeries(dbId)
        d.addCallbacks(onLoadSeriesSuccess,onFailure)
        return d
    
    def loadGraphParams(self, dbId):
        def onLoadParamSuccess(result):
            log.debug('loaded graph parameters')
            log.debug(result)
            if result:
                return True
            else:
                return False
        def onFailure(reason):
            log.error('loadgraphparams: %s' % reason)
            return False
        dbId = int(dbId)
        d = txdbinterface.loadGraphParameters(dbId)
        d.addCallbacks(onLoadParamSuccess,onFailure)
        return d
        
    def setRegexp(self, field, patt):
        if field == 'd':
            self.domRegexp = patt
        elif field == 'h':
            self.hostRegexp = patt
        elif field == 's':
            self.svcRegexp = patt
        elif field == 'm':
            self.metRegexp = patt
        else:
            log.debug('unknown field for regexp')
    
    def getRegexp(self):
        return (self.domRegexp, self.hostRegexp, self.svcRegexp, self.metRegexp)
        