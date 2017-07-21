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
import time as time_
from datetime import datetime, date
import json
from indigo_adaptor import IndigoAdaptor
from influxdb import InfluxDBClient

class Plugin(indigo.PluginBase):
    def __init__(self, pluginId, pluginDisplayName, pluginVersion, pluginPrefs):
        super(Plugin, self).__init__(pluginId, pluginDisplayName, pluginVersion, pluginPrefs)
        indigo.devices.subscribeToChanges()
        self.connection = None
        self.adaptor = IndigoAdaptor()
        self.folders = {}

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
            indigo.server.log(unicode(e))


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
        # tag by folder if present
        tagnames = 'name folderId'.split()
        newjson = self.adaptor.diff_to_json(newDev)

        newtags = {}
        for tag in tagnames:
            newtags[tag] = unicode(getattr(newDev, tag))

        # add a folder name tag
        if hasattr(newDev, 'folderId') and newDev.folderId != 0:
            newtags['folder'] = indigo.devices.folders[newDev.folderId].name

        if self.pluginPrefs.get('debug', False):
            indigo.server.log(json.dumps(newjson).encode('utf-8'))

        self.send(newtags, newjson)

