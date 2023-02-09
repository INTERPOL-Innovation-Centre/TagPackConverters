#!/usr/bin/env python3
"""
Convert BitcoinAbuse data to a TagPack.
"""
import os
import json
from datetime import datetime, date
from typing import List

import yaml
from selenium import webdriver
from selenium.common.exceptions import NoSuchElementException, TimeoutException, StaleElementReferenceException
from selenium.webdriver.common.by import By
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.remote.webelement import WebElement
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.wait import WebDriverWait


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
        wd.get(self.url)
        # Collect reports
        report_data = {}
        banned_urls = set()

        def yet_unknown_url(link: WebElement):
            try:
                return link.get_attribute('href') not in report_data and link.get_attribute('href') not in banned_urls
            except StaleElementReferenceException:
                return False

        report_xpath = '//a[contains(@href, "/reports/1") or contains(@href, "/reports/3")'\
                       ' or contains(@href, "/reports/bc1")]'
        while True:
            report_links = list(filter(yet_unknown_url, wd.find_elements(By.XPATH, report_xpath)))
            if len(report_links) > 0:
                report_link = report_links[0]
                report_url = report_link.get_attribute('href')
                report_link.click()
                for retry_index in range(20):
                    try:
                        # Wait for address to appear
                        WebDriverWait(wd, 60).until(
                            EC.presence_of_element_located((By.XPATH, '//th[text()="Address"]/following-sibling::td/i'))
                        )
                    except TimeoutException:
                        if 'chainabuse.com' not in wd.current_url:
                            print('Reload {url} (retry {index})'.format(url=report_url, index=retry_index))
                            wd.refresh()
                        else:
                            banned_urls.add(report_url)
                            wd.back()
                        continue
                    else:
                        break
                try:
                    address = wd.find_element(By.XPATH, '//th[text()="Address"]/following-sibling::td/i').text
                    count = int(wd.find_element(By.XPATH, '//th[text()="Report Count"]/following-sibling::td').text)
                    latest_report_date = wd.find_element(By.XPATH, '//th[text()="Latest Report"]/following-sibling::td')
                except NoSuchElementException:
                    wd.back()
                    continue
                latest_datetime = datetime.strptime(latest_report_date.text.split('\n')[0], '%a, %d %b %y %H:%M:%S %z')
                report_data[report_url] = {
                    'address': address,
                    'count': count,
                    'latest_date': latest_datetime.isoformat()
                }
                wd.back()
            else:
                try:
                    next_page_xpath = '//ul[@class="pagination"]/li[contains(@class, "active")]/following-sibling::li/a'
                    next_page_link = wd.find_element(By.XPATH, next_page_xpath)
                    next_page_link.click()
                except NoSuchElementException:
                    break
        # Write reports to raw data file
        with open(self.fn, 'w') as json_file:
            json.dump(report_data, json_file, indent=4)
        # Clean up
        wd.quit()
        os.remove('geckodriver.log')

    def read(self) -> List[dict]:
        with open(self.fn, 'r', encoding='utf-8') as json_file:
            return json.load(json_file).values()


class TagPackGenerator:
    """
    Generate a TagPack from BitcoinAbuse data.
    """

    def __init__(self, rows: List[dict], title: str, creator: str, description: str, lastmod: date, source: str):
        self.data = {
            'title': title,
            'creator': creator,
            'description': description,
            'source': source,
            'lastmod': lastmod,
            'currency': 'BTC',
            'category': 'user',  # like in the OFAC TagPack generator
            'confidence': 'web_crawl',
            'tags': []
        }
        self.rows = rows

    def generate(self):
        tags = []
        for row in self.rows:
            label = 'Abuse report' if row['count'] == 1 else 'Abuse reports'
            lastmod = datetime.fromisoformat(row['latest_date']).date()
            tag = {
                'address': row['address'],
                'label': label,
                'lastmod': lastmod,
                'source': 'https://www.bitcoinabuse.com/reports/{address}'.format(address=row['address'])
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
