#!/usr/bin/env python3
# -*- coding:utf-8 -*- 

import os
import re
import yaml
import requests

# Taken from OFAC Specially Designated Nationals generator and modified
REGEX = [
    ('BTC', re.compile(r'\b((bc(0([ac-hj-np-z02-9]{39}|[ac-hj-np-z02-9]{59})|1[ac-hj-np-z02-9]{8,87}))|[13][a-km-zA-HJ-NP-Z1-9]{25,34})\b')),
    ('BCH', re.compile(r'\b(((?:bitcoincash|bchtest):)?([13][0-9a-zA-Z]{33}))|(((?:bitcoincash|bchtest):)?(qp)?[0-9a-zA-Z]{40})\b')),
    ('LTC', re.compile(r'\b([LM3][a-km-zA-HJ-NP-Z1-9]{25,33})\b')),
    ('ZEC', re.compile(r'\b([tz][13][a-km-zA-HJ-NP-Z1-9]{33})\b')),
    ('ETH', re.compile(r'\b((0x)?[0-9a-fA-F]{40})\b')),
    ('USDT', re.compile(r'\bT[A-Za-z1-9]{33}\b'))
]


class RawData:
    def __init__(self, fileName, url):
        self.fileName = fileName
        self.url = url
        if not os.path.exists(self.fileName):
            self.downloadYaml()

    def downloadYaml(self):
        res = requests.get(self.url)
        with open(self.fileName, "w") as fout:
            fout.write(res.text)

    def returnYaml(self):
        with open(self.fileName, "r") as fin:
            yamlData = yaml.safe_load(fin.read())
        return yamlData


class Tag:
    def __init__(self, address, currency, label, source, category):
        category_and_abuse_map = {
            "Phishing": {"category": "perpetrator", "abuse": "phishing"},
            "Fake ICO": {"category": "perpetrator", "abuse": "investment_fraud"},
            "Scamming": {"category": "perpetrator", "abuse": "scam"},
            "Scam": {"category": "perpetrator", "abuse": "scam"}
        }
        self.data = {"address": address, "currency": currency, "label": "Scam at " + label,
                     "source": "https://cryptoscamdb.org/" if source == "MyCrypto" else source,
                     "category": category_and_abuse_map[category]["category"],
                     "abuse": category_and_abuse_map[category]["abuse"],
                     'confidence': 'web_crawl',}

    def getTagData(self):
        return self.data


class TagPack:
    def __init__(self, title, creator, description, lastmod):
        self.data = {}
        self.data["title"]       = title
        self.data["creator"]     = creator
        self.data["description"] = description
        self.data["lastmod"]     = lastmod
        self.data["tags"]        = []

    def addTag(self, tag):
        self.data["tags"] += [tag.getTagData()]

    def dumpYaml(self):
        return yaml.dump(self.data, sort_keys=False)


class TagPackGenerator:
    def __init__(self, rawYaml, title, creator, description, lastmod):
        self.rawYaml = rawYaml
        self.tagPack = TagPack(title, creator, description, lastmod)
        self.checkList = ["addresses", "coin", "name", "reporter", "category"]

    def generate(self):
        for datum in self.rawYaml:
            invalid = False
            for check in self.checkList:
                if check not in datum:
                    invalid = True
                    break
            if invalid:
                continue
            for address in datum["addresses"]:
                for coin, address_format in REGEX:
                    if address_format.fullmatch(address):
                        datum["coin"] = coin
                        break
                else:
                    print('Unknown address format: ' + address)
                    continue
                tag = Tag(address,
                          datum["coin"],
                          datum["name"],
                          datum["reporter"], 
                          datum["category"])
                self.tagPack.addTag(tag)

    def saveYaml(self, fileName):
        with open(fileName, "w") as fout:
            fout.write(self.tagPack.dumpYaml())


if __name__ == "__main__":
    with open("config.yaml", "r") as fin:
        config = yaml.safe_load(fin)

    rawData = RawData(config["RAW_FILE_NAME"], config["URL"])
    rawYaml = rawData.returnYaml()

    tagPackGenerator = TagPackGenerator(rawYaml, config["TITLE"], config["CREATOR"], config["DESCRIPTION"], config["LASTMOD"])
    tagPackGenerator.generate()
    tagPackGenerator.saveYaml(config["TAGPACK_FILE_NAME"])
