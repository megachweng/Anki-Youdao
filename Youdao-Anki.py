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


class Note(object):
    css = '''<style>.card {font-family: arial;font-size: 14px;text-align: left;color: #212121;background-color: white;}#phrsListTab h2 {line-height: 30px;font-size: 24px;margin-bottom: 0px;overflow: hidden;word-break: break-all;}.pronounce {margin-right: 30px;font-size: 14px;display: inline-block;line-height: 26px;}.phonetic{font-size: 14px;margin-left: .2em;font-family: "lucida sans unicode",arial,sans-serif;color: #01848f}.keyword {vertical-align: bottom;margin-right: 15px;}.trans-container {margin: 1em 0 2em 0;border-bottom: 2px solid #4caf50;}ul, ol, li {list-style: none;padding: 0;font-weight: bold;}.phrase{color:#01848f;padding-right: 1em;}</style>'''

    @classmethod
    def returnFront(self, Nphrase):
        base = '''<div id="phrsListTab"><h2><span class="keyword">{{''' + '''term}}</span><div class="baav"><span class="pronounce">英<span class="phonetic">[{{uk-phonetic}}]</span></span><span class="pronounce">美<span class="phonetic">[{{us-phonetic}}]</span></span></div></h2><div class="trans-container"><ul><li>轻按查看定义</li></ul></div></div><ul>'''
        a = ''
        for i in range(0, Nphrase):
            a += '<p><span style="color:#01848f;padding-right: 1em;">{{' + ("phrase" + str(i)) + '}}: ?</p>'
        a += '</ul>'
        return(Note.css + base + a)

    @classmethod
    def returnBack(self, Nphrase):
        base = '''<div id="phrsListTab"><h2><span class="keyword">{{''' + '''term}}</span><div class="baav"><span class="pronounce">英<span class="phonetic">[{{uk-phonetic}}]</span></span><span class="pronounce">美<span class="phonetic">[{{us-phonetic}}]</span></span></div></h2><div class="trans-container"><ul><li>{{''' + '''definition}}</li></ul></div></div><ul>'''
        a = ''
        for i in range(0, Nphrase):
            a += '''<p><span style="color:#01848f;padding-right: 1em;">{{phrase''' + str(i) + '''}}: {{phraseExplain''' + str(i) + '''}}</p>'''
        a += '</ul>'
        return (Note.css + base + a)


def addCustomModel(name, col):
    """create a new custom model for the imported deck"""
    mm = col.models
    existing = mm.byName("YoudaoWordBook")
    if existing:
        return existing
    m = mm.new("YoudaoWordBook")
    # add fields
    mm.addField(m, mm.newField("term"))
    mm.addField(m, mm.newField("definition"))
    mm.addField(m, mm.newField("uk-phonetic"))
    mm.addField(m, mm.newField("us-phonetic"))
    mm.addField(m, mm.newField("phrase0"))
    mm.addField(m, mm.newField("phrase1"))
    mm.addField(m, mm.newField("phrase2"))
    mm.addField(m, mm.newField("phraseExplain0"))
    mm.addField(m, mm.newField("phraseExplain1"))
    mm.addField(m, mm.newField("phraseExplain2"))

    # add cards
    t = mm.newTemplate("Normal")
    t['qfmt'] = Note.returnFront(1)
    t['afmt'] = Note.returnBack(1)

    mm.addTemplate(m, t)

    mm.add(m)
    return m


def testMode():
    deck = mw.col.decks.get(mw.col.decks.id("test"))
    model = addCustomModel("test", mw.col)

    # assign custom model to new deck
    mw.col.decks.select(deck["id"])
    mw.col.decks.get(deck)["mid"] = model["id"]
    mw.col.decks.save(deck)

    # assign new deck to custom model
    mw.col.models.setCurrent(model)
    mw.col.models.current()["did"] = deck["id"]
    mw.col.models.save(model)
    mw.col.reset()
    mw.reset()


"""
deck, sync
fromWordbook, fromYoudaoDict
us_phonetic, uk_phonetic
phrase, phraseExplain
sync_process

username, password, loginTest
appID, appKey, apiTest,fromPublicAPI
"""


class Window(QWidget):
    def __init__(self, parent=None):
        super(Window, self).__init__(parent)
        self.results = None
        self.thread = None
        self.settings = None
        # settings = self.retriveSettings()
        uic.loadUi("../../addons/youdao.ui", self)  # load ui from *.ui file
        self.setupUI(self)  # setupUI
        self.updateSettings(self)
        # testMode()
        self.show()  # shows the window

    def setupUI(self, window):
        window.progressLabel.hide()
        window.setWindowTitle("Sync with Youdao Word-list")
        window.password.textEdited[str].connect(lambda: window.loginTest.setEnabled(window.password.text() != "" and window.username.text() != ""))
        window.username.textEdited[str].connect(lambda: window.loginTest.setEnabled(window.password.text() != "" and window.username.text() != ""))
        window.password.textEdited[str].connect(lambda: window.sync.setEnabled(window.password.text() != "" and window.username.text() != "" and window.deck.text() != ""))
        window.deck.textEdited[str].connect(lambda: window.deck.setEnabled(window.deck.text() != ""))
        window.username.textEdited[str].connect(lambda: window.loginTest.setEnabled(window.password.text() != "" and window.username.text() != ""))
        window.appID.textEdited[str].connect(lambda: window.apiTest.setEnabled(window.appID.text() != "" and window.appKey.text() != ""))
        window.appKey.textEdited[str].connect(lambda: window.apiTest.setEnabled(window.appKey.text() != "" and window.appID.text() != ""))
        window.fromYoudaoDict.toggled.connect(lambda: window.cloudAPI.setEnabled((window.fromPublicAPI.isChecked() is False)))
        window.fromYoudaoDict.toggled.connect(lambda: window.apiStatus.setText("Press buttom to test API validation"))
        window.fromYoudaoDict.toggled.connect(lambda: window.phraseExplain.setEnabled(window.phrase.isChecked()))
        window.fromWordbook.toggled.connect(lambda: window.apiStatus.setText("Select 'From Youdao' radioButtom first"))
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
            window.phraseExplain.setEnabled(not settings[3])

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

    def clickSync(self):
        self.testOption = "no"
        settings = self.getSettingsFromUI(self)
        self.settings = settings
        if settings[0] == '' or settings[1] == '':
            self.tabWidget.setCurrentIndex(1)
            showInfo('\n\nPlease enter your Username and Password!')
        elif settings[2] == '':
            showInfo('\n\nPlease enter Deckname!')
        elif askUser('Sync Now?'):
            self.saveSettings(settings[0], settings[1], settings[2], settings[3], settings[4], settings[5], settings[6], settings[7], settings[8], settings[9], settings[10], settings[11])
            # [0username, 1password, 2deckname, 3fromWordbook, 4fromYoudaoDict, 5us, 6uk, 7phrase, 8phraseExplain, 9appID, 10appKey,11fromPublicAPI]
            self.tabWidget.setEnabled(False)
            self.sync.setText("Wait")
            # self.progressLabel.setText("Fetching Words")
            # stop the previous thread first
            if self.thread is not None:
                self.thread.terminate()
            # download the data!
            self.thread = YoudaoDownloader(self)
            self.thread.start()
            while not self.thread.isFinished():
                mw.app.processEvents()
                self.thread.wait(50)

            # error with fetching data
            if self.thread.error:
                self.debug.appendPlainText("Something went wrong")
            else:
                # result = json.loads(self.thread.results)
                # self.syncYoudao(result)
                # got finally data from here
                self.debug.appendPlainText(self.thread.results)

            self.thread.terminate()
            self.thread = None

    def clickLoginTest(self):
        self.testOption = "login"
        self.loginTest.setEnabled(False)
        self.loginTest.setText("Checking..")

        try:
            if self.thread is not None:
                self.thread.terminate()

            self.thread = YoudaoDownloader(self)
            self.thread.start()
            while not self.thread.isFinished():
                mw.app.processEvents()
                self.thread.wait(50)

        except Exception as e:
            showInfo(str(e))

    def clikAPITest(self):
        self.testOption = "API"
        errorCode = {
            0: "API Successfully!",
            108: "Application ID or Application Key invalid!",
            101: "The Application does not have a binding instance!"
        }

        try:
            if self.thread is not None:
                self.thread.terminate()

            self.thread = YoudaoDownloader(self)
            self.thread.start()
            while not self.thread.isFinished():
                mw.app.processEvents()
                self.thread.wait(50)
        except Exception as e:
            showInfo(str(e))
        # e = testPart.APItest(self.appID.text(), self.appKey.text())
        ec = self.thread.errorCode
        self.apiStatus.setText(errorCode.get(int(ec), "Faild with errorCode: {}".format(str(ec))))

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

    def getSettingsFromUI(self, window):
        username = window.username.text()
        password = window.password.text()
        deckname = window.deck.text()
        fromWordbook = window.fromWordbook.isChecked() and 1 or 0
        fromYoudaoDict = window.fromYoudaoDict.isChecked() and 1 or 0
        us = window.us_phonetic.isChecked() and 2 or 0
        uk = window.uk_phonetic.isChecked() and 1 or 0
        phrase = window.phrase.isChecked() and 4 or 0
        phraseExplain = window.phraseExplain.isChecked() and 8 or 0
        appID = window.appID.text()
        appKey = window.appKey.text()
        fromPublicAPI = window.fromPublicAPI.isChecked() and 1 or 0
        return [username, password, deckname, fromWordbook, fromYoudaoDict, us, uk, phrase, phraseExplain, appID, appKey, fromPublicAPI]

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
            us = ((values[0][6] == 2) and True or False)
            uk = ((values[0][7] == 1) and True or False)
            phrase = ((values[0][8] == 4) and True or False)
            phraseExplain = ((values[0][9] == 8) and True or False)
            appID = values[0][10]
            appKey = values[0][11]
            fromPublicAPI = ((values[0][12] == 1) and True or False)
        else:
            return False
        cursor.rowcount
        conn.commit()
        conn.close()
        return [username, password, deckname, fromWordbook, fromYoudaoDict, us, uk, phrase, phraseExplain, appID, appKey, fromPublicAPI]


class YoudaoDownloader(QThread):
    """thread that downloads results from the Youdao-wordlist website"""

    def __init__(self, window):
        super(YoudaoDownloader, self).__init__()
        self.window = window
        self.error = False
        self.results = None
        self.errorCode = 1000

    def run(self):
        # test login
        if self.window.testOption == "login":
            if self.login(self.window.username.text(), self.window.password.text()):
                self.window.loginStatus.setText("Login Successfully!")
            else:
                self.window.loginStatus.setText("Login Failed!")
            self.window.loginTest.setText("Check")
            self.window.loginTest.setEnabled(True)

        # test API
        elif self.window.testOption == "API":
            self.errorCode = self.APITest(self.window.appID.text(), self.window.appKey.text())

        # grab data from wordbook
        else:
            self.window.progressLabel.setText("Fetching Words")
            # get youdao wordlist
            parser = parseWordbook(self.window)
            if not self.login(self.window.username.text(), self.window.password.text()):
                self.window.tabWidget.setCurrentIndex(1)
                self.window.loginStatus.setText('Login Failed, Please check your account!!')
                self.window.username.clear()
                self.window.password.clear()
            else:
                totalPage = self.totalPage()
                self.window.progress.setMaximum(totalPage)
                self.window.progress.setValue(0)
                self.window.progressLabel.show()
                for index in range(0, totalPage):
                    self.window.progress.setValue(index + 1)
                    # trigger progressBar everysingle time
                    parser.feed(self.crawler(index))

                previous = parser.retrivePrevious()
                if previous:
                    self.results = json.dumps(parser.compare(previous))
                    self.window.progress.setValue(0)

                else:
                    self.results = json.dumps(parser.nocompare(), indent=4)

                # if no results, there was an error
                if self.results is None:
                    self.error = True

                self.window.progressLabel.setText("Done")

            self.window.sync.setText('Sync')
            self.window.tabWidget.setEnabled(True)

    def login(self, username, password):
        password = hashlib.md5(password.encode('utf-8')).hexdigest()

        url = "https://logindict.youdao.com/login/acc/login"
        payload = "username=" + urllib.quote(username) + "&password=" + password + \
            "&savelogin=1&app=web&tp=urstoken&cf=7&fr=1&ru=http%3A%2F%2Fdict.youdao.com%2Fwordbook%2Fwordlist%3Fkeyfrom%3Dnull&product=DICT&type=1&um=true&savelogin=1"
        headers = {
            'Cache-Control': '"no-cache"',
            'Referer': 'http://account.youdao.com/login?service=dict&back_url=http://dict.youdao.com/wordbook/wordlist%3Fkeyfrom%3Dlogin_from_dict2.index',
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_12_6) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/60.0.3112.101 Safari/537.36',
            'Content-Type': 'application/x-www-form-urlencoded'
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

    def APITest(self, appID, appKey):
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

    def crawler(self, pageIndex):
        response = self.opener.open(
            "http://dict.youdao.com/wordbook/wordlist?p=" + str(pageIndex) + "&tags=")
        return response.read()

    def totalPage(self):
        # page index start from 0 end at max-1
        response = self.opener.open("http://dict.youdao.com/wordbook/wordlist?p=0&tags=")
        source = response.read()
        try:
            return int(re.search('<a href="wordlist.p=(.*).tags=" class="next-page">最后一页</a>', source, re.M | re.I).group(1)) - 1
        except Exception:
            return 1
            pass


class parseWordbook(HTMLParser, object):
    def __init__(self, window):
        HTMLParser.__init__(self)
        self.window = window
        self.terms = []
        self.definitions = []
        conn = sqlite3.connect('youdao-anki.db')
        cursor = conn.cursor()
        cursor.execute(
            'create table if not exists syncHistory (id INTEGER primary key, added TEXT,deleted TEXT,time varchar(20))')
        cursor.execute(
            'create table if not exists history (id INTEGER primary key, terms TEXT,definitions TEXT,time varchar(20))')
        cursor.rowcount
        cursor.close()
        conn.commit()
        conn.close()

    def handle_starttag(self, tag, attrs):
        # retrive the terms
        if tag == 'div':
            for attribute, value in attrs:
                if value == 'word':
                    self.terms.append(attrs[1][1])
        # retrive the definitions
                if value == 'desc':
                    if attrs[1][1]:
                        self.definitions.append(attrs[1][1])
                    else:
                        self.definitions.append(None)

    def nocompare(self):
        data = {'deleted': [None], 'terms': []}

        for index, value in enumerate(self.terms):
            data['terms'].append({'term': value, 'definition': self.definitions[index], "phrase": {'phrase_terms': [], 'phrase_explains': []}})

        # self.savePreviews(self.terms, self.definitions)
        # self.saveSyncHistory(self.terms, self.definitions)

        # wordbook only
        # the phrase option posibilities
        '''
        K:1	    KS:3    KR:5	KE:8    KSR:7   KRE:12  KSRE:14
        S:2	    SR:6    SE:9    SRE:13
        R:4	    RE:11
        E:7
        '''
        self.window.progress.setMaximum(len(data['terms']))
        self.window.progressLabel.setText("Fetching Details")
        if self.window.settings[3] == 1:
            self.window.progress.setValue(0)
            # result = json.loads(self.thread.results)
            return data
        # get more from API
        elif self.window.settings[4] == 1:
            self.window.progress.setValue(0)

            # fromPublicAPI self.window.settings[5:9]
            if self.window.settings[11] == 1:
                for index, value in enumerate(data['terms']):
                    search = API.publicAPI(value['term'], self.window)
                    value["uk_phonetic"] = search["uk_phonetic"]
                    value["us_phonetic"] = search["us_phonetic"]
                    value["definition"] = search["definition"]
                    value['phrase']["phrase_terms"] = search["phrases"]
                    value['phrase']["phrase_explains"] = search["phrase_explains"]

            # fromPrivateAPI self.window.settings[5:11]
            else:
                api = API(self.window.appID.text(), self.window.appKey.text(), self.window)
                for index, value in enumerate(data['terms']):
                    search = api.request(value['term'])
                    value["uk_phonetic"] = search["uk_phonetic"]
                    value["us_phonetic"] = search["us_phonetic"]
                    value["definition"] = search["definition"]
                    value['phrase']["phrase_terms"] = search["phrases"]
                    value['phrase']["phrase_explains"] = search["phrase_explains"]
            # return self.processData(data, self.window.settings[5:9])
            return self.processData(data, self.window.settings[5:9])

    def processData(self, results, args):
        option = sum(args)
        for data in results['terms']:
            if option is 0:
                data.pop("phrase")
                data.pop("us_phonetic")
                data.pop("uk_phonetic")
            elif option is 1:
                data.pop("phrase")
                data.pop("us_phonetic")
            elif option is 2:
                data.pop("phrase")
                data.pop("uk_phonetic")
            elif option is 3:
                data.pop("phrase")
            elif option is 4:
                data["phrase"].pop("phrase_explains")
                data.pop("uk_phonetic")
                data.pop("us_phonetic")
            elif option is 5:
                data["phrase"].pop("phrase_explains")
                data.pop("us_phonetic")
            elif option is 6:
                data["phrase"].pop("phrase_explains")
                data.pop("uk_phonetic")
            elif option is 7:
                data["phrase"].pop("phrase_explains")
            elif option is 8:
                data.pop("phrase")
                data.pop("us_phonetic")
                data.pop("uk_phonetic")
            elif option is 9:
                data.pop("phrase")
                data.pop("us_phonetic")
            elif option is 10:
                data.pop("phrase")
                data.pop("uk_phonetic")
            elif option is 11:
                data.pop("phrase")
            elif option is 12:
                data.pop("uk_phonetic")
                data.pop("us_phonetic")
            elif option is 13:
                data.pop("us_phonetic")
            elif option is 14:
                data.pop("uk_phonetic")

        return results

    def savePreviews(self, terms, definitions):
        conn = sqlite3.connect('youdao-anki.db')
        cursor = conn.cursor()
        cursor.execute(
            'create table if not exists history (id INTEGER primary key, terms TEXT,definitions TEXT,time varchar(20))')
        cursor.execute('insert into history (terms,definitions,time) values (?,?,?)',
                       (pickle.dumps(terms), (pickle.dumps(definitions)), time.strftime("%Y-%m-%d")))
        cursor.rowcount
        cursor.close()
        conn.commit()
        conn.close()

    def saveSyncHistory(self, added, deleted):
        conn = sqlite3.connect('youdao-anki.db')
        cursor = conn.cursor()
        cursor.execute(
            'create table if not exists syncHistory (id INTEGER primary key, added TEXT,deleted TEXT,time varchar(20))')
        cursor.execute('insert into syncHistory (added,deleted,time) values (?,?,?)',
                       (pickle.dumps(added), (pickle.dumps(deleted)), time.strftime("%Y-%m-%d")))
        cursor.rowcount
        cursor.close()
        conn.commit()
        conn.close()

    def retrivePrevious(self):
        conn = sqlite3.connect('youdao-anki.db')
        cursor = conn.cursor()
        cursor.execute('select * from history order by id desc limit 0, 1')
        values = cursor.fetchall()
        # values[number of raw][0->id,1->terms,2->definitions,3->time]
        if values:
            terms = pickle.loads(values[0][1])
            definitions = pickle.loads(values[0][2])
        else:
            return False
        cursor.close()
        conn.close()
        return [terms, definitions]


class API(object):
    def __init__(self, appID, appKey, window):
        self.url = 'http://fanyi.youdao.com/openapi.do'
        self.appKey = appKey
        self.appID = appID
        self._from = "EN"
        self.to = "zh-CHS"
        self.window = window

    def request(self, q):
        self.q = q
        self.salt = str(int(time.time()))
        s = hashlib.md5()
        s.update(self.appID + self.q + self.salt + self.appKey)
        self.sign = s.hexdigest()
        params = urllib.urlencode({
            'q': self.q,
            'from': self._from,
            'to': self.to,
            'sign': self.sign,
            'salt': self.salt,
            'appKey': self.appID
        })

        f = urllib2.urlopen('http://openapi.youdao.com/api?' + params)
        json_result = json.loads(f.read())
        try:
            explains = ",".join(json_result["basic"]["explains"])
        except:
            try:
                explains = ",".join(json_result["web"][0]["value"])
            except:
                explains = "No definition"

        try:
            uk_phonetic = json_result["basic"]["uk-phonetic"]
        except:
            uk_phonetic = "No UK Phonetic"
        try:
            us_phonetic = json_result["basic"]["us-phonetic"]
        except:
            us_phonetic = "No US Phonetic"

        try:
            phrases = []
            phrase_explains = []
            json_phrase = json_result["web"]
            nphrases = len(json_phrase)
            for i in range(1, nphrases):
                phrases.append(json_phrase[i]['key'])
                phrase_explains.append(json_phrase[i]['value'][0])
        except:
            phrases = "No Phrase"
            phrase_explains = "No Phrase"

        # indicate api progress
        self.window.progress.setValue(self.window.progress.value() + 1)
        return {"uk_phonetic": uk_phonetic,
                "us_phonetic": us_phonetic,
                "definition": explains,
                "phrases": phrases,
                "phrase_explains": phrase_explains
                }

    @classmethod
    def publicAPI(self, q, window):
        query = urllib.urlencode({"q": q})
        f = urllib2.urlopen("https://dict.youdao.com/jsonapi?{}&dicts=%7B%22count%22%3A%2099%2C%22dicts%22%3A%20%5B%5B%22ec%22%2C%22phrs%22%5D%2C%5B%22web_trans%22%5D%2C%5B%22fanyi%22%5D%5D%7D".format(query))
        r = f.read()
        json_result = json.loads(r)
        try:
            explains = json_result["ec"]["word"][0]["trs"][0]["tr"][0]["l"]["i"][0]
        except:
            try:
                explains = json_result["web_trans"]["web-translation"][0]["trans"][0]["value"]
            except:
                try:
                    explains = json_result["fanyi"]["tran"]
                except:
                    explains = "No definition"

        try:
            uk_phonetic = json_result["ec"]["word"][0]["ukphone"]
        except:
            try:
                uk_phonetic = json_result["simple"]["word"][0]["ukphone"]
            except:
                try:
                    uk_phonetic = json_result["ec"]["word"][0]["phone"]
                except:
                    uk_phonetic = "No UK Phonetic"

        try:
            us_phonetic = json_result["ec"]["word"][0]["usphone"]
        except:
            try:
                us_phonetic = json_result["simple"]["word"][0]["usphone"]
            except:
                try:
                    us_phonetic = json_result["ec"]["word"][0]["phone"]
                except:
                    us_phonetic = "No US Phonetic"
        try:
            phrases = []
            phrase_explains = []
            json_phrases = json_result["phrs"]["phrs"]
            for value in json_phrases:
                phrases.append(value["phr"]["headword"]["l"]["i"])
                phrase_explains.append(value["phr"]["trs"][0]["tr"]["l"]["i"])
        except:
            phrases = "No phrase"
            phrase_explains = "No phrase definition"

        window.progress.setValue(window.progress.value() + 1)

        return {
            "uk_phonetic": uk_phonetic,
            "us_phonetic": us_phonetic,
            "definition": explains,
            "phrases": phrases,
            "phrase_explains": phrase_explains
        }


def runYoudaoPlugin():
    """menu item pressed; display search window"""
    global __window
    __window = Window()


# create menu item
action = QAction("Import your Youdao WordList", mw)
mw.connect(action, SIGNAL("triggered()"), runYoudaoPlugin)
mw.form.menuTools.addAction(action)
