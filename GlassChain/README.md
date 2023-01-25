# Convert Glasschain.org data

This code converts This code converts the data provided by the [Glasschain.org](https://glasschain.org/providers) to GraphSense TagPacks.

# Usage
```
python3 generateTagPack.py
```

You may find the output named `glasschain_tagpack.yaml`.

Running `python3 generateTagPack-large.py` gets even more addresses from GlassChain.

# Requirements
This converter uses `requests` and `BeautifulSoup`.