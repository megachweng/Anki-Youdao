#!/usr/bin/env python
# -*- coding: utf-8 -*-
from HTMLParser import HTMLParser
import sys
import urllib
import urllib2
import cookielib
import re
import sqlite3
import pickle
import json
import hashlib
import time
reload(sys)
sys.setdefaultencoding('utf-8')
# Anki
from aqt import mw
from aqt.qt import *
from aqt.utils import showInfo, askUser
# PyQT
from PyQt4 import QtGui, uic
from PyQt4.QtGui import *
__window = None


"""
deck, sync
fromWordbook, fromYoudaoDict
us_phonetic, uk_phonetic
phrase, phraseExplain
sync_process

username, password, loginTest
appID, appKey, apiTest,fromPublicAPI
"""


def match(a, b): return [b[i] if x == "" else x for i, x in enumerate(a)] == b


class Window(QWidget):
    def __init__(self, parent=None):
        super(Window, self).__init__(parent)
        self.results = None
        self.thread = None
        # settings = self.retriveSettings()
        uic.loadUi("../../addons/youdao.ui", self)  # load ui from *.ui file
        self.setupUI(self)  # setupUI
        self.updateSettings(self)
        self.show()  # shows the window

    def setupUI(self, window):
        window.setWindowTitle("Sync with Youdao Word-list")
        window.password.textEdited[str].connect(lambda: window.loginTest.setEnabled(window.password.text() != "" and window.username.text() != ""))
        window.username.textEdited[str].connect(lambda: window.loginTest.setEnabled(window.password.text() != "" and window.username.text() != ""))
        window.password.textEdited[str].connect(lambda: window.sync.setEnabled(window.password.text() != "" and window.username.text() != "" and window.deck.text() != ""))
        window.deck.textEdited[str].connect(lambda: window.deck.setEnabled(window.deck.text() != ""))
        window.username.textEdited[str].connect(lambda: window.loginTest.setEnabled(window.password.text() != "" and window.username.text() != ""))
        window.appID.textEdited[str].connect(lambda: window.apiTest.setEnabled(window.appID.text() != "" and window.appKey.text() != ""))
        window.appKey.textEdited[str].connect(lambda: window.apiTest.setEnabled(window.appKey.text() != "" and window.appID.text() != ""))
        window.fromYoudaoDict.toggled.connect(lambda: window.cloudAPI.setEnabled((window.fromPublicAPI.isChecked() is False)))
        window.fromWordbook.toggled.connect(lambda: window.apiStatus.setText("Select 'From Youdao' radioButtom first"))
        window.fromYoudaoDict.toggled.connect(lambda: window.apiStatus.setText("Press buttom to test API validation"))
        window.sync.clicked.connect(self.clickSync)
        window.loginTest.clicked.connect(self.clickLoginTest)
        window.apiTest.clicked.connect(self.clikAPITest)
        window.tabWidget.setCurrentIndex(0)
        window.setWindowTitle("Sync with Youdao wordbook")

    def updateSettings(self, window):
        settings = self.getSettingsFromDatabase()
        if (settings):
            window.deck.setText(settings[2])
            window.username.setText(settings[0])
            window.password.setText(settings[1])
            window.fromWordbook.setChecked(settings[3])
            if settings[4]:
                window.apiStatus.setText("Press buttom to check API validation!")
                window.fromYoudaoDict.setChecked(True)
                window.fromPublicAPI.setEnabled(True)
                if settings[11]:
                    window.fromPublicAPI.setChecked(True)
                    window.cloudAPI.setEnabled(False)
            else:
                window.apiStatus.setText("Select 'From Youdao' radioButtom first")
                window.fromYoudaoDict.setChecked(False)
            window.fromPublicAPI.setEnabled(settings[4])
            window.us_phonetic.setChecked(settings[5])
            window.uk_phonetic.setChecked(settings[6])
            window.phrase.setChecked(settings[7])
            window.phraseExplain.setChecked(settings[8])

            window.appID.setText(settings[9])
            window.appKey.setText(settings[10])
        else:
            window.deck.setText("Youdao")

        window.loginTest.setEnabled(window.password.text() != "" and window.username.text() != "")
        window.apiTest.setEnabled(window.appID.text() != "" and window.appKey.text() != "")
        window.sync.setEnabled(window.password.text() != "" and window.username.text() != "" and window.deck.text() != "" and window.deck.text() != "")

        # go to login tab first if no username and password provided
        if self.username.text() == '' or self.password.text() == '':
            self.tabWidget.setCurrentIndex(1)

    def getSettingsFromUI(self, window):
        username = window.username.text()
        password = window.password.text()
        deckname = window.deck.text()
        fromWordbook = window.fromWordbook.isChecked() and 1 or 0
        fromYoudaoDict = window.fromYoudaoDict.isChecked() and 1 or 0
        us = window.us_phonetic.isChecked() and 1 or 0
        uk = window.uk_phonetic.isChecked() and 1 or 0
        phrase = window.phrase.isChecked() and 1 or 0
        phraseExplain = window.phraseExplain.isChecked() and 1 or 0
        appID = window.appID.text()
        appKey = window.appKey.text()
        fromPublicAPI = window.fromPublicAPI.isChecked() and 1 or 0
        return [username, password, deckname, fromWordbook, fromYoudaoDict, us, uk, phrase, phraseExplain, appID, appKey, fromPublicAPI]

    def clickSync(self):
        settings = self.getSettingsFromUI(self)
        if settings[0] == '' or settings[1] == '':
            self.tabWidget.setCurrentIndex(1)
            showInfo('\n\nPlease enter your Username and Password!')
        elif settings[2] == '':
            showInfo('\n\nPlease enter Deckname!')
        elif askUser('Sync Now?'):
            self.saveSettings(settings[0], settings[1], settings[2], settings[3], settings[4], settings[5], settings[6], settings[7], settings[8], settings[9], settings[10], settings[11])
            # [0username, 1password, 2deckname, 3fromWordbook, 4fromYoudaoDict, 5us, 6uk, 7phrase, 8phraseExplain, 9appID, 10appKey,11fromPublicAPI]
            if settings[3] == 1:
                showInfo("only wordbook")
            # elif match([[]], settings):
            #     pass

    def clickLoginTest(self, window):
        self.loginStatus.setText(testPart.login(self.username.text(), self.password.text()) and "Login Successfully!" or "Login Faild!")

    def clikAPITest(self, window):

        errorCode = {
            0: "API Successfully!",
            108: "Application ID or Application Key invalid!",
            101: "The Application does not have a binding instance!"
        }
        e = testPart.APItest(self.appID.text(), self.appKey.text())
        self.apiStatus.setText(errorCode.get(int(e), "Faild with errorCode: {}".format(str(e))))

    def saveSettings(self, username, password, deckname, fromWordbook, fromYoudaoDict, us, uk, phrase, phraseExplain, appID, appKey, fromPublicAPI):
        conn = sqlite3.connect('youdao-anki.db')
        cursor = conn.cursor()
        cursor.execute(
            'create table if not exists settings (id INTEGER primary key, username TEXT,password TEXT,deckname TEXT,fromWordbook INTEGER,fromYoudaoDict INTEGER ,us INTEGER,uk INTEGER,phrase INTEGER,phraseExplain INTEGER, appID TEXT,appKey TEXT, fromPublicAPI INTEGER)')
        cursor.execute('INSERT OR IGNORE INTO settings (id,username,password,deckname,fromWordbook,fromYoudaoDict,us,uk,phrase,phraseExplain,appID,appKey,fromPublicAPI) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)',
                       (1, username, password, deckname, fromWordbook, fromYoudaoDict, us, uk, phrase, phraseExplain, appID, appKey, fromPublicAPI))
        cursor.execute('UPDATE settings SET username=?,password=?,deckname=?,fromWordbook=?,fromYoudaoDict=?,us=?,uk=?,phrase=?,phraseExplain=?,appID=?,appKey=?,fromPublicAPI=? WHERE id=1',
                       (username, password, deckname, fromWordbook, fromYoudaoDict, us, uk, phrase, phraseExplain, appID, appKey, fromPublicAPI))
        cursor.rowcount
        conn.commit()
        conn.close()

    def getSettingsFromDatabase(self):
        conn = sqlite3.connect('youdao-anki.db')
        cursor = conn.cursor()
        cursor.execute(
            'create table if not exists settings (id INTEGER primary key, username TEXT,password TEXT,deckname TEXT,fromWordbook INTEGER,fromYoudaoDict INTEGER ,us INTEGER,uk INTEGER,phrase INTEGER,phraseExplain INTEGER, appID TEXT,appKey TEXT,fromPublicAPI INTEGER)')
        cursor.execute('select * from settings')
        values = cursor.fetchall()
        if values:
            username = values[0][1]
            password = values[0][2]
            deckname = values[0][3]
            fromWordbook = ((values[0][4] == 1) and True or False)
            fromYoudaoDict = ((values[0][5] == 1) and True or False)
            us = ((values[0][6] == 1) and True or False)
            uk = ((values[0][7] == 1) and True or False)
            phrase = ((values[0][8] == 1) and True or False)
            phraseExplain = ((values[0][9] == 1) and True or False)
            appID = values[0][10]
            appKey = values[0][11]
            fromPublicAPI = ((values[0][12] == 1) and True or False)
        else:
            return False
        cursor.rowcount
        conn.commit()
        conn.close()
        return [username, password, deckname, fromWordbook, fromYoudaoDict, us, uk, phrase, phraseExplain, appID, appKey, fromPublicAPI]


class testPart(object):
    @classmethod
    def login(self, username, password):
        password = hashlib.md5(password.encode('utf-8')).hexdigest()
        url = "https://logindict.youdao.com/login/acc/login"
        payload = "username=" + urllib.quote(username) + "&password=" + password + "&savelogin=1&app=web&tp=urstoken&cf=7&fr=1&ru=http%3A%2F%2Fdict.youdao.com%2Fwordbook%2Fwordlist%3Fkeyfrom%3Dnull&product=DICT&type=1&um=true"
        headers = {
            'cache-control': "no-cache",
            'content-type': "application/x-www-form-urlencoded"
        }
        url = url + '?' + payload
        req = urllib2.Request(url, headers=headers)
        cookie = cookielib.CookieJar()
        self.opener = urllib2.build_opener(urllib2.HTTPCookieProcessor(cookie))
        self.req = urllib2.install_opener(self.opener)
        response = urllib2.urlopen(req)
        if "登录" in response.read():
            return False
        else:
            return True

    @classmethod
    def APItest(self, appID, appKey):
        q = "test"
        salt = str(int(time.time()))
        s = hashlib.md5()
        s.update(appID + q + salt + appKey)
        sign = s.hexdigest()
        params = urllib.urlencode({
            'q': q,
            'from': "EN",
            'to': "zh-CHS",
            'sign': sign,
            'salt': salt,
            'appKey': appID
        })

        f = urllib2.urlopen('http://openapi.youdao.com/api?' + params)
        json_result = json.loads(f.read())
        return json_result['errorCode']


def runYoudaoPlugin():
    """menu item pressed; display search window"""
    global __window
    __window = Window()


# create menu item
action = QAction("Import your Youdao WordList", mw)
mw.connect(action, SIGNAL("triggered()"), runYoudaoPlugin)
mw.form.menuTools.addAction(action)
