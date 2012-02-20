#!/usr/bin/python

from twisted.web import client, error as weberror
from twisted.internet import error as interror
from twisted.application import internet
import urllib, json
import utils

log = utils.get_logger("RAPIService")

class RestResource(object):
    
    def __init__(self, uri):
        self.uri = uri
        
    def get(self, headers, cookies):
        return self._sendRequest('GET', headers=headers, cookies=cookies)

    def post(self, postData, headers, cookies):
        postData = urllib.urlencode(postData)
        mimeType = 'application/x-www-form-urlencoded'
        return self._sendRequest('POST', headers, cookies, postData, mimeType)

    def put(self, data, mimeType):
        return self._sendRequest('PUT', data, mimeType)

    def delete(self):
        return self._sendRequest('DELETE')

    def _sendRequest(self, method, headers, cookies, data="", mimeType=None):
        headers['Accept'] = 'application/json'
        if mimeType:
            headers['Content-Type'] = mimeType
        if data:
            headers['Content-Length'] = str(len(data))
        return client.getPage(self.uri, 
                              method=method, 
                              postdata=data, 
                              headers=headers, 
                              cookies=cookies)

class dataFetcher(object):
    
    def __init__(self, srv_uri, rest_uri):
        self.srv_uri = srv_uri
        self.rest_uri = rest_uri
        
    def getData(self, headers, cookies):
        uri = '%s/%s' % (self.srv_uri, self.rest_uri)
        d = RestResource(uri)
        log.debug('requesting %s with headers: %s and cookies: %s' % (uri, headers, cookies))
        return d.get(headers, cookies).addCallback(self.onResult).addErrback(self.onError)
    
    def postData(self, postData, headers, cookies):
        uri = '%s/%s' % (self.srv_uri, self.rest_uri)
        d = RestResource(uri)
        log.debug('posting to %s' % uri)
        return d.post(postData, headers, cookies).addCallback(self.onResult).addErrback(self.onError, uri)
    
    def onResult(self, result):
        log.debug('Got Result!')
        reply = json.loads(result)
        #log.debug('got result: %s' % reply)
        return reply
        
    def onError(self, reason, uri=None, *a, **kw):
        l = reason.trap(weberror.Error,
                    interror.NoRouteError,
                    interror.ConnectError,
                    interror.ConnectionRefusedError,
                    interror.TimeoutError,
                    interror.SSLError,
                    interror.ConnectionLost
                    )
        if l == interror.NoRouteError:
            log.error("Login Error: No route to host")
        elif l == interror.ConnectError:
            log.error("Connection Error")
        else:
            log.error('Bind Error during uri request: %s - %s' % (uri,reason))
        raise LoginError

class LoginError(Exception):
    """ Error received while attempting remote Opsview Login """
    def __repr__(self):
        return 'LoginError'
    
def getInfo(srv_uri, req_uri, headers={}, cookies={}):
    rest_uri = req_uri
    rester = dataFetcher(srv_uri, rest_uri)
    return rester.getData(headers, cookies)

def postData(srv_uri, req_uri, postData, headers={}, cookies={}):
    rester = dataFetcher(srv_uri, req_uri)
    return rester.postData(postData, headers, cookies)
    