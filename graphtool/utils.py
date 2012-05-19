#/usr/bin/python
"""
Utils module for servers

"""
import logging
import logging.handlers
import ConfigParser

import os 
import sys


def set_log_level(log):
    """
    log - target logger object on which log level needs to be set
    """
    config = get_config()
    #log_level should be any one of the following - DEBUG , INFO, ERROR, CRITICAL , FATAL
    log_level = config.get("general", "loglevel")
    log.setLevel(getattr(logging, log_level))
    
def get_logger(name):
    """
    Creates and sets log level on a python logger object 
    Returns the created logger object
    
    name - name of the logger to be created
    """
    log = logging.getLogger(name)
    set_log_level(log)
    return log

def get_post_vars(req):
    vars = {}
    for k, v in req.args.items():
        vars[k] = v[0]
    return vars
    
    
_config = None
def get_config():
    # Singleton
    global _config
    
    if _config is None:        
        _config = ConfigParser.ConfigParser()
        _config.optionxform = str
        
        #filepath = os.path.join(os.path.dirname(__file__), 'etc', 'graphtool.conf')
        filepath = 'etc/graphtool.conf'
        f=open(filepath)
        _config.readfp(f)
        config_log()
    
    return _config
    

def config_log():
    logpath = _config.get("general", "logpath")
    logfile = _config.get("general", "logfile")
    rootlogger = logging.getLogger('')
    fmt = logging.Formatter('%(asctime)s-%(name)s-%(levelname)s : %(message)s')
    sh = logging.StreamHandler()
    sh.setFormatter(fmt)
    rootlogger.addHandler(sh)
    rfh = logging.handlers.RotatingFileHandler(logpath+"/"+logfile, maxBytes=2048000, backupCount=10)
    rfh.setFormatter(fmt)
    rootlogger.addHandler(rfh)

def normalize_data(tdict):
    if not tdict:
        return None
    
    oldkey = None
    rdict = {}
    for key, value in tdict.iteritems():
        if not oldkey:
            oldkey = key

        if (key - oldkey) > 1: 
            for i in range(oldkey +1, key):
                rdict[i] = ''

        rdict[key] = value
        oldkey = key
    return rdict

def reduce_data(tdict, size):                                                                                                                       
    if len(tdict) <= size:
        return tdict
    skip = len(tdict)/size - 1
    ret = {}
    oldkeys = []
    for k,v in tdict.iteritems():
       if len(oldkeys)<skip:
           oldkeys.append(k)
           continue
       oldkeys.append(k)
       sumval = 0
       for var in oldkeys:
           sumval = tdict[var] + sumval
       ret[oldkeys[0]] = sumval/len(oldkeys)
       oldkeys = []
    if len(oldkeys) != 0:
        sumval = 0
        for var in oldkeys:
            sumval = tdict[var] + sumval
        ret[oldkeys[0]] = sumval/len(oldkeys)
    return ret

config = get_config()   
log=get_logger("utils")
