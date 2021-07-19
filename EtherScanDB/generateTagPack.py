# -*- coding:utf-8 -*- 
#!/usr/bin/pyhton3

import os
import yaml
import requests

class RawData:
    def __init__(self, fileName, url):
        self.fileName = fileName
        self.url = url
        if not os.path.exists(self.fileName):
            self.downloadYAML()

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
        self.data = {}
        self.data["address"]  = address
        self.data["currency"] = currency
        self.data["label"]    = label
        self.data["source"]   = source
        if self.data["source"] == "MyCrypto":
            self.data["source"] = "https://cryptoscamdb.org/"
        self.data["category"] = category

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
