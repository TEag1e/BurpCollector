#!coding:utf-8

'''
======
TEag1e@www.teagle.top
米斯特安全团队@www.hi-ourlife.com
======
'''

import time
import os
import json
from urlparse import urlparse
import pymysql
from MysqlController import MysqlController

from burp import IBurpExtender
from burp import IExtensionStateListener
from burp import IContextMenuFactory

from javax.swing import JMenuItem


class BurpExtender(IBurpExtender, IExtensionStateListener, IContextMenuFactory):

    def registerExtenderCallbacks(self, callbacks):

        # Set extension's name
        callbacks.setExtensionName('Burp Collector')

        self._callbacks = callbacks

        # create Log File
        self.createLogFile()

        # test the database connection
        MysqlController().connectTest()

        # retrieve the context menu factories
        callbacks.registerContextMenuFactory(self)

        # register ourselves as an Extension listener
        callbacks.registerExtensionStateListener(self)

    #
    # create log files with current time
    #

    def createLogFile(self):

        # currentTime = Year Month Day Hour Minute
        currentTime = time.strftime('%Y%m%d%H%M%S',time.localtime())

        # make directory
        if not os.path.exists('log'):
            os.mkdir('log')

        os.chdir('log')

        # make log file
        self._paramLog = '{}param.log'.format(currentTime)
        self._fileLog = '{}file.log'.format(currentTime)
        self._pathLog = '{}path.log'.format(currentTime)

        if not os.path.exists(self._paramLog):
            open(self._paramLog,'w').close()
        if not os.path.exists(self._fileLog):
            open(self._fileLog,'w').close()
        if not os.path.exists(self._pathLog):
            open(self._pathLog,'w').close()

    #
    # implement IContextMenuFactory
    #

    def createMenuItems(self, invocation): 

        mainMenu = JMenuItem('History To Log',
            actionPerformed = self.menuOnClick)
        return [mainMenu]

    #
    # stores Data when Clicking on Context Menu
    #

    def menuOnClick(self, event):

        # extract path,file and param from Proxy History 
        DataExtractor(self._callbacks, self._pathLog, self._fileLog, self._paramLog)

    #
    # implement IExtensionStateListener
    #

    def extensionUnloaded(self):

        # extract path,file and param from Proxy History 
        DataExtractor(self._callbacks, self._pathLog, self._fileLog, self._paramLog)

        # stored in MySQL from the log file
        MysqlController().coreProcessor(self._pathLog, self._fileLog, self._paramLog)

#
# extract path,file and param from Proxy History 
#

class DataExtractor():

    def __init__(self, callbacks, pathLog, fileLog, paramLog):

        self._callbacks = callbacks
        self._helpers = callbacks.getHelpers()
        self._pathLog = pathLog
        self._fileLog = fileLog
        self._paramLog = paramLog
        self.coreProcessor()
    
    def coreProcessor(self):
        
        with open('../config.ini')as config_f:
            self._config = json.load(config_f)

        allHistoryMessage = self._callbacks.getProxyHistory()
        
        # define three variable to remove duplicate data
        collectionParam = []
        collectionFile = []
        collectionPath = []

        # processing each message
        for historyMessage in allHistoryMessage:

            httpService = historyMessage.getHttpService()
            requestInfo = self._helpers.analyzeRequest(httpService, historyMessage.getRequest())
            host = httpService.getHost()
            url = str(requestInfo.getUrl())
            path = urlparse(url).path
            path,file = self.formatPathFile(path)

            # invoke host filter
            if not self.filterHost(host):
                continue

            # invoke file filter
            if not self.filterFile(file):
                continue

            # path to log
            currentPath = '{}\t{}'.format(host, path)
            if path and currentPath not in collectionPath:
                print(currentPath)
                with open(self._pathLog, 'a')as path_f:
                    path_f.write(currentPath+'\n')
                collectionPath.append(currentPath)

            # file to log 
            currentFile = '{}\t{}'.format(host, file)
            if file and currentFile not in collectionFile:
                print(currentFile)
                with open(self._fileLog, 'a')as file_f:
                    file_f.write(currentFile+'\n')
                collectionFile.append(currentFile)

            # parameters to log
            paramsObject = requestInfo.getParameters()
            params = self.processParamsObject(paramsObject)
            currentParams = '{}\t{}'.format(host, ','.join(params))
            if params and currentParams not in collectionParam:
	                print(currentParams)
	                with open(self._paramLog, 'a')as params_f:
	                    params_f.write(currentParams+'\n')
	                collectionParam.append(currentParams)

    # format path and file
    def formatPathFile(self, path):

        sepIndex = path.rfind('/')
        # EX: http://xxx/?id=1
        if path == '/':
            file = ''
            path = ''
        # EX: http://xxx/index.php
        # file = index.php
        elif sepIndex == 0:
            file = path[1:]
            path = ''
        # EX: http://xxx/x/index.php
        # path = /x/
        # file = index.php
        else:
            file = path[sepIndex+1:]
            path = path[:sepIndex+1]

        return path,file

    # extractor data from host
    def filterHost(self, host):

        blackHosts = self._config.get('blackHosts')

        for blackHost in blackHosts:
            if host.endswith(blackHost):
                return

        return True

    # extractor data from file
    def filterFile(self, file):

        balckPaths = self._config.get('blackExtension')

        for blackPath in balckPaths:
            if file.endswith(blackPath):
                return False
        return True

    # extract params
    def processParamsObject(self, paramsObject):

        # get parameters
        params = []
        for paramObject in paramsObject:

            # don't process Cookie's Pamrams
            if paramObject.getType() == 2:
                continue
            param = paramObject.getName()
            if param.startswith('_'):
                continue
            params.append(param)
        return params