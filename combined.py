# -*- coding: utf-8 -*-
from HTMLParser import HTMLParser
import sys
import os
import urllib
import urllib2
import cookielib
reload(sys)
sys.setdefaultencoding('utf-8')

# ################Login section################


class SmartRedirectHandler(urllib2.HTTPRedirectHandler):
    def http_error_302(self, req, fp, code, msg, headers):
        result = urllib2.HTTPRedirectHandler.http_error_302(self, req, fp, code, msg, headers)
        result.status = code
        result.headers = headers
        return result


class youdao(object):

    def __init__(self, username, password):
        self.cookie_filename = 'youdao_cookie'
        self.fake_header = [
            ('User-Agent', 'Mozilla/5.0 (Macintosh Intel Mac OS X 10_10_5) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/47.0.2526.106 Safari/537.36'),
            ('Content-Type', 'application/x-www-form-urlencoded'),
            ('Cache-Control', 'no-cache'),
            ('Accept', '*/*'),
            ('Connection', 'Keep-Alive'),
        ]
        self.username = username
        self.password = password
        self.cj = cookielib.LWPCookieJar(self.cookie_filename)
        if os.access(self.cookie_filename, os.F_OK):
            self.cj.load(self.cookie_filename, ignore_discard=True, ignore_expires=True)
        self.opener = urllib2.build_opener(
            SmartRedirectHandler(),
            urllib2.HTTPHandler(debuglevel=0),
            urllib2.HTTPSHandler(debuglevel=0),
            urllib2.HTTPCookieProcessor(self.cj)
        )
        self.opener.addheaders = self.fake_header

    def loginToYoudao(self):
        self.cj.clear()
        self.opener.open(
            'http://account.youdao.com/login?back_url=http://dict.youdao.com&service=dict')
        login_data = urllib.urlencode({
            'app': 'web',
            'tp': 'urstoken',
            'cf': '7',
            'fr': '1',
            'ru': 'http://dict.youdao.com',
            'product': 'DICT',
            'type': '1',
            'um': 'true',
            'username': self.username,
            'password': self.password,
            'savelogin': '1',
        })
        response = self.opener.open('https://logindict.youdao.com/login/acc/login', login_data)
        if response.headers.get('Set-Cookie').find(self.username) > -1:
            self.cj.save(self.cookie_filename, ignore_discard=True, ignore_expires=True)
            return True
        else:
            return False
# #############################################

# ################Parse section################


class YoudaoParser(HTMLParser):
    def __init__(self):
        HTMLParser.__init__(self)
        self.terms = []
        self.definitions = []

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


# ################main
login = youdao('Username', 'Password')
parser = YoudaoParser()

# open page and retrive source page

# extract the terms and definitions
