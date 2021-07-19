# EtherScan DB

This codes convert the data provided by EtherScan DB to GraphSense TagPacks. EthersScan DB is an open-source database to keep track of all the current ethereum scams.

While this data contains reporters of each address tagged, please kindly note that there is no exact URL proving that the address is involved in a crime.


# Usage
```
pip3 install -r requirements.txt
python3 generateTagPack.py
```

You may find the output named `etherscamdb_tagpack.yaml`.
