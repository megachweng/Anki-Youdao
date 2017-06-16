# -*- coding: utf-8 -*-
from HTMLParser import HTMLParser
import sys
reload(sys)
sys.setdefaultencoding('utf-8')


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


parser = YoudaoParser()

# open page and retrive source page

# extract the terms and definitions
