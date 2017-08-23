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
appID, appKey, apiTest
"""


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
        window.username.textEdited[str].connect(lambda: window.sync.setEnabled(window.password.text() != "" and window.username.text() != "" and window.deck.text() != ""))
        window.appID.textEdited[str].connect(lambda: window.apiTest.setEnabled(window.appID.text() != "" and window.appKey.text() != ""))
        window.appKey.textEdited[str].connect(lambda: window.apiTest.setEnabled(window.appKey.text() != "" and window.appID.text() != ""))

        window.sync.clicked.connect(self.clickSync)
        window.loginTest.clicked.connect(self.clickLoginTest)
        window.apiTest.clicked.connect(self.clikAPITest)

    def updateSettings(self, window):
        window.username.setText("megachweng@163.com")
        window.password.setText("cs123456")
        window.appID.setText("3c72f9f4fdcb013a")
        window.appKey.setText("fwrRXdnp4AmIylMTvO50GXKxm7ieRyCU")
        window.deck.setText("Youdao")

        window.loginTest.setEnabled(window.password.text() != "" and window.username.text() != "")
        window.apiTest.setEnabled(window.appID.text() != "" and window.appKey.text() != "")
        window.sync.setEnabled(window.password.text() != "" and window.username.text() != "" and window.deck.text() != "")

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
        return [username, password, deckname, fromWordbook, fromYoudaoDict, us, uk, phrase, phraseExplain]

    def clickSync(self):
        settings = self.getSettingsFromUI(self)
        self.saveSettings(settings[0], settings[1], settings[2], settings[3], settings[4], settings[5], settings[6], settings[7], settings[8])
        if self.username.text() == '' or self.password.text() == '':
            self.tabWidget.setCurrentIndex(1)
            showInfo('\n\nPlease enter your Username and Password!')
        else:
            if askUser('Sync Now?'):
                pass

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

    def saveSettings(self, username, password, deckname, fromWordbook, fromYoudaoDict, us, uk, phrase, phraseExplain):
        conn = sqlite3.connect('youdao-anki.db')
        cursor = conn.cursor()
        cursor.execute(
            'create table if not exists settings (id INTEGER primary key, username TEXT,password TEXT,deckname TEXT,fromWordbook INTEGER,fromYoudaoDict INTEGER ,us INTEGER,uk INTEGER,phrase INTEGER,phraseExplain INTEGER)')
        cursor.execute('INSERT OR IGNORE INTO settings (id,username,password,deckname,fromWordbook,fromYoudaoDict,us,uk,phrase,phraseExplain) VALUES(?,?,?,?,?,?,?,?,?,?)',
                       (1, username, password, deckname, fromWordbook, fromYoudaoDict, us, uk, phrase, phraseExplain))
        cursor.execute('UPDATE settings SET username=?,password=?,deckname=?,fromWordbook=?,fromYoudaoDict=?,us=?,uk=?,phrase=?,phraseExplain=? WHERE id=1',
                       (username, password, deckname, fromWordbook, fromYoudaoDict, us, uk, phrase, phraseExplain))
        cursor.rowcount
        conn.commit()
        conn.close()

    def getSettingsFromDatabase(self):
        conn = sqlite3.connect('youdao-anki.db')
        cursor = conn.cursor()
        cursor.execute(
            'create table if not exists settings (id INTEGER primary key, username TEXT,password TEXT,deckname TEXT,fromWordbook INTEGER,fromYoudaoDict INTEGER ,us INTEGER,uk INTEGER,phrase INTEGER,phraseExplain INTEGER)')
        cursor.execute('select * from settings')
        values = cursor.fetchall()
        if values:
            username = values[0][1]
            password = values[0][2]
            deckname = values[0][3]
            fromWordbook = values[0][4]
            fromYoudaoDict = values[0][5]
            us = values[0][6]
            uk = values[0][7]
            phrase = values[0][8]
            phraseExplain = values[0][9]
        else:
            return False
        cursor.rowcount
        conn.commit()
        conn.close()
        return [username, password, deckname, fromWordbook, fromYoudaoDict, us, uk, phrase, phraseExplain]


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

