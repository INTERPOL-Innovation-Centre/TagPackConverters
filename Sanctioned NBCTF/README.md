# Sanctioned Cryptocurrency list by National Bureau for Counter Terror Financing of Israel  

This codes convert the data provided by the [NBCTF](https://nbctf.mod.gov.il/en/designations/Pages/downloads.aspx) to GraphSense TagPacks.  

# Usage
This specific converter requires an additional python package: *selenium* therefore, it has its own `requirements.txt` file.  
*Selenium* is used to handle the captcha human validation process.

```
pip3 install -r requirements.txt
python3 generateTagPack.py
```

You may find the output named `sanctionednbctf_tagpack.yaml`.

# Requirements
This converter uses selenium to control a Firefox browser and grab pages.
On MacOSX machines this will require geckodriver:
```
brew install geckodriver
```
On Windows, download geckodriver from https://github.com/mozilla/geckodriver/releases.

