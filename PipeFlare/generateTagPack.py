#!/usr/bin/env python3
"""
Convert PipeFlare data to a TagPack.
"""
import os
import re
import json
from datetime import datetime

import yaml
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.support.wait import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

ZEC_REGEX = re.compile(r'\b([tz][13][a-km-zA-HJ-NP-Z1-9]{33})\b')
ZEC_EXPLORER_URL = 'https://explorer.zcha.in/transactions/'
GAME_LEADERBOARD_URL = 'https://pipeflare.io/game/leaderboard'
REFERRAL_LEADERBOARD_URL = 'https://pipeflare.io/referral/leaderboard'
LEADERBOARD_INTERVAL = 40


class DatetimeEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, datetime):
            return obj.isoformat()
        return json.JSONEncoder.default(self, obj)


class RawData:
    """
    Download and read data provided by the source.
    """
    def __init__(self, fn: str, url: str):
        self.fn = fn
        self.url = url
        self.explorer_tx_links = {}
        self.addresses = {}

    def add_tx_links(self, wd: webdriver.Remote) -> bool:
        print('Processing {url}'.format(url=wd.current_url))
        zec_explorer_link_xpath = '//a[starts-with(@href, "{url}")]'.format(url=ZEC_EXPLORER_URL)
        new_tx_links = [link.get_attribute('href') for link in wd.find_elements(By.XPATH, zec_explorer_link_xpath)]
        new_tx_links_found = not set(new_tx_links).issubset(set(self.explorer_tx_links.keys()))
        # Overwrite existing source URL with the earlier transaction
        self.explorer_tx_links.update(dict.fromkeys(new_tx_links, wd.current_url))
        return new_tx_links_found

    def download_transactions(self, wd: webdriver.Remote):
        wd.get(self.url)
        self.add_tx_links(wd)

    def download_leaderboard(self, wd: webdriver.Remote, start_url: str, next_page_link_xpath: str):
        wd.get(start_url)
        self.add_tx_links(wd)
        page_index = last_page_with_new_zec_index = 1
        while True:
            next_page_link = wd.find_element(By.XPATH, next_page_link_xpath)
            if next_page_link:
                next_page_link.click()
                page_index += 1
            else:
                break
            added = self.add_tx_links(wd)
            if added:
                last_page_with_new_zec_index += 1
            if page_index - last_page_with_new_zec_index > LEADERBOARD_INTERVAL:
                break

    def download_game_leaderboard(self, wd: webdriver.Remote):
        self.download_leaderboard(wd, GAME_LEADERBOARD_URL, '//i[contains(@class, "fa-angle-left")]/parent::a')

    def download_referral_leaderboard(self, wd: webdriver.Remote):
        self.download_leaderboard(wd, REFERRAL_LEADERBOARD_URL,
                                  '//*[@id="wrap-leader-board"]/div/a[contains(@class, "btn-primary")][last()]')

    def get_addresses_from_tx_links(self, wd: webdriver.Remote):
        for link, source in self.explorer_tx_links.items():
            wd.get(link)
            tx_date_xpath = '//div[text()="Received Time"]/following-sibling::div'
            tx_date_text = WebDriverWait(wd, 10).until(EC.visibility_of_element_located((By.XPATH, tx_date_xpath))).text
            if '(' in tx_date_text:
                tx_date_text = tx_date_text.split('(')[0].strip()
            tx_date = datetime.strptime(tx_date_text, '%a %d %b %Y %H:%M:%S')
            tx_addr_xpath = '//div[contains(text(), "Inputs (")]/parent::div/div/span/span/span/a'
            for tx_addr_element in wd.find_elements(By.XPATH, tx_addr_xpath):
                tx_addr = tx_addr_element.text.strip()
                if not ZEC_REGEX.match(tx_addr):
                    raise ValueError('String {s} is not a ZEC address')
                # Add earliest source
                if tx_addr not in self.addresses or tx_date < self.addresses[tx_addr]['date']:
                    self.addresses[tx_addr] = {'date': tx_date, 'source': source}

    def download(self):
        options = Options()
        options.set_preference('javascript.enabled', False)
        options.set_preference('permissions.default.image', 2)
        wd = webdriver.Firefox(options=options)
        self.download_transactions(wd)
        self.download_game_leaderboard(wd)
        self.download_referral_leaderboard(wd)
        if ZEC_EXPLORER_URL in self.explorer_tx_links:
            del self.explorer_tx_links[ZEC_EXPLORER_URL]  # Drop link(s) to the ZEC explorer itself
        wd.quit()
        wd = webdriver.Firefox()
        self.get_addresses_from_tx_links(wd)
        wd.quit()
        with open(self.fn, 'w', encoding='utf-8') as json_file:
            json.dump(self.addresses, json_file, cls=DatetimeEncoder, indent=4)

    def read(self) -> dict:
        with open(self.fn, 'r', encoding='utf-8') as json_file:
            return json.load(json_file)


class TagPackGenerator:
    """
    Generate a TagPack from PipeFlare data.
    """

    def __init__(self, rows: dict, title: str, creator: str, description: str, lastmod: str, source: str):
        self.rows = [{'address': address, **data} for address, data in rows.items()]
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
            tag = {
                'address': row['address'],
                'currency': 'ZEC',
                'label': 'PipeFlare',
                'lastmod': row['date'],
                'source': row['source'],
                'category': 'faucet',
                'confidence': 'web_crawl'
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

    last_mod = datetime.fromtimestamp(os.path.getmtime(config['RAW_FILE_NAME'])).isoformat()
    generator = TagPackGenerator(raw_data.read(), config['TITLE'], config['CREATOR'], config['DESCRIPTION'],
                                 last_mod, config['SOURCE'])
    generator.generate()
    generator.saveYaml(config['TAGPACK_FILE_NAME'])
