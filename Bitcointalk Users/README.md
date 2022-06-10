# Convert BitcoinTalk forum user profiles

This code converts the cryptocurrency addresses in the user profiles at the [BitcoinTalk forum](https://bitcointalk.org/) to GraphSense TagPacks.

# Usage
```
python3 generateTagPack.py
```

You may find the output named `bitcointalk_users_tagpack.yaml`.

# Help
This converter uses selenium to control a firefox browser and grab pages.
On MacOSX machines this will require geckodriver:
```
brew install geckodriver
```
