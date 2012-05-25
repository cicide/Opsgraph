#!/usr/bin/python


import sys, os
sys.path.insert(0, os.getcwd()) #Hack to make twistd work when run as root
os.chdir(os.path.split(os.getcwd())[0])
#print os.path.dirname()


import utils
log = utils.get_logger("Twistd")

from twisted.python.log import PythonLoggingObserver
twistdlog = PythonLoggingObserver("Twistd")
twistdlog.start()

from twisted.application import service
from twisted.internet import reactor

graphtoolService = service.MultiService()
application = service.Application("Graphtool")
graphtoolService.setServiceParent(application)

def addServices():

    import web
    webServices = web.getService()
    for service in webServices:
        graphtoolService.addService(service)
    import opsview
    #import rest_api - imported in opsview

    #shutdown cleanup
    #reactor.addSystemEventTrigger('before', 'shutdown', web.shutdown)
    
reactor.callWhenRunning(addServices)

