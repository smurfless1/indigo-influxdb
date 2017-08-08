Indigo Plug-Ins for InfluxDB and Kafka
---

Indigo Plug-In for writing JSON to InfluxDB 

Before starting
---

* Install/license Indigo 7


Configure Indigo
---

* Download the InfluxDB Plugin directory
* Run the script install_python_modules.sh from Terminal and restart the Indigo server process.  THIS REALLY HAS TO BE DONE BEFORE INSTALLING THE PLUGIN.  Stop and restart the indigo server from the UI so it can learn about the new modules.  I hate this step, but there you go. 
* Install the plugin by double-clicking.
* Configure the hostname/user/pass/ports etc. For me the defaults for the local system are already set.
* go get a drink, turning switches on and off along the way, setting off motion sensors, opening doors, and generally being disruptive. 

But I don't have Influx or Grafana
---

There are lots of ways to make it work. Luckily homebrew is awesome for the rest of us. 

* Install homebrew : https://brew.sh

```
# use https://github.com/Homebrew/homebrew-services
brew tap homebrew/services
```

Install InfluxDB on my mac
---

```
brew install influxdb
```

Did it work?

```
which influx && echo "Installed!"
which influx && brew services start influxdb
```

Teach influx that I'm going to be putting things in from indigo. The plugin creates the database if required. Just need a user. Copy-paste the next 4 lines all at once and hit return after the EOF line

```
influx <<EOF
CREATE USER indigo WITH PASSWORD 'indigo'
GRANT ALL PRIVILEGES TO indigo
EOF
```

Check the installation:

```
alias indigoinflux="influx -host localhost -port 8086 -username indigo -password indigo -database indigo"
indigoinflux -execute 'select * from device_changes'
# no error, no output - after all, I just created it

indigoinflux -execute 'select * from device_changes' | wc -l
```

Anything bigger than about 2 shows data is going in. WIN! If not, check the indigo log for hints, suspect user name/password, the port, newer versions of indigo than I wrote this for, needing a different version of the python modules, etc.

Install Grafana on my mac
---

```
brew install grafana
brew services start grafana
```

Boostrap: user admin pass admin - they really need to tell you that better from the brew install.

```
open http://localhost:3000
```

Use the "login" tab.  Create whatever users, passwords, and logins you want. Since I plan to visit Grafana from other systems, I learned not to use localhost as the data source hostname - use IP, bonjour name (something.local.), or resolvable hostname. Use the "proxy" option, it's not what I expected, it makes the server do all the work. Start creating dashboards. which I'm not good at apparently. They have docs, I have them open a lot. 

To see the raw data:

```
indigoinflux -execute 'select * from device_changes' > /tmp/raw_device_data.txt
vim /tmp/raw_device_data.txt
```

In vim, ```:set nowrap``` so it's more table-ish


