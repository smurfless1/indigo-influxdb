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
from influxdb.exceptions import InfluxDBClientError

class Plugin(indigo.PluginBase):
    def __init__(self, pluginId, pluginDisplayName, pluginVersion, pluginPrefs):
        super(Plugin, self).__init__(pluginId, pluginDisplayName, pluginVersion, pluginPrefs)
        indigo.devices.subscribeToChanges()
        indigo.variables.subscribeToChanges()
        self.connection = None
        self.adaptor = IndigoAdaptor()
        self.folders = {}

    def connect(self):
        indigo.server.log(u'Starting influx connection')

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

        indigo.server.log(u'Connecting...')
        self.connection.create_database(self.database)
        self.connection.switch_database(self.database)
        self.connection.create_retention_policy('two_year_policy', '730d', '1')
        indigo.server.log(u'Influx connection succeeded')

    # send this a dict of what to write
    def send(self, tags, what, measurement='device_changes'):
        json_body=[
            {
                'measurement': measurement,
                'tags' : tags,
                'fields':  what
            }
        ]

        if self.pluginPrefs.get(u'debug', False):
            indigo.server.log(json.dumps(json_body).encode('utf-8'))

        # don't like my types? ok, fine, what DO you want?
        retrylimit = 30
        unsent = True
        while unsent and retrylimit > 0:
            retrylimit -= 1
            try:
                self.connection.write_points(json_body)
                unsent = False
            except InfluxDBClientError as e:
                #print(str(e))
                field = json.loads(e.content)['error'].split('"')[1]
                #measurement = json.loads(e.content)['error'].split('"')[3]
                retry = json.loads(e.content)['error'].split('"')[4].split()[7]
                if retry == 'integer':
                    retry = 'int'
                if retry == 'string':
                    retry = 'str'
                # float is already float
                # now we know to try to force this field to this type forever more
                self.adaptor.typecache[field] = retry
                try:
                    newcode = '%s("%s")' % (retry, str(json_body[0]['fields'][field]))
                    #indigo.server.log(newcode)
                    json_body[0]['fields'][field] = eval(newcode)
                except ValueError:
                    pass
                    #indigo.server.log('One of the columns just will not convert to its previous type. This means the database columns are just plain wrong.')
            except ValueError:
                if self.pluginPrefs.get(u'debug', False):
                    indigo.server.log(u'Unable to force a field to the type in Influx - a partial record was still written')
            except Exception as e:
                indigo.server.log("Error while trying to write:")
                indigo.server.log(unicode(e))
        if retrylimit == 0 and unsent:
            if self.pluginPrefs.get(u'debug', False):
                indigo.server.log(u'Unable to force all fields to the types in Influx - a partial record was still written')

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
        tagnames = u'name folderId'.split()
        newjson = self.adaptor.diff_to_json(newDev)

        newtags = {}
        for tag in tagnames:
            newtags[tag] = unicode(getattr(newDev, tag))

        # add a folder name tag
        if hasattr(newDev, u'folderId') and newDev.folderId != 0:
            newtags[u'folder'] = indigo.devices.folders[newDev.folderId].name

        measurement = newjson[u'measurement']
        del newjson[u'measurement']
        self.send(tags=newtags, what=newjson, measurement=measurement)

    def variableUpdated(self, origVar, newVar):
        indigo.PluginBase.variableUpdated(self, origVar, newVar)

        newtags = {u'varname': newVar.name}
        newjson = {u'name': newVar.name, u'value': newVar.value }
        numval = self.adaptor.smart_value(newVar.value, True)
        if numval != None:
            newjson[u'value.num'] = numval

        self.send(tags=newtags, what=newjson, measurement=u'variable_changes')

