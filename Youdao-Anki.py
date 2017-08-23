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
from PyQt4 import QtGui
from PyQt4.QtGui import *

__window = None


def addCustomModel(name, col):
    """create a new custom model for the imported deck"""
    mm = col.models
    existing = mm.byName("Basic Youdao")
    if existing:
        return existing
    m = mm.new("Basic Youdao")
    # add fields
    mm.addField(m, mm.newField("Front"))
    mm.addField(m, mm.newField("Back"))
    mm.addField(m, mm.newField("Add Reverse"))
    # add cards
    t = mm.newTemplate("Normal")
    t['qfmt'] = "{{Front}}"
    t['afmt'] = "{{FrontSide}}\n\n<hr id=answer>\n\n{{Back}}"
    mm.addTemplate(m, t)

    t = mm.newTemplate("Reverse")
    t['qfmt'] = "{{#Add Reverse}}{{Back}}{{/Add Reverse}}"
    t['afmt'] = "{{FrontSide}}\n\n<hr id=answer>\n\n{{Front}}"
    mm.addTemplate(m, t)

    mm.add(m)
    return m


class Window(QWidget):
    def __init__(self, parent=None):
        super(Window, self).__init__(parent)
        self.results = None
        self.thread = None
        username = ''
        password = ''
        deckname = 'Youdao'
        settings = self.retriveSettings()
        if settings:
            username = settings[0]
            password = settings[1]
            deckname = settings[2]
        self.setUI(username, password, deckname)

    def setUI(self, username, password, deckname):
        # creates the tabwidget
        self.tabwidget = QTabWidget()
        self.sync_tab = QWidget()
        self.setting_tab = QWidget()
        # adds the tabs to the tabwidget
        self.tabwidget.addTab(self.sync_tab, "Sync")
        self.tabwidget.addTab(self.setting_tab, "Login")

        # ###loging tab
        self.username_edit = QLineEdit(username)
        self.username_edit.setPlaceholderText("example: john@163.com ")
        self.password_edit = QLineEdit(password)
        self.password_edit.setPlaceholderText("Input your Password")
        self.password_edit.setEchoMode(QLineEdit.Password)
        self.setting_tab_layout = QGridLayout()
        self.setting_tab_layout.setContentsMargins(-1, -2, -1, -1)
        self.setting_tab_layout.setGeometry(QRect(10, 10, 351, 71))
        self.setting_tab_layout.addWidget(QLabel('Username:'), 0, 0, 1, 1)
        self.setting_tab_layout.addWidget(self.username_edit, 0, 1, 1, 1)
        self.setting_tab_layout.addWidget(QLabel('Password:'), 1, 0, 1, 1)
        self.setting_tab_layout.addWidget(self.password_edit, 1, 1, 1, 1)
        self.setting_tab.setLayout(self.setting_tab_layout)

        # #sync tab
        self.sync_layoutWidget = QWidget(self.sync_tab)
        self.sync_layoutWidget.setGeometry(QRect(7, 10, 361, 81))
        self.sync_all_layout = QGridLayout(self.sync_layoutWidget)
        self.sync_all_layout.setContentsMargins(0, 0, 0, 0)
        self.sync_main_layout = QGridLayout()
        self.sync_to_lineEdit = QLineEdit(deckname)
        self.sync_button = QPushButton('Sync')
        self.sync_button.clicked.connect(self.onCode)
        self.progress = QProgressBar(self.sync_layoutWidget)
        self.progress.setGeometry(QRect(7, 70, 361, 23))
        self.progress.setMaximum(23)
        self.progress.setProperty("value", 0)
        self.progress.setInvertedAppearance(False)
        self.sync_layout = QGridLayout()
        self.sync_layout.setGeometry(QRect(10, 10, 351, 71))
        self.sync_main_layout.addWidget(QLabel("Sync to"), 0, 0, 1, 1)
        self.sync_main_layout.addWidget(self.sync_to_lineEdit, 0, 1, 1, 1)
        self.sync_main_layout.addWidget(self.sync_button, 0, 2, 1, 1)
        self.sync_all_layout.addLayout(self.sync_main_layout, 0, 0, 1, 1)
        self.sync_all_layout.addWidget(self.progress, 1, 0, 1, 1)
        self.sync_tab.setLayout(self.sync_layout)

        # creates a vertical box layout for the window
        vlayout = QVBoxLayout()
        vlayout.addWidget(self.tabwidget)  # adds the tabwidget to the layout
        self.setLayout(vlayout)  #
        self.resize(420, 150)
        self.setMaximumHeight(150)
        self.setMaximumWidth(150)
        self.setMinimumWidth(420)
        self.setMinimumWidth(420)

        # login first if no username and password provided
        if self.username_edit.text() == '' or self.password_edit.text() == '':
            self.tabwidget.setCurrentIndex(1)
        self.setWindowTitle("Sync with Youdao Word-list")

        self.show()  # shows the window

    def onCode(self):
        if self.username_edit.text() == '' or self.password_edit.text() == '':
            self.tabwidget.setCurrentIndex(1)
            showInfo('\n\nPlease enter your Username and Password!')
        else:
            if askUser('Sync Now?'):
                username = self.username_edit.text()
                password = self.password_edit.text()
                deckname = self.sync_to_lineEdit.text()

                self.sync_button.setEnabled(False)
                self.sync_button.setText('Please Wait')
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
                    print "Something went wrong"
                else:
                    self.saveSettings(username, password, deckname)
                    result = json.loads(self.thread.results)
                    self.syncYoudao(result)

                self.thread.terminate()
                self.thread = None

    def syncYoudao(self, result):
        name = self.sync_to_lineEdit.text()
        deleted = result['deleted']
        terms = result['terms']
        cardID = []
        info_add = '0'
        info_delete = '0'

        if terms[0] is not None:
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
                note["Front"] = term["term"]
                if term['definition'] is None:
                    term["definition"] = 'NULL'
                note["Back"] = term["definition"].replace('\n', '<br>')

                mw.col.addNote(note)
            mw.col.reset()
            mw.reset()
            info_add = str(len(terms))

        if deleted[0] is not None:
            for iterm in deleted:
                cardsToDelete = []
                deckID = mw.col.decks.id(name)
                cardID.append(mw.col.findCards("front:" + iterm))
                for iterm in cardID:
                    for cid in iterm:
                        query = "select id from cards where did = " + \
                            str(deckID) + " and id= " + str(cid)
                        r = mw.col.db.list(query)
                        if r:
                            cardsToDelete.append(r[0])

            for iterm in cardsToDelete:
                mw.col.db.execute("delete from cards where id = ?", iterm)
                mw.col.db.execute("delete from notes where id = ?", iterm)
            mw.col.fixIntegrity()
            mw.reset()
            info_delete = str(len(deleted))
        showInfo('\nAdded : ' + info_add + '\n\nDeleted : ' + info_delete)

    def saveSettings(self, username, password, deckname):
        conn = sqlite3.connect('youdao-anki.db')
        cursor = conn.cursor()
        cursor.execute('INSERT OR IGNORE INTO settings (id,username,password,deckname) VALUES(?,?,?,?)',
                       (1, username, password, deckname))
        cursor.execute('UPDATE settings SET username=?,password=?,deckname=? WHERE id=1',
                       (username, password, deckname))
        cursor.rowcount
        conn.commit()
        conn.close()

    def retriveSettings(self):
        conn = sqlite3.connect('youdao-anki.db')
        cursor = conn.cursor()
        cursor.execute(
            'create table if not exists settings (id INTEGER primary key, username TEXT,password TEXT,deckname TEXT)')
        cursor.execute('select * from settings')
        values = cursor.fetchall()
        # values[number of raw][0->id,1->username,2->password,3->deckname]
        if values:
            username = values[0][1]
            password = values[0][2]
            deckname = values[0][3]
        else:
            return False
        cursor.rowcount
        conn.commit()
        conn.close()
        return [username, password, deckname]

    def loginFailed(self):
        self.tabwidget.setCurrentIndex(1)


class YoudaoDownloader(QThread):
    """thread that downloads results from the Youdao-wordlist website"""

    def __init__(self, window):
        super(YoudaoDownloader, self).__init__()
        self.window = window
        self.error = False
        self.results = None

    def run(self):
        """run thread; download results!"""

        # get youdao wordlist
        parser = YoudaoParser()
        if not self.login(self.window.username_edit.text(), self.window.password_edit.text()):
            self.window.loginFailed()
            self.window.username_edit.setPlaceholderText(
                'Login Failed!! Please Check Userinfo!!')
            self.window.username_edit.clear()
            self.window.password_edit.clear()
        else:
            totalPage = self.totalPage()
            self.window.progress.setMaximum(totalPage)

            for index in range(0, totalPage):
                self.window.progress.setValue(index + 1)
                # trigger progressBar everysingle time
                parser.feed(self.crawler(index))

            previous = parser.retrivePrevious()
            if previous:
                self.results = json.dumps(parser.compare(previous))
            else:
                self.results = json.dumps(parser.nocompare())

            # if no results, there was an error
            if self.results is None:
                self.error = True

        self.window.sync_button.setEnabled(True)
        self.window.sync_button.setText('Sync')

    def hex_md5(self, password):
        return hashlib.md5(password.encode('utf-8')).hexdigest()

    def login(self, username, password):
        password = self.hex_md5(password)

        url = "https://logindict.youdao.com/login/acc/login"
        payload = "username=" + urllib.quote(username) + "&password=" + password + \
            "&savelogin=1&app=web&tp=urstoken&cf=7&fr=1&ru=http%3A%2F%2Fdict.youdao.com%2Fwordbook%2Fwordlist%3Fkeyfrom%3Dnull&product=DICT&type=1&um=true"
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


class YoudaoParser(HTMLParser):
    def __init__(self):
        HTMLParser.__init__(self)
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
            data['terms'].append({'term': value, 'definition': self.definitions[index]})

        self.savePreviews(self.terms, self.definitions)
        self.saveSyncHistory(self.terms, self.definitions)
        return data

    def compare(self, previous):
        data = {'deleted': [None], 'terms': [None]}
        added = []
        deleted = []

        for iterm in previous[0]:
            if iterm not in self.terms:
                deleted.append(iterm)
        if len(deleted):
            data['deleted'] = deleted

        for index, iterm in enumerate(self.terms):
            if iterm not in previous[0]:
                added.append(
                    {'term': iterm, 'definition': self.definitions[index]})
        if len(added):
            data['terms'] = added

        self.saveSyncHistory(data['terms'], data['deleted'])
        self.savePreviews(self.terms, self.definitions)
        return data  # {'deleted': [apple,orange], 'terms': [None]}

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


def runYoudaoPlugin():
    """menu item pressed; display search window"""
    global __window
    __window = Window()


# create menu item
action = QAction("Import your Youdao WordList", mw)
mw.connect(action, SIGNAL("triggered()"), runYoudaoPlugin)
mw.form.menuTools.addAction(action)
