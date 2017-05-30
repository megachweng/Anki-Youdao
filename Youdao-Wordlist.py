#!/usr/bin/env python
# -*- coding: utf-8 -*-
__window = None

import sys
import math
import time
import datetime as dt
import urllib as url1
import urllib2 as url2
import json
import re

# Anki
from aqt import mw
from aqt.qt import *

# PyQT
from PyQt4.QtGui import *
# from PyQt4.Qt import Qt

# Add custom model if needed


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


class YoudaoWindow(QWidget):
    """main window of Youdao plugin; shows search results"""

    def __init__(self):
        super(YoudaoWindow, self).__init__()
        self.results = None
        self.thread = None
        self.initGUI()
        self.deckName = ''

    def initGUI(self):
        """create the GUI skeleton"""

        self.box_top = QVBoxLayout()
        self.box_upper = QHBoxLayout()

        # left side
        self.box_left = QVBoxLayout()

        # name field
        urlFromFile = ' '
        deckName = 'Youdao-Wordlist'
        if os.path.exists('url'):
            f1 = open('url', 'r').read()
            urlFromFile = f1
        if os.path.exists('deck'):
            f2 = open('deck', 'r').read()
            deckName = f2
        self.box_name = QHBoxLayout()
        self.box_name1 = QHBoxLayout()
        self.label_name = QLabel("Server Address:")
        self.label_name1 = QLabel("Sync to Deck:")
        self.text_name = QLineEdit(urlFromFile, self)
        self.text_name1 = QLineEdit(deckName, self)
        self.text_name.setMaximumWidth(150)
        self.text_name.setMinimumWidth(150)
        self.text_name1.setMaximumWidth(150)
        self.text_name1.setMinimumWidth(150)

        self.box_name.addWidget(self.label_name)
        self.box_name.addWidget(self.text_name)
        self.box_name1.addWidget(self.label_name1)
        self.box_name1.addWidget(self.text_name1)
        self.box_left.addLayout(self.box_name)
        self.box_left.addLayout(self.box_name1)
        self.box_right = QVBoxLayout()
        self.box_code = QHBoxLayout()
        self.button_code = QPushButton("Sync", self)
        self.button_code.setMinimumWidth(100)
        self.button_code.setMinimumHeight(70)
        self.box_code.addStretch(1)
        self.box_code.addWidget(self.button_code)
        self.button_code.clicked.connect(self.onCode)

        self.box_right.addLayout(self.box_code)
        self.box_upper.addLayout(self.box_left)
        self.box_upper.addSpacing(10)
        self.box_upper.addLayout(self.box_right)
        self.box_top.addLayout(self.box_upper)
        self.box_top.addStretch(1)
        self.setLayout(self.box_top)
        self.setMinimumWidth(400)
        self.setMaximumHeight(400)
        self.setSizePolicy(QSizePolicy.Minimum, QSizePolicy.Minimum)
        self.setWindowTitle("Sync with Youdao Word-list")
        self.show()

    def onCode(self):
        # build URL
        deck_url = self.text_name.text()
        deckName = self.text_name1.text()
        self.deckName = deckName
        f1 = open('url', 'wb')
        f1.write(deck_url)
        f1.close()

        f2 = open('deck', 'wb')
        f2.write(deckName)
        f2.close()
        # stop the previous thread first
        if not self.thread == None:
            self.thread.terminate()

        # download the data!
        self.thread = YoudaoDownloader(self, deck_url)
        self.thread.start()

        while not self.thread.isFinished():
            mw.app.processEvents()
            self.thread.wait(50)

        # error with fetching data
        if self.thread.error:
            print "Something went wrong"
        else:
            result = self.thread.results
            self.syncYoudao(result)
            # self.close()
        self.thread.terminate()
        self.thread = None

    def syncYoudao(self, result):
        """create new Anki deck from downloaded data"""
        # create new deck and custom model

        # name = result['title'] + " by " + result['created_by']
        # name = "Youdao-Wordlist"
        name = self.text_name1.text()
        deleted = result['deleted']
        terms = result['terms']
        cardID = []
        if not terms[0] is None:
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
            txt = u"""
            <div><img src="{0}" /></div>
            """
            for term in terms:
                note = mw.col.newNote()
                note["Front"] = term["term"]
                if term['definition'] is None:
                    term["definition"] = 'NULL'
                note["Back"] = term["definition"].replace('\n', '<br>')
                # if not term["image"] is None:
                #     # stop the previous thread first
                #     file_name = self.fileDownloader(term["image"]["url"])
                #     note["Back"] += txt.format(file_name)
                #     mw.app.processEvents()
                mw.col.addNote(note)
            mw.col.reset()
            mw.reset()

        if not deleted[0] is None:
            for iterm in deleted:
                cardsToDelete = []
                deckID = mw.col.decks.id(self.deckName)
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

    # def fileDownloader(self, url):
    #     file_name = "Youdao-" + url.split('/')[-1]
    #     url1.urlretrieve(url, file_name)
    #     return file_name


class YoudaoDownloader(QThread):
    """thread that downloads results from the Youdao API"""

    def __init__(self, window, url):
        super(YoudaoDownloader, self).__init__()
        self.window = window
        self.url = url
        self.error = False
        self.results = None

    def run(self):
        """run thread; download results!"""
        self.window.button_code.setEnabled(False)
        self.window.button_code.setText('Syncing......')
        try:
            self.results = json.load(url2.urlopen(self.url))  # Here pass the json data
        except url2.URLError:
            self.error = True
        else:
            # if no results, there was an error
            if self.results == None:
                self.error = True
        self.window.button_code.setEnabled(True)
        self.window.button_code.setText('Sync')


def runYoudaoPlugin():
    """menu item pressed; display search window"""
    global __window
    __window = YoudaoWindow()


# create menu item
action = QAction("Import your Youdao WordList", mw)
mw.connect(action, SIGNAL("triggered()"), runYoudaoPlugin)
mw.form.menuTools.addAction(action)
