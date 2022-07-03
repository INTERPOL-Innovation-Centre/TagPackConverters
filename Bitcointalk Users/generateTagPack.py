#!/usr/bin/env python3
"""
Convert BitcoinTalk users data to a TagPack.
"""
import os
import re
import sys
import json
import time
from datetime import datetime
from typing import List, Union, TextIO

import yaml
from selenium import webdriver
from selenium.common.exceptions import NoSuchElementException, TimeoutException
from selenium.webdriver.common.by import By
from selenium.webdriver.firefox.options import Options

# Taken from Sanctioned NBCTF generator and modified
REGEX = [
    ('BTC', re.compile(r'\b((bc(0([ac-hj-np-z02-9]{39}|[ac-hj-np-z02-9]{59})|1[ac-hj-np-z02-9]{8,87}))|[13][a-km-zA-HJ-NP-Z1-9]{25,34})\b')),
    ('BCH', re.compile(r'\b(((?:bitcoincash|bchtest):)?([13][0-9a-zA-Z]{33}))|\b(((?:bitcoincash|bchtest):)?(qp)?[0-9a-zA-Z]{40})\b')),
    ('LTC', re.compile(r'\b([LM3][a-km-zA-HJ-NP-Z1-9]{25,33})\b')),
    ('ZEC', re.compile(r'\b([tz][13][a-km-zA-HJ-NP-Z1-9]{33})\b')),
    ('ETH', re.compile(r'\b((0x)?[0-9a-fA-F]{40})\b'))
]

BITCOINTALK_PROFILE_URL = 'https://bitcointalk.org/index.php?action=profile;u={user_id}'

class RawData:
    """
    Download and read data provided by the source.
    """
    def __init__(self, fn: str, url: str):
        self.fn = fn
        self.url = url

    @staticmethod
    def download_profile(wd: webdriver.Remote, user_id: int) -> Union[dict, None]:
        url = BITCOINTALK_PROFILE_URL.format(user_id=user_id)
        for _ in range(5):
            try:
                wd.get(url)
            except TimeoutException:
                print('Retrying URL {url} (retry {retry})'.format(url=url, retry=_+1), file=sys.stderr)
                continue
            else:
                break
        # If no profile found, exit here
        if wd.title == 'An Error Has Occurred!':
            return None
        # So we got a user profile, which we put into a dictionary
        data = {'user_id': user_id}
        for entry in wd.find_elements(By.XPATH, '//table/tbody/tr/td/table/tbody/tr[2]/td[1]/table/tbody/tr'):
            try:
                key = entry.find_element(By.XPATH, 'td[1]/b').text
            except NoSuchElementException:
                continue  # No key, hence no information here
            try:
                value = entry.find_element(By.XPATH, 'td[2]').text
            except NoSuchElementException:
                continue  # No value, hence no information here
            # Normalise key and value
            key = key.strip().lower().replace(':', '').replace(' ', '_')
            value = value.strip()
            # Skip entry with either empty key or empty value
            if not key or not value:
                continue
            # E-mail address is always hidden, hence we skip it
            if key == 'email':
                continue
            # Age may be hidden; if so, we skip the entry too
            if key == 'age' and value == 'N/A':
                continue
            # Convert values in certain entries to integers
            if key in ('posts', 'activity', 'merit', 'age'):
                value = int(value)
            # Add entry to the profile data
            data[key] = value
        # Also scrape signature
        try:
            signature = wd.find_element(By.XPATH, '//div[@class="signature"]').text
        except NoSuchElementException:
            pass
        else:
            if signature:
                data['signature'] = signature
        # ... and avatar URL
        try:
            avatar_url = wd.find_element(By.XPATH, '//img[@class="avatar"]').get_attribute('src')
        except NoSuchElementException:
            pass
        else:
            if avatar_url:
                data['avatar_url'] = avatar_url
        #  ... and avatar text
        try:
            avatar_text = ' '.join([el.text for el in wd.find_elements(By.XPATH, '//img[@class="avatar"]/..')]).strip()
        except NoSuchElementException:
            pass
        else:
            if avatar_text:
                data['avatar_text'] = avatar_text
        #print(data)
        return data

    def download_profiles(self, out_file: TextIO, wd: webdriver.Remote, starting_user_id: int):
        user_id = last_valid_user_id = starting_user_id
        while True:
            # Exit if we could not fetch too many profiles
            if user_id - last_valid_user_id >= 1000:
                break
            # Fetch profile and, if valid, save it
            profile = self.download_profile(wd, user_id)
            if profile is not None:
                last_valid_user_id = user_id
                print(json.dumps(profile, ensure_ascii=False), file=out_file)
            # We pause for 1 second to confirm to the rules of the forum
            time.sleep(1)
            user_id += 1

    @staticmethod
    def get_max_user_id(file: TextIO) -> int:
        user_id = 0
        for line in file:
            profile = json.loads(line)
            user_id = max(profile['user_id'], user_id)
        return user_id

    @staticmethod
    def get_missing_user_ids(file: TextIO, max_id: int) -> List[int]:
        user_ids = set()
        for line in file:
            profile = json.loads(line)
            user_ids.add(profile['user_id'])
        return [user_id for user_id in range(1, max_id + 1) if user_id not in user_ids]

    def download_missing_profiles(self, out_file: TextIO, wd: webdriver.Remote, missing_ids: List[int]):
        for user_id in missing_ids:
            profile = self.download_profile(wd, user_id)
            if profile is not None:
                print(json.dumps(profile, ensure_ascii=False), file=out_file)
            time.sleep(1)

    def download(self, update=False):
        # Create Firefox webdriver, do not load Javascript and image files
        options = Options()
        options.set_preference('javascript.enabled', False)
        options.set_preference('permissions.default.image', 2)
        wd = webdriver.Firefox(options=options)
        # Scrape user profiles
        if update:
            # Calculate next user id
            with open(self.fn, 'r', encoding='utf-8') as jsonlines_file:
                next_user_id = self.get_max_user_id(jsonlines_file) + 1
            print('Starting with user ID {next_user_id}'.format(next_user_id=next_user_id))
            # Proceed with next user id
            with open(self.fn, 'a', encoding='utf-8') as jsonlines_file:
                self.download_profiles(jsonlines_file, wd, next_user_id)
        else:
            with open(self.fn, 'w', encoding='utf-8') as jsonlines_file:
                self.download_profiles(jsonlines_file, wd, 1)
        # Calculate missing user ids and try to download them again. This should add missing profiles.
        with open(self.fn, 'r', encoding='utf-8') as jsonlines_file:
            max_user_id = self.get_max_user_id(jsonlines_file)
        with open(self.fn, 'r', encoding='utf-8') as jsonlines_file:
            missing_user_ids = self.get_missing_user_ids(jsonlines_file, max_user_id)
        print('Found {len} missing user IDs; trying to re-fetch them...'.format(len=len(missing_user_ids)))
        with open(self.fn, 'a', encoding='utf-8') as jsonlines_file:
            self.download_missing_profiles(jsonlines_file, wd, missing_user_ids)
        # Clean up
        wd.quit()
        os.remove('geckodriver.log')

    def read(self) -> List[dict]:
        with open(self.fn, 'r', encoding='utf-8') as jsonlines_file:
            return [json.loads(line) for line in jsonlines_file]


class TagPackGenerator:
    """
    Generate a TagPack from BitcoinTalk users data.
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
            user_addresses = {}
            for key, value in row.items():
                if type(value) != str:
                    continue
                for currency, address_pattern in REGEX:
                    for match in address_pattern.finditer(value):
                        address = match.group(0)
                        if address not in user_addresses:
                            user_addresses[address] = currency
            #if user_addresses:
            #    print(row['user_id'], user_addresses)
            for address, currency in user_addresses.items():
                tag = {
                    'address': address,
                    'currency': currency,
                    'label': 'User {name} at BitcoinTalk forum'.format(name=row['name']),
                    'source': BITCOINTALK_PROFILE_URL.format(user_id=row['user_id']),
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
    update_raw_data = len(sys.argv) >= 2 and sys.argv[1] == 'update'
    if not os.path.exists(config['RAW_FILE_NAME']) or update_raw_data:
        raw_data.download(update_raw_data)

    last_mod = datetime.fromtimestamp(os.path.getmtime(config['RAW_FILE_NAME'])).isoformat()
    generator = TagPackGenerator(raw_data.read(), config['TITLE'], config['CREATOR'], config['DESCRIPTION'],
                                 last_mod, config['SOURCE'])
    generator.generate()
    generator.saveYaml(config['TAGPACK_FILE_NAME'])
