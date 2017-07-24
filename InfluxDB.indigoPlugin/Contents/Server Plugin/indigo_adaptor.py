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
        self.stringonly = 'displayStateValRaw displayStateValUi displayStateImageSel protocol'.split()

        # have the json serializer always use this
        json.JSONEncoder.default = indigo_json_serial

        # remember previous states for diffing, smaller databases
        self.cache = {}

    # returns None or a value, trying to convert strings to floats where
    # possible
    def smart_value(self, invalue, mknumbers=False):
        value = None
        if unicode(invalue) != u"null" \
            and unicode(invalue) != u"None" \
            and not isinstance(invalue, indigo.List) \
            and not isinstance(invalue, list) \
            and not isinstance(invalue, indigo.Dict) \
            and not isinstance(invalue, dict):
            value = invalue
            try:
                if mknumbers:
                    # early exit if we want a number but already have one
                    if isinstance(invalue, int) or isinstance(invalue, float):
                        return None
                    elif isinstance(invalue, (datetime, date)):
                        return None
                    # if we have a string, but it really is a number,
                    # MAKE IT A NUMBER IDIOTS
                    elif isinstance(invalue, basestring):
                        value = float(invalue)
                # convert datetime to timestamps of another flavor
                elif isinstance(invalue, (datetime, date)):
                    ut = time_.mktime(invalue.timetuple())
                    value = int(ut)
                # explicitly change enum values to strings
                # TODO find a more reliable way to change enums to strings
                elif invalue.__class__.__bases__[0].__name__ == 'enum':
                    value = unicode(invalue)
            except ValueError:
                if mknumbers:
                    # if we were trying to force numbers but couldn't
                    value = None
                pass
        return value

    def to_json(self, device):
        attrlist = [attr for attr in dir(device) if
                    attr[:2] + attr[-2:] != '____' and not callable(getattr(device, attr))]
        #indigo.server.log(device.name + ' ' + ' '.join(attrlist))
        newjson = {}
        newjson[u'name'] = unicode(device.name)
        for key in attrlist:
            #import pdb; pdb.set_trace()
            if hasattr(device, key) \
                and key not in newjson.keys():
                val = self.smart_value(getattr(device, key), False);
                # some things change types - define the original name as original type, key.num as numeric
                if val != None:
                    newjson[key] = val
                if key in self.stringonly:
                    continue
                val = self.smart_value(getattr(device, key), True);
                if val != None:
                    newjson[key + '.num'] = val

        # trouble areas
        # dicts end enums will not upload without a little abuse
        for key in 'states globalProps pluginProps ' \
            'ownerProps'.split():
            if key in newjson.keys():
                del newjson[key]

        for key in newjson.keys():
            if newjson[key].__class__.__name__.startswith('k'):
                newjson[key] = unicode(newjson[key])

        for key in self.stringonly:
            if key in newjson.keys():
                newjson[key] = unicode(newjson[key])

        for state in device.states:
            val = self.smart_value(device.states[state], False);
            if val != None:
                newjson[unicode('state.' + state)] = val
            if state in self.stringonly:
                continue
            val = self.smart_value(device.states[state], True);
            if val != None:
                newjson[unicode('state.' + state + '.num')] = val

        # Try to tell the caller what kind of measurement this is
        if u'setpointHeat' in device.states.keys():
            newjson[u'measurement'] = u'thermostat_changes'
        elif device.model == u'Weather Station':
            newjson[u'measurement'] = u'weather_changes'
        else:
            newjson[u'measurement'] = u'device_changes'

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
        diffjson[u'measurement'] = newjson[u'measurement']

        if self.debug:
            indigo.server.log(json.dumps(newjson, default=indigo_json_serial).encode('utf-8'))
            indigo.server.log(u'diff:')
            indigo.server.log(json.dumps(diffjson, default=indigo_json_serial).encode('utf-8'))

        return diffjson

