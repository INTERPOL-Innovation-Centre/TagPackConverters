#!/usr/bin/env python3
"""
Convert Southern Poverty Law Center Cryptocurrency Report to a TagPack.
"""

import os
import csv
from datetime import datetime, date
from typing import List

import yaml


CURRENCY = {
    'Bitcoin Addresses': 'BTC',
    'Ethereum Addresses': 'ETH',
    'Litecoin Addresses': 'LTC',
    'Monero Address': 'XMR'
}


class RawData:
    """
    Download and read data provided by the source.
    """
    def __init__(self, fn: str, url: str):
        self.fn = fn
        self.url = url

    def download(self):
        from urllib.request import urlretrieve
        urlretrieve(self.url, self.fn)

    def read(self) -> List[dict]:
        with open(self.fn, 'r',encoding='utf-8', newline='') as csvfile:
            reader = csv.DictReader(csvfile, delimiter=',', quotechar='"')
            return [row for row in reader]


class TagPackGenerator:
    """
    Generate a TagPack from SPLC Cryptocurrency Report.
    """

    def __init__(self, rows: List[dict], title: str, creator: str, description: str, lastmod: date, source: str):
        self.rows = rows
        self.data = {
            'title': title,
            'creator': creator,
            'description': description,
            'lastmod': lastmod,
            'tags': []
        }
        self.source = source

    def generate(self):
        tags = []
        for row in self.rows:
            for column in ['Bitcoin Addresses', 'Ethereum Addresses', 'Litecoin Addresses', 'Monero Address']:
                for address in row[column].split('\n'):
                    if not address:
                        continue
                    tag = {
                        'address': address,
                        'currency': CURRENCY[column],
                        'label': row['Entity'],
                        'source': self.source,
                        'category': 'User'  # like in the OFAC TagPack generator
                    }
                    tags.append(tag)
        self.data['tags'] = tags

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
