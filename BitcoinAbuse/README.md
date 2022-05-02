# Convert Bitcoin Abuse Database

This code converts the data provided by the [Bitcoin Abuse Database](https://www.bitcoinabuse.com/) to GraphSense TagPacks.

# Usage
```
python3 generateTagPack.py
```

You may find the output named `seekoin_tagpack.yaml`.  
# Help
This converter uses selenium to control a firefox browser and grab pages.  
On MacOSX machines this will require geckodriver:
```
brew install geckodriver
```
