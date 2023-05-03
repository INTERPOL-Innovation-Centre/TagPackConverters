# What is this?
Each of the above folder is a source of verifiable information linking a cryptocurrency wallet to an entity.
These sources are public sanctions lists as well as other publicly advertised lists published by service providers.

These lists help investigators make links between addresses and entities but absolutely need to be verified prior to prosecution.
Each of the folder contains the necessary scripts to scrape the contents and build datasets that may be used to automate these purposes.

# TagPackGenerators

In investigating Cryptocurrencies and Virtual Assets, **attribution is key**.
A TagPack contains information about the actors owning the asset and where this information was found.

This repository contains codes to convert public information regarding tagged virtual assets to the [GraphSense TagPacks format](https://github.com/graphsense/graphsense-tagpacks).

Please refer to the READMEs in each folder to use the converters. 

## Prerequisit - for all of the converters in the sub-folders

Works with Python3.  
Requires Python tools: *regex* (re), *PyYAML* (yaml), and *requests* (requests).  
Python tools *datetime* and *json* should already be installed.  

These are typically installed with [pip](https://pip.pypa.io/en/stable/)  
```
pip3 install -r requirements.txt
```

## Run in a docker container 

This approach is a convenient way of generating all tagpacks. It can easily be deployed on a server.

Clone the repository, start up the container

```
docker-compose up -d
```

You can check the progress in the log file:

```commandline
docker-compose logs  -f tagpackcreation
```



## Disclaimer
*Prior to working on this repository and its contents, please make sure your agree to our [disclaimer](https://github.com/INTERPOL-Innovation-Centre/DISCLAIMER)*  
*This repository only contains the code, not the police data. Please do not store your TagPack(s) in this repository.*  
*Please let us know by opening an [Issue](https://github.com/INTERPOL-Innovation-Centre/TagPackConverters/issues) if you want to suggest a new feature or data source or find a bug.*
