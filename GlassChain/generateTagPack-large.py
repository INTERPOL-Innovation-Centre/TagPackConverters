#!/usr/bin/env python3
"""
Convert GlassChain data to a TagPack.
"""
import os
import re
import json
import logging
from datetime import datetime
from urllib.parse import urljoin

import yaml
from bs4 import BeautifulSoup
from requests import Session

BTC_REGEX = re.compile(r'\b((bc(0([ac-hj-np-z02-9]{39}|[ac-hj-np-z02-9]{59})|1[ac-hj-np-z02-9]{8,87}))|[13][a-km-zA-HJ-NP-Z1-9]{25,34})\b')


class LiveServerSession(Session):  # From https://stackoverflow.com/a/51026159
    def __init__(self, base_url=None):
        super().__init__()
        self.base_url = base_url

    def request(self, method, url, *args, **kwargs):
        joined_url = urljoin(self.base_url, url)
        return super().request(method, joined_url, *args, **kwargs)


def get_data(s: Session, url: str):
    for retry in range(20):
        try:
            return s.get(url, timeout=60.0)
        except:
            logging.debug('Retry {retry}'.format(retry=retry+1))
            continue
    else:
        raise SystemExit('Too many retries')


class RawData:
    """
    Download and read data provided by the source.
    """
    def __init__(self, fn: str, url: str):
        self.fn = fn
        self.url = url
        self.data = {}

    @staticmethod
    def download_wallet(s: Session, link: str, addresses: list):
        wallet_id = link.split('/')[-1]
        # Get count of addresses
        wallet_data_url = 'https://api.glasschain.io/taffy/api/index.cfm?endpoint=/wallet/getWalletKPI&walletid={wallet_id}'.format(wallet_id=wallet_id)
        response = get_data(s, wallet_data_url)
        addresses_count = json.loads(response.text)['data'][0]['DSP_INT_WALLET_ADDRESSES']
        # Get addresses from paginated table
        page_index = 0
        while len(addresses) < addresses_count:
            logging.debug('Fetch page {index} having {count} addresses of {max}'.format(index=page_index, count=len(addresses), max=addresses_count))
            addr_url = 'https://glasschain.org/views/wallet/Addresses.cfm?ref={wallet_id}&page={index}&paging=100000'.format(wallet_id=wallet_id, index=page_index)
            response = get_data(s, addr_url)
            for address_link in BeautifulSoup(response.text, 'html.parser').find_all('a'):
                address = address_link.text
                if not BTC_REGEX.match(address):
                    logging.warning('Address {address} has wrong format')
                    continue
                addresses.append(address)
            page_index += 1

    def download_provider(self, s: Session, link: str, wallets: list):
        response = get_data(s, link)
        if response.url == 'https://glasschain.org/404':
            logging.warning('Provider not found!')
            return
        page = BeautifulSoup(response.text, features='html.parser')
        table = page.select_one('main table')
        for row in table.find_all('tr'):
            cells = row.find_all('td')
            if len(cells) == 0:  # Header row
                continue
            if len(cells) == 1 and cells[0].text == 'No Wallets identified yet':  # Empty row
                continue
            wallet_link = cells[0].find('a').get('href')
            wallet_label = cells[1].find('b').text
            wallet_lastmod, wallet_creator = tuple(cells[1].find('label').text.split(' by '))
            wallet = {
                'source': wallet_link,
                'label': wallet_label,
                'lastmod': wallet_lastmod,
                'creator': wallet_creator,
                'addresses': []
            }
            wallets.append(wallet)
            logging.info('Downloading wallet {label}'.format(label=wallet_label))
            self.download_wallet(s, wallet_link, wallet['addresses'])

    def download_providers(self, s: Session, data: dict):
        response = get_data(s, self.url)
        page = BeautifulSoup(response.text, features='html.parser')
        table = page.select_one('main table')
        for row in table.find_all('tr'):
            cells = row.find_all('td')
            wallet_count = int(cells[2].find('span').text)
            link_element = cells[0].find('a')
            provider_name = link_element.text
            if wallet_count == 0:
                logging.debug('Skipping provider {name}'.format(name=provider_name))
                continue
            provider_link = link_element.get('href')
            provider_category = cells[1].text
            # Create provider entry and fill it with content
            provider = {
                'category': provider_category,
                'wallets': []
            }
            logging.info('Downloading provider {name}'.format(name=provider_name))
            self.download_provider(s, provider_link, provider['wallets'])
            data[provider_name] = provider

    def download(self):
        with LiveServerSession(self.url) as session:
            session.headers.update({
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:108.0) Gecko/20100101 Firefox/108.0'
            })
            self.download_providers(session, self.data)

        with open(self.fn, 'w', encoding='utf-8') as json_file:
            json.dump(self.data, json_file, ensure_ascii=False, indent=4)

    def read(self) -> dict:
        with open(self.fn, 'r', encoding='utf-8') as json_file:
            return json.load(json_file)


class TagPackGenerator:
    """
    Generate a TagPack from BitcoinTalk users data.
    """

    def __init__(self, raw_data_: dict, title: str, creator: str, description: str, lastmod: str, source: str):
        self.raw_data = raw_data_
        self.data = {
            'title': title,
            'creator': creator,
            'description': description
        }
        self.source = source

    def generate(self):

        def get_category_from_provider(p: dict) -> str:
            category_map = {
                'Advertising Networks': 'organization',
                'CoinJoin Providers': 'coinjoin',
                'Criminal Entities': 'perpetrator',
                'Cryptocurrency Mixers': 'mixing_service',
                'Crypto Exchanges': 'exchange',
                'Darknet Markets': 'market',
                'Media Platforms': 'organization',
                'Miner': 'miner',
                'Mining Pools': 'miner',
                'P2P Crypto Exchanges': 'exchange',
                'Payment Providers': 'payment_processor',
                'Telegram Trading Chat': 'exchange',
                'Wallet Providers': 'wallet_service'
            }
            return category_map[p['category']]

        def get_label_from_wallet(w: dict) -> str:
            wallet_label_fix = {
                'WSM Hot Wallet': 'Wall Street Market Hot Wallet',
                'Garantex Deposit': 'Garantex Deposit Wallet',
                'Nucleus Wallet': 'Nucleus Market Wallet'
            }
            w_label = w['label']
            if w_label in wallet_label_fix:
                w_label = wallet_label_fix[w_label]
            return w_label

        def get_currency_from_wallet(w: dict) -> str:
            if '/btc/' in w['source']:
                return 'BTC'
            raise ValueError('Unknown currency for source {source}'.format(source=w['source']))

        def get_creator_from_wallet(w: dict, l: str) -> str:
            if w['creator'] == 'Glasschain':
                return 'Glasschain'
            raise ValueError('Creator of wallet {label} is not Glasschain, but {creator}'.format(label=l,
                                                                                                 creator=w['creator']))

        providers_sorted_by_size = sorted(self.raw_data.keys(),
                                          key=lambda name: sum(map(lambda wallet: len(wallet['addresses']),
                                                                   self.raw_data[name]['wallets'])))
        for provider_name in providers_sorted_by_size:
            # Get provider
            logging.info('Process provider {name}'.format(name=provider_name))
            provider = self.raw_data[provider_name]
            category = get_category_from_provider(provider)
            # Process wallets
            for wallet_index, wallet in enumerate(provider['wallets'], 1):
                label = get_label_from_wallet(wallet)
                logging.debug('Processing wallet {label}'.format(label=label))
                get_creator_from_wallet(wallet, label)  # The call is needed to verify that creator is Glasschain only
                get_currency_from_wallet(wallet)  # The call is needed to verify that currency is BTC only
                self.data['currency'] = 'BTC'
                self.data['label'] = label
                self.data['lastmod'] = datetime.fromisoformat(wallet['lastmod']).date()
                self.data['source'] = urljoin('https://glasschain.org/', wallet['source'])
                self.data['category'] = category
                self.data['tags'] = [{'address': address} for address in wallet['addresses']]
                fn = 'glasschain_{name}_wallet_{index}_tagpack.yaml'.format(name=provider_name, index=wallet_index)
                self.saveYaml(fn)
           # Delete provider
            del self.raw_data[provider_name]

    def saveYaml(self, fn: str):
        with open(fn, 'w', encoding='utf-8') as f:
            f.write(yaml.dump(self.data, sort_keys=False))

    def generateAndSave(self):
        self.generate()


if __name__ == '__main__':
    logging.basicConfig(format='%(asctime)s - %(levelname)s - %(message)s', level=logging.INFO)

    with open('config.yaml', 'r') as config_file:
        config = yaml.safe_load(config_file)

    raw_data = RawData(config['RAW_FILE_NAME'], config['URL'])
    if not os.path.exists(config['RAW_FILE_NAME']):
        raw_data.download()

    last_mod = datetime.fromtimestamp(os.path.getmtime(config['RAW_FILE_NAME'])).isoformat()
    generator = TagPackGenerator(raw_data.read(), config['TITLE'], config['CREATOR'], config['DESCRIPTION'],
                                 last_mod, config['SOURCE'])
    generator.generateAndSave()
