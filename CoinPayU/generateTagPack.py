#!/usr/bin/env python3
"""
Convert CoinPayU data to a TagPack.
"""
import logging
import os
import re
import json
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, date, timezone
from queue import Queue
from time import sleep

import yaml
from selenium import webdriver
from selenium.common.exceptions import NoSuchElementException, TimeoutException, WebDriverException
from selenium.webdriver.common.by import By
from selenium.webdriver.support.select import Select
from selenium.webdriver.support.wait import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC


RE_DATE_BLOCKCHAIR = re.compile(r'date: (\d\d\d\d-\d\d-\d\d)')
RE_DATE_ETHERSCAN = re.compile(r'\(([^)]+)\)')


def collect_links(start_url: str, option_text: str, out_queue: Queue):
    wd = webdriver.Firefox()
    wd.get(start_url)

    select = Select(WebDriverWait(wd, 15).until(EC.element_to_be_clickable((By.XPATH, '//select'))))
    WebDriverWait(wd, 15).until(EC.element_to_be_clickable((By.XPATH, '//select/option')))
    select.select_by_visible_text(option_text)

    collected = set()
    while True:
        try:
            WebDriverWait(wd, 60).until(EC.presence_of_all_elements_located((By.XPATH, '//tbody/tr')))
        except TimeoutException:
            logging.warning('Browser hangs, going one page back')
            wd.find_element(By.XPATH, '//span[text()="«"]').click()  # If browser hangs, try to go to the previous page
            continue
        for link in wd.find_elements(By.XPATH, '//a[@title="check"]'):
            url = link.get_attribute('href')
            if url not in collected:
                out_queue.put(url)
                collected.add(url)
                logging.info(url)
        try:
            next_page = wd.find_element(By.XPATH, '//span[text()="»"]')
            next_page.location_once_scrolled_into_view  # Workaround from https://stackoverflow.com/a/56085622
            next_page.click()
        except NoSuchElementException:
            out_queue.put(None)
            break
    wd.quit()


def get_blockchair_data(driver: webdriver.Remote) -> dict:
    for _ in range(5):
        try:
            WebDriverWait(driver, 60).until(EC.presence_of_element_located((By.XPATH, '//span[text()="Transaction status"]')))
        except TimeoutException:
            logging.warning('Timeout. Retrying...')
            driver.refresh()
            continue
        else:
            break

    tx_description = driver.find_element(By.XPATH, '//meta[@name="description"]').get_attribute('content')
    tx_date = datetime.strptime(RE_DATE_BLOCKCHAIR.search(tx_description).group(1), '%Y-%m-%d')
    tx_addresses_xpath = '//*[starts-with(@id, "io-inputs")]//a[contains(@href, "address")]'
    tx_addresses = [element.text for element in driver.find_elements(By.XPATH, tx_addresses_xpath)]
    return {'date': tx_date, 'addresses': tx_addresses}


def get_btc_com_data(driver: webdriver.Remote) -> dict:
    # Blockchair data is preferred, as the time stamps are in UTC, whereas btc.com explorer converts them
    # to local time zone and stores the original timestamp in the tooltip over the date string only
    for _ in range(5):
        try:
            link = WebDriverWait(driver, 60).until(EC.element_to_be_clickable((By.XPATH, '//a[text()="BLOCKCHAIR"]')))
            driver.get(link.get_attribute('href'))
        except (TimeoutException, WebDriverException):
            logging.warning('Timeout. Retrying...')
            driver.refresh()
            continue
        else:
            break
    return get_blockchair_data(driver)


def get_btc_com_data_unused(driver: webdriver.Remote) -> dict:
    tx_date_xpath = '//span[text()="Timestamp"]/parent::div/following-sibling::div/span/div'
    tx_date = datetime.strptime(driver.find_element(By.XPATH, tx_date_xpath).text, '%Y-%m-%d %H:%M:%S')
    tx_addresses_xpath = '//span[contains(@class, "Card_title") and text()="Transaction"]/parent::div'\
                         '/following-sibling::div/div/div/div/section[1]/ul/li/div/div/a'
    tx_addresses = [
        element.get_attribute('href').split('/')[-1] for element in driver.find_elements(By.XPATH, tx_addresses_xpath)
    ]
    return {'date': tx_date, 'addresses': tx_addresses}


def get_etherscan_data(driver: webdriver.Remote) -> dict:
    tx_date_xpath = '//div[@id="ContentPlaceHolder1_divTimeStamp"]/div[contains(@class, "row")]/div[2]'
    tx_date_text = driver.find_element(By.XPATH, tx_date_xpath).text
    tx_date = datetime.strptime(RE_DATE_ETHERSCAN.search(tx_date_text).group(1), '%b-%d-%Y %I:%M:%S %p +%Z')
    tx_address = driver.find_element(By.XPATH, '//i[@data-bs-content="The sending party of the transaction."]/parent::div/following-sibling::div/div/a[contains(@href, "/address/")]').text
    return {'date': tx_date, 'addresses': [tx_address]}


def get_tronscan_data(driver: webdriver.Remote) -> dict:
    tx_address_xpath = '//section[@id="n_owner_address"]/section/span/div/div/span/div/a/div'
    tx_address = WebDriverWait(driver, 20).until(EC.presence_of_element_located((By.XPATH, tx_address_xpath))).text
    tx_date_text_xpath = '//th[span[text()="Time"]]/following-sibling::td/div/div/span/span'
    tx_date_text = driver.find_element(By.XPATH, tx_date_text_xpath).text
    tx_date = datetime.strptime(tx_date_text, '%Y-%m-%d %H:%M:%S (Local)').astimezone(timezone.utc)
    return {'date': tx_date, 'addresses': [tx_address]}


class DatetimeEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, datetime):
            return obj.isoformat()
        return json.JSONEncoder.default(self, obj)


def save_source_addresses(options: list, in_queue: Queue, fn: str):
    """
    Collect addresses from cryptocurrency explorers
    """
    wd = webdriver.Firefox()
    end_counter = 0
    data = {}
    while True:
        link = in_queue.get()
        if link is None:
            end_counter += 1
            if end_counter == len(options):
                break
        else:
            for _ in range(5):
                try:
                    wd.get(link)
                    logging.info('{link} ({count})'.format(link=link, count=in_queue.qsize()))
                except TimeoutException:
                    logging.warning('Timeout. Retrying...')
                    continue
                except WebDriverException:
                    logging.warning('Driver error. Retrying...')
                    continue
                else:
                    break
            if link.startswith('https://blockchair.com/bitcoin/transaction/'):
                currency = 'BTC'
                try:
                    tx_data = get_blockchair_data(wd)
                except NoSuchElementException as e:
                    try:
                        error_element = wd.find_element(By.XPATH, '//div[@class="h3"]')
                        if error_element.text == ' Not Found ':
                            logging.warning('Blockchair.com has no information about {tx}'.format(tx=link.split('/')[-1]))
                            continue
                    except NoSuchElementException:
                        raise e
            elif link.startswith('https://bch.btc.com/'):
                currency = 'BCH'
                tx_data = get_btc_com_data(wd)
            elif link.startswith('https://blockchair.com/litecoin/transaction/'):
                currency = 'LTC'
                tx_data = get_blockchair_data(wd)
            elif link.startswith('https://etherscan.io/tx/'):
                currency = 'ETH'
                try:
                    tx_data = get_etherscan_data(wd)
                    sleep(1.0)
                except NoSuchElementException as e:
                    try:
                        error_element_xpath = '//h2[@class="h5" and text()="Sorry, We are unable to locate this TxnHash"]'
                        error_element = wd.find_element(By.XPATH, error_element_xpath)
                        logging.warning('Etherscan.io has no information about {tx}'.format(tx=link.split('/')[-1]))
                        continue
                    except NoSuchElementException:
                        raise e
            elif link.startswith('https://tronscan.org/#/transaction/'):
                currency = 'USDT'
                try:
                    tx_data = get_tronscan_data(wd)
                except TimeoutException as e:
                    try:
                        error_element_xpath = '//span[text()="Sorry, the transaction could not be found."]'
                        error_element = wd.find_element(By.XPATH, error_element_xpath)
                        logging.warning('Tronscan.io has no information about {tx}'.format(tx=link.split('/')[-1]))
                        continue
                    except NoSuchElementException:
                        raise e
            else:
                raise ValueError('Link {link} does not have data processor'.format(link=link))
            for address in tx_data['addresses']:
                if address not in data:
                    data[address] = {'date': tx_data['date'], 'currency': currency}
                elif data[address]['currency'] == currency and data[address]['date'] < tx_data['date']:
                    data[address]['date'] = tx_data['date']
    wd.quit()
    with open(fn, 'w', encoding='utf-8') as json_file:
        json.dump(data, json_file, cls=DatetimeEncoder, indent=4)


class RawData:
    """
    Download and read data provided by the source.
    """
    def __init__(self, fn: str, url: str):
        self.fn = fn
        self.url = url

    def download(self):
        links_queue = Queue()
        options_texts = ['Bitcoin (BTC)', 'Bitcoin Cash (BCH)', 'Litecoin (LTC)', 'Ethereum (ETH)', 'Tether TRC20 (USDT)']
        with ThreadPoolExecutor(max_workers=4) as executor:
            executor.submit(save_source_addresses, options_texts, links_queue, self.fn)
            for text in options_texts:
                executor.submit(collect_links, self.url, text, links_queue)

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
            'label': 'CoinPayU',
            'description': description,
            'source': source,
            'category': 'faucet',
            'confidence': 'web_crawl',
            'lastmod': lastmod,
            'tags': []
        }
        self.source = source

    def generate(self):
        tags = []
        for row in self.rows:
            tag = {
                'address': row['address'],
                'currency': row['currency'],
                'lastmod': datetime.fromisoformat(row['date']).date()
            }
            tags.append(tag)
        self.data['tags'] = tags

    def saveYaml(self, fn: str):
        with open(fn, 'w', encoding='utf-8') as f:
            f.write(yaml.dump(self.data, sort_keys=False, allow_unicode=True))


if __name__ == '__main__':
    with open('config.yaml', 'r') as config_file:
        config = yaml.safe_load(config_file)

    logging.basicConfig(format='%(asctime)s - %(threadName)s - %(levelname)s - %(message)s', level=logging.INFO)
    raw_data = RawData(config['RAW_FILE_NAME'], config['SOURCE'])
    if not os.path.exists(config['RAW_FILE_NAME']):
        raw_data.download()

    last_mod = datetime.fromtimestamp(os.path.getmtime(config['RAW_FILE_NAME'])).date()
    generator = TagPackGenerator(raw_data.read(), config['TITLE'], config['CREATOR'], config['DESCRIPTION'],
                                 last_mod, config['SOURCE'])
    generator.generate()
    generator.saveYaml(config['TAGPACK_FILE_NAME'])
