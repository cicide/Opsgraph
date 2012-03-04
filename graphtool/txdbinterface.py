#!/usr/local/bin/python

from twisted.enterprise import adbapi
from twisted.internet import threads
from twisted.internet.defer import Deferred
import MySQLdb, oursql
import threading
import Queue
import utils
import time, pickle

log = utils.get_logger("txDBmysql")

ranconnect = 0
dbpool = None
query_q=Queue.Queue()
dbis = {}

class txDBInterface:
    def __init__(self, *query):
        self.dbpool = dbi
        self.resultdf = Deferred()
        self.query = query

    def runResultQuery(self):
        df = self.dbpool.runQuery(*self.query)
        df.addCallbacks(self.onResult, self.onFail)
        return self.resultdf

    def runActionQuery(self):
        df = self.dbpool.runOperation(*self.query)
        df.addCallbacks(self.onResult, self.onFail)
        log.debug("running query: %s" % self.query)
        return self.resultdf

    def onResult(self, result):
        self.resultdf.callback(result)

    def onFail(self, error):
        if isinstance(error, adbapi.ConnectionLost):
            log.info("We lost connection to db. re-running the query")
            return self.runQuery()
        self.resultdf.errback(error)
    
def _getUserData(txn, username):
    #runs in a thread, won't block
    sql = """SELECT id from users where username = '%s'"""
    sql_args = (username)
    sql_q = sql % sql_args
    log.debug('execting query %s' % sql_q)
    txn.execute(sql_q)
    result = txn.fetchall()
    if not result:
        log.debug('Got no result for query %s' % sql_q)
        sql = """INSERT INTO users (username) VALUES ('%s')"""
        sql_args = (username)
        sql_q = sql % sql_args
        log.debug('executing query %s' % sql_q)
        txn.execute(sql_q)
        log.debug('getting insert id')
        txn.execute("""SELECT LAST_INSERT_ID()""")
        log.debug('firing off transaction')
        result = txn.fetchall()
        log.debug('returned from transaction')
        if result:
            log.debug('got query result: %s' % result[0][0])
            return result[0][0]
        else:
            return False
    else:
        log.debug('got query result: %s' % result[0][0])
        return result[0][0]

def _getEventData(txn, node):
    sql = """ SELECT e.id,
                     e.node,
                     et.name,
                     et.description,
                     et.color,
                     et.alpha,
                     e.name,
                     e.description,
                     e.start_time,
                     e.end_time,
                     e.url
               FROM events e
               JOIN event_type et
               ON et.id = e.event_type
               WHERE e.node = '%s' """
    sql_args = (node)
    sql_q = sql % sql_args
    txn.execute(sql_q)
    result = txn.fetchall()
    log.debug(result)
    if result:
        return result
    else:
        return False
    
def _getEventTypes(txn):
    sql = """SELECT name from event_type"""
    txn.execute(sql)
    result = txn.fetchall()
    if result:
        return result
    else:
        return False
    
def _getGraphList(txn, uname):
    sql = """SELECT g.id,
                    g.graph_name,
                    g.graph_title,
                    u.username,
                    FROM_UNIXTIME(g.graph_create_date),
                    g.graph_engine,
                    g.graph_type
             FROM graph g
             JOIN users u
             ON g.owner_id = u.id
             WHERE g.graph_privacy = 'Public'
             OR u.username = '%s'"""
    sql_args = uname
    sql_q = sql % sql_args
    txn.execute(sql_q)
    result = txn.fetchall()
    return result

def _getSuiteList(txn, uname):
    sql = """SELECT s.id,
                    s.name,
                    s.title,
                    u.username,
                    FROM_UNIXTIME(s.create_date)
             FROM suite s
             JOIN users u
             ON s.owner_id = u.id"""
    txn.execute(sql)
    result = txn.fetchall()
    return result

def _loadGraphDefinition(txn, dbId):
    log.debug('loading graph definition')
    sql = """ SELECT owner_id,
                     graph_engine,
                     graph_name,
                     graph_title,
                     graph_privacy,
                     graph_type,
                     graph_dur_mod,
                     graph_dur_len,
                     graph_dur_unit,
                     graph_start,
                     events
              FROM graph
              WHERE id=%i"""
    sql_args = (dbId)
    sql_q = sql % sql_args
    txn.execute(sql_q)
    result = txn.fetchall()
    if result:
        return result[0]
    else:
        return False

def _loadGraphParams(txn, dbId):
    log.debug('loading graph parameters')
    sql = """ SELECT p_section, p_directive, p_value FROM graph_parameters WHERE graph_id=%i"""
    sql_args = (dbId)
    sql_q = sql % sql_args
    log.debug(sql_q)
    txn.execute(sql_q)
    result = txn.fetchall()
    if result:
        return result
    else:
        return False
    
def _loadGraphSeries(txn, dbId):
    log.debug('loading graph series')
    sql = """ SELECT g_node, g_host, g_service,g_metric FROM graph_series WHERE graph_id=%i ORDER BY graph_seq_id ASC"""
    sql_args = (dbId)
    sql_q = sql % sql_args
    log.debug(sql_q)
    txn.execute(sql_q)
    result = txn.fetchall()
    if result:
        return result
    else:
        return False
    
def _saveGraphDescription(txn, chart_def, chart_obj, chart_series):
    log.debug('storing graph description')
    owner_id = chart_def['owner_id']
    graph_name = chart_def['graph_name']
    graph_engine = chart_def['graph_engine']
    graph_title = chart_def['graph_title']
    graph_privacy = chart_def['graph_privacy']
    graph_type = chart_def['graph_type']
    graph_start = chart_def['graph_start']
    graph_dur_mod = chart_def['graph_dur_mod']
    graph_dur_len = chart_def['graph_dur_len']
    graph_dur_unit = chart_def['graph_dur_unit']
    graph_events = chart_def['graph_event']
    sql = """INSERT INTO graph (owner_id, 
                                graph_engine, 
                                graph_name,
                                graph_title,
                                graph_privacy,
                                graph_type,
                                graph_dur_mod,
                                graph_dur_len,
                                graph_dur_unit,
                                graph_start,
                                graph_create_date,
                                events)
                        VALUES (%i, '%s', '%s', '%s', '%s', '%s', '%s', '%s', '%s', %i, %i, '%s')"""
    sql_args = (int(owner_id), 
                graph_engine, 
                graph_name, 
                graph_title, 
                graph_privacy, 
                graph_type, 
                graph_dur_mod,
                graph_dur_len,
                graph_dur_unit,
                graph_start,
                int(time.time()),
                graph_events
                )
    sql_q = sql % sql_args
    log.debug('executing sql: %s' % sql_q)
    txn.execute(sql_q)
    txn.execute("""SELECT LAST_INSERT_ID()""")
    result = txn.fetchall()
    if result:
        return result[0][0]
    else:
        return False
    
def _saveGraphData(txn, graphId, chart_obj, chart_series, graph_engine):
    # store series data
    seq = 0
    for row in chart_series:
        seq += 1
        sql = """INSERT INTO graph_series (graph_id, 
                                           graph_seq_id, 
                                           g_node, 
                                           g_host, 
                                           g_service, 
                                           g_metric)
                                   VALUES (%i, %i, '%s', '%s', '%s', '%s')"""
        sql_args = (int(graphId), seq, row[0], row[1], row[2], row[3])
        sql_q = sql % sql_args
        txn.execute(sql_q)
    # store graph parameters
    if graph_engine == 'FusionCharts':
        # Fusion charts have four sections: chart, categories, dataset, and styles
        # the categories and dataset are generated at the time of graph build
        # so we only store the chart and styles sections here, however, the styles 
        # section has subsections (definition and application) that we need to handle as well
        chart_struct = chart_obj['chart']
        for key in chart_struct.keys():
            value = chart_struct[str(key)]
            sql = """INSERT INTO graph_parameters (graph_id, p_section, p_directive, p_value)
                     VALUES (%i, '%s', '%s', '%s')"""
            sql_args = (int(graphId), 'chart', str(key), str(value))
            sql_q = sql % sql_args
            txn.execute(sql_q)
        definition = chart_obj['styles']['definition'][0]
        application = chart_obj['styles']['application'][0]
        for key in definition.keys():
            value = definition[str(key)]
            sql = """INSERT INTO graph_parameters (graph_id, p_section, p_directive, p_value)
                     VALUES (%i, '%s', '%s', '%s')"""
            sql_args = (int(graphId), 'definition', str(key), str(value))
            sql_q = sql % sql_args
            txn.execute(sql_q)
        for key in application.keys():
            value = application[str(key)]
            sql = """INSERT INTO graph_parameters (graph_id, p_section, p_directive, p_value)
                     VALUES (%i, '%s', '%s', '%s')"""
            sql_args = (int(graphId), 'application', str(key), str(value))
            sql_q = sql % sql_args
            txn.execute(sql_q)
        #execute the transaction
        result = txn.fetchall()
        if result:
            return result[0][0]
        else:
            return False
    else:
        return False
        
def _deleteGraphs(txn, graph_ids):
    if len(graph_ids):
        sql = """ DELETE FROM graph_series WHERE graph_id in (%s) """
        sql_args = ','.join(["%s" % el for el in graph_ids])
        sql_q = sql % sql_args
        log.debug(sql_q)
        txn.execute(sql_q)
        sql = """ DELETE FROM graph_parameters WHERE graph_id in (%s) """
        sql_args = ','.join(["%s" % el for el in graph_ids])
        sql_q = sql % sql_args
        log.debug(sql_q)
        txn.execute(sql_q)
        sql = """ DELETE FROM graph WHERE id in (%s) """
        sql_args = ','.join(["%s" % el for el in graph_ids])
        sql_q = sql % sql_args
        log.debug(sql_q)
        txn.execute(sql_q)
        #result = txn.fetchall()
        return True
    else:
        return False

def _saveSuite(txn, suite_def, suite_members):
    owner_id  = suite_def['owner_id']
    suite_name = suite_def['name']
    suite_title = suite_def['title']
    dur_mod = suite_def['dur_mod']
    dur_len = suite_def['dur_len']
    dur_unit = suite_def['dur_unit']
    suite_start = suite_def['start']
    suite_cols = suite_def['numCols']
    suite_ena_override = suite_def['override']
    graphList = pickle.dumps(suite_members)
    sql = """ INSERT INTO suite (owner_id,
                                 name,
                                 title,
                                 dur_mod,
                                 dur_len,
                                 dur_unit,
                                 start,
                                 create_date,
                                 graphList,
                                 numCols,
                                 enableOverride)
              VALUES (%i, '%s', '%s', '%s', '%s', '%s', %i, %i, "%s", %i, %i)"""
    sql_args = (int(owner_id),
                suite_name,
                suite_title,
                dur_mod,
                dur_len,
                dur_unit,
                suite_start,
                int(time.time()),
                graphList,
                suite_cols,
                suite_ena_override)
    sql_q = sql % sql_args
    txn.execute(sql_q)
    txn.execute("""SELECT LAST_INSERT_ID()""")
    result = txn.fetchall()
    if result:
        return result[0][0]
    else:
        return False
    
def _loadSuite(txn, dbId):
    log.debug('loading suite for suite id %s' % dbId)
    sql = """SELECT owner_id,
                    name,
                    title,
                    dur_mod,
                    dur_len,
                    dur_unit,
                    start,
                    graphList,
                    numCols,
                    enableOverride
              FROM suite
              WHERE id=%i"""
    sql_args = (int(dbId))
    sql_q = sql % sql_args
    txn.execute(sql_q)
    result = txn.fetchall()
    log.debug(result)
    if result:
        reply = list(result[0][:])
        reply[7] = pickle.loads(str(reply[7]))
        return reply
    else:
        return False
    

def _loadOdwData(txn, host, service, metric, start, end):
    log.debug('loading odw data')
    sql = """ SELECT UNIX_TIMESTAMP(pd.datetime), 
                     pd.value
              FROM performance_data pd 
              JOIN performance_labels pl ON pl.id = pd.performance_label 
              JOIN servicechecks sc ON sc.id = pl.servicecheck 
              JOIN hosts h ON h.id = sc.host 
              WHERE h.name = '%s' 
              AND sc.name = '%s' 
              AND pl.name = '%s'
              AND pd.datetime >= FROM_UNIXTIME(%i)
              AND pd.datetime <= FROM_UNIXTIME(%i)"""
    sql_args = (host, service, metric, start, end)
    sql_q = sql % sql_args
    log.debug(sql_q)
    txn.execute(sql_q)
    result = txn.fetchall()
    sql = """ SELECT pl.units
              FROM performance_labels pl
              JOIN servicechecks sc ON sc.id = pl.servicecheck 
                            JOIN hosts h ON h.id = sc.host 
                            WHERE h.name = '%s' 
                            AND sc.name = '%s' 
                            AND pl.name = '%s'"""
    sql_args = (host, service, metric)
    sql_q = sql % sql_args
    log.debug(sql_q)
    txn.execute(sql_q)
    units = txn.fetchall()
    if result:
        return result, units[0]
    else:
        return False

def loadOdwData(odwHost, odwDb, odwUser, odwPass, host, service, metric, start, end):
    dbiKey = '%s:%s' % (odwHost, odwDb)
    if dbiKey not in dbis:
        dbis[dbiKey] = adbapi.ConnectionPool('oursql', cp_min=3, cp_max=5, cp_noisy=False, cp_reconnect=True, db=odwDb, user=odwUser, passwd=odwPass, host=odwHost, autoreconnect=True, charset=None)
    return dbis[dbiKey].runInteraction(_loadOdwData, host, service, metric, start,end)
    
def saveGraph(chart_def, chart_obj, chart_series):
    def onSuccess(result):
        if not result:
            return False
        else:
            graph_dbId = result
            graph_engine = chart_def['graph_engine']
            tmp = dbi.runInteraction(_saveGraphData, graph_dbId, chart_obj, chart_series, graph_engine)
            if not tmp:
                log.debug('returning false due to a lack of value returned from INSERT')
                return False
            else: 
                return True
    def onFailure(reason):
        log.error(reason)
    # store the graph definition
    d = dbi.runInteraction(_saveGraphDescription, chart_def, chart_obj, chart_series)
    d.addCallbacks(onSuccess,onFailure)

def saveSuite(suite_desc, suite_members):
    return dbi.runInteraction(_saveSuite, suite_desc, suite_members)

def updateSuite(suite_desc, suite_members):
    log.error('this function is not implemented yet')
    return False

def loadSuite(suite_id):
    return dbi.runInteraction(_loadSuite, suite_id)

def deleteGraphs(graph_ids):
    return dbi.runInteraction(_deleteGraphs, graph_ids)

def getUserData(username):
    return dbi.runInteraction(_getUserData, username)

def getEventData(node):
    return dbi.runInteraction(_getEventData, node)

def getEventTypes():
    return dbi.runInteraction(_getEventTypes)

def getGraphList(uname):
    return dbi.runInteraction(_getGraphList, uname)

def getSuiteList(uname):
    return dbi.runInteraction(_getSuiteList, uname)

def loadGraphDefinition(graph_id):
    return dbi.runInteraction(_loadGraphDefinition, graph_id)
    
def loadGraphParameters(graph_id):
    return dbi.runInteraction(_loadGraphParams, graph_id)

def loadGraphSeries(graph_id):
    return dbi.runInteraction(_loadGraphSeries, graph_id)

def texecute(qlist):
    for sql in qlist:
        aexecute(*sql)

def execute(*query):
    txdbi = txDBInterface(*query)
    return txdbi.runResultQuery()

def aexecute(*query):
    txdbi = txDBInterface(*query)
    return txdbi.runActionQuery()

dbname = utils.config.get("database", "dbname")
username = utils.config.get("database", "username")
password = utils.config.get("database", "password")
host = utils.config.get("database", "host")

#dbi = txDBPool(dbname, username, password, host)
dbi = adbapi.ConnectionPool('oursql', cp_min=3, cp_max=5, cp_noisy=False, cp_reconnect=True, db=dbname, user=username, passwd=password, host=host, autoreconnect=True, charset=None)
