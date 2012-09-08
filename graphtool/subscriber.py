#!/usr/bin/python

from twisted.internet import defer
from twisted.internet.task import LoopingCall
import json, time, datetime, re
import utils, opsview, txdbinterface, graph, authentication, emailhelper

log = utils.get_logger("SubscriberService")

PASS_MSG = '''Hi,\n\n Your graphtool password has been reset to a temporary password.\n\n You will be forced to change your password when you try to login with this temporary password.\n\n The temporary password is:%s \n\nSincerely,\nThe Graphtool Team '''
SMTP_HOST      = utils.config.get('mail', 'smtp_host')
USE_GMAIL_SMTP = utils.config.get('mail', 'use_gmail')
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

# re-authenticate to opsview every 45 minutes
reauth_timeout = 2700

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
                             'Scatter': 'scatter',
                             'Column': 'column',
                             'Bar': 'bar',
                            }
#graph_size = {}
#graph_size['Small'] = ('600','400')
#graph_size['Medium'] = ('800','600')
#graph_size['Large'] = ('1000','800')
#graph_size['Huge'] = ('1200','1000')
graph_privacy = {}
graph_privacy['Public'] = 0
graph_privacy['Private'] = 2
cfg_sections = utils.config.sections()

subscribers = {}

class subscriber(object):

    def __init__(self, username, password, first_name = None, last_name = None, opsview_creds = []):
        self.username       = username
        self.password       = password
        self.raw_password   = password
        self.salt           = None
        self.first_name     = first_name
        self.last_name      = last_name
        self.force_pass_change = False
        self.opsview_creds  = opsview_creds #[{"server_name":"", "login_id":"", "password":""},{}] 
        self.auth_node_list = {}  # dictionary of node_name: [auth_token, cred_time]
        self.authed         = False
        self.auth_count     = 0
        self.auth_tkt       = None
        self.web_session    = None # this is the opsview web session, not the user's web session
        self.webSession     = None # this is the users web session
        self.currentChart   = None # describes a the current chart being edited 
        self.dbId           = None
        self.chartList      = []
        self.livePageList   = []
        self.liveCharts     = {}
        self.reauth_node_set = set([])

        
    def setPassword(self, password):
        log.debug("subscriber:setPassword:Called")
        try:
            scrambled_passwd = authentication.ScrambledPassword(password, self.salt)
            if scrambled_passwd != self.password:
                scrambled_passwd = authentication.ScrambledPassword(password)
                self.password    = scrambled_passwd.getHashed() 
                self.salt        = scrambled_passwd.getSalt() 
        except authentication.PasswordException, e:
            log.exception("setPassword: Exception - %s"%e.message)
            return defer.fail(e)

        # Scramble the opsview passwords
        if self.opsview_creds:
            for opsview_cred in self.opsview_creds:
                try:
                    crypter = authentication.Crypter()
                    opsview_cred["password"] = crypter.encrypt(opsview_cred["password"], self.raw_password)
                    log.info("setPassword: %s password encrypted"%opsview_cred["server_name"])
                except authentication.CheckSumError, e:
                    log.exception("setPassword: Exception with opsview password for %s - %s"%(opsview_cred["server_name"], e.message))
                    return defer.fail(e)
                except Exception, e:
                    log.exception("setPassword: Exception with opsview password for %s - %s"%(opsview_cred["server_name"], e.message))
                    return defer.fail(e)

        log.debug("setPassword: Exiting with opsviewcreds %s"%self.opsview_creds)
        return defer.succeed(True)

    def checkPassword(self):
        log.debug("subscriber:checkPassword:Called")
        try:
            #log.debug("subscriber:checkPassword:raw_password=%s password=%s salt=%s"%(self.raw_password, self.password, self.salt))
            scrambled_passwd = authentication.ScrambledPassword(self.raw_password, self.salt)
            if scrambled_passwd != self.password:
                return defer.fail("Password does not match")
        except authentication.PasswordException, e:
            log.exception("checkPassword: Exception - %s"%e.message)
            return defer.fail(e)
        return defer.succeed(True)

    def setup(self):
        ''' Create a new subscriber in the DB '''
        
        log.debug("subscriber:setup:Called")

        def onPassSuccess(result):
            log.debug("+++++ onPassSuccess +++++++")
            log.debug("setup: Password valid. Now store in DB. Result = %s"%str(result))
            # Store the sub into the DB
            d = txdbinterface.createUser(self)
            d.addCallbacks(self.onCreateSuccess, self.onCreateFailure)
            return d

        def onPassFailure(failure):
            log.debug("+++++ onPassFailure +++++++")
            log.error("create: Password failure - %s"%failure)
            return failure

        # set the password
        d = self.setPassword(self.password)
        d.addCallback(onPassSuccess)
        d.addErrback(onPassFailure)

        return d

    def onCreateSuccess(self, result):
        log.debug('onCreateSuccess: got db id %s' % result)
        self.dbId = result
        return self.dbId
             
    def onCreateFailure(self, failure):
        log.error("onCreateFailure: Error creating subscriber - %s"%failure)
        return failure

    def _setTouchTime_decorator(target_function):

        def wrapper(self, *args, **kwargs):
            lastTouched = int(time.time() - self._touchTime)
            self._touchTime = int(time.time())
            return target_function(self, *args, **kwargs)
        return wrapper

    def login(self):
        d = txdbinterface.getUserData(self.username)
        d.addCallbacks(self.onRetreiveSuccess, self.onRetreiveFailure)
        log.debug('login: subscriber %s initialized' % self.username)
        return d

    def _setSubscriber(self, user_record):
        self.dbId              = user_record[0][0]
        self.username          = user_record[0][1]
        self.password          = user_record[0][2]
        self.salt              = user_record[0][3]
        self.first_name        = user_record[0][4]
        self.last_name         = user_record[0][5]
        self.force_pass_change = user_record[0][6]

    def onRetreiveSuccess(self, result):
        log.debug('onRetreiveSuccess: got db id %s' % result)
        if result and type(result) != type(bool()):
            self._setSubscriber(result)
            # Check if we need to force password reset
            if self.force_pass_change:
                return defer.fail(authentication.ForcePasswordChange("Please change your password"))
            d =  self.checkPassword()
            d.addCallback(self.onLoginSuccess)
            d.addErrback(self.onLoginFailure)
            return d
        return defer.fail("Unable to retreive user")

    def onRetreiveFailure(self, failure):
        log.debug("++++++ OnRetreiveFailure ++++++")
        log.error(failure)
        return failure

    def onLoginSuccess(self, result):
        log.debug("++++++ onLoginSuccess ++++++")
        subscribers[self.username] = self
        d =  txdbinterface.getOpsviewUserData(self.dbId)
        d.addCallback(self.onLoginComplete)
        d.addErrback(self.onLoginCompleteFailure)

        self._touchTime = int(time.time())
        self.timeoutChecker = LoopingCall(self._checkTimeout)
        self.timeoutChecker.start(5)

        return d

    def onLoginFailure(self, failure):
        log.debug("++++++ onLoginFailure ++++++")
        log.error(failure)
        return failure

    def _setSubscriberOpsviewData(self, opsview_records):
        for record in opsview_records:
            opsview_cred = {}
            opsview_cred["server_name"] = record[0]
            if type(opsview_cred["server_name"]) is unicode:
                opsview_cred["server_name"] = opsview_cred["server_name"].encode('utf-8')
            opsview_cred["login_id"]    = record[1]
            if type(opsview_cred["login_id"]) is unicode:
                opsview_cred["login_id"] = opsview_cred["login_id"].encode('utf-8')
            opsview_cred["password"]    = record[2]
            if type(opsview_cred["password"]) is unicode:
                opsview_cred["password"] = opsview_cred["password"].encode('utf-8')
            self.opsview_creds.append(opsview_cred)
            log.debug("subscriber: Retrieved opsview_cred - %s"%opsview_cred)

    @_setTouchTime_decorator
    def onLoginComplete(self, result):
        log.debug("++++++ OnLoginComplete ++++++")
        if result and type(result).__name__ == 'list':
            self._setSubscriberOpsviewData(result)
        return self

    def onLoginCompleteFailure(self, failure):
        log.debug("++++++ OnLoginCompleteFailure ++++++")
        log.error(failure)
        log.debug("User does not have any opsview credentials!")
        return True

    def updatePassword(self, new_password, opsview_creds):
        ''' Update the password, and rejigger the opsview credentials '''

        def onRetreiveSuccess(result, opsview_creds):
            log.debug('updatePassword: onRetreiveSuccess: got db id %s' % result)
            if result and type(result) != type(bool()):
                self._setSubscriber(result)
                # Check if old password is right
                d =  self.checkPassword()
                d.addCallback(onLoginSuccess, opsview_creds)
                d.addErrback(onLoginFailure)
                return d
            return defer.fail("Unable to retreive user")

        def onRetreiveFailure(failure):
            log.debug("updatePassword: ++++++ OnRetreiveFailure ++++++")
            log.error(failure)
            return failure

        def onLoginSuccess(result, opsview_creds):
            log.debug("updatePassword: ++++++ OnLoginSuccess ++++++")
            self.opsview_creds = opsview_creds
            d = self.resetPassword(new_password)
            d.addCallback(onPassChangeSuccess)
            d.addErrback(onPassChangeFailure)
            return d

        def onLoginFailure(failure):
            log.debug("updatePassword: ++++++ OnLoginFailure ++++++")
            log.error(failure)
            return failure

        def onPassUpdateSuccess(result):
            log.debug("++++++ onPassUpdateSuccess +++++") 
            log.debug("store opsview creds result = %s"%result)
            return True

        def onPassUpdateFailure(failure):
            log.debug("++++++ onPassUpdateFailure +++++") 
            return failure

        def onPassChangeSuccess(result):
            log.debug("++++++ onPassChangeSuccess +++++") 
            d = txdbinterface.storeOpsviewCreds(self)
            d.addCallback(onPassUpdateSuccess)
            d.addErrback(onPassUpdateFailure)
            return d

        def onPassChangeFailure(failure):
            log.debug("++++++ onPassChangeFailure +++++") 
            return failure

        # First get the user record and login with old password
        d = txdbinterface.getUserData(self.username)
        d.addCallback(onRetreiveSuccess, opsview_creds)
        d.addErrback(onRetreiveFailure)

        return d

    def resetPassword(self, new_password = None):
            
        def onResetSuccess(result, new_pass):
            log.debug("++++++ onResetSuccess +++++") 
            if not new_pass:
                email_helper = emailhelper.EmailSender("noreply@graphtool.com", 
                                                       self.username, 
                                                       "Your Graphtool password has been reset", 
                                                       PASS_MSG%self.raw_password)
                                                       #"%s %s"%(PASS_MSG, self.raw_password))
                if USE_GMAIL_SMTP:
                    log.debug("Sending gmail ... - %s"%USE_GMAIL_SMTP)
                    email_helper.gmail_send()
                else:
                    log.debug("Sending email ...")
                    email_helper.send(SMTP_HOST)
            return True

        def onResetFailure(failure):
            log.debug("++++++ onResetFailure +++++")
            return failure

        def onPassSetSuccess(result, new_pass):
            log.debug("++++++ onPassSetSuccess +++++")
            if not new_pass:
                self.force_pass_change = True
            else:
                self.force_pass_change = False
            d = txdbinterface.storePassword(self)
            d.addCallback(onResetSuccess, new_pass)
            d.addErrback(onResetFailure)
            return d

        def onPassSetFailure(failure):
            log.debug("++++++ onPassSetFailure +++++")
            return failure 

        def onGetUserSuccess(result, new_pass):
            log.debug("++++++ onGetUserSuccess +++++")
            if result and type(result) != type(bool()):
                self._setSubscriber(result)
                if not new_pass:
                    temp_pass = utils.pass_generate()
                else:
                    temp_pass = new_pass
                self.raw_password = temp_pass
                d = self.setPassword(temp_pass)
                d.addCallback(onPassSetSuccess, new_pass)
                d.addErrback(onPassSetFailure)
                return d
            return defer.fail("Unable to find user")

        def onGetUserFailure(failure):
            log.debug("++++++ onGetUserFailure +++++")
            log.error(failure)
            return failure
        d = txdbinterface.getUserData(self.username)
        d.addCallback(onGetUserSuccess, new_password)
        d.addErrback(onGetUserFailure)
        return d

    def isDuplicate(self):
        ''' Check if subscriber with same username exisits in DB '''

        def onIsDuplicateSuccess(result):
            if result and type(result) != type(bool()):
       	        return True
            return False

        def onIsDuplicateFailure(failure):
            log.error(failure)
            return failure

        log.debug("isDuplicate: called")
        d = txdbinterface.getUserData(self.username)
        d.addCallbacks(onIsDuplicateSuccess, onIsDuplicateFailure)
        return d
        
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
        
    def registerLiveElement(self, liveElement, chart=None, chartId=None):
        if liveElement not in self.livePageList:
            # Register a new Live Element 
            self.livePageList.append(liveElement)
            self.liveCharts[liveElement] = []
            if chart:
                # Register a new live chart for updating with new data
                if chart not in self.liveCharts:
                    self.liveCharts[liveElement].append(chart)
                else:
                    log.debug('liveUpdate requested for an element already in my update list')
                # Let the chart object know it's live - it will be responsible for getting fresh data
                # and sending it to the live element
                chart.addLiveElement(liveElement, chartId)
        elif chart:
            # Let the chart object know it's live
            self.liveCharts[liveElement].append(chart)
            chart.addLiveElement(liveElement,chartId)
                
    
    def unregisterLiveElement(self, liveElement):
        # if this live element was registered, we remove it now
        if liveElement in self.livePageList:
            tmp = self.livePageList.remove(liveElement)
            if liveElement in self.liveCharts:
                # if the live element had any live charts, clear them as well
                for chart in self.liveCharts[liveElement]:
                    # let the chart object know that it's no longer live for this element
                    chart.cancelLiveElement(liveElement)
                tmp = self.liveCharts.pop(liveElement, None)
        
    def isAuthed(self):
        return self.authed

    def getUsername(self):
        username = self.username        
        if type(username) is unicode:
            username = username.encode('utf-8')
        return username

    def checkCredentials(self, selected_node):
        def onSuccess(result):
            log.debug('result: %s' % result)
            return result
        def onFailure(reason):
            log.error(reason)
            return False
        opsview_login, opsview_pass = self._getOpsviewCredentials(selected_node)
        creds = {'X-Opsview-Username': opsview_login, 'X-Opsview-Token': token}
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
    def _getOpsviewCredentials(self, node):
        login_id = None
        raw_password = None
        crypter = authentication.Crypter()
        if node:
            for opsview_cred in self.opsview_creds:
                if opsview_cred["server_name"] == node:
                    login_id = opsview_cred["login_id"]
                    try:
                        raw_password = crypter.decrypt(opsview_cred["password"], self.raw_password)
                        if type(raw_password) is unicode:
                            raw_password = raw_password.encode('utf-8')
                        #log.info("_getOpsviewCredentials: %s password decrypted - %s"%(opsview_cred["server_name"], raw_password))
                    except authentication.CheckSumError, e:
                        log.exception("_getOpsviewCredentials: Exception with opsview password for %s - %s"%(opsview_cred["server_name"], e.message))
                        raw_password = None
                    except Exception, e:
                        log.exception("_getOpsviewCredentials: Exception with opsview password for %s - %s"%(opsview_cred["server_name"], e.message))
                        raw_password = None
    
        return (login_id, raw_password)

    @_setTouchTime_decorator
    def authenticateNode(self, auth_node):
        def onLogin(result, auth_node):
            if result:
                log.debug('Got login result for user login: %s' % self.username)
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
                return login_result
                #return defer.succeed(True)
            else:
                log.debug('attempting re-auth')
                opsview_login, opsview_pass = self._getOpsviewCredentials(auth_node)
                login_result = opsview.node_list[auth_node].loginUser(opsview_login, opsview_pass)
        else:
            log.debug('authenticating new node')
            opsview_login, opsview_pass = self._getOpsviewCredentials(auth_node)
            login_result = opsview.node_list[auth_node].loginUser(opsview_login, opsview_pass)
        return login_result.addCallback(onLogin, auth_node).addErrback(onError)
        
    @_setTouchTime_decorator
    def authenticateNodes(self):
        def onSuccess(result):
            log.debug("++++++++++++++ authenticateNodes onSuccess +++++++++++")
            log.debug('returning login request result: %s' % self.authed)
            return self.authed
        def onNodeSuccess(result):
            log.debug("++++++++++++++ authenticateNodes onNodeSuccess +++++++++++")
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
            log.debug("++++++++++++++ authenticateNodes onFailure +++++++++++")
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

    def checkNodes(self, chart):
        ''' Validate all nodes required by all the graphs are healthy '''
        log.debug("subscriber:checkNodes: called")

        def onNodeReauthSuccess(result, node_name):
            ''' REauth succeeded '''
            log.debug("subscriber:checkNodes:onNodeReauthSuccess for %s result=%s"%(node_name,result))
            if node_name in self.reauth_node_defers_dict:
                defers_list = self.reauth_node_defers_dict[node_name]
                # fire all deferreds for this node
                for d in defers_list:
                    d.callback(result)
            else:
                log.debug("subscriber:checkNodes:onNodeReauthSuccess for %s . Strangely no deferreds waiting on this node!"%(node_name))
            # Finished processing reauth for this node, remove from reauth node set
            log.debug("subscriber:onNodeReauthSuccess set=%s"%self.reauth_node_set)
            log.debug("subscriber:checkNodes:onNodeReauthSuccess dict = %s"%self.reauth_node_defers_dict)
            if node_name in self.reauth_node_set:
                self.reauth_node_set.remove(node_name)
            if node_name in self.reauth_node_defers_dict:
                del(self.reauth_node_defers_dict[node_name])
            log.debug("subscriber:checkNodes:onNodeReauthSuccess set after delete = %s"%self.reauth_node_set)
            log.debug("subscriber:checkNodes:onNodeReauthSuccess dict after delete = %s"%self.reauth_node_defers_dict)
            return None

        def onNodeReauthFail(failure, node_name):
            ''' REauth failed '''
            log.debug("subscriber:checkNodes:onNodeReauthFail for %s result=%s"%(node_name,failure))
            if node_name in self.reauth_node_defers_dict:
                defers_list = self.reauth_node_defers_dict[node_name]
                # fire all deferreds for this node
                for d in defers_list:
                    d.errback(failure)
            else:
                log.debug("subscriber:checkNodes:onNodeReauthFail for %s . Strangely no deferreds waiting on this node!"%(node_name))
            return None

        self.reauth_node_set = set([])
        self.reauth_node_defers_dict = {} #{"kixeye":[d1,d2], "netgeeks":[d1,d2,d3]}
        for row in chart.getSeries():
            data_node, host, service, metric = chart.getSeriesTracker(row)
            log.debug("subscriber:checkNodes: Processing %s"%data_node)
            if data_node not in self.reauth_node_set:
                log.debug("subscriber:checkNodes: Not in reauth_node_set %s"%data_node)
                # Fresh node needs reauth
                d = self.authenticateNode(data_node)
                if type(d) == type(bool()):
                    log.debug("subscriber:checkNodes: No need to reauth at all for %s"%data_node)
                    continue
                d.addCallback(onNodeReauthSuccess, data_node)
                d.addErrback(onNodeReauthFail, data_node)
                '''
                # put deferred in deferreds storage
                if data_node in reauth_node_defers_dict:
                    reauth_node_defers_dict[data_node].append(d)
                else:
                    # very first one
                    reauth_node_defers_dict[data_node] = [d]
                '''
                # indicate that this node is already in queue for re-auth
                self.reauth_node_set.add(data_node)
            else:
                log.debug("subscriber:checkNodes: Already in reauth_node_set %s"%data_node)

            log.debug("subscriber:checkNodes loop set=%s"%self.reauth_node_set)

            d_dummy = defer.Deferred() # just a dummy deferred to hold on to
            # put deferred in deferreds storage
            if data_node in self.reauth_node_defers_dict:
                self.reauth_node_defers_dict[data_node].append(d_dummy)
            else:
                self.reauth_node_defers_dict[data_node] = [d_dummy]
            
            log.debug("subscriber:checkNodes loop reauth_node_defers_dict=%s"%self.reauth_node_defers_dict)

        # prepare the final list of defers for all reauths
        reauth_node_defers_list = []
        for key, value in self.reauth_node_defers_dict.iteritems():
            reauth_node_defers_list.extend(value)
        log.debug("subscriber:checkNodes:Final list of deferreds = %s"%reauth_node_defers_list)
        dlist = defer.DeferredList(reauth_node_defers_list, consumeErrors=True)
        return dlist
         

    @_setTouchTime_decorator
    def makeGraph(self, chart, returnData=True, end_time=None, extendCache=False, skipODW=False):

        ######### DEBUG SIMULATE #########
        #self.auth_node_list = {}
        ######### DEBUG SIMULATE #########
        log.debug('subscriber:makeGraph called - subscribers auth_list is %s' % self.auth_node_list)


        def onReAuthSuccess(result, chart, returnData=returnData, end_time=end_time, extendCache=extendCache, skipODW=skipODW):
            log.debug("subscriber:makeGraph: onReAuthSuccess reuslt=%s"%result)
            log.debug('graphing the following series: %s' % chart.getSeries())
            ds = []
            for row in chart.getSeries():
                result = self._fetchMetricData(chart, row, returnData, end_time, extendCache, skipODW)
                if result:
                    result.addCallback(onSeriesSuccess, row)
                    ds.append(result)
                else:
                    log.debug('oops, somehow our fetchMetricData request failed for row -'%row)
            d = defer.DeferredList(ds, consumeErrors=False)
            d.addCallbacks(onTotalSuccess, onTotalFailure)
            return d

        def onReAuthFail(failure, chart, returnData=returnData, end_time=end_time, extendCache=extendCache, skipODW=skipODW):
            log.debug("subscriber:makeGraph: onReAuthFail failure=%s"%failure)
       
        def onSeriesSuccess(result, series_id):
            log.debug('subscriber:makeGraph:onSeriesSuccess:sending data to chart object series_id=%s'%(series_id))
            chart.setSeriesData(series_id, result)

        def onTotalSuccess(result):
            log.debug('subscriber:makeGraph:onTotalSuccess: got all results!')
            return chart.getSeriesData()

        def onTotalFailure(reason):
            log.error("subscriber:makeGraph:onTotalFailure: reason=%s"%reason)
            return False

        # First check the nodes are fine
        chart.setSeriesData()
        chart.setDataNodes([])
        d = self.checkNodes(chart)
        d.addCallback(onReAuthSuccess, chart, returnData, end_time, extendCache, skipODW)
        d.addErrback(onReAuthFail, chart, returnData, end_time, extendCache, skipODW)

        return d

    def _fetchMetricData(self, chart, row, returnData=True, end_time=None, extendCache=False, skipODW=False):
        log.debug("subscriber:_fetchMetricData called")
        data_node, host, service, metric = chart.getSeriesTracker(row)

        log.debug('trying to grab four items from %s' % chart.getSeriesTracker(row))

        if data_node not in chart.getDataNodes():
            chart.addDataNode(data_node)

        opsview_login, opsview_pass = self._getOpsviewCredentials(data_node)
        creds = {'X-Opsview-Username': opsview_login, 'X-Opsview-Token': self.auth_node_list[data_node][0]}
        cookies = {'auth_tkt': self.auth_tkt}
        api_uri = '%s::%s::%s' % (host, service, metric)
        chart.setSeriesUri(row, data_node, api_uri)
        if not extendCache:
            log.debug('calculating end time')
            end_time,duration = chart.calculateGraphPeriod()
            durSet = (chart.getChartDurationModifier(), chart.getChartDurationLength(), chart.getChartDurationUnit())
            endTime = startTime = None
        elif end_time:
            startTime = opsview.node_list[data_node].getMaxCacheTimeValue(host, service, metric) + 1
            endTime = end_time
            durSet = None
            log.debug('end time provided by calling party')
        else:
            startTime = opsview.node_list[data_node].getMaxCacheTimeValue(host, service, metric) + 1
            end_time = endTime = int(time.time())
            durSet = None
            log.debug('end set to now, no need to calculate')
        log.debug('end time: %s' % end_time )
        log.debug('startTime: %s' % startTime)
        log.debug('endTime: %s' % endTime)
        #result = opsview.node_list[data_node].fetchData(api_uri, end_time, duration, creds, cookies, (host, service, metric))
        result = defer.maybeDeferred(opsview.node_list[data_node].fetchData, api_uri, end_time, creds=creds, cookies=cookies, hsm=(host, service, metric), durSet=durSet, endTime=endTime, startTime=startTime, returnData=returnData, skipODW=skipODW, dataSubscriber=chart)
        return result

    '''
    def _makeGraph(self, result, chart, returnData, end_time, extendCache, skipODW):
        """ called from makeGraph when authentication has failed during a graph build"""
        return self.makeGraph(chart, returnData, end_time, extendCache, skipODW)

    @_setTouchTime_decorator
    def makeGraph(self, chart, returnData=True, end_time=None, extendCache=False, skipODW=False):
        def onTotalSuccess(result):
            log.debug('got all results!')
            return chart.getSeriesData()
        def onSeriesSuccess(result, series_id):
            log.debug('sending data to chart object')
            chart.setSeriesData(series_id, result)
        def onFailure(reason):
            log.error(reason)
            return False
        ds = []
        chart.setSeriesData()
        chart.setDataNodes([])
        log.debug('graphing the following series: %s' % chart.getSeries())
        for row in chart.getSeries():
            result = self._fetchMetricData(chart, row, returnData, end_time, extendCache, skipODW)
            if result:
                result.addCallback(onSeriesSuccess, row)
                ds.append(result)
            else:
                log.debug('oops, somehow our fetchMetricData request failed')
        d = defer.DeferredList(ds, consumeErrors=False)
        d.addCallbacks(onTotalSuccess, onFailure)
        return d

    def _reFetchMetricData(self, result, chart, row, returnData, end_time, extendCache, skipODW):
        # called from _fetchMetricData when a node re-auth is required
        return self._fetchMetricData(chart, row, returnData=returnData, end_time=end_time, extendCache=extendCache, skipODW=skipODW)

    def _fetchMetricData(self, chart, row, returnData=True, end_time=None, extendCache=False, skipODW=False):
        data_node, host, service, metric = chart.getSeriesTracker(row)
        if data_node not in self.auth_node_list:
            log.debug('Requested data node is not in our authed node list - attempting re-auth')
            d = self.authenticateNode(data_node)
            d.addCallback(self._reFetchMetricData, chart, row, returnData=returnData, end_time=end_time, extendCache=extendCache, skipODW=skipODW).addErrback(self.onFailure)
            return d
        log.debug('trying to grab four items from %s' % chart.getSeriesTracker(row))
        log.debug('subscribers auth_list is %s' % self.auth_node_list)
        try:
            cred_token, cred_time = self.auth_node_list[data_node]
        except:
            log.error("subscriber: makeGraph: Cannot get cred_token for data_node=%s"%data_node)
            return None
        if time.time() > (cred_time + reauth_timeout):
            # if we have exceeded our auth time, force a re-authentication.
            d = self.authenticateNode(data_node)
            log.debug('re-authentication requested')
            d.addCallback(self._makeGraph, chart, returnData, end_time, extendCache, skipODW).addErrback(self.onFailure)
            return d
        if data_node not in chart.getDataNodes():
            chart.addDataNode(data_node)
        opsview_login, opsview_pass = self._getOpsviewCredentials(data_node)
        creds = {'X-Opsview-Username': opsview_login, 'X-Opsview-Token': self.auth_node_list[data_node][0]}
        cookies = {'auth_tkt': self.auth_tkt}
        api_uri = '%s::%s::%s' % (host, service, metric)
        chart.setSeriesUri(row, data_node, api_uri)
        if not extendCache:
            log.debug('calculating end time')
            end_time,duration = chart.calculateGraphPeriod()
            durSet = (chart.getChartDurationModifier(), chart.getChartDurationLength(), chart.getChartDurationUnit())
            endTime = startTime = None
        elif end_time:
            startTime = opsview.node_list[data_node].getMaxCacheTimeValue(host, service, metric) + 1
            endTime = end_time
            durSet = None
            log.debug('end time provided by calling party')
        else:
            startTime = opsview.node_list[data_node].getMaxCacheTimeValue(host, service, metric) + 1
            end_time = endTime = int(time.time())
            durSet = None
            log.debug('end set to now, no need to calculate')
        log.debug('end time: %s' % end_time )
        log.debug('startTime: %s' % startTime)
        log.debug('endTime: %s' % endTime)
        #result = opsview.node_list[data_node].fetchData(api_uri, end_time, duration, creds, cookies, (host, service, metric))
        result = defer.maybeDeferred(opsview.node_list[data_node].fetchData, api_uri, end_time, creds=creds, cookies=cookies, hsm=(host, service, metric), durSet=durSet, endTime=endTime, startTime=startTime, returnData=returnData, skipODW=skipODW)
        return result
    '''
        
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
            log.debug('sending start time %s to chart/suite' %  start_time)
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
            log.debug('graph completely loaded')
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
        
###################### Authentication ######################
def isLoggedIn(username):
    if username in subscribers:
        if subscribers[username].isAuthed():
            log.debug('User %s already logged in' % username)
            return True
    return False

def loginSubscriber(username, password):
    if username in subscribers:
        if subscribers[username].isAuthed():
            log.debug('User %s already logged in' % username)
            return defer.fail(authentication.AlreadyLoggedIn("User already logged in."))
        else:
            return subscriber(username, password).login()
    else:
        return subscriber(username, password).login()
        
def createSubscriber(username, password, first_name = None, last_name = None, opsview_creds = None):
    ''' Create a new user in the system '''

    log.debug("subscriber:createSubscriber called")
    if not utils.is_valid_email(username):
        return defer.fail("Invalid login id. Please enter a valid email address")
    new_subscriber = subscriber(username = username,
                                password = password,
                                first_name = first_name,
                                last_name = last_name,
                                opsview_creds = opsview_creds)
    return new_subscriber.setup()

def forgotPassword(username):
    ''' Reset the password to temporary value and send an email '''
    log.debug("subscriber: Resetting password for - %s"%username)
    
    sub = subscriber(username, None)
    return sub.resetPassword()

def updatePassword(username, password, new_password, opsview_creds):
    ''' Save the password and also update opsview credentials '''
    log.debug("subscriber: Updating password for - %s"%username)
    
    sub = subscriber(username, password)
    return sub.updatePassword(new_password, opsview_creds)

def isDuplicate(username):
    ''' Check id username is already taken '''
    #sub = subscriber(username)
    #return sub.isDuplicate()
    return False

###################### Authentication ######################

# Load the defined graph sizes from the config file

graph_size = {}
for section in cfg_sections:
    if section[:10] == 'graphsize_':
        size_name = str(utils.config.get(section, "name"))
        size_width = str(utils.config.get(section, "width"))
        size_height = str(utils.config.get(section, "height"))
        graph_size[size_name] = (size_width,size_height)
