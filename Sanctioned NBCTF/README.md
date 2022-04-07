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
