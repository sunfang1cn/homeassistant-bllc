"""
bllc fresh air
only tested on bllc BE series
"""
#coding:utf8
import asyncio
import logging
import json
from urllib import request,parse

from datetime import timedelta

import time
import voluptuous as vol

from homeassistant.components.fan import (
    PLATFORM_SCHEMA,
    FanEntity
)
from homeassistant.components.fan import FanEntityFeature
from homeassistant.config_entries import SOURCE_IMPORT
from homeassistant.const import (
    ATTR_ID,
    ATTR_ENTITY_ID,
    ATTR_MODE,
    ATTR_TEMPERATURE,
    CONF_HOST,
    CONF_NAME,CONF_SCAN_INTERVAL,
    CONF_TOKEN,
)
from homeassistant.helpers.event import track_time_interval
import homeassistant.helpers.config_validation as cv
from homeassistant.components.climate.const import (ATTR_CURRENT_TEMPERATURE,
                                                    ATTR_PRESET_MODE)
SPEED_HIGH = 100
SPEED_LOW = 33
SPEED_MEDIUM = 66
SPEED_OFF = 0

_LOGGER = logging.getLogger(__name__)
ATTR_HUMIDITY = "humidity"
ATTR_FILTER_REMAIN = 'filter_remain'
ATTR_SPEED_LIST = "speed_list"


LIST_URL = "https://api.gizwits.com/app/devdata/{did}/latest"
CTRL_URL = "https://api.gizwits.com/app/control/{did}"

DEFAULT_NAME = 'Bllc'
ATTR_AVAILABLE = 'available'

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required('applicationId'): cv.string,
    vol.Required('deviceId'): cv.string,
    vol.Required('userToken'): cv.string,
    vol.Optional(CONF_SCAN_INTERVAL, default=timedelta(seconds=30)): (
        vol.All(cv.time_period, cv.positive_timedelta)),
})


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the bllc fan devices."""
    applicationId = config.get('applicationId')
    deviceId = config.get('deviceId')
    userToken = config.get('userToken')
    scan_interval = config.get(CONF_SCAN_INTERVAL)

    bllc = bllcData(hass, applicationId, deviceId,userToken)
    bllc.update_data()
    if not bllc.devs:
        _LOGGER.error("No bllc devices detected.")
        return None

    devices = []
    for index in range(len(bllc.devs)):
        devices.append(bllcFan(bllc, index))
    add_entities(devices)

    bllc.devices = devices
    track_time_interval(hass, bllc.update, scan_interval)


class bllcData():
    """Class for handling the data retrieval."""

    def __init__(self, hass,applicationId, deviceId,userToken):
        """Initialize the data object."""
        self._hass = hass
        self._applicationId = applicationId
        self._deviceId = deviceId
        self._userToken = userToken
        self.devs = None



    def update(self,time2=None):
        """Update online data and update ha state."""
        self.update_data()
        time.sleep(1)
        index = 0
        update_tasks = []
        for device in self.devices:
          device.schedule_update_ha_state()



    def update_data(self):
        """Update online data."""
        try:
            _json = self.request(LIST_URL.replace('{did}',self._deviceId))
            if _json is None:
                _LOGGER.error("failed to get bllc devices")
                return
            devs = []
            devs.append({'is_on': 0 if _json['attr']['Mode'] == '5' else 1,
                         ATTR_PRESET_MODE: _json['attr']['Mode'],
                         ATTR_CURRENT_TEMPERATURE: _json['attr']['Temp']/10,
                         ATTR_AVAILABLE: _json['attr'] is not None,
                         ATTR_HUMIDITY:_json['attr']['Hum'],
                         ATTR_FILTER_REMAIN: _json['attr']['Filter'],
                         ATTR_ID:_json['did']})
            self.devs = devs
            _LOGGER.info("List device: devs=%s", self.devs)
        except Exception:
            import traceback
            _LOGGER.error(traceback.format_exc())

    def control(self, index, prop, value):
        """Control device via server."""
        try:
            postdata = {}
            postdata['attrs'] = {}
            postdata['attrs'][prop] = value
            device_id = self.devs[index][ATTR_ID]
            json = self.request(CTRL_URL.replace('{did}',device_id), postdata)
            _LOGGER.debug("Control device: prop=%s, json=%s", prop, json)
            self.update()
            if json is not None:
                return True
            return False
        except Exception:
            import traceback
            _LOGGER.error('Exception: %s', traceback.format_exc())
            return False

    def request(self, url,postdata=None):
        """Request from server."""
        headers = {    
            'Accept': 'application/json',
            'X-Gizwits-Application-Id': self._applicationId,
            'X-Gizwits-User-token': self._userToken
        }
        req = None
        if postdata is not None:
            headers['Content-Type'] = 'application/json';
            _postdata = bytes(json.dumps(postdata),'utf8')
            req = request.Request(url=url,data=_postdata,headers=headers,method='POST')
        else:
            req = request.Request(url=url,data=None,headers=headers,method='GET')
            
        try:
            response = request.urlopen(req,timeout=5)
        except urllib.error.HTTPError as e:
            print(f"HTTP Error: {e.code} - {e.reason}")
        except urllib.error.URLError as e:
            print(f"URL Error: {e.reason}")
        except Exception as e:
            print(f"An unexpected error occurred: {e}")
            
        if response.status == 200:
            res = json.loads(response.read().decode('utf-8'))
            if type(res) is not dict:
                _LOGGER.error('HTTP REQUEST FAILED, %req, %res',req,res)
                _LOGGER.error(postdata,headers,url)
                return None
            return res




        

class bllcFan(FanEntity):
    """Representation of a bllc fan device."""

    def __init__(self, bllc, index):
        """Initialize the fan device."""
        self._index = index
        self._data = bllc

    @property
    def name(self):
        """Return the name of the climate device."""
        return '布朗新风' + str(self._index)

    @property
    def unique_id(self):
        """Return a unique ID.
        This is based on the topic that comes from mqtt
        """
        return 'bllc_' + self._data.devs[self._index][ATTR_ID]
        
    @property
    def speed_list(self) -> list:
        """Get the list of available speeds."""
        speeds = [SPEED_LOW,SPEED_MEDIUM,SPEED_HIGH,SPEED_OFF]
        return speeds
        
    @property
    def available(self):
        """Return if the sensor data are available."""
        return self.get_value(ATTR_AVAILABLE)

    @property
    def device_state_attributes(self):
        """Return the state attributes of the device."""
        return self._data.devs[self._index]
        
    @property
    def extra_state_attributes(self) -> dict:
        """Return optional state attributes."""
        return {
            ATTR_HUMIDITY: self.get_value(ATTR_HUMIDITY),
            ATTR_FILTER_REMAIN: self.get_value(ATTR_FILTER_REMAIN),
            ATTR_CURRENT_TEMPERATURE: self.get_value(ATTR_CURRENT_TEMPERATURE)
        }
    @property
    def supported_features(self):
        """Return the list of supported features."""
        return FanEntityFeature.SET_SPEED | FanEntityFeature.TURN_ON | FanEntityFeature.TURN_OFF

    @property
    def temperature_unit(self):
        """Return the unit of measurement."""
        return self._data._hass.config.units.temperature_unit
        
    @property
    def speed(self) -> str:
        """Return the current speed."""
        _speed = SPEED_OFF
        if self.get_value(ATTR_PRESET_MODE) == '1':
            _speed = SPEED_HIGH
        if self.get_value(ATTR_PRESET_MODE) == '2':
            _speed = SPEED_MEDIUM
        if self.get_value(ATTR_PRESET_MODE) == '3':
            _speed = SPEED_LOW

        return _speed


    @property
    def current_temperature(self):
        """Return the current temperature."""
        return self.get_value(ATTR_CURRENT_TEMPERATURE)



    def set_speed(self,
        speed: str = None):
        if speed == SPEED_HIGH:
            self.set_value('Mode','1')
            self._data.devs[self._index]['is_on'] = 1
            self._data.devs[self._index][ATTR_PRESET_MODE] = 1

        if speed == SPEED_LOW:
            self.set_value('Mode','3')
            self._data.devs[self._index]['is_on'] = 1
            self._data.devs[self._index][ATTR_PRESET_MODE] = 3

        if speed == SPEED_MEDIUM:
            self.set_value('Mode','2')
            self._data.devs[self._index]['is_on'] = 1
            self._data.devs[self._index][ATTR_PRESET_MODE] = 2
        if speed == SPEED_OFF:
            self.set_value('Mode','5')
            self._data.devs[self._index]['is_on'] = 0
            self._data.devs[self._index][ATTR_PRESET_MODE] = 5

        
    def set_percentage(self, percentage: int) -> None:    
        if percentage == 0:
            self.set_speed(SPEED_OFF)
        if percentage > 0 and percentage <= 33:
            self.set_speed(SPEED_LOW)
        if percentage > 33 and percentage <= 66:
            self.set_speed(SPEED_MEDIUM)
        if percentage > 66 and percentage <= 100:
            self.set_speed(SPEED_HIGH)

    def turn_on(
        self,
        speed: str = None,
        percentage = None,
        preset_mode = None):
        """Turn the device on."""
        if speed:
            # If operation mode was set the device must not be turned on.
            result = self.set_speed(speed)
        else:
            result = self.set_value('Mode','1')
            self._data.devs[self._index]['is_on'] = 1
            self._data.devs[self._index][ATTR_PRESET_MODE] = 1
            
    @property
    def is_on(self):
        """Return true if device is on."""
        return self.get_value('is_on') == 1

    def turn_off(self) -> None:
        """Turn the device off."""
        result = self.set_value('Mode','5')
        self._data.devs[self._index]['is_on'] = 0
        self._data.devs[self._index][ATTR_PRESET_MODE] = 5

    def get_value(self, prop):
        """Get property value"""
        devs = self._data.devs
        if devs and self._index < len(devs):
            return devs[self._index][prop]
        return None

    def set_value(self, prop, value):
        """Set property value"""
        self._data.control(self._index, prop, value)


