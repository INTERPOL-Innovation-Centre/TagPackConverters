#!/usr/bin/env python3
"""
Convert BitcoinAbuse data to a TagPack.
"""
import os
import sys
import json
from datetime import datetime
from typing import List

import yaml
from selenium import webdriver
from selenium.common.exceptions import NoSuchElementException, TimeoutException
from selenium.webdriver.common.by import By
from selenium.webdriver.firefox.options import Options


class RawData:
    """
    Download and read data provided by the source.
    """
    def __init__(self, fn: str, url: str):
        self.fn = fn
        self.url = url

    def download(self):
        # Do not load Javascript and image files
        options = Options()
        options.set_preference('javascript.enabled', False)
        options.set_preference('permissions.default.image', 2)
        wd = webdriver.Firefox(options=options)
        for _ in range(5):
            try:
                wd.get(self.url)
            except TimeoutException:
                print('Retrying URL {url} (retry {retry})'.format(url=self.url, retry=_+1), file=sys.stderr)
                continue
            else:
                break
        # Collect URLs of all reports
        report_urls = set()
        while True:
            for report_link in wd.find_elements(By.XPATH, '//a[contains(@href, "/reports/1") or contains(@href, "/reports/3") or contains(@href, "/reports/bc1")]'):
                report_urls.add(report_link.get_attribute('href'))
            try:
                next_page_link = wd.find_element(By.XPATH, '//ul[@class="pagination"]/li[contains(@class, "active")]/following-sibling::li/a')
                next_page_link.click()
            except NoSuchElementException:
                break
        print('Collected {len} addresses'.format(len=len(report_urls)))
        # Collect reports and write them into the raw data file
        with open(self.fn, 'w', encoding='utf-8') as jsonlines_file:
            for report_index, report_url in enumerate(report_urls, 1):
                print('Fetching {url} [{index}/{count}]'.format(url=report_url, index=report_index, count=len(report_urls)))
                for _ in range(5):
                    try:
                        wd.get(report_url)
                        # Here we try to find the most important element, which is absent on code 503 from CloudFlare
                        address = wd.find_element(By.XPATH, '//th[text()="Address"]/following-sibling::td/i').text
                    except (TimeoutException, NoSuchElementException):
                        print('Retrying URL {url} (retry {retry})'.format(url=report_url, retry=_+1), file=sys.stderr)
                        continue
                    else:
                        break
                count = int(wd.find_element(By.XPATH, '//th[text()="Report Count"]/following-sibling::td').text)
                latest_date = datetime.strptime(wd.find_element(By.XPATH, '//th[text()="Latest Report"]/following-sibling::td').text.split('\n')[0], '%a, %d %b %y %H:%M:%S %z').isoformat()
                data = {
                    'address': address,
                    'count': count,
                    'latest_date': latest_date
                }
                print(json.dumps(data), file=jsonlines_file)
        # Clean up
        wd.quit()
        os.remove('geckodriver.log')

    def read(self) -> List[dict]:
        with open(self.fn, 'r', encoding='utf-8') as jsonlines_file:
            return [json.loads(line) for line in jsonlines_file]


class TagPackGenerator:
    """
    Generate a TagPack from BitcoinAbuse data.
    """

    def __init__(self, rows: List[dict], title: str, creator: str, description: str, lastmod: str, source: str):
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
            date = datetime.fromisoformat(row['latest_date']).strftime('%Y-%m-%d')
            if row['count'] == 1:
                label = 'Abuse report added on {date}'.format(date=date)
            else:
                label = 'Last of {count} abuse reports added on {date}'.format(count=row['count'], date=date)
            tag = {
                'address': row['address'],
                'currency': 'BTC',
                'label': label,
                'source': 'https://www.bitcoinabuse.com/reports/{address}'.format(address=row['address']),
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

    last_mod = datetime.fromtimestamp(os.path.getmtime(config['RAW_FILE_NAME'])).isoformat()
    generator = TagPackGenerator(raw_data.read(), config['TITLE'], config['CREATOR'], config['DESCRIPTION'],
                                 last_mod, config['SOURCE'])
    generator.generate()
    generator.saveYaml(config['TAGPACK_FILE_NAME'])
