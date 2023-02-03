#!/usr/bin/env python3
"""
Convert PipeFlare data to a TagPack.
"""
import os
import re
import json
import logging
from datetime import datetime, date
from queue import Queue
from threading import Thread
from typing import Set

import yaml
from selenium import webdriver
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.common.by import By
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.support.wait import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

ZEC_REGEX = re.compile(r'\b([tz][13][a-km-zA-HJ-NP-Z1-9]{33})\b')
ZEC_EXPLORER_URL = 'https://explorer.zcha.in/transactions/'
LEADERBOARD_INTERVAL = 40


def get_tx_links(driver: webdriver.Remote) -> Set[str]:
    logging.info('Processing {url}'.format(url=driver.current_url))
    zec_explorer_link_xpath = '//a[starts-with(@href, "{url}")]'.format(url=ZEC_EXPLORER_URL)
    return set([link.get_attribute('href') for link in driver.find_elements(By.XPATH, zec_explorer_link_xpath)])


def collect_links(start_url: str, out_queue: Queue, next_page_link_xpath=None, link_text_changes=False):
    options = Options()
    options.set_preference('javascript.enabled', False)
    options.set_preference('permissions.default.image', 2)
    wd = webdriver.Firefox(options=options)

    wd.get(start_url)
    for link in get_tx_links(wd):
        out_queue.put((link, wd.current_url))

    if next_page_link_xpath is None:  # Processing ends here for the TX log
        out_queue.put(None)
        wd.quit()
        return

    # Process leaderboards page-by-page
    tx_links = set()
    page_index = last_page_with_new_zec_index = 1
    retries = 0
    while True:
        if retries > 20:  # Prevent never-ending loops when PipeFlare.io is unresponsive and CloudFlare gives time-outs
            break
        try:
            next_page_link = WebDriverWait(wd, 60).until(
                EC.visibility_of_element_located((By.XPATH, next_page_link_xpath))
            )
        except TimeoutException:
            logging.info('Refreshing page...')
            wd.refresh()
            retries += 1
            continue
        else:
            retries = 0
        if next_page_link:
            if link_text_changes:
                next_page_link_text = next_page_link.text
                next_page_link.click()
                WebDriverWait(wd, 300).until_not(
                    EC.text_to_be_present_in_element((By.XPATH, next_page_link_xpath), next_page_link_text)
                )
            else:
                next_page_link.click()
            page_index += 1
        else:
            break
        new_tx_links = get_tx_links(wd)
        if new_tx_links:
            last_page_with_new_zec_index = page_index
        new_tx_links -= tx_links
        for link in new_tx_links:
            out_queue.put((link, wd.current_url))
        tx_links.update(new_tx_links)
        if page_index - last_page_with_new_zec_index > LEADERBOARD_INTERVAL:
            break

    out_queue.put(None)
    wd.quit()


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
        self.addresses = {}

    def download(self):
        links_queue = Queue()

        collector_threads = [
            # Strictly speaking, transaction log is an ever-changing source and hence unreliable
            Thread(target=collect_links, args=(self.url[0], links_queue), name='Transactions'),
            Thread(target=collect_links,
                   args=(self.url[1], links_queue, '//i[contains(@class, "fa-angle-left")]/parent::a'),
                   name='Game Leaderboard'),
            Thread(target=collect_links,
                   args=(self.url[2], links_queue,
                         '//*[@id="wrap-leader-board"]/div/a[contains(@class, "btn-primary")][last()]', True),
                   name='Referral Leaderboard')
        ]
        for thread in collector_threads:
            thread.start()

        # Collect TX links and get source addresses
        wd = webdriver.Firefox()
        urls_finished = 0
        processed_tx_links = {}
        while True:
            collected = links_queue.get()
            if collected is None:
                urls_finished += 1
                if urls_finished == len(collector_threads):
                    break
                continue
            tx_link, tx_source = collected
            if tx_link == ZEC_EXPLORER_URL:
                continue
            if tx_link in processed_tx_links and 'transactions' not in processed_tx_links[tx_link]:
                continue  # Prefer leaderboards to transactions log
            # Process TX link
            logging.info('Processing TX link {url}'.format(url=tx_link))
            wd.get(tx_link)
            try:
                tx_date_xpath = '//div[text()="Received Time"]/following-sibling::div'
                tx_date_text = WebDriverWait(wd, 10).until(
                    EC.visibility_of_element_located((By.XPATH, tx_date_xpath))
                ).text
            except TimeoutException as error:
                if wd.find_element(By.XPATH, '//span[starts-with(text(), "Transaction has not yet been mined: ")]'):
                    logging.warning('TX with link {url} has yet not been mined'.format(url=tx_link))
                    continue
                else:
                    raise error
            if '(' in tx_date_text:
                tx_date_text = tx_date_text.split('(')[0].strip()
            tx_date = datetime.strptime(tx_date_text, '%a %d %b %Y %H:%M:%S')
            tx_addr_xpath = '//div[contains(text(), "Inputs (")]/parent::div/div/span/span/span/a'
            for tx_addr_element in wd.find_elements(By.XPATH, tx_addr_xpath):
                tx_addr = tx_addr_element.text.strip()
                if not ZEC_REGEX.match(tx_addr):
                    raise ValueError('String {s} is not a ZEC address')
                # Add latest source
                if tx_addr not in self.addresses or tx_date > self.addresses[tx_addr]['date'] or \
                        'transactions' in self.addresses[tx_addr]['source']:  # Prefer leaderboards to transactions log
                    self.addresses[tx_addr] = {'date': tx_date, 'source': tx_source}
            processed_tx_links[tx_link] = tx_source
        wd.quit()

        for thread in collector_threads:
            thread.join()

        with open(self.fn, 'w', encoding='utf-8') as json_file:
            json.dump(self.addresses, json_file, cls=DatetimeEncoder, indent=4)

    def read(self) -> dict:
        with open(self.fn, 'r', encoding='utf-8') as json_file:
            return json.load(json_file)


class TagPackGenerator:
    """
    Generate a TagPack from PipeFlare data.
    """

    def __init__(self, rows: dict, title: str, creator: str, description: str, lastmod: date, source: str):
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

    logging.basicConfig(format='%(asctime)s - %(threadName)s - %(levelname)s - %(message)s', level=logging.WARNING)
    raw_data = RawData(config['RAW_FILE_NAME'], config['URL'])
    if not os.path.exists(config['RAW_FILE_NAME']):
        raw_data.download()

    last_mod = datetime.fromtimestamp(os.path.getmtime(config['RAW_FILE_NAME'])).date()
    generator = TagPackGenerator(raw_data.read(), config['TITLE'], config['CREATOR'], config['DESCRIPTION'],
                                 last_mod, config['SOURCE'])
    generator.generate()
    generator.saveYaml(config['TAGPACK_FILE_NAME'])
