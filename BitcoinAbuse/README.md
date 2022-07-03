# Convert Bitcoin Abuse Database

This code converts the data provided by the [Bitcoin Abuse Database](https://www.bitcoinabuse.com/) to GraphSense TagPacks.

# Usage
```
python3 generateTagPack.py
```

You may find the output named `bitcoinabuse_tagpack.yaml`.

# Requirements
This converter uses selenium to control a Firefox browser and grab pages.  
On MacOSX machines this will require geckodriver:
```
brew install geckodriver
```
On Windows, download geckodriver from https://github.com/mozilla/geckodriver/releases.
