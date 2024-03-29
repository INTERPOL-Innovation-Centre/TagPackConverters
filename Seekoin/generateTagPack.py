#!/usr/bin/env python3
"""
Convert SeeKoin data to a TagPack.
"""

import os
import json
from datetime import datetime, date
from typing import List

import yaml
from selenium import webdriver
from selenium.common import StaleElementReferenceException
from selenium.webdriver.common.by import By


class RawData:
    """
    Download and read data provided by the source.
    """
    def __init__(self, fn: str, url: str):
        self.fn = fn
        self.url = url

    def download(self):
        wd = webdriver.Firefox()
        wd.get(self.url)
        with open(self.fn, 'w', encoding='utf-8') as jsonlines_file:
            while True:
                for row in wd.find_elements(By.CSS_SELECTOR, 'table tr'):
                    address_links = row.find_elements(By.CSS_SELECTOR, 'td a')
                    if not address_links:
                        continue
                    address_link = address_links[-1]
                    if address_link.text == '>>>':  # Handle next page link
                        address_link.click()
                        break
                    elif address_link.text == '<<<':  # Handle end of table
                        wd.quit()
                        os.remove('geckodriver.log')
                        return
                    # Skip spam entries
                    try:
                        comment = row.find_element(By.CSS_SELECTOR, 'td:nth-child(5)').text
                    except StaleElementReferenceException:
                        continue
                    if comment == 'Bittrex is a global crypt' or comment == 'Huobi is a Seychelles-bas':
                        continue
                    data = {
                        'address': address_link.text,
                        'date': row.find_element(By.CSS_SELECTOR, 'td:nth-child(2)').text,
                        'type': row.find_element(By.CSS_SELECTOR, 'td:nth-child(3)').text,
                        'hits': int(row.find_element(By.CSS_SELECTOR, 'td:nth-child(4)').text),
                        'comment': comment
                    }
                    print(json.dumps(data, ensure_ascii=False), file=jsonlines_file)

    def read(self) -> List[dict]:
        with open(self.fn, 'r', encoding='utf-8') as jsonlines_file:
            return [json.loads(line) for line in jsonlines_file]


class TagPackGenerator:
    """
    Generate a TagPack from Seekoin data.
    """

    def __init__(self, rows: List[dict], title: str, creator: str, description: str, lastmod: date, source: str):
        self.rows = rows
        self.data = {
            'title': title,
            'creator': creator,
            'description': description,
            'lastmod': lastmod,
            'category': 'perpetrator',
            'confidence': 'web_crawl',
            'tags': []
        }
        self.source = source

    def generate(self):
        tags = []
        for row in self.rows:
            tag = {
                'address': row['address'],
                'currency': 'BTC',
                'label': '{type} report(s) at SeeKoin.com'.format(type=row['type']),
                'source': 'https://seekoin.com/addr-{address}'.format(address=row['address'])
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
