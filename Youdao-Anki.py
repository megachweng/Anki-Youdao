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
import copy
reload(sys)
sys.setdefaultencoding('utf-8')
# Anki
from aqt import mw
from aqt.qt import *
from aqt.utils import showInfo, askUser, tooltip
# PyQT
from PyQt4 import QtGui, uic
from PyQt4.QtGui import *
try:
    from PyQt4.QtCore import QString
except ImportError:
    QString = str
__window = None


class Note(object):
    css = '''<style>.card {font-family: arial;font-size: 14px;text-align: left;color: #212121;background-color: white;}#phrsListTab h2 {line-height: 30px;font-size: 24px;margin-bottom: 0px;overflow: hidden;word-break: break-all;}.pronounce {margin-right: 30px;font-size: 14px;display: inline-block;line-height: 26px;}.phonetic{font-size: 14px;margin-left: .2em;font-family: "lucida sans unicode",arial,sans-serif;color: #01848f}.keyword {vertical-align: bottom;margin-right: 15px;}.trans-container {margin: 1em 0 2em 0;border-bottom: 2px solid #4caf50;}ul, ol, li {list-style: none;padding: 0;font-weight: bold;}.phrase{color:#01848f;padding-right: 1em;}</style>'''

    @classmethod
    def returnFront(self, Nphrase):
        base = '''<div id="phrsListTab"><h2><span class="keyword">{{''' + '''term}}</span><div class="baav"><span class="pronounce">英<span class="phonetic">[{{''' + '''uk_phonetic}}]</span></span><span class="pronounce">美<span class="phonetic">[{{''' + '''us_phonetic}}]</span></span></div></h2><div class="trans-container"><ul><li>轻按查看定义</li></ul></div></div><ul>'''
        a = ''
        for i in range(0, Nphrase):
            a += '<p><span style="color:#01848f;padding-right: 1em;">{{' + ("phrase" + str(i)) + '}}</p>'
        a += '</ul>'
        return(Note.css + base + a)

    @classmethod
    def returnBack(self, Nphrase):
        base = '''<div id="phrsListTab"><h2><span class="keyword">{{''' + '''term}}</span><div class="baav"><span class="pronounce">英<span class="phonetic">[{{''' + '''uk_phonetic}}]</span></span><span class="pronounce">美<span class="phonetic">[{{''' + '''us_phonetic}}]</span></span></div></h2><div class="trans-container"><ul><li>{{''' + '''definition}}</li></ul></div></div><ul>'''
        a = ''
        for i in range(0, Nphrase):
            a += '''<p><span style="color:#01848f;padding-right: 1em;">{{phrase''' + str(i) + '''}} {{phraseExplain''' + str(i) + '''}}</p>'''
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
    mm.addField(m, mm.newField("uk_phonetic"))
    mm.addField(m, mm.newField("us_phonetic"))
    mm.addField(m, mm.newField("phrase0"))
    mm.addField(m, mm.newField("phrase1"))
    mm.addField(m, mm.newField("phrase2"))
    mm.addField(m, mm.newField("phraseExplain0"))
    mm.addField(m, mm.newField("phraseExplain1"))
    mm.addField(m, mm.newField("phraseExplain2"))

    # add cards
    t = mm.newTemplate("Normal")
    t['qfmt'] = Note.returnFront(3)
    t['afmt'] = Note.returnBack(3)
    mm.addTemplate(m, t)
    mm.add(m)
    return m


class Window(QWidget):
    def __init__(self, parent=None):
        super(Window, self).__init__(parent)
        self.initDB()
        self.terms = []
        self.termsFromDB = None
        self.thread = None
        self.settings = None
        # load ui from *.ui file
        uic.loadUi("../../addons/YAsupportFiles/main.ui", self)
        self.setupUI(self)
        self.updateSettings(self)
        self.show()  # shows the window
        self.dwindow = False

    def initDB(self):
        conn = sqlite3.connect('youdao-anki.db')
        cursor = conn.cursor()
        cursor.execute('create table if not exists history (id INTEGER primary key, terms TEXT,time TEXT,mark TEXT,deckname TEXT)')
        cursor.execute('create table if not exists settings (id INTEGER primary key, username TEXT,password TEXT,deckname TEXT ,uk INTEGER,us INTEGER,phrase INTEGER,phraseExplain INTEGER)')
        cursor.rowcount
        cursor.close()
        conn.commit()
        conn.close()

    def setupUI(self, window):
        window.progressLabel.hide()
        window.setWindowTitle("Sync with Youdao Word-list")
        window.password.textEdited[str].connect(lambda: window.loginTest.setEnabled(window.password.text() != "" and window.username.text() != ""))
        window.username.textEdited[str].connect(lambda: window.loginTest.setEnabled(window.password.text() != "" and window.username.text() != ""))
        window.username.textEdited[str].connect(lambda: window.sync.setEnabled(window.password.text() != "" and window.username.text() != "" and window.deckList.currentText() != ""))
        window.password.textEdited[str].connect(lambda: window.sync.setEnabled(window.password.text() != "" and window.username.text() != "" and window.deckList.currentText() != ""))
        window.deckList.editTextChanged.connect(lambda: window.sync.setEnabled(window.password.text() != "" and window.username.text() != "" and window.deckList.currentText() != ""))
        window.username.textEdited[str].connect(lambda: window.loginTest.setEnabled(window.password.text() != "" and window.username.text() != ""))
        window.sync.clicked.connect(self.clickSync)
        window.showDebug.clicked.connect(self.showDebugWindow)
        window.loginTest.clicked.connect(self.clickLoginTest)
        window.tabWidget.setCurrentIndex(0)
        window.setWindowTitle("Sync with Youdao wordbook")
        window.RestoreHistory.clicked.connect(self.clickRestoreHistory)
        window.deleteHistory.clicked.connect(self.clickDeleteHistory)
        self.setupHistoryList()
        self.setLastSync()
        self.setAllDeck()
        # self.pushButton.clicked.connect(self.clickAllDeck)
        # window.deckList.editTextChanged.connect(self.clickAllDeck)

    def setAllDeck(self):
        t = self.deckList.currentText()
        self.deckList.clear()
        alldecks = mw.col.decks.allNames()
        alldecks.remove('Default')
        for deckname in alldecks:
            self.deckList.addItem(deckname)
        self.debug.appendPlainText(str(mw.col.decks.allNames()))
        if t:
            self.deckList.setEditText(t)

    def clickAllDeck(self):
        self.debug.appendPlainText(self.deckList.currentText())

    def showDebugWindow(self):
        if self.dwindow:
            self.resize(363, 340)
        else:
            self.resize(363, 500)
        self.dwindow = not self.dwindow

    def setLastSync(self):
        conn = sqlite3.connect('youdao-anki.db')
        cursor = conn.cursor()
        cursor.execute('select * from history order by id desc limit 0, 1')
        values = cursor.fetchall()
        cursor.close()
        conn.close()
        # values[number of raw][0->id,1->terms,2->time]
        if values:
            time = 'Last sync: ' + str(values[0][2])
        else:
            time = 'Last sync: None'
        self.lastSync.setText(time)

    def setupHistoryList(self):
        self.table.clear()
        conn = sqlite3.connect('youdao-anki.db')
        cursor = conn.cursor()
        cursor.execute('select * from history order by id desc')
        values = cursor.fetchall()
        cursor.close()
        conn.close()
        # values[number of raw][0->id,1->terms,2->time]
        self.table.setColumnCount(2)
        self.table.setRowCount(len(values))
        self.table.setHorizontalHeaderLabels(QString("Mark;Time;").split(";"))
        for index, day in enumerate(values):
            self.table.setItem(index, 1, QTableWidgetItem(str(day[2])))
            mark = day[3]
            if mark is None:
                mark = 'N'
            self.table.setItem(index, 0, QTableWidgetItem(mark))

    def clickRestoreHistory(self):
        self.Option = "restore"
        for index in self.table.selectedIndexes():
            selected = index.row()
            time = self.table.item(int(selected), 1).text()
        conn = sqlite3.connect('youdao-anki.db')
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM history WHERE time='%s'" % time)
        row = pickle.loads(cursor.fetchone()[1])
        self.termsFromDB = row
        cursor.close()
        conn.close()
        self.clickSync('restore')
        self.debug.appendPlainText(str(row))

    def clickDeleteHistory(self):
        if askUser('Are you sure you want to delete this record?'):
            conn = sqlite3.connect('youdao-anki.db')
            cursor = conn.cursor()
            for index in self.table.selectedIndexes():
                selected = index.row()
                time = self.table.item(int(selected), 1).text()
            sql = "DELETE FROM history WHERE time='%s'" % time
            cursor.execute(sql)
            conn.commit()
            conn.close()
            self.setupHistoryList()
            self.debug.appendPlainText('%s deleted' % time)
            self.setLastSync()

    def updateSettings(self, window):
        settings = self.getSettingsFromDatabase()
        window.debug.appendPlainText(str(settings))
        if (settings):
            window.username.setText(settings[0])
            window.password.setText(settings[1])
            # window.deckList.setText(settings[2])
            window.uk_phonetic.setChecked(settings[3])
            window.us_phonetic.setChecked(settings[4])
            window.phrase.setChecked(settings[5])
            window.phraseExplain.setChecked(settings[6] and settings[5])
        else:
            window.deckList.addItem("Youdao")

        window.loginTest.setEnabled(window.password.text() != "" and window.username.text() != "")
        window.sync.setEnabled(window.password.text() != "" and window.username.text() != "" and window.deckList.currentText() != "")

        # switch ti login tab first if no username or password is provided
        if self.username.text() == '' or self.password.text() == '':
            self.tabWidget.setCurrentIndex(1)

    def clickSync(self, sig=None):
        if sig is None:
            self.Option = "syncFromWordBook"
        else:
            self.Option = sig
        settings = self.getSettingsFromUI(self)
        self.settings = settings
        if settings[0] == '' or settings[1] == '':
            self.tabWidget.setCurrentIndex(1)
            showInfo('\n\nPlease enter your Username and Password!')
        elif settings[2] == '':
            showInfo('\n\nPlease enter Deckname!')
        elif askUser('Sync Now?'):
            # [0username, 1password, 2deckname, 3uk, 4us, 5phrase, 6phraseExplain]
            self.saveSettings(settings[0], settings[1], settings[2], settings[3], settings[4], settings[5], settings[6])

            self.tabWidget.setEnabled(False)
            self.sync.setText("Wait")

            # stop the previous thread first
            if self.thread is not None:
                self.thread.terminate()
            # download the data!
            self.thread = YoudaoDownloader(self)
            self.thread.start()
            self.debug.appendPlainText('170')
            while not self.thread.isFinished():
                mw.app.processEvents()
                self.thread.wait(50)

            # error with fetching data
            if self.thread.error:
                showInfo("Something went wrong")
            else:
                result = json.loads(self.thread.results)
                self.debug.appendPlainText('180')
                # save data to Anki Card
                self.syncYoudao(result, settings[2])
                self.setupHistoryList()
            self.thread.terminate()
            self.thread = None

    def syncYoudao(self, result, name):
        deleted = result['deleted']
        terms = result['terms']
        cardID = []

        if terms:
            deck = mw.col.decks.get(mw.col.decks.id(name))
            model = addCustomModel(name, mw.col)

            # assign custom model to new deck
            mw.col.decks.select(deck["id"])
            mw.col.decks.get(deck)["mid"] = model["id"]
            mw.col.decks.save(deck)

            # assign new deck to custom model
            mw.col.models.setCurrent(model)
            mw.col.models.current()["did"] = deck["id"]
            mw.col.models.save(model)
            for term in terms:
                note = mw.col.newNote()
                note['term'] = term['term']
                if term['definition']:
                    note['definition'] = term['definition']
                else:
                    note['definition'] = 'No definition'
                if 'uk_phonetic' in term.keys():
                    note['uk_phonetic'] = term['uk_phonetic']
                if 'us_phonetic' in term.keys():
                    note['us_phonetic'] = term['us_phonetic']

                # fill phrase field
                if ('phrase' in term.keys()) and term['phrase']['phrase_terms']:
                    Nphrases = len(term['phrase']['phrase_terms'])
                    if ('phrase_terms' in term['phrase']) and ('phrase_explains' in term['phrase']):
                        for i in range((Nphrases < 3 and Nphrases or 3)):
                            note['phrase' + str(i)] = term['phrase']['phrase_terms'][i] + "\t"
                            note['phraseExplain' + str(i)] = term['phrase']['phrase_explains'][i]
                    else:
                        for i in range((Nphrases < 3 and Nphrases or 3)):
                            note['phrase' + str(i)] = term['phrase']['phrase_terms'][i]
                mw.col.addNote(note)
            mw.col.reset()
            mw.reset()

        # delete cards
        if deleted:
            for term in deleted:
                cardID = mw.col.findCards("term:" + term)
                deckID = mw.col.decks.id(name)
                for cid in cardID:
                    nid = mw.col.db.scalar("select nid from cards where id = ? and did = ?", cid, deckID)
                    if nid is not None:
                        mw.col.db.execute("delete from cards where id =?", cid)
                        mw.col.db.execute("delete from notes where id =?", nid)

            mw.col.fixIntegrity()
            mw.col.reset()
            mw.reset()
        self.setAllDeck()
        showInfo('\nAdded : ' + str(len(terms)) + '\n\nDeleted : ' + str(len(deleted)))

    def clickLoginTest(self):
        self.Option = "login"
        self.loginTest.setEnabled(False)
        self.loginTest.setText("Checking..")
        if self.thread is not None:
            self.thread.terminate()

        self.thread = YoudaoDownloader(self)
        self.thread.start()
        while not self.thread.isFinished():
            mw.app.processEvents()
            self.thread.wait(50)
        if self.thread.error:
            showInfo('\n\nLogin test Failed!')
        else:
            showInfo('\n\nLogin test passed!')

    def saveSettings(self, username, password, deckname, uk, us, phrase, phraseExplain):
        conn = sqlite3.connect('youdao-anki.db')
        cursor = conn.cursor()
        cursor.execute('INSERT OR IGNORE INTO settings (id,username,password,deckname,uk,us,phrase,phraseExplain) VALUES(?,?,?,?,?,?,?,?)',
                       (1, username, password, deckname, uk, us, phrase, phraseExplain))
        cursor.execute('UPDATE settings SET username=?,password=?,deckname=?,uk=?,us=?,phrase=?,phraseExplain=? WHERE id=1',
                       (username, password, deckname, uk, us, phrase, phraseExplain))
        cursor.rowcount
        conn.commit()
        conn.close()

    def getSettingsFromUI(self, window):
        username = window.username.text()
        password = window.password.text()
        deckname = window.deckList.currentText()
        uk = window.uk_phonetic.isChecked() and 1 or 0
        us = window.us_phonetic.isChecked() and 2 or 0
        phrase = window.phrase.isChecked() and 4 or 0
        phraseExplain = window.phraseExplain.isChecked() and 8 or 0
        return [username, password, deckname, uk, us, phrase, phraseExplain]

    def getSettingsFromDatabase(self):
        try:
            conn = sqlite3.connect('youdao-anki.db')
            cursor = conn.cursor()
            cursor.execute('select * from settings')
            values = cursor.fetchall()
            cursor.rowcount
            conn.commit()
            conn.close()
            if values:
                username = values[0][1]
                password = values[0][2]
                deckname = values[0][3]
                uk = ((values[0][4] == 1) and True or False)
                us = ((values[0][5] == 2) and True or False)
                phrase = ((values[0][6] == 4) and True or False)
                phraseExplain = ((values[0][7] == 8) and True or False)
            else:
                return False
            return [username, password, deckname, uk, us, phrase, phraseExplain]
        except:
            return False


class YoudaoDownloader(QThread):
    """thread that downloads results from the YoudaoWordBook"""

    def __init__(self, window):
        super(YoudaoDownloader, self).__init__()
        self.window = window
        self.error = False
        self.results = None
        self.errorCode = 1000
        self.loadedCookies = None

    def run(self):
        # test login
        if self.window.Option == "login":
            if self.login(self.window.username.text(), self.window.password.text()):
                self.window.debug.appendPlainText("Login Successfully!")
            else:
                self.window.debug.appendPlainText("Login Failed!")
            self.window.loginTest.setText("Check")
            self.window.loginTest.setEnabled(True)

        # grab words from wordbook
        else:
            self.window.progressLabel.setText("Fetching Words")
            # get youdao wordlist
            parser = parseWordbook(self.window)
            if not self.login(self.window.username.text(), self.window.password.text()):
                self.window.tabWidget.setCurrentIndex(1)
                self.window.loginStatus.setText('Login Failed, Please check your account!!')
            else:
                if self.window.Option is not 'restore':
                    totalPage = self.totalPage()
                    self.window.progress.setMaximum(totalPage)
                    self.window.progress.setValue(0)
                    self.window.progressLabel.show()
                    for index in range(totalPage):
                        self.window.progress.setValue(index + 1)
                        # trigger progressBar everysingle time
                        parser.feed(self.crawler(index))
                previous = parser.retrivePrevious(self.window.deckList.currentText())
                if previous:
                    self.results = json.dumps(parser.compare(previous))
                    self.window.progress.setValue(0)
                else:
                    self.results = json.dumps(parser.noCompare(), indent=4)
                # if no results, there was an error
                if self.results is None:
                    self.error = True

                self.window.progressLabel.setText("Done")

            self.window.sync.setText('Sync')
            self.window.tabWidget.setEnabled(True)

    def saveCookies(self, cookiejar):
        MozillaCookieJar = cookielib.MozillaCookieJar()
        for c in cookiejar:
            args = dict(vars(c).items())
            args['rest'] = args['_rest']
            del args['_rest']
            c = cookielib.Cookie(**args)
            MozillaCookieJar.set_cookie(c)
        MozillaCookieJar.save('youdaoCookies', ignore_discard=True)

    def loadCookies(self):
        try:
            MozillaCookieJar = cookielib.MozillaCookieJar()
            MozillaCookieJar.load('youdaoCookies', ignore_discard=True)
            return MozillaCookieJar
        except:
            return False

    def login(self, username, password):
        if self.totalPage():
            self.window.debug.appendPlainText('cookie Successfully')
            return True
        else:
            self.window.debug.appendPlainText('process login!')
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
            urllib2.urlopen(req)
            if any(username in c.value for c in cookie):
                self.saveCookies(cookie)
                return True
            else:
                return False

    def crawler(self, pageIndex):
        req = urllib2.Request("http://dict.youdao.com/wordbook/wordlist?p=" + str(pageIndex) + "&tags=")
        opener = urllib2.build_opener(urllib2.HTTPCookieProcessor(self.loadedCookies))
        urllib2.install_opener(opener)
        response = urllib2.urlopen(req)
        return response.read()

    def totalPage(self):
        try:
            self.loadedCookies = self.loadCookies()
            # page index start from 0 end at max-1
            req = urllib2.Request('http://dict.youdao.com/wordbook/wordlist?p=0&tags=')
            opener = urllib2.build_opener(urllib2.HTTPCookieProcessor(self.loadedCookies))
            urllib2.install_opener(opener)
            response = urllib2.urlopen(req)
            source = response.read()
            if '密码错误' in source:
                return False
            else:
                try:
                    return int(re.search('<a href="wordlist.p=(.*).tags=" class="next-page">最后一页</a>', source, re.M | re.I).group(1)) - 1
                except Exception:
                    return 1
        except Exception as e:
            return False


class parseWordbook(HTMLParser, object):
    def __init__(self, window):
        HTMLParser.__init__(self)
        self.window = window
        self.terms = []

    def handle_starttag(self, tag, attrs):
        # retrive the terms
        if tag == 'div':
            for attribute, value in attrs:
                if attribute == 'class' and value == 'word':
                    self.terms.append(attrs[1][1])

    def noCompare(self):
        data = {'deleted': [], 'terms': []}
        for term in self.terms:
            data['terms'].append({'term': term, 'definition': "", "phrase": {'phrase_terms': [], 'phrase_explains': []}})

        # All the phrase option posibilities
        '''None:0    K:1    S:2    KS:3    R:4    KR:5    SR:6    KSR:7    E:8    KE:9    SE:10    RE:12    KRE:13    SRE:14    KSRE:15'''

        self.window.progress.setMaximum(len(data['terms']))
        self.window.progressLabel.setText("Fetching Details")

        # get detials from API
        self.window.progress.setValue(0)
        for value in data['terms']:
            search = API.publicAPI(value['term'], self.window)
            value["uk_phonetic"] = search["uk_phonetic"]
            value["us_phonetic"] = search["us_phonetic"]
            value["definition"] = search["definition"]
            value['phrase']["phrase_terms"] = search["phrases"]
            value['phrase']["phrase_explains"] = search["phrase_explains"]

        self.savePreviews(self.terms, self.window.settings[2])
        return self.processData(data, self.window.settings[3:])

    def compare(self, previous):
        if self.window.Option is 'restore':
            self.terms = self.window.termsFromDB
        data = {'deleted': [], 'terms': []}
        addedTerms = []
        for iterm in previous:
            if iterm not in self.terms:
                data['deleted'].append(iterm)

        for i, iterm in enumerate(self.terms):
            if iterm not in previous:
                addedTerms.append(iterm)

        for value in addedTerms:
            data['terms'].append({'term': value, 'definition': "", "phrase": {'phrase_terms': [], 'phrase_explains': []}})

        if len(addedTerms) > 0:
            self.window.progress.setMaximum(len(addedTerms))

        self.window.progressLabel.setText("Fetching Details")
        self.window.progress.setValue(0)
        for index, value in enumerate(data['terms']):
            search = API.publicAPI(value['term'], self.window)
            value["uk_phonetic"] = search["uk_phonetic"]
            value["us_phonetic"] = search["us_phonetic"]
            value["definition"] = search["definition"]
            value['phrase']["phrase_terms"] = search["phrases"]
            value['phrase']["phrase_explains"] = search["phrase_explains"]

        self.savePreviews(self.terms, self.window.settings[2])
        return self.processData(data, self.window.settings[3:])

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

    def savePreviews(self, terms, deckname):
        conn = sqlite3.connect('youdao-anki.db')
        cursor = conn.cursor()
        if self.window.Option == 'restore':
            cursor.execute('insert OR IGNORE into history (terms,time,mark,deckname) values (?,?,?,?)', (pickle.dumps(terms), time.strftime("%Y-%m-%d %H:%M:%S"), 'Restored', deckname))
        else:
            cursor.execute('insert OR IGNORE into history (terms,time,mark,deckname) values (?,?,?,?)', (pickle.dumps(terms), time.strftime("%Y-%m-%d %H:%M:%S"), 'N', deckname))
        cursor.rowcount
        cursor.close()
        conn.commit()
        conn.close()
        self.window.setLastSync()

    def retrivePrevious(self, deckname):
        conn = sqlite3.connect('youdao-anki.db')
        cursor = conn.cursor()
        cursor.execute("select * from history where deckname='%s'order by id desc limit 0, 1" % deckname)
        values = cursor.fetchall()
        cursor.close()
        conn.close()
        # values[number of raw][0->id,1->terms,2->time]
        if values:
            terms = pickle.loads(values[0][1])
            return terms

        else:
            return False


class API(object):

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
            phrases = ["No phrase"]
            phrase_explains = ["No phrase definition"]

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
