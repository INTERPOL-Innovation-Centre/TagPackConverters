#!/usr/bin/env python3
"""
Convert Seizures of Cryptocurrency list by National Bureau for Counter Terror Financing of Israel to a TagPack.
"""

import os
import re
import csv
from datetime import datetime
from typing import List

import yaml
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC


# Taken from OFAC Specially Designated Nationals generator and modified
REGEX = [
    ('BTC', re.compile(r'\b((?:[13]|bc1)[A-HJ-NP-Za-km-z1-9]{27,34})\b')),
    ('BCH', re.compile(r'\b(((?:bitcoincash|bchtest):)?(qp)?[0-9a-zA-Z]{40})\b')),
    ('LTC', re.compile(r'\b([LM3][a-km-zA-HJ-NP-Z1-9]{25,33})\b')),
    ('ZEC', re.compile(r'\b([tz][13][a-km-zA-HJ-NP-Z1-9]{33})\b')),
    ('ETH', re.compile(r'\b((0x)?[0-9a-fA-F]{40})\b')),
    ('USDT', re.compile(r'\b(T[A-Za-z1-9]{33})\b'))
]


class RawData:
    """
    Download and read data provided by the source.
    """

    def __init__(self, fn: str, url: str):
        self.fn = fn
        self.url = url

    def download(self):
        """
        Scrape data from table at https://nbctf.mod.gov.il/en/seizures/Pages/Blockchain1.aspx

        The site is protected against robots, hence we use selenium to be able to solve the appearing CAPTCHA.
        """
        wd = webdriver.Firefox()
        wd.maximize_window()  # Without this, we do not get values in the last column
        wd.get(self.url)
        table = WebDriverWait(wd, 30).until(  # Wait for up to 30 seconds, because it needs time to solve CAPTCHA
            EC.presence_of_element_located((By.XPATH, '//table[2]'))
        )
        """
        This table has a very peculiar structure, with at least once an address in one row and the currency quote
        in the next row. Also, quite often, currency quotes are plain wrong. For example, several Bitcoin addresses
        have Tether as currency quote, notwithstanding the differences between the address formats.
        
        Hence it seems the best solution to save only the order ID, the address, and the _automatically_ recognised
        currency quote.
        """
        header_row = [cell.text.strip() for cell in table.find_elements(By.XPATH, 'tbody/tr[1]/th')]
        assert header_row == ['Order ID', 'Full name', 'Palestinian Authority ID No', 'Palestinian Authority Passport No', 'D.O.B (DD/MM/YYYY)', 'Virtual currency address / User ID', '']
        data_rows = [['Order ID', 'Address', 'Currency']]  # This is the container of values
        column_count = len(header_row)
        order_id = ''
        rows = table.find_elements(By.XPATH, 'tbody/tr')
        for row_index in range(1, len(rows)):
            row = rows[row_index].find_elements(By.TAG_NAME, 'td')
            if len(row) == column_count:
                order_id = row[0].text.strip().replace('\n', ' ').replace('  ', ' ')
            for column_index in range(1 if len(row) == column_count else 0, len(row)):
                cell_value = row[column_index].text
                for currency, address_format in REGEX:
                    for match in address_format.finditer(cell_value):
                        if currency == 'LTC' and data_rows[-1][2] == 'BTC' and data_rows[-1][1] == match.group(1):
                            continue  # We cannot have a LTC address equal previous BTC address; it is a false positive
                        data_rows.append([order_id, match.group(1), currency])
        wd.quit()
        # Write data rows to CSV file
        with open(self.fn, 'w', encoding='utf-8', newline='') as csvfile:
            writer = csv.writer(csvfile)
            writer.writerows(data_rows)

    def read(self) -> List[dict]:
        with open(self.fn, 'r', encoding='utf-8', newline='') as csvfile:
            reader = csv.DictReader(csvfile)
            return [row for row in reader]


class TagPackGenerator:
    """
    Generate a TagPack from Seizures of Cryptocurrency list.
    """

    def __init__(self, rows: List[dict], title: str, creator: str, description: str, lastmod: str, source: str):
        self.rows = rows
        self.data = {
            'title': title,
            'creator': creator,
            'description': description,
            'lastmod': lastmod,
            'source': source,
            'category': 'perpetrator',
            'abuse': 'terrorism',
            'tags': []
        }

    def generate(self):
        tags = []
        processed_addresses = set()
        for row in self.rows:
            if row['Address'] in processed_addresses:
                continue
            tag = {
                'address': row['Address'],
                'currency': row['Currency'],
                'label': 'Seized by NBCTF of Israel (order ID: {order_id})'.format(order_id=row['Order ID'])
            }
            tags.append(tag)
            processed_addresses.add(row['Address'])
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