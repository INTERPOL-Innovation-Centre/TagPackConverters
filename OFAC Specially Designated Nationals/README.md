# OFAC-TagPack
Automated scraping of the US Treasury Office of Foreign Assets Control  
Specially Designated Nationals List

This repository contains the tool to create a YAML TagPack with the Virtual Assets addresses found in the OFAC-SDN lists.  
This TagPack can be used in Cryptocurrency analytics tools such as [GraphSense](https://github.com/graphsense/graphsense-tagpacks).

## Disclaimer
This tool will scrape the URL in the config file and will add the following cryptocurrencies to the TagPack:
- BTC
- BCH
- ETH
- ZEC
- LTC
- WMR
- DASH  
Other addresses or adddresses not complying with our controls will not be added to the TagPack. 

This Python script may be tweaked to scrape other pages, currently it is written to search for the string *Digital Currency Address* and extract the address and the Cryptocurrency code found immediately after that string.

## Authors
Shun Inagaki
[github/skynde](https://github.com/skynde)  
Vincent Danjean
[github/VinceICPO](https://github.com/VinceICPO)

## Use
Download the generateTagPack.py and config.json.  
Edit the Config.json file as required.  
It shall contain:
- source : the URL to scrape (this will also be the source tag in the resulting json tagpack.  
- label : the description to be added in the tagpack for this source.  
- title : The short text identification that will appear on addresses matching in the cryptocurrency analytics tool
- creator : This is for users to know who created this tagpack
- category : considering the [darkweb and virtual assets taxonomy](https://github.com/INTERPOL-Innovation-Centre/DW-VA-Taxonomy), the entity to which these addresses belong to, here an end "user".

Then simply run:
```
python3 generateTagPack.py
```
The output should be similar to:
```
This address was skipped (currency not supported yet): 12sjrrhoFEsedNRhtgwvvRqjFTh8fZTDX9 (BSV)
This address was skipped (invalid address?) 5be5543ff73456ab9f2d207887e2af87322c651ea1a873c5b25b7ffae456c320 (XMR)
This address was skipped (currency not supported yet): GPwg61XoHqQPNmAucFACuQ5H9sGCDv9TpS (BTG)
This address was skipped (invalid address?) 0xa7e5d5a720f06526557c513402f2e6b5fa20b00 (ETH)
This address was skipped (currency not supported yet): DFFJhnQNZf8rf67tYnesPu7MuGUpYtzv7Z (XVG)
Processed  95 tags with  5  addresses skipped because they failed our controls.
```
And of course an OFAC_tagpack.yaml file which is the TagPack itself.
