#!/usr/bin/env python3
"""
Convert ScamSearch data to a TagPack.
"""
import os
import re
import json
from datetime import datetime
from typing import List, Optional, Tuple

import yaml
from selenium import webdriver
from selenium.webdriver.common.by import By

REGEX = [
    ('BTC', re.compile(r'\b((bc(0([ac-hj-np-z02-9]{39}|[ac-hj-np-z02-9]{59})|1[ac-hj-np-z02-9]{8,87}))|[13][a-km-zA-HJ-NP-Z1-9]{25,34})\b')),
    ('BCH', re.compile(r'\b(((?:bitcoincash|bchtest):)?([13][0-9a-zA-Z]{33}))|(((?:bitcoincash|bchtest):)?(qp)?[0-9a-zA-Z]{40})\b')),
    ('LTC', re.compile(r'\b([LM3][a-km-zA-HJ-NP-Z1-9]{25,33})\b')),
    ('ZEC', re.compile(r'\b([tz][13][a-km-zA-HJ-NP-Z1-9]{33})\b')),
    ('ETH', re.compile(r'\b((0x)?[0-9a-fA-F]{40})\b'))
]
NO_BTC_INTERVAL = 100


class RawData:
    """
    Download and read data provided by the source.
    """
    def __init__(self, fn: str, url: str):
        self.fn = fn
        self.url = url

    def download(self):
        options = webdriver.FirefoxOptions()
        options.add_argument('--headless')
        wd = webdriver.Firefox(options=options)
        wd.get(self.url)
        with open(self.fn, 'w', encoding='utf-8') as jsonlines_file:
            scraped_addresses = set()

            def find_currency(address: str) -> Optional[str]:
                for currency, regex in REGEX:
                    if regex.fullmatch(address):
                        return currency
                else:
                    return None

            def find_unscraped_address_index(addresses: List[str]) -> Tuple[Optional[int], Optional[str]]:
                for index, address in enumerate(addresses):
                    if address not in scraped_addresses:
                        currency = find_currency(address)
                        if currency is None:
                            continue
                        return index, currency
                else:
                    return None, None

            page_index = last_page_with_btc_index = 1
            while True:
                address_links = wd.find_elements(By.CSS_SELECTOR, 'button.looklink')
                index, currency = find_unscraped_address_index([link.text for link in address_links])
                if index is None:
                    if page_index - last_page_with_btc_index > NO_BTC_INTERVAL:
                        break
                    next_page_link = wd.find_element(By.XPATH, '//li[@class="uk-active"]/following-sibling::li[1]/a')
                    next_page_link.click()
                    page_index += 1
                else:
                    last_page_with_btc_index = page_index
                    address = address_links[index].text
                    address_links[index].click()
                    report_count = wd.find_element(By.XPATH, '//td[text()="Report Count"]/following-sibling::td').text
                    latest_report = wd.find_element(By.XPATH, '//td[text()="Latest Report"]/following-sibling::td').text
                    latest_date = datetime.strptime(latest_report.strip(), '%a, %d %b %Y %H:%M:%S').date()
                    data = {
                        'address': address,
                        'currency': currency,
                        'date': str(latest_date),
                        'count': int(report_count)
                    }
                    print(json.dumps(data, ensure_ascii=False), file=jsonlines_file)
                    scraped_addresses.add(address)
                    wd.back()
        wd.quit()

    def read(self) -> List[dict]:
        with open(self.fn, 'r',encoding='utf-8') as jsonlines_file:
            return [json.loads(line) for line in jsonlines_file]


class TagPackGenerator:
    """
    Generate a TagPack from ScamSearch data.
    """

    def __init__(self, rows: List[dict], title: str, creator: str, description: str, lastmod: str, source: str):
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
                'currency': row['currency'],
                'label': 'Abuse report at ScamSearch.io' if row['count'] == 1 else 'Abuse reports at ScamSearch.io',
                'source': 'https://scamsearch.io/search_report?searchoption=all&search={address}'.format(
                    address=row['address']
                )
            }
            tags.append(tag)
        self.data['tags'] = tags

    def saveYaml(self, fn: str):
        with open(fn, 'w', encoding='utf-8') as f:
            f.write(yaml.dump(self.data, sort_keys=False, allow_unicode=True))


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
