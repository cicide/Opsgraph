#!/usr/bin/python

from zope.interface import implements, Interface, Attribute
from twisted.python import filepath, util
from twisted.internet import defer, ssl
from twisted.application import internet
from twisted.cred import checkers, error as credError
from twisted.cred.portal import Portal, IRealm
from twisted.cred.credentials import IUsernamePassword, IAnonymous
from nevow import appserver, athena, loaders, rend, inevow, guard, inevow, url, static, tags as T
from nevow.inevow import ISession, IRequest
from nevow.athena import expose
import random, os, time, string, json
import utils, subscriber

log = utils.get_logger("WEBService")
trueVals = ('Yes', 'yes', 'True', 'true')
falseVals = ('No', 'no', 'False', 'false')

css_dir = os.path.join(os.path.split(__file__)[0],'css')
img_dir = os.path.join(os.path.split(__file__)[0],'image')
js_dir = os.path.join(os.path.split(__file__)[0],'javascript')

httpport = utils.config.getint("general", "httpport")
sslport = utils.config.getint("general", "sslport")
sslPrivKey = utils.config.get("general", "sslKey")
sslCaCert = utils.config.get("general", "sslCert")
auto_series = utils.config.get("graph", "autocomplete_series")
modal_close = utils.config.get("general", "dialog_autoclose")
if modal_close in (trueVals):
    modal_close = True
else:
    modal_close = False

if auto_series in (trueVals):
    auto_series = True
else:
    auto_series = False

class Mind:
    def __init__(self, request, credentials):
        self.request = request
        self.credentials = credentials

class ISubscriberObject(Interface):
    pass

class opsviewWebChecker:
    implements(checkers.ICredentialsChecker)
    credentialInterfaces = (IUsernamePassword,)
    
    def __init__(self):
        pass
    
    def requestAvatarId(self, credentials):
        def onSuccess(result, sub):
            log.debug('Got login request result: %s' % result)
            if result:
                return defer.succeed(sub)
            else:
                return defer.fail(credError.UnauthorizedLogin("Incorrect Login"))
        def onFailure(reason):
            log.debug(reason)
            return defer.fail(credError.UnauthorizedLogin("Incorrect Login"))
        uname = credentials.username
        passwd = credentials.password
        sub = subscriber.addSubscriber(uname, passwd)
        if not sub:
            # a False value for sub means the user is already logged in
            return defer.fail(credError.LoginDenied("User already logged in."))
        auth_result = sub.authenticateNodes()
        return auth_result.addCallback(onSuccess, sub).addErrback(onFailure)
        
class opsviewRealm(object):
    implements(IRealm)
    
    def __init__(self, pageResource, anonResource):
        self.pageResource = pageResource
        self.anonResource = anonResource
        
    def requestAvatar(self, avatarId, mind, *interfaces):
        log.debug('in requestAvatar')
        for iface in interfaces:
            #if avatarId is checkers.ANONYMOUS:
                #resc = LoginForm()
                #resc.realm = self
                #return (inevow.IResource, resc, lambda: None)
            if avatarId is checkers.ANONYMOUS:
                resc = self.anonResource
                resc.realm = self
                return (inevow.IResource, resc, lambda: None)
            else:
                resc = self.pageResource
                resc.realm = self
                resc.setSubscriber(avatarId)
                return (inevow.IResource, resc, self.createLogout(avatarId, mind))
        log.debug('in not implemented section of requestAvatar')
        raise NotImplementedError()
    
    def createLogout(self, avatarId, mind):
        def logout():
            session = mind.request.getSession()
            l = avatarId.logout()
            session.setComponent(ISubscriberObject, None)
        return logout
            
class TopTabs(rend.Fragment):
    """ Navigation bar """

    def __init__(self):
        rend.Fragment.__init__(self)
        
    def child_createGraph(self, ctx):
        return ExternalPage()
    
    def child_loadGraph(self, ctx):
        return LoadGraphPage()
    
    def child_viewGraph(self, ctx):
        return ViewGraphPage()
    
    def child_loadSuite(self, ctx):
        return LoadSuitePage()
    
    def child_createSuite(self, ctx):
        return ViewSuitesPage()
    
    def child_rootPage(self, cts):
        return RootPage()

    
    docFactory = loaders.stan(
        T.div(id="navbar")[
            T.span(class_="inbar")[
                T.ul(class_="menu_tabbed")[
                    T.li[
                        T.a(href="/")[
                            T.span["Home"]
                        ]
                    ],
                    T.li[
                        T.a(href='/createGraph')[
                            T.span["Build a Graph"]
                        ]
                    ],
                    T.li[
                        T.a(href='/createSuite')[
                            T.span["Build a Suite"]
                        ]
                    ],
                    T.li[
                        T.a(href='/loadGraph')[
                            T.span["Load a Graph"]
                        ]
                    ],
                    T.li[
                        T.a(href='/loadSuite')[
                            T.span["Load a Suite"]
                        ]
                    ],
                    T.li[
                        T.a(href='/__logout__')[
                            T.span["Logout"]
                        ]
                    ]
                ]
            ]
        ]
    )
    
class LoginForm(rend.Page):
    """ Minimalist Login Page"""
    
    def __init__(self):
        rend.Page.__init__(self)
        self.remember(self, inevow.ICanHandleNotFound)
    
    def renderHTTP_notFound(self, ctx):
            request = inevow.IRequest(ctx)
            request.redirect('/')
            return ''

# These are for anonymous viewing
    #def child_viewGraph(self, ctx):
        #return ViewGraphPage()
    
    #def child_viewSuite(self, ctx):
        #return ViewSuitesPage()
    
    def _renderErrors(self, ctx, data):
        log.debug('login page context: %s' % ctx)
        log.debug('login page data: %s' % data)
        request = IRequest(ctx)
        log.debug('login request: %s' % request)
        if 'login-failure' in request.args:
            loginError = 'Invalid Login'
        else:
            loginError = ''
        return loginError
    
    addSlash = True
    docFactory = loaders.stan(
        T.html[
            T.head[
                T.title["Opsgraph: Please Login"],
                T.style(type="text/css")[
                    T.comment[""" #outer {
                                  position: absolute;
                                  top: 50%;
                                  left: 0px;
                                  width: 100%;
                                  height: 1px;
                                  overflow: visible;
                                  }

                                  #inner {
                                  width: 300px;
                                  height: 200px;
                                  margin-left: -150px;  /***  width / 2   ***/
                                  position: absolute;
                                  top: -100px;          /***  height / 2   ***/
                                  left: 50%;
                                  }
                                  
                                  .loginErr {text-align: center; color: red; font-weight: bold}
                                  .input-error {border:2px solid red;}"""
                    ]
                ]
            ],
            T.body[
                T.div(id='outer')[
                    T.div(id='inner')[
                        T.form(action=guard.LOGIN_AVATAR, method="post")[
                            T.table[
                                T.tr[
                                    T.td(class_='loginErr', colspan='2') [_renderErrors]
                                ],
                                T.tr[
                                    T.td[ "Username:" ],
                                    T.td[ T.input(type='text', name='username') ],
                                ],
                                T.tr[
                                    T.td[ "Password:" ],
                                    T.td[ T.input(type='password', name='password') ],
                                ],
                                T.tr[
                                    T.td(align='right', colspan='2')[
                                        T.input(type='submit', value='Login')
                                    ]
                                ]
                            ],
                        ]
                    ]
                ]
            ]
        ])
    
class RootPage(rend.Page):
    """Some resource."""

    def __init__(self):
        rend.Page.__init__(self)
        self.subscriber = None
        self.remember(self, inevow.ICanHandleNotFound)

    def renderHTTP_notFound(self, ctx):
        request = inevow.IRequest(ctx)
        request.redirect('/')
        return ''
    
    def render_navBar(self, ctx, data):
        return ctx.tag[TopTabs()]
    
    def setSubscriber(self, sub):
        self.subscriber = sub


    def render_theTitle(self, ctx, data):
        session = ISession(ctx)
        sess_sub = session.getComponent(ISubscriberObject)
        if sess_sub != self.subscriber:
            session.setComponent(ISubscriberObject, self.subscriber)
        username = self.subscriber.getUserName()
        self.subscriber.registerAvatarLogout(session)
        return 'Opsgraph: Main Menu'
    
    def child_createGraph(self, ctx):
        return ExternalPage()
    
    def child_loadGraph(self, ctx):
        return LoadGraphPage()
    
    def child_viewGraph(self, ctx):
        return ViewGraphPage()
    
    def child_loadSuite(self, ctx):
        return LoadSuitePage()
    
    def child_createSuite(self, ctx):
        return ViewSuitesPage()

    addSlash = True
    child_css = static.File('css')
    child_images = static.File('image')
    child_fusioncharts = static.File('fusioncharts')
    child_highcharts = static.File('highcharts')
    child_javascript = static.File('javascript')
    
    docFactory = loaders.stan(
        T.html[
            T.head[
                T.title[render_theTitle],
                T.link(type='text/css', href='css/opsgraph.css', rel='Stylesheet'),
                T.style(type="text/css")[
                    T.comment[""" #outer {
                                  position: absolute;
                                  top: 50%;
                                  left: 0px;
                                  width: 100%;
                                  height: 1px;
                                  overflow: visible;
                                  }

                                  #inner {
                                  width: 300px;
                                  height: 200px;
                                  margin-left: -150px;  /***  width / 2   ***/
                                  position: absolute;
                                  top: -100px;          /***  height / 2   ***/
                                  left: 50%;
                                  }"""
                    ]
                ]
            ],
            T.body[
                T.div[render_navBar]
                #T.div(id='outer')[
                    #T.div(id='inner')[
                        #T.div(align='center')[T.a(id='createGraph', href=url.here.child('createGraph'))['Create a Graph']],
                        #T.p[''],
                        #T.div(align='center')[T.a(id='createSuite', href=url.here.child('createSuite'))['Create a Suite']],
                        #T.p[''],
                        #T.div(align='center')[T.a(id='loadGraph', href=url.here.child('loadGraph'))['Load a Graph']],
                        #T.p[''],
                        #T.div(align='center')[T.a(id='loadSuite', href=url.here.child('loadSuite'))['Load a Graph Suite']],
                        #T.p[''],
                        #T.div(align='center')[T.a(href=url.here.child(guard.LOGOUT_AVATAR))['Logout']]
                    #]
                #]
            ]
        ]
    )
    
class ViewGraphPage(athena.LivePage):
    
    def __init__(self, *a, **kw):
        super(ViewGraphPage, self).__init__(*a, **kw)
        modulePath = filepath.FilePath(__file__).parent().child('js').child('graphtool_view.js')
        self.jsModules.mapping.update( {'ViewGraphs': modulePath.path} )
        
    def render_theTitle(self, ctx, data):
        return 'Opsgraph: View Graph'

    def render_navBar(self, ctx, data):
        return ctx.tag[TopTabs()]
    
    def render_viewGraphsElement(self, ctx, data):
        session = ISession(ctx)
        request = IRequest(ctx)
        log.debug(request)
        if 'cid' in request.args:
            chart_dbId = request.args['cid'][0]
        else:
            chart_dbId = 0
        log.debug('got chart id: %s' % chart_dbId)
        subscriber = session.getComponent(ISubscriberObject)
        d = self.notifyOnDisconnect()
        f = ViewGraphsElement(subscriber, chart_dbId, d)
        f.setFragmentParent(self)
        return ctx.tag[f]
    
    docFactory = loaders.stan(
        T.html[
            T.title[render_theTitle],
            T.head(render=T.directive('liveglue'))[
                T.link(type='text/css', href='css/jquery-ui.css', rel='Stylesheet'),
                T.link(type='text/css', href='css/opsgraph.css', rel='Stylesheet'),
                T.script(type='text/javascript', src='javascript/jquery-1.6.2.min.js'),
                T.script(type='text/javascript', src='javascript/jquery-ui-1.8.16.custom.min.js'),
                T.script(type='text/javascript', src='fusioncharts/FusionCharts.js'),
                T.script(type='text/javascript', src='highcharts/highcharts.js')
            ],
            T.body(render=T.directive('viewGraphsElement'))[
                T.div(id='graphArea')
            ]
        ]
    )
    
class ViewGraphsElement(athena.LiveElement):
    
    def __init__(self, subscriber, chart_dbId, disc_defer, *a, **kw):
        super(ViewGraphsElement, self).__init__(*a, **kw)
        self.subscriber = subscriber
        self.chart_dbId = chart_dbId
        disc_defer.addCallbacks(self.discon,self.discon)
        self.subscriber.registerLiveElement(self)
        
    def discon(self, result):
        log.debug('this live element has been disconnected')
        self.subscriber.unregisterLiveElement(self)

    def initialize(self):
        def onGraphLoaded(result):
            log.debug(result)
            if result:
                return self.makeGraph(result)
            else:
                return False
        def onFailure(reason):
            log.error(reason)
        log.debug('initialize called')
        d = self.subscriber.loadGraph(self.chart_dbId)
        d.addCallbacks(onGraphLoaded,onFailure)
        return d
    
    def pageQuit(self):
        d = self.callRemote('reDirect', unicode('/'))
        
    def makeGraph(self, chart):
        def onSuccess(result):
            #format the data for fusion charts
            chart_cell = 'graphArea'
            graph_object = self.subscriber.buildMultiSeriesTimeObject(chart, chart_cell, result)
            #log.debug(graph_object)
            graph_settings = self.subscriber.getGraphSettings(chart)
            graph_type = graph_settings['graph_type']
            graph_width = graph_settings['graph_width']
            graph_height = graph_settings['graph_height']
            #TODO: send the new unique Id back to the subscriber so we have access to this chart (need for live chart)
            defChart = getRandString(8)
            if chart.getChartEngine() == 'FusionCharts':
                self.callRemote('addFusionChart', unicode(graph_type), unicode(defChart), unicode('100%'), unicode('100%'), graph_object, unicode(chart_cell))
            elif chart.getChartEngine() == 'HighCharts':
                self.callRemote('addHighChart', graph_object)
            # register this chart as live
            self.subscriber.registerLiveElement(self, chart)
            #self.subscriber.returnToLastChart()
        def onFailure(reason):
            log.error(reason)
        #get the data from opsview for the requested graph
        d = self.subscriber.makeGraph(chart)
        d.addCallbacks(onSuccess,onFailure)

    initialize = expose(initialize)
    jsClass = u'ViewGraphs.ViewGraphWidget'
    docFactory = loaders.stan(
        T.div(render=T.directive('liveElement')))
    
class ViewSuitesPage(athena.LivePage):

    def __init__(self, *a, **kw):
        super(ViewSuitesPage, self).__init__(*a, **kw)
        modulePath = filepath.FilePath(__file__).parent().child('js').child('graphtool_suite.js')
        self.jsModules.mapping.update( {'ViewSuites': modulePath.path} )
        
    def render_theTitle(self, ctx, data):
        return 'Opsgraph: View Suite'
    
    def render_navBar(self, ctx, data):
        request = IRequest(ctx)
        if 'glist' in request.args:
            return ctx.tag[TopTabs()]
        elif 'sid' in request.args:
            if 'perms' in request.args:
                perms = request.args['perms'][0]
                if perms == 'rw':
                    return ctx.tag[TopTabs()]
                else:
                    return ''
            else:
                perms = 'ro'
                return ''
        else:
            return ctx.tag[TopTabs()]
        
    
    def render_viewSuitesElement(self, ctx, data):
        session = ISession(ctx)
        request = IRequest(ctx)
        log.debug(request.args)
        subscriber = session.getComponent(ISubscriberObject)
        d = self.notifyOnDisconnect()
        if 'glist' in request.args:
            # create suite from list of graphs
            glist = request.args['glist'][0]
            g_list = str(glist).split('|')
            log.debug(g_list)
            f = ViewSuitesElement(subscriber, g_list, None, 'rw', d)
        elif 'sid' in request.args:
            # create suite from saved suite
            dbId = request.args['sid'][0]
            if 'perms' in request.args:
                perms = request.args['perms'][0]
            else:
                perms = 'ro'
            f = ViewSuitesElement(subscriber, None, dbId, perms, d)
        else:
            g_list = []
            f = ViewSuitesElement(subscriber, g_list, None, 'rw', d)
        f.setFragmentParent(self)
        return ctx.tag[f]
    
    docFactory = loaders.stan(
            T.html[
                T.title[render_theTitle],
                T.head(render=T.directive('liveglue'))[
                    T.link(type='text/css', href='css/jquery-ui.css', rel='Stylesheet'),
                    T.link(type='text/css', href='css/opsgraph.css', rel='Stylesheet'),
                    T.script(type='text/javascript', src='javascript/jquery-1.6.2.min.js'),
                    T.script(type='text/javascript', src='javascript/jquery-ui-1.8.16.custom.min.js'),
                    T.script(type='text/javascript', src='javascript/jquery-ui-timepicker-addon.js'),
                    T.script(type='text/javascript', src='fusioncharts/FusionCharts.js'),
                    T.script(type='text/javascript', src='highcharts/highcharts.js')
                ],
                T.body(render=T.directive('viewSuitesElement'))[
                    T.div[render_navBar],
                    T.span(width='100%')[
                        T.div(id='suiteControl'),
                        T.div(id='suiteArea')
                    ]
                ]
            ]
        )
    
class ViewSuitesElement(athena.LiveElement):
    
    def __init__(self, subscriber, graph_list, suite_dbId, suite_perms, disc_defer, *a, **kw):
        super(ViewSuitesElement, self).__init__(*a, **kw)
        self.subscriber = subscriber
        if graph_list is not None:
            self.suite = self.subscriber.editSuiteInit(graph_list)
        elif suite_dbId:
            self.suite = self.subscriber.loadSuite(suite_dbId, suite_perms)
        self.suite.registerSubscriber(self)
        self.changeList = []
        disc_defer.addCallbacks(self.discon,self.discon)
        self.subscriber.registerLiveElement(self)
    
    def pageQuit(self):
        d = self.callRemote('reDirect', unicode('/'))

    def discon(self, result):
        log.debug('this live element has been disconnected')
        self.suite.unregisterSubscriber(self)
        self.subscriber.unregisterLiveElement(self)
        
    def updateSuite(self, item, value):
        log.debug('Got suite update request for %s with value of %s' % (item, value))

    def initialize(self):
        def onSuccess(result):
            log.debug('got suite member list: %s' % result)
            g_array = []
            for item in result:
                g_array.append(unicode(item))
            log.debug('member list is %i long' % len(g_array))
            return [g_array, 
                    unicode('suiteArea'),
                    unicode(self.subscriber.getGraphName(self.suite)),
                    unicode(self.subscriber.getGraphTitle(self.suite)),
                    unicode(self.subscriber.getGraphStartTime(self.suite)),
                    unicode(self.subscriber.getGraphDuration(self.suite)),
                    unicode(self.subscriber.getSuiteColumns(self.suite)),
                    modal_close
                    ]
        def onError(reason):
            log.error(reason)
            return False
        log.debug('getting suite member list')
        member_list = self.subscriber.getSuiteMemberList(self.suite)
        member_list.addCallbacks(onSuccess,onError)
        return member_list
    
    def makeGraph(self, chart, dbId):
        def onSuccess(result):
            chart_cell = 'gid%s' % dbId
            chart_uid = '%s-%s' % (chart_cell, str(time.time()))
            #format the data
            graph_object = self.subscriber.buildMultiSeriesTimeObject(chart, chart_cell, result)
            #log.debug(graph_object)
            graph_settings = self.subscriber.getGraphSettings(chart)
            graph_type = graph_settings['graph_type']
            graph_width = graph_settings['graph_width']
            graph_height = graph_settings['graph_height']
            if chart.getChartEngine() == 'FusionCharts':
                self.callRemote('addFusionChart', unicode(chart_cell), unicode(graph_type), unicode(chart_uid), unicode('100%'), unicode('100%'), graph_object)
            elif chart.getChartEngine() == 'HighCharts':
                self.callRemote('addHighChart', graph_object, unicode(dbId))
            # register this graph as live for active updates
            self.subscriber.registerLiveElement(self, chart)
            return True
        def onFailure(reason):
            log.error(reason)
            return False
        # add the graph id and object reference to the suite
        self.subscriber.addSuiteGraph(self.suite, chart, dbId)
        #get the data from opsview for the requested graph
        d = self.subscriber.makeGraph(chart)
        d.addCallbacks(onSuccess,onFailure)    
        
    def tableLoadComplete(self):
        def onMemberList(result):
            for grDbId in result:
                d = self.subscriber.loadGraph(int(grDbId))
                d.addCallback(onGraphLoaded,grDbId).addErrback(onFailure)
                log.debug('building graph id %s' % grDbId)
        def onGraphLoaded(result, grDbId):
            if result:
                self.makeGraph(result, grDbId)
        def onFailure(reason):
            log.error(reason)
        log.debug('table load is complete, collecting graph information')
        suite_permission = self.subscriber.getSuitePermissions(self.suite)
        if suite_permission == 'rw':
            self.callRemote('unhideItem', unicode('suiteControl'))
        elif suite_permission == 'ro':
            self.callRemote('hideItem', unicode('suiteControl'))
            self.callRemote('lockPositions')
        d = self.subscriber.getSuiteMemberList(self.suite)
        d.addCallbacks(onMemberList,onFailure)
    
    def saveSuite(self, suiteList):
        log.debug(suiteList)
        return self.subscriber.saveSuite(suiteList, self.suite)

    def applyOverrides(self):
        def onSuccess(result):
            return True
        def onMakeSuccess(result, dbId, chart):
            chart_cell = 'gid%s' % dbId
            chart_uid = '%s-%s' % (chart_cell, str(time.time()))
            #format the data
            graph_object = self.subscriber.buildMultiSeriesTimeObject(chart, chart_cell, result)
            #log.debug(graph_object)
            graph_settings = self.subscriber.getGraphSettings(chart)
            graph_type = graph_settings['graph_type']
            graph_width = graph_settings['graph_width']
            graph_height = graph_settings['graph_height']
            if chart.getChartEngine() == 'FusionCharts':
                self.callRemote('addFusionChart', unicode(chart_cell), unicode(graph_type), unicode(chart_uid), unicode('100%'), unicode('100%'), graph_object)
            elif chart.getChartEngine() == 'HighCharts':
                self.callRemote('addHighChart', graph_object)
            return True
        def onFailure(reason):
            log.error(reason)
            return False
        chartList = self.subscriber.applySuiteOverrides(self.suite)
        ds = []
        if chartList:
            for chart in chartList:
                chart_id = chart[0]
                chart_obj = chart[1]
                d = self.subscriber.makeGraph(chart_obj)
                d.addCallback(onMakeSuccess, chart_id, chart_obj).addErrback(onFailure)
                ds.append(d)
            d = defer.DeferredList(ds, consumeErrors=True)
            d.addCallbacks(onSuccess,onFailure)
            return d
        else:
            return True
    
    def setItem(self, item, choice):
        if item == 'startTime':
            log.debug('got %s for suite start time' % choice)
            result = self.subscriber.setGraphStartTime(choice, self.suite)
            if result:
                self.changeList.append({'start': choice})
                log.debug('got a valid duration entry')
                #unhide the make graph button, and remove error class
                self.callRemote('clearError', unicode('invalid time duration'), unicode('suiteDuration'))
                self.callRemote('unhideItem', unicode('over4'))
            else:
                log.debug('got an invalid duration entry')
                #hide the make graph button, and add error class
                self.callRemote('displayError', unicode('invalid time duration'), unicode('suiteDuration'))
                self.callRemote('hideItem', unicode('over4'))
        elif item == 'suiteDuration':
            log.debug('got %s for suite start time' % choice)
            result = self.subscriber.setGraphDuration(choice, self.suite)
            if result:
                durMod = result[2]
                durUnit = result[1]
                durLen = result[0]
                self.changeList.append({'durLen': durLen})
                self.changeList.append({'durUnit': durUnit})
                self.changeList.append({'durMod': durMod})
                #unhide the make graph button, and remove error class
                self.callRemote('clearError', unicode('invalid time duration'), unicode('suiteDuration'))
                self.callRemote('unhideItem', unicode('applyOverrideButton'))
            else:
                log.debug('got an invalid duration entry')
                self.callRemote('displayError', unicode('invalid time duration'), unicode('suiteDuration'))
                self.callRemote('hideItem', unicode('applyOverrideButton'))
        elif item == 'suiteName':
            log.debug('got %s for suite name' % choice)
            result = self.subscriber.setGraphName(choice, self.suite)
            if result:
                self.changeList.append({'name': choice})
        elif item == 'suiteDesc':
            log.debug('got %s for suite description' % choice)
            result = self.subscriber.setGraphTitle(choice, self.suite)
            if result:
                self.changeList.append({'title', choice})
        elif item == 'numCols':
            log.debug(' got %s for number of colums' % choice)
            result = self.subscriber.setSuiteColumns(self.suite, choice)
            if result:
                self.changeList.append('numCols', choice)
        else:
            log.debug('got %s for %s' % (choice, item))
            
    initialize = expose(initialize)
    tableLoadComplete = expose(tableLoadComplete)
    saveSuite = expose(saveSuite)
    setItem = expose(setItem)
    applyOverrides = expose(applyOverrides)
    jsClass = u'ViewSuites.ViewSuiteWidget'
    docFactory = loaders.stan(
        T.div(render=T.directive('liveElement')))
    
class LoadSuitePage(athena.LivePage):
    
    def __init__(self, *a, **kw):
            super(LoadSuitePage, self).__init__(*a, **kw)
            modulePath = filepath.FilePath(__file__).parent().child('js').child('graphtool_suite_load.js')
            self.jsModules.mapping.update( {'LoadSuites': modulePath.path} )
        
    def render_theTitle(self, ctx, data):
        return 'Opsgraph: Load Suite'
    
    def render_navBar(self, ctx, data):
        return ctx.tag[TopTabs()]
    
    def render_loadSuitesElement(self, ctx, data):
        session = ISession(ctx)
        subscriber = session.getComponent(ISubscriberObject)
        disco = self.notifyOnDisconnect()
        f = LoadSuitesElement(subscriber, disco)
        f.setFragmentParent(self)
        return ctx.tag[f]
    
    docFactory = loaders.stan(
        T.html[
            T.title[render_theTitle],
            T.head(render=T.directive('liveglue'))[
                T.link(type='text/css', href='css/jquery-ui.css', rel='Stylesheet'),
                T.link(type='text/css', href='css/tablesort.css', rel='Stylesheet'),
                T.link(type='text/css', href='css/opsgraph.css', rel='Stylesheet'),
                T.script(type='text/javascript', src='javascript/jquery-1.6.2.min.js'),
                T.script(type='text/javascript', src='javascript/jquery-ui-1.8.16.custom.min.js'),
                T.script(type='text/javascript', src='javascript/jquery.dataTables.min.js')
            ],
            T.body(render=T.directive('loadSuitesElement'))[
                T.div[render_navBar],
                T.form(name='loadSuiteForm')[
                    T.table(id='loadSuitesTable', class_='sortableTable', width='100%')[
                        T.thead[
                            T.tr[
                                T.th(width='25%')['Name'],
                                T.th(width='45%')['Title'],
                                T.th(width='10%')['Author'],
                                T.th(width='15%')['Birthday'],
                                T.th(id='action_column', width='5%')
                            ]
                        ],
                        T.tbody(id='loadSuitesTableBody')
                    ],
                    T.div(id='form_button_row')
                ]
            ]
        ]
    )

class LoadSuitesElement(athena.LiveElement):
    
    def __init__(self, subscriber, disc_defer, *a, **kw):
        super(LoadSuitesElement, self).__init__(*a, **kw)
        self.subscriber = subscriber
        disc_defer.addCallbacks(self.discon,self.discon)
        self.subscriber.registerLiveElement(self)
    
    def pageQuit(self):
        d = self.callRemote('reDirect', unicode('/'))
    
    def discon(self, result):
        log.debug('this live element has been disconnected')
        self.subscriber.unregisterLiveElement(self)
    
    def initialize(self):
        def onSuccess(result):
            return result # return the result through a deferred
            # self.callRemote('addSuiteListings', result) # old method
        def onFailure(reason):
            log.error(reason)
        # called when the live Element is loaded
        d = self.subscriber.getSavedSuiteList()
        d.addCallbacks(onSuccess,onFailure)
        return d # return the deferred to the client javascript
        
    def viewSuite(self, dbId):
        return False
    
    def editSuite(self, dbId):
        d = self.subscriber.loadSuite(int(dbId), 'rw')
        # format url correctly
        return unicode('/createSuite?sid=%s&perms=rw' % dbId)        
    
    def deleteSuites(self, suite_ids):
        def onSuccess(result, suite_ids):
            return suite_ids
        def onFailure(reason):
            log.error(reason)
        log.debug(suite_ids)
        suiteIds = []
        for suiteId in suite_ids:
            sid = int(suiteId)
            suiteIds.append(sid)
        d = self.subscriber.deleteSuites(suiteIds)
        d.addCallback(onSuccess, suite_ids).addErrback(onFailure)
        return d
    
    initialize = expose(initialize)
    editSuite = expose(editSuite)
    viewSuite = expose(viewSuite)
    deleteSuites = expose(deleteSuites)
    jsClass = u'LoadSuites.LoadSuiteWidget'
    docFactory = loaders.stan(
        T.div(render=T.directive('liveElement')))

class LoadGraphPage(athena.LivePage):
    
    def __init__(self, *a, **kw):
        super(LoadGraphPage, self).__init__(*a, **kw)
        modulePath = filepath.FilePath(__file__).parent().child('js').child('graphtool_load.js')
        self.jsModules.mapping.update( {'LoadGraphs': modulePath.path} )
    
    def render_theTitle(self, ctx, data):
        return 'Opsgraph: Load Graph'
    
    def render_navBar(self, ctx, data):
        return ctx.tag[TopTabs()]
    
    def render_loadGraphsElement(self, ctx, data):
        session = ISession(ctx)
        subscriber = session.getComponent(ISubscriberObject)
        d = self.notifyOnDisconnect()
        f = LoadGraphsElement(subscriber, d)
        f.setFragmentParent(self)
        return ctx.tag[f]
    
    docFactory = loaders.stan(
        T.html[
            T.title[render_theTitle],
            T.head(render=T.directive('liveglue'))[
                T.link(type='text/css', href='css/jquery-ui.css', rel='Stylesheet'),
                T.link(type='text/css', href='css/tablesort.css', rel='Stylesheet'),
                T.link(type='text/css', href='css/opsgraph.css', rel='Stylesheet'),
                T.script(type='text/javascript', src='javascript/jquery-1.6.2.min.js'),
                T.script(type='text/javascript', src='javascript/jquery-ui-1.8.16.custom.min.js'),
                T.script(type='text/javascript', src='javascript/jquery.dataTables.min.js')
            ],
            T.body(render=T.directive('loadGraphsElement'))[
                T.div[render_navBar],
                T.form(name='loadGraphForm')[
                    T.table(id='loadGraphsTable', class_='sortableTable', width='100%')[
                        T.thead[
                            T.tr[
                                T.th(id='all_toggle', width='5%'),
                                T.th(width='15%')['Name'],
                                T.th(width='20%')['Title'],
                                T.th(width='10%')['Author'],
                                T.th(width='15%')['Birthday'],
                                T.th(width='15%')['Engine'],
                                T.th(width='15%')['Type'],
                                T.th(id='action_column', width='5%')
                            ]
                        ],
                        T.tbody(id='loadGraphsTableBody')
                    ],
                    T.div(id='form_button_row')
                ]
            ]
        ]
    )
    
class LoadGraphsElement(athena.LiveElement):
    
    def __init__(self, subscriber, disc_defer, *a, **kw):
        super(LoadGraphsElement, self).__init__(*a, **kw)
        self.subscriber = subscriber
        disc_defer.addCallbacks(self.discon,self.discon)
        self.subscriber.registerLiveElement(self)

    def pageQuit(self):
        d = self.callRemote('reDirect', unicode('/'))

    def discon(self, result):
        log.debug('this live element has been disconnected')
        self.subscriber.unregisterLiveElement(self)
        
    def initialize(self):
        def onSuccess(result):
            self.callRemote('addGraphListings', result)
        def onFailure(reason):
            log.error(reason)
        # called when the live Element is loaded
        d = self.subscriber.getSavedGraphList()
        d.addCallbacks(onSuccess,onFailure)
        return False
        
    def viewGraph(self, grDbId):
        return False
    
    def editGraph(self, grDbId):
        def onGraphLoaded(result):
            if result:
                self.subscriber.setCurrentChart(result)
                self.callRemote('reDirect', unicode('/createGraph'))
        def onFailure(reason):
            log.error(reason)
        d = self.subscriber.loadGraph(int(grDbId))
        d.addCallbacks(onGraphLoaded,onFailure)
        return True
    
    def createSuite(self, graph_ids):
        log.debug(graph_ids)
        if len(graph_ids):
            graph_id_arg = str('|'.join(graph_ids))
            url = '/createSuite?glist=%s' % graph_id_arg
            #self.callRemote('reDirect', unicode(url))
            return unicode(url)
        else:
            return False
        
    def deleteGraphs(self, graph_ids):
        def onSuccess(result, graph_ids):
            return graph_ids
        def onFailure(reason):
            log.error(reason)
        log.debug(graph_ids)
        graphIds = []
        for graphId in graph_ids:
            gid = int(graphId)
            graphIds.append(gid)
        d = self.subscriber.deleteGraphs(graphIds)
        d.addCallback(onSuccess, graph_ids).addErrback(onFailure)
        return d
    
    deleteGraphs = expose(deleteGraphs)
    initialize = expose(initialize)
    editGraph = expose(editGraph)
    viewGraph = expose(viewGraph)
    createSuite = expose(createSuite)
    jsClass = u'LoadGraphs.LoadGraphWidget'
    docFactory = loaders.stan(
        T.div(render=T.directive('liveElement')))

class ExternalElement(athena.LiveElement):
    
    def __init__(self, subscriber, disc_defer, *a, **kw):
        super(ExternalElement, self).__init__(*a, **kw)
        self.subscriber = subscriber
        disc_defer.addCallbacks(self.discon,self.discon)
        self.chart = self.subscriber.editGraphInit()
        self.subscriber.registerLiveElement(self)
        self.regexpCellId = {'d': unicode('nodeRegexp'), 'h': unicode('hostRegexp'), 's': unicode('serviceRegexp'), 'm': unicode('metricRegexp')}
        
    def pageQuit(self):
        d = self.callRemote('reDirect', unicode('/'))
        return d
        
    def discon(self, result):
        log.debug('this live element has been disconnected')
        self.subscriber.unregisterLiveElement(self)

    def setItem(self, item, choice):
        log.debug('Setting %s to %s for %s' % (item, choice, self.subscriber.getUserName()))
        if item == 'node':
            self.getOptions('host_options', choice)
        elif item == 'host':
            self.getOptions('service_options', choice)
        elif item == 'service':
            self.getOptions('metric_options', choice)
        elif item == 'metric':
            self.subscriber.setMetric(choice, self.chart)
            log.debug("metric selected!")
        elif item == 'engine':
            graph_list = self.subscriber.setGraphEngine(choice, self.chart)
            selected_type = self.subscriber.getGraphType(self.chart)
            if selected_type:
                def_option = [unicode(selected_type), unicode(selected_type)]
                if selected_type in graph_list:
                    tmp = graph_list.pop(selected_type)
                self.setItem('graphtype', selected_type)
            else:
                self.callRemote('hideItem', unicode('makeGraphButtonRow'))
                def_option = [unicode('Select a Graph Type'), unicode('select_an_option')]
            log.debug("engine selected!")
            if not graph_list:
                log.debug('got an empty graph list')
            else:
                graph_type_list =[]
                for graph_type in graph_list.keys():
                    graph_type_list.append(unicode(graph_type))
                optionListId = unicode('12SettingsCellContent')
                selectId = unicode('graphtype')
                self.callRemote('addNamedSelect', graph_type_list, optionListId, selectId, def_option, unicode('Type: '))
        elif item == 'graphtype':
            graph_type = self.subscriber.setGraphType(str(choice), self.chart)
            if graph_type:
                def_name = self.subscriber.getGraphName(self.chart)
                self.callRemote('addNamedTextInput', unicode('21SettingsCellContent'), unicode('Graph Name: '), unicode('graph_name'), unicode(def_name), unicode(''))
                def_title = self.subscriber.getGraphTitle(self.chart)
                self.callRemote('addNamedTextInput', unicode('22SettingsCellContent'), unicode('Graph Title: '), unicode('graph_title'), unicode(def_title), unicode(''))
                def_start_time = self.subscriber.getGraphStartTime(self.chart)
                self.callRemote('addNamedTextInput', unicode('23SettingsCellContent'), unicode('Start Time: '), unicode('graph_start_time'), unicode('Now'), unicode('datetime'))
                def_duration = self.subscriber.getGraphDuration(self.chart)
                self.callRemote('addNamedTextInput', unicode('24SettingsCellContent'), unicode('Duration: '), unicode('graph_duration'), unicode(def_duration),unicode(''))
                if (str(choice) in ('Zoom Chart') and self.subscriber.getGraphEngine(self.chart) == 'FusionCharts') or (self.subscriber.getGraphEngine(self.chart) == 'HighCharts'):
                    # We can show events on a Zoom Cart
                    event_type_list = self.subscriber.getEventTypeList(self.chart)
                    def_event = self.subscriber.getSelectedEventType(self.chart)
                    e_type_list = []
                    if def_event:
                        def_option = [unicode(def_event), unicode(def_event)]
                        if def_option in event_type_list:
                            tmp = event_type_list.pop(def_event)
                    else:
                        def_option = [unicode('Select Event Types'), unicode('select_an_event_type')]
                    for record in event_type_list:
                        e_type_list.append(unicode(record))
                    optionListId = unicode('13SettingsCellContent')
                    selectId = unicode('event_type')
                    self.callRemote('addNamedSelect', e_type_list, optionListId, selectId, def_option, unicode('Event Overlays: '))
                else:
                    self.callRemote('hideItem', unicode('13SettingsCellContent'))
                def_size = self.subscriber.getGraphSize(self.chart)
                log.debug('setting selected graph size: %s' % def_size)
                graph_sizes = self.subscriber.getGraphSizes()
                graph_size_list = []
                for size in graph_sizes.keys():
                    graph_size_list.append(unicode(size))
                optionListId = unicode('25SettingsCellContent')
                def_option = [unicode(def_size), unicode(def_size)]
                log.debug('sending default graph size to web as %s' % def_option)
                selectId = unicode('graph_size')
                self.callRemote('addNamedSelect', graph_size_list, optionListId, selectId, def_option, unicode('Size: '))
                graph_privacies = self.subscriber.getGraphPrivacies()
                selected_privacy = self.subscriber.getGraphPrivacy(self.chart)
                privacy_list = []
                for privacy in graph_privacies:
                    privacy_list.append(unicode(privacy))
                optionListId=unicode('26SettingsCellContent')
                def_option = [unicode(selected_privacy), unicode(selected_privacy)]
                selectId = unicode('graph_privacy')
                self.callRemote('addNamedSelect', privacy_list, optionListId, selectId, def_option, unicode('Share: '))
                self.callRemote('unhideItem', unicode('21SettingsCell'))
                self.callRemote('unhideItem', unicode('22SettingsCell'))
                self.callRemote('unhideItem', unicode('23SettingsCell'))
                self.callRemote('unhideItem', unicode('24SettingsCell'))
                self.callRemote('unhideItem', unicode('25SettingsCell'))
                self.callRemote('unhideItem', unicode('26SettingsCell'))
                self.callRemote('unhideItem', unicode('makeGraphButtonRow'))
            else:
                self.callRemote('displayError', unicode('Invalid Graph Type'), unicode('12SettingsCellContent'))
                self.callRemote('hideItem', unicode('makeGraphButtonRow'))
                log.error('User selected invalid graph type')
        elif item == 'graph_name':
            graph_name = self.subscriber.setGraphName(str(choice), self.chart)
        elif item == 'graph_title':
            graph_title = self.subscriber.setGraphTitle(str(choice), self.chart)
        elif item == 'graph_size':
            graph_size = self.subscriber.setGraphSize(str(choice), self.chart)
        elif item == 'graph_start_time':
            graph_start = self.subscriber.setGraphStartTime(str(choice), self.chart)
                
        elif item == 'graph_duration':
            graph_duration = self.subscriber.setGraphDuration(str(choice), self.chart)
            if graph_duration:
                log.debug('got a valid duration entry')
                #unhide the make graph button, and remove error class
                self.callRemote('clearError', unicode('invalid time duration'), unicode('graph_duration'))
                self.callRemote('unhideItem', unicode('makeGraphButtonCell'))
            else:
                log.debug('got an invalid duration entry')
                #hide the make graph button, and add error class
                self.callRemote('displayError', unicode('invalid time duration'), unicode('graph_duration'))
                self.callRemote('hideItem', unicode('makeGraphButtonCell'))
                
        elif item == 'graph_privacy':
            graph_privacy = self.subscriber.setGraphPrivacy(str(choice), self.chart)
        elif item == 'event_type':
            event_type = self.subscriber.setGraphEventType(str(choice), self.chart)

    def removeRowId(self, rowId):
        log.debug('got request to remove row %s' % rowId)
        newRowId = str(rowId[8:])
        res = self.subscriber.cancelSeriesId(newRowId, self.chart)
        if res:
            log.debug('requesting client removal of row %s' % rowId)
            self.callRemote('removeRow',rowId)
        else:
            log.debug('unable to remove row %s' % rowId)
            pass

    def addServiceMetric(self, req_action):
        log.debug('got addServiceMetric %s request' % (req_action))
        graphSeries = self.subscriber.addGraphSeries(self.chart)
        log.debug('got graph series back from subscriber %s' % graphSeries)
        #log.debug(graphSeries)
        s_node = unicode(graphSeries[0])
        s_host = unicode(graphSeries[1])
        s_serv = unicode(graphSeries[2])
        s_metr = unicode(graphSeries[3])
        s_name = unicode(graphSeries[4])
        self.callRemote('addGraphSeries', s_node, s_host, s_serv, s_metr, s_name)
        self.getOptions('node_options')
        log.debug('sent series to browser for display')
            
    def getOptions(self, optionListId, option_filter=None):
        log.debug('getOptions called with optionListId: %s' % optionListId)
        #fetch options for the specified option list - this should be based on the login user
        optionList = []
        def_option = []
        rowId = unicode(optionListId)
        optionListId = unicode(optionListId)
        if optionListId == 'node_options':
            log.debug('requesting auth nodes from subscriber')
            nodes = self.subscriber.getAuthNodes()
            if auto_series:
                prev_series = self.subscriber.getPreviousSeries(self.chart)
                if prev_series:
                    prev_node = prev_series[0]
                else:
                    prev_node = None
            else:
                prev_node = None
            if not nodes:
                log.debug('Subscriber is not authorized for any nodes')
            else:
                node_list = []
                if prev_node:
                    def_option = [unicode(prev_node), unicode(prev_node)]
                    if prev_node in nodes:
                        tmp = nodes.remove(prev_node)
                else:
                    if nodes and len(nodes) > 1:
                        def_option = [unicode('Select a Node'), unicode('select_an_option')]
                for node in nodes:
                    log.debug('adding node %s to node select' % node)
                    node_list.append(unicode(node))
                selectId = unicode('node')
                self.callRemote('addSelect', node_list, rowId, selectId, def_option)
                if prev_node:
                    self.getOptions('host_options', option_filter=prev_node)
        elif optionListId == 'host_options':
            node = option_filter
            node_host_list = self.subscriber.getHostList(node, self.chart)
            if auto_series:
                prev_series = self.subscriber.getPreviousSeries(self.chart)
                if prev_series:
                    prev_node = prev_series[0]
                    if prev_node == node:
                        prev_host = prev_series[1]
                    else:
                        self.subscriber.resetPreviousSeries(self.chart)
                        prev_host = None
                else:
                    prev_host = None
            else:
                prev_host = None
            host_list = []
            if prev_host and (prev_node == node):
                def_option = [unicode(prev_host), unicode(prev_host)]
                if prev_host in node_host_list:
                    tmp = node_host_list.remove(prev_host)
            else:
                def_option = [unicode('Select a Host'),unicode('select_an_option')]
            for host in node_host_list:
                host_list.append(unicode(host))
            selectId = unicode('host')
            log.debug('sending %i hosts to host select' % len(host_list))
            self.callRemote('addSelect', host_list, rowId, selectId, def_option)
            if prev_host:
                self.getOptions('service_options', option_filter=prev_host)
        elif optionListId == 'service_options':
            host = option_filter
            host_service_list = self.subscriber.getServiceList(host, self.chart)
            if auto_series:
                prev_series = self.subscriber.getPreviousSeries(self.chart)
                if prev_series:
                    prev_host = prev_series[1]
                    if prev_host == host:
                        prev_svc = prev_series[2]
                    else:
                        self.subscriber.resetPreviousSeries(self.chart)
                        prev_svc = None
                else:
                    prev_svc = None
            else:
                prev_svc = None
            service_list = []
            if prev_svc and (prev_host == host):
                def_option = [unicode(prev_svc), unicode(prev_svc)]
                if prev_svc in host_service_list:
                    tmp = host_service_list.remove(prev_svc)
            else:
                def_option = [unicode('Select a Service'), unicode('select_an_option')]
            for service in host_service_list:
                service_list.append(unicode(service))
            selectId = unicode('service')
            log.debug('sending %i services to service select' % len(service_list))
            self.callRemote('addSelect', service_list, rowId, selectId, def_option)
            if prev_svc:
                self.getOptions('metric_options', option_filter=prev_svc)
        elif optionListId == 'metric_options':
            service = option_filter
            service_metric_list = self.subscriber.getMetricList(service, self.chart)
            metric_list = []
            for metric in service_metric_list:
                metric_list.append(unicode(metric))
            def_option = [unicode('Select a Metric'), unicode('select_an_option')]
            selectId = unicode('metric')
            log.debug('sending %i metrics to metric select' % len(metric_list))
            self.callRemote('addSelect', metric_list, rowId, selectId, def_option)
        elif optionListId == 'setting_options':
            log.debug('got options request for settings options')
            #add the engine cell
            settings_engine_list = self.subscriber.getGraphEngineList()
            selected_engine = self.subscriber.getGraphEngine(self.chart)
            if selected_engine:
                def_option = [unicode(selected_engine), unicode(selected_engine)]
                if selected_engine in settings_engine_list:
                    settings_engine_list.remove(selected_engine)
                self.setItem('engine', selected_engine)
            else:
                def_option = [unicode('Select a Graphing Engine'), unicode('select_an_option')]
            engine_list = []
            for engine in settings_engine_list:
                engine_list.append(unicode(engine))
            optionListId = unicode('11SettingsCellContent')
            selectId = unicode('engine')
            log.debug('returning options settings')
            self.callRemote('addNamedSelect', engine_list, optionListId, selectId, def_option, unicode('Graph Engine: '))
        else:
            log.debug('getOptions called with unknown request: %s' % optionListId)
    

    def makeGraph(self):
        def onSuccess(result):
            log.debug('sending graph to page')
            #format the data for fusion charts
            chart_cell = 'chart_cell'
            graph_object = self.subscriber.buildMultiSeriesTimeObject(self.chart, chart_cell, result)
            if not graph_object:
                return False 
            #log.debug(graph_object)
            log.debug('getting graph settings')
            graph_settings = self.subscriber.getGraphSettings(self.chart)
            graph_type = graph_settings['graph_type']
            graph_width = graph_settings['graph_width']
            graph_height = graph_settings['graph_height']
            log.debug('graph settings returned')
            #TODO: send the new unique Id back to the subscriber so we have access to this chart (need for live chart)
            defChart = getRandString(8)
            if self.chart.getChartEngine() == 'FusionCharts':
                log.debug('sending object as fusionchart')
                self.callRemote('addFusionChart', unicode(graph_type), unicode(defChart), unicode(graph_width), unicode(graph_height), graph_object, unicode(chart_cell))
            elif self.chart.getChartEngine() == 'HighCharts':
                log.debug('sending object as highchart')
                self.callRemote('addHighChart', graph_object)
            # register this chart as live
            self.subscriber.registerLiveElement(self, self.chart)
            return True
        def onFailure(reason):
            log.error(reason)
            return False
        #get the data from opsview for the requested graph
        d = self.subscriber.makeGraph(self.chart)
        d.addCallbacks(onSuccess,onFailure)
        return d
        
    def initialize(self):
        #check to see if we were in the progress of building a graph, and correctly setup the page if we were
        log.debug("initialization called")
        pageInitData = self.subscriber.initializeGraphPage(self.chart)
        if len(pageInitData) == 2:
            graphData, currentChart = pageInitData
        elif len(pageInitData) == 1:
            self.chart = pageInitData
        else:
            graphData = []
        if graphData:
            for record in graphData:
                self.callRemote('addGraphSeries', unicode(record[0]), unicode(record[1]), unicode(record[2]), unicode(record[3]), unicode(record[4]))
            if currentChart:
                self.makeGraph()
        return modal_close
    
    def saveGraph(self):
        log.debug('save graph requested.')
        graph_saved = self.subscriber.saveGraph(self.chart)
        if graph_saved:
            return True
        else:
            return False
    
    def _initRegexp(self, dPatt, hPatt, sPatt, mPatt):
        d = self.subscriber.setRegexp(self.chart, 'd', dPatt)
        h = self.subscriber.setRegexp(self.chart, 'h', hPatt)
        s = self.subscriber.setRegexp(self.chart, 's', sPatt)
        m = self.subscriber.setRegexp(self.chart, 'm', mPatt)
        matches = unicode(self.subscriber.getRegexpMatchCount(self.chart)[0])
        log.debug("Returning %s matches for regexp initialization" % matches)
        return matches
    
    def _setRegexp(self, item, patt):
        log.debug('Setting regexp %s to %s' % (item, patt))
        tmp = self.subscriber.setRegexp(self.chart, item, patt)
        cellId = self.regexpCellId[str(item)]
        if not tmp:
            self.callRemote('displayError', unicode('Invalid regexp pattern'), cellId)
        else:
            self.callRemote('clearError', unicode('Invalid regexp pattern'), cellId)
        return unicode(self.subscriber.getRegexpMatchCount(self.chart)[0])
    
    def _getRegexMatches(self, item, patt):
        log.debug('Getting list of choices for regexp %s to %s' % (item, patt))
        tmp = self.subscriber.setRegexp(self.chart, item, patt)
        cellId = self.regexpCellId[str(item)]
        if not tmp:
            self.callRemote('displayError', unicode('Invalid regexp pattern'), cellId)
        else:
            self.callRemote('clearError', unicode('Invalid regexp pattern'), cellId)
        result = self.subscriber.getRegexpMatchCount(self.chart)
        match_count = result[0]
        dhsmList = result[1]
        itemPos = 'dhsm'.index(item)
        listResult = []
        for row in dhsmList:
            if row[itemPos] not in listResult:
                listResult.append(row[itemPos])
        returnResult = [match_count,listResult]
        log.debug(returnResult)
        return unicode(json.dumps(returnResult))
    
    def checkRegexpSelect(self):
        dhsmCount, dhsm = self.subscriber.getRegexpMatchCount(self.chart)
        return dhsmCount
        
    def _addRegexpSelect(self):
        dhsmIndexedList = self.subscriber.addRegexpSelect(self.chart)
        self.getOptions('node_options')
        return dhsmIndexedList
    
    def resetNodeSelection(self):
        log.debug("resetNodeSelection called ")
        rowId      = unicode('node_options')
        def_option = []
        node_list  = []
        nodes      = self.subscriber.getAuthNodes()
        if nodes and len(nodes) > 1:
            def_option = [unicode('Select a Node'), unicode('select_an_option')]
        for node in nodes:
            node_list.append(unicode(node))
        selectId   = unicode('node')
        self.callRemote('addSelect', node_list, rowId, selectId, def_option)

    def removeAllRows(self):
        log.debug('got request to remove all rows')
        self.chart.series = []
        self.chart.metricSeries = []
        self.chart.seriesTracker = {}
        rowCount = self.chart.seriesCounter
        self.chart.seriesCounter = 0

        self.callRemote('removeAllRows', rowCount)

    def resetGraphValues(self):
        # Reset all selections on graph page
        log.debug('resetGraphValues(): Called')
        matches = self._initRegexp('.*', '.*', '.*', '.*')
        log.debug("resetGraphValues(): matches = %s"%str(matches))
        self.removeAllRows()
        return matches

    saveGraph = expose(saveGraph)
    initialize = expose(initialize)
    makeGraph = expose(makeGraph)
    getOptions = expose(getOptions)
    addServiceMetric = expose(addServiceMetric)
    setNode = expose(setItem)
    removeRowId = expose(removeRowId)
    initRegexp = expose(_initRegexp)
    setRegexp = expose(_setRegexp)
    addRegexpSelect = expose(_addRegexpSelect)
    checkRegexpSelect = expose(checkRegexpSelect)
    getRegexMatches = expose(_getRegexMatches)
    resetGraphValues = expose(resetGraphValues)
    resetNodeSelection = expose(resetNodeSelection)
    removeAllRows = expose(removeAllRows)
    jsClass = u'Extern.ExternWidget'
    _tpl = filepath.FilePath(__file__).parent().child('templates').child('athena_livepage.html')
    docFactory = loaders.xmlfile(_tpl.path)
    
class ExternalPage(athena.LivePage):
    def __init__(self, *a, **kw):
        super(ExternalPage, self).__init__(*a, **kw)
        modulePath = filepath.FilePath(__file__).parent().child('js').child('graphtool.js')
        self.jsModules.mapping.update( {'Extern': modulePath.path} )
        
    def render_theTitle(self, ctx, data):
        return 'Opsgraph: Create Graph'
    
    def render_navBar(self, ctx, data):
        return ctx.tag[TopTabs()]
    
    def render_externalElement(self, ctx, data):
        session = ISession(ctx)
        request = ISession(ctx)
        subscriber = session.getComponent(ISubscriberObject)
        d = self.notifyOnDisconnect()
        f = ExternalElement(subscriber, d)
        f.setFragmentParent(self)
        return ctx.tag[f]
        
    docFactory = loaders.stan(
        T.html[
            T.title[render_theTitle
            ],
            T.head(render=T.directive('liveglue'))[
                T.link(type='text/css', href='css/jquery-ui.css', rel='Stylesheet'),
                T.link(type='text/css', href='css/opsgraph.css', rel='Stylesheet'),
                T.script(type='text/javascript', src='javascript/jquery-1.6.2.min.js'),
                T.script(type='text/javascript', src='javascript/jquery-ui-1.8.16.custom.min.js'),
                T.script(type='text/javascript', src='javascript/jquery-ui-timepicker-addon.js'),
                T.script(type='text/javascript', src='fusioncharts/FusionCharts.js'),
                T.script(type='text/javascript', src='highcharts/highcharts.js')
            ],
            T.body(render=T.directive('externalElement'))[
                T.div[render_navBar]
            ]
        ]
    )
    
class NotFoundPage(rend.Page):
    implements(inevow.ICanHandleNotFound)
    
    addSlash = True
    
    docFactory = loaders.stan(T.html)
    
    def renderHTTP_notFound(self, ctx):
        request = inevow.IRequest(ctx)
        request.redirect('/')
        return ''
    

def getRandString(length):
    digs = string.digits
    ltrs = string.letters
    rndset = digs + ltrs
    rndStr = "".join([random.choice(rndset) for i in xrange(length)])
    return rndStr

def wrapAuthorized(site, anonSite):
    site = inevow.IResource(site)
    anonSite = inevow.IResource(anonSite)
    realmObject = opsviewRealm(site, anonSite)
    portalObject = Portal(realmObject)
    myChecker = opsviewWebChecker()
    #Allow anonymous access to the login page
    portalObject.registerChecker(
        checkers.AllowAnonymousAccess(), IAnonymous
    )
    #Allow authenticated users to the main page
    portalObject.registerChecker(myChecker)
    site = appserver.NevowSite(resource=guard.SessionWrapper(portalObject, mindFactory=Mind))
    site.remember(NotFoundPage(), inevow.ICanHandleNotFound)
    return site
    

site = wrapAuthorized(RootPage(),LoginForm())

def getService():
    services = []
    if httpport:
        service = internet.TCPServer(httpport, site)
        service.setName("WEBService")
        services.append(service)
    if sslport:
        sslContext = ssl.DefaultOpenSSLContextFactory(sslPrivKey,sslCaCert,)
        service = internet.SSLServer(sslport,site,contextFactory = sslContext)
        services.append(service)
    return services
