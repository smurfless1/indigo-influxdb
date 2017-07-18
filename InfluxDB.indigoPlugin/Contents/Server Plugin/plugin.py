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
import json

from influxdb import InfluxDBClient

class Plugin(indigo.PluginBase):
    def __init__(self, pluginId, pluginDisplayName, pluginVersion, pluginPrefs):
        super(Plugin, self).__init__(pluginId, pluginDisplayName, pluginVersion, pluginPrefs)
        indigo.devices.subscribeToChanges()
        self.connection = None

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
        self.connection.create_retention_policy('month_policy', '31d', '1')
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
        self.connection.write_points(json_body)

    def startup(self):
        try:
            self.host = self.pluginPrefs.get('host', 'localhost')
            self.port = self.pluginPrefs.get('port', '8086')
            self.user = self.pluginPrefs.get('user', 'indigo')
            self.password = self.pluginPrefs.get('password', 'indigo')
            self.database = self.pluginPrefs.get('database', 'indigo')
            self.debug = self.pluginPrefs.get('debug', False)

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
        newjson = {}
        newjson['timestamp'] = int(round(time_.time()))
        newtags = {}
        newtags['name'] = newDev.name

        for key in keynames.split():
            if hasattr(origDev, key) and str(getattr(origDev, key)) != "null" and str(getattr(origDev, key)) != "None":
                newjson[key] = getattr(origDev, key)
            if hasattr(newDev, key) and str(getattr(newDev, key)) != "null" and str(getattr(newDev, key)) != "None":
                newjson[key] = getattr(newDev, key)

        for state in newDev.states:
            newjson['state.' + state] = newDev.states[state]

        if self.debug:
            indigo.server.log(json.dumps(newjson).encode('ascii'))

        self.send(newtags, newjson)

