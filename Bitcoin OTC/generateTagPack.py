#!/usr/bin/env python3
"""
Convert #bitcoin-otc web of trust data to a TagPack.
"""

import os
from urllib.error import HTTPError
from urllib.parse import urlencode, unquote
from urllib.request import urlretrieve, urlopen
from datetime import datetime, date
from typing import List

import yaml


SKS_LOOKUP_URL = 'https://sks.pod01.fleetstreetops.com/pks/lookup'


class RawData:
    """
    Download and read data provided by the source.
    """
    def __init__(self, fn: str, url: str):
        self.fn = fn
        self.url = url

    def download(self):
        urlretrieve(self.url, self.fn)

    def read(self) -> List[dict]:
        import json
        with open(self.fn, 'r',encoding='utf-8') as jsonfile:
            return json.load(jsonfile)


class TagPackGenerator:
    """
    Generate a TagPack from #bitcoin-otc web of trust data.
    """

    def __init__(self, rows: List[dict], title: str, creator: str, description: str, lastmod: date, source: str):
        self.rows = rows
        self.data = {
            'title': title,
            'creator': creator,
            'description': description,
            'source': source,
            'lastmod': lastmod,
            'currency': 'BTC',
            'category': 'user',
            'confidence': 'web_crawl',
            'tags': []
        }

    def generate(self):
        tags = []
        self.data['tags'] = tags
        for row in self.rows:
            if row['bitcoinaddress'] is None:
                continue  # There is no value for a tag without BTC address
            tag = {'address': row['bitcoinaddress']}
            label = ['User {nick} at Libera IRC #bitcoin-otc channel'.format(nick=row['nick'])]
            keyid = row['keyid']
            if keyid is not None:
                label += ['OpenPGP key id: {keyid}'.format(keyid=keyid)]
                params = urlencode({'search': '0x{id}'.format(id=row['keyid']), 'fingerprint': 'on', 'op': 'index'})
                url = '{lookup_url}?{params}'.format(lookup_url=SKS_LOOKUP_URL, params=params)
                try:
                    with urlopen(url) as req:
                        lines = req.read().decode('utf-8').split('\n')
                    label += [unquote(line.split(':')[1]) for line in lines if line.startswith('uid:')]
                except HTTPError as error:
                    if error.code != 404:
                        print('{error}, URL: {url}'.format(error=error, url=url))
            tag['label'] = ', '.join(label)
            tags.append(tag)

    def saveYaml(self, fn: str):
        with open(fn, 'w', encoding='utf-8') as f:
            f.write(yaml.dump(self.data, sort_keys=False))


if __name__ == '__main__':
    with open('config.yaml', 'r') as config_file:
        config = yaml.safe_load(config_file)

    raw_data = RawData(config['RAW_FILE_NAME'], config['URL'])
    if not os.path.exists(config['RAW_FILE_NAME']):
        raw_data.download()

    last_mod = datetime.fromtimestamp(os.path.getmtime(config['RAW_FILE_NAME'])).date()
    generator = TagPackGenerator(raw_data.read(), config['TITLE'], config['CREATOR'], config['DESCRIPTION'],
                                 last_mod, config['SOURCE'])
    generator.generate()
    generator.saveYaml(config['TAGPACK_FILE_NAME'])
