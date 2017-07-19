#!/bin/bash

# explicitly use the system python - this only affects this script
PATH=/usr/bin:/bin:/usr/sbin:/sbin

# make sure pip is around
sudo easy_install pip

# install and/or upgrade influxdb
sudo /usr/local/bin/pip install influxdb
sudo /usr/local/bin/pip install influxdb --upgrade

