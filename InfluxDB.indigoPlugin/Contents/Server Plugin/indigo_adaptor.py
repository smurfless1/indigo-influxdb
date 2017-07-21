from datetime import date, datetime
import time as time_
import json
import indigo
from enum import Enum

# explicit changes
def indigo_json_serial(obj):
    """JSON serializer for objects not serializable by default json code"""
    #indigo.server.log(unicode(obj))
    if isinstance(obj, (datetime, date)):
        ut = time_.mktime(obj.timetuple())
        return int(ut)
    if isinstance(obj, indigo.Dict):
        dd = {}
        for key,value in obj.iteritems():
            dd[key] = value
        return dd
    raise TypeError ("Type %s not serializable" % type(obj))

class IndigoAdaptor():
    '''
    Change indigo objects to flat dicts for simpler databases
    '''
    def __init__(self):
        self.debug = False
        # Class Properties on http://wiki.indigodomo.com/doku.php?id=indigo_7_documentation:device_class
        self.keynames = 'address description deviceTypeId ' \
                   'energyAccumBaseTime model name ' \
                   'pluginId'.split()
        self.intkeys = 'activeZone zoneCount pausedScheduleZone pausedScheduleRemainingZoneDuration batteryLevel brightness ' \
                  'brightnessLevel buttonGroupCount energyAccumTimeDelta folderId id speedIndex speedIndexCount ' \
                  'humiditySensorCount temperatureSensorCount'.split()
        self.floatkeys = 'energyCurLevel energyAccumTotal sensorValue coolSetpoint heatSetpoint ' \
                'humidityInput1 humidityInput2 humidityInput3 ' \
                'temperatureInput1 temperatureInput2 temperatureInput3 setpointCool setpointHeat'.split()
        self.boolkeys = 'configured enabled onState onOffState remoteDisplay speedLevel zone1 zone2 zone3 zone4 zone5 zone6 ' \
                   'coolIsOn dehumidifierIsOn fanIsOn heatIsOn humidifierIsOn'.split()
        self.datekeys = ['lastChanged']
        self.dictkeys = 'globalProps ownerProps pluginProps states'.split()
        self.floatlists = 'temperatures humidities'.split()

        for somelist in [self.intkeys, self.floatkeys, self.boolkeys, self.datekeys]:
            self.keynames.extend(somelist)

        # have the json serializer always use this
        json.JSONEncoder.default = indigo_json_serial

        # remember previous states for diffing, smaller databases
        self.cache = {}

    # returns None or a value, trying to convert strings to floats where
    # possible
    def smart_value(self, invalue):
        value = None
        if unicode(invalue) != "null" \
            and unicode(invalue) != "None" \
            and not isinstance(invalue, indigo.List) \
            and not isinstance(invalue, list) \
            and not isinstance(invalue, indigo.Dict) \
            and not isinstance(invalue, dict):
            value = invalue
            try:
                # convert datetime to timestamps of another flavor
                if isinstance(invalue, (datetime, date)):
                    ut = time_.mktime(invalue.timetuple())
                    value = int(ut)
                # if we have a string, but it really is a number,
                # MAKE IT A NUMBER IDIOTS
                elif isinstance(invalue, basestring):
                    value = float(invalue)
                # explicitly change enum values to strings
                # TODO find a more reliable way to change enums to strings
                elif invalue.__class__.__bases__[0].__name__ == 'enum':
                    value = unicode(invalue)
            except ValueError:
                pass
        return value

    def to_json(self, device):
        attrlist = [attr for attr in dir(device) if
                    attr[:2] + attr[-2:] != '____' and not callable(getattr(device, attr))]
        #indigo.server.log(device.name + ' ' + ' '.join(attrlist))
        newjson = {}
        newjson['name'] = device.name
        for key in attrlist:
            #import pdb; pdb.set_trace()
            if hasattr(device, key) \
                and key not in newjson.keys() \
                and self.smart_value(getattr(device, key)) != None:
                newjson[key] = self.smart_value(getattr(device, key))

        # trouble areas
        # dicts end enums will not upload without a little abuse
        for key in 'states globalProps pluginProps ' \
            'ownerProps'.split():
            if key in newjson.keys():
                del newjson[key]

        for key in newjson.keys():
            if newjson[key].__class__.__name__.startswith('k'):
                newjson[key] = unicode(newjson[key])

        for key in 'displayStateValRaw displayStateValUi displayStateImageSel protocol'.split():
            if key in newjson.keys():
                newjson[key] = unicode(newjson[key])

        for state in device.states:
            if self.smart_value(device.states[state]) != None:
                newjson['state.' + state] = self.smart_value(device.states[state])

        return newjson

    def diff_to_json(self, device):
        # strip out matching values?
        # find or create our cache dict
        newjson = self.to_json(device)

        localcache = {}
        if device.name in self.cache.keys():
            localcache = self.cache[device.name]

        diffjson = {}
        for kk, vv in newjson.iteritems():
            if kk not in localcache or localcache[kk] != vv:
                if not isinstance(vv, indigo.Dict) and not isinstance(vv, dict):
                    diffjson[kk] = vv

        if not device.name in self.cache.keys():
            self.cache[device.name] = {}
        self.cache[device.name].update(newjson)

        # always make sure these survive
        diffjson['name'] = device.name
        diffjson['id'] = device.id

        if self.debug:
            indigo.server.log(json.dumps(newjson, default=indigo_json_serial).encode('utf-8'))
            indigo.server.log(u'diff:')
            indigo.server.log(json.dumps(diffjson, default=indigo_json_serial).encode('utf-8'))

        return diffjson

