#!/usr/bin/env python
# -*- coding: utf-8 -*-
from flask import Flask
import requests
import os
import pickle
import cookielib
import urllib2
import json
import re
import datetime
import time
import copy
import pickle
from lxml import etree
from lxml import html
app = Flask(__name__)

@app.route('/')
def hello():
    def save_cookies_lwp(cookiejar, filename):
        lwp_cookiejar = cookielib.LWPCookieJar()
        for c in cookiejar:
            args = dict(vars(c).items())
            args['rest'] = args['_rest']
            del args['_rest']
            c = cookielib.Cookie(**args)
            lwp_cookiejar.set_cookie(c)
        lwp_cookiejar.save(filename, ignore_discard=True)
    def load_cookies_from_lwp(filename):
        lwp_cookiejar = cookielib.LWPCookieJar()
        lwp_cookiejar.load(filename, ignore_discard=True)
        return lwp_cookiejar
    def login(userName,passWord):
        url = "https://logindict.youdao.com/login/acc/login"
        payload = "username="+userName+"&password="+passWord+"&savelogin=1&app=web&tp=urstoken&cf=7&fr=1&ru=http%3A%2F%2Fdict.youdao.com%2Fwordbook%2Fwordlist%3Fkeyfrom%3Dnull&product=DICT&type=1&um=true"
        headers = {
            'cache-control': "no-cache",
            'content-type': "application/x-www-form-urlencoded"
            }
        s = requests.session()
        response = s.post(url, data=payload, headers=headers)
        #save human-readable
        save_cookies_lwp(s.cookies, "cookies")
        # pass a LWPCookieJar directly to requests
        # requests.get(url, cookies=load_cookies_from_lwp(filename))
        return [response ,s]
    def getRaw(sessioned):
        raw = []
        response = sessioned[0]
        s = sessioned[1]
        totalPage = int(re.findall(r'(\w*[0-9]+)\w*',html.fromstring(response.text).xpath('//div[@id="pagination"]/a[last()]/@href')[0])[0])-1;
        #抓取每一页
        for num in range(0,totalPage):
            r = s.get("http://dict.youdao.com/wordbook/wordlist?p="+str(num)+"&tags=")
            raw.append(r.text.encode('utf-8'))
        return raw
    def extract(raw):
        terms=[]
        definition=[]
        dates=[]
        for item in raw:
            data={'deleted':[None],'terms':{}}
            html = etree.HTML(item)
            raw_terms = html.xpath('//div[@class="word"]//a//strong')
            raw_definition = html.xpath('//div[@class="desc"]')
            raw_dates  = html.xpath('//*[@id="wordlist"]/table/tbody/tr/td[last()-2]')
            for item in raw_terms:
                terms.append(item.text)

            for item in raw_definition:
                definition.append(item.text)

            for item in raw_dates:
                dates.append(item.text)

        return [terms,definition,dates]

    def echoJson(terms,definition,dates):
        data = {'deleted':[None],'terms':[]}
        for index,item in enumerate(terms):
            data['terms'].append({'term':item,'definition':definition[index],'image':None,'date':dates[index]})
        data['terms'] = sortByDate(data['terms'])
        return json.dumps(data,indent=4)

    def sortByDate(dt):
            dt.sort(key=lambda item: datetime_timestamp(item['date']))
            dt.reverse()
            return dt
    def datetime_timestamp(dt):
        time.strptime(dt, '%Y-%m-%d')
        s = time.mktime(time.strptime(dt, '%Y-%m-%d'))
        return int(s)

    def saveCurrent(current):
        f=open('previous','wb')
        pickle.dump(current,f) 
    def compare(current):
        data = {'deleted':[None],'terms':[None]}
        added = []
        deleted = []
        if os.path.exists('previous'):
            previous = pickle.load(open('previous','rb'))
            for iterm in previous[0]:
                if iterm not in current[0]:
                    deleted.append(iterm)
            if len(deleted):
                data['deleted'] = deleted

            for index,iterm in enumerate(current[0]):
                if iterm not in previous[0]:
                    added.append({'term':iterm,'definition':current[1][index],'image':None,'date':current[2][index]})
            if len(added):
                data['terms'] = sortByDate(added)

            saveCurrent(current)
            return json.dumps(data,indent=4)
        else:
            saveCurrent(current)
            return echoJson(current[0],current[1],current[2])


    ###############

    current = getRaw(login('这里修改用户名','这里修改密码'))
    current = extract(current)
    return compare(current)

app.run()
