# Convert CoinPayU data

This code converts the data provided by the [CoinPayU.com](https://www.coinpayu.com/) to GraphSense TagPacks.

# Usage
```
python3 generateTagPack.py
```

You may find the output named `coinpayu_tagpack.yaml`.

# Requirements (really???)
This converter uses selenium to control a Firefox browser and grab pages.  
On MacOSX machines this will require geckodriver:
```
brew install geckodriver
```
On Windows, download geckodriver from https://github.com/mozilla/geckodriver/releases.
