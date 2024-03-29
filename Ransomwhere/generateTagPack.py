#!/usr/bin/env python3
# -*- coding:utf-8 -*- 

import os
import json
from datetime import datetime as dt

import yaml
import requests


class RawData:
    def __init__(self, fileName, url):
        self.fileName = fileName
        self.url = url
        if not os.path.exists(self.fileName):
            self.downloadJson()

    def downloadJson(self):
        res = requests.get(self.url)
        with open(self.fileName, "w") as fout:
            fout.write(res.text)

    def returnJson(self):
        with open(self.fileName, "r") as fin:
            jsonData = json.load(fin)
        return jsonData["result"]


class Tag:
    def __init__(self, address, currency, label):
        self.data = {"address": address, "currency": currency, "label": label}

    def getTagData(self):
        return self.data


class TagPack:
    def __init__(self, title, creator, description, lastmod, source):
        self.data = {"title": title, "creator": creator, "description": description, "lastmod": lastmod,
                     "category": "perpetrator", "abuse": "ransomware", "source": source, "tags": []}

    def addTag(self, tag):
        self.data["tags"] += [tag.getTagData()]

    def dumpYaml(self):
        return yaml.dump(self.data, sort_keys=False)


class TagPackGenerator:
    def __init__(self, rawJson, title, creator, description, lastmod, source):
        self.rawJson = rawJson
        self.tagPack = TagPack(title, creator, description, lastmod, source)
        self.checkList = ["address", "blockchain", "family"]

    @staticmethod
    def getCoinAlias(blockchain):
        table = {"ada": "ADA", "bitcoin cash": "BCH", "binance": "BNB", "bitcoin sv": "BSV", "bitcoin": "BTC",
                 "dash": "DASH", "dogecoin": "DOGE", "eos": "EOS", "ethereum": "ETH", "litecoin": "LTC",
                 "vertcoin": "VTC", "stellar lumen": "XLM", "monero": "XMR", "ripple": "XRP", "tez": "XTZ",
                 "zcash": "ZEC"}
        if blockchain in table:
            return table[blockchain]
        else:
            return blockchain

    def generate(self):
        for datum in self.rawJson:
            invalid = False
            for check in self.checkList:
                if check not in datum:
                    invalid = True
                    break
            if invalid:
                continue
            tag = Tag(datum["address"],
                      self.getCoinAlias(datum["blockchain"]),
                      "Ransomware: {family}".format(family=datum["family"]))
            self.tagPack.addTag(tag)

    def saveYaml(self, fileName):
        with open(fileName, "w") as fout:
            fout.write(self.tagPack.dumpYaml())


if __name__ == "__main__":
    with open("config.yaml", "r") as fin:
        config = yaml.safe_load(fin)

    rawData = RawData(config["RAW_FILE_NAME"], config["URL"])
    rawJson = rawData.returnJson()

    lastmod = dt.now().date()

    tagPackGenerator = TagPackGenerator(rawJson, config["TITLE"], config["CREATOR"], config["DESCRIPTION"], lastmod, config["SOURCE"])
    tagPackGenerator.generate()
    tagPackGenerator.saveYaml(config["TAGPACK_FILE_NAME"])
