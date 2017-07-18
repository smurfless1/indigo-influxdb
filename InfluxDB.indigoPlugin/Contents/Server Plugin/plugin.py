#! /usr/bin/env python
# -*- coding: utf-8 -*-
# Copyright (c) 2017, Dave Brown
#
# config reference
# http://wiki.indigodomo.com/doku.php?id=indigo_7_documentation:plugin_guide#configuration_dialogs
# device fields
# http://wiki.indigodomo.com/doku.php?id=indigo_7_documentation:device_class#device_base_class
# object reference
# http://wiki.indigodomo.com/doku.php?id=indigo_7_documentation:object_model_reference
# Subscribe to changes mentioned:
# http://forums.indigodomo.com/viewtopic.php?f=108&t=14647
#
# CREATE USER indigo WITH PASSWORD 'indigo'
# GRANT ALL PRIVILEGES TO indigo
#
import indigo

import os
import sys
import time as time_
from datetime import datetime, date
import json

from influxdb import InfluxDBClient

# explicit changes
def json_serial(obj):
    """JSON serializer for objects not serializable by default json code"""
    indigo.server.log(str(obj))
    if isinstance(obj, (datetime, date)):
        ut = time_.mktime(obj.timetuple())
        return int(ut)
    if isinstance(obj, indigo.Dict):
        dd = {}
        for key,value in obj.iteritems():
            dd[key] = value
        return dd
    raise TypeError ("Type %s not serializable" % type(obj))

class Plugin(indigo.PluginBase):
    def __init__(self, pluginId, pluginDisplayName, pluginVersion, pluginPrefs):
        super(Plugin, self).__init__(pluginId, pluginDisplayName, pluginVersion, pluginPrefs)
        indigo.devices.subscribeToChanges()
        self.connection = None
        self.cache = {}

    def connect(self):
        indigo.server.log(u'starting influx connection')

        self.connection = InfluxDBClient(
            host=self.host,
            port=int(self.port),
            username=self.user,
            password=self.password,
            database=self.database)

        if self.pluginPrefs.get('reset', False):
            try:
                indigo.server.log(u'dropping old')
                self.connection.drop_database(self.database)
            except:
                pass

        indigo.server.log(u'create')
        self.connection.create_database(self.database)
        indigo.server.log(u'switch')
        self.connection.switch_database(self.database)
        indigo.server.log(u'retention')
        self.connection.create_retention_policy('two_year_policy', '730d', '1')
        indigo.server.log(u'influx connection succeeded')

    # send this a dict of what to write
    def send(self, tags, what):
        json_body=[
            {
                'measurement': 'device_changes',
                'tags' : tags,
                'fields':  what
            }
        ]
        try:
            self.connection.write_points(json_body)
        except Exception as e:
            indigo.server.log("InfluxDB write error:")
            indigo.server.log(str(e))


    def startup(self):
        try:
            self.host = self.pluginPrefs.get('host', 'localhost')
            self.port = self.pluginPrefs.get('port', '8086')
            self.user = self.pluginPrefs.get('user', 'indigo')
            self.password = self.pluginPrefs.get('password', 'indigo')
            self.database = self.pluginPrefs.get('database', 'indigo')

            self.connect()
        except:
            indigo.server.log(u'Failed to connect in startup')
            pass

    # called after runConcurrentThread() exits
    def shutdown(self):
        pass

    def deviceUpdated(self, origDev, newDev):
        # call base implementation
        indigo.PluginBase.deviceUpdated(self, origDev, newDev)

        # custom add to influx work
        tagnames = 'name folderId'
        keynames = 'address batteryLevel brightness buttonGroupCount configured description deviceTypeId enabled energyCurLevel ' \
                   'energyAccumTotal energyAccumBaseTime energyAccumTimeDelta folderId id model name onState' \
                   'pluginId sensorValue activeZone'
        # TODO force floats from weather plugin

        attrlist = [attr for attr in dir(newDev) if attr[:2] + attr[-2:] != '____' and not callable(getattr(newDev, attr))]
        newjson = {}
        newtags = {}
        newtags['name'] = newDev.name

        for key in keynames:
            for dev in [newDev, origDev]:
                if hasattr(dev, key) \
                        and str(getattr(dev, key)) != "null" \
                        and str(getattr(dev, key)) != "None" \
                        and key not in newjson.keys():
                    newjson[key] = getattr(dev, key)

        for state in newDev.states:
            newjson['state.' + state] = newDev.states[state]

        # strip out matching values?
        # find or create our cache dict
        localcache = {}
        if newDev.name in self.cache.keys():
            localcache = self.cache[newDev.name]

        diffjson = {}
        for kk, vv in newjson.iteritems():
            if kk not in localcache or localcache[kk] != vv:
                if not isinstance(vv, indigo.Dict) and not isinstance(vv, dict):
                    diffjson[kk] = vv;
        # always make sure these survive
        diffjson['name'] = origDev.name;
        diffjson['id'] = origDev.id;

        self.cache[newDev.name] = newjson

        # use the custom encoder to make a cleaned-up string
        if self.pluginPrefs.get('debug', False):
            indigo.server.log(json.dumps(newjson, default=json_serial).encode('ascii'))
            indigo.server.log(u'diff:')
            indigo.server.log(json.dumps(diffjson, default=json_serial).encode('ascii'))

        self.send(newtags, diffjson)

