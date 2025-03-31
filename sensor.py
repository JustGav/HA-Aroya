import logging
import aiohttp
import async_timeout

from homeassistant.components.sensor import SensorEntity
from homeassistant.const import CONF_API_KEY
from .const import DOMAIN, API_BASE

_LOGGER = logging.getLogger(__name__)

IGNORED_MODELS = {"gateway", "sink"}
IGNORED_SENSOR_TYPES = {
    "travel_time", "link_quality", "radio_power", "signal", "battery_v"
}

async def async_setup_entry(hass, entry, async_add_entities):
    api_key = entry.data[CONF_API_KEY]
    headers = {"Authorization": f"Bearer {api_key}"}
    entities = []

    async with aiohttp.ClientSession(headers=headers) as session:
        try:
            async with async_timeout.timeout(15):
                async with session.get(f"{API_BASE}/devices") as resp:
                    if resp.status != 200:
                        _LOGGER.error("Failed to fetch devices: HTTP %s", resp.status)
                        return
                    device_data = await resp.json()
        except Exception as e:
            _LOGGER.error("Failed to load devices from Aroya API: %s", e)
            return

        for device in device_data.get("results", []):
            model_key = device.get("modelKey")
            if model_key in IGNORED_MODELS:
                continue

            device_id = device["id"]
            serial = device.get("serialNumber", str(device_id))

            try:
                async with async_timeout.timeout(15):
                    async with session.get(f"{API_BASE}/devices/{device_id}/chart") as resp:
                        if resp.status != 200:
                            _LOGGER.warning("Chart request failed for %s: HTTP %s", device_id, resp.status)
                            continue
                        try:
                            chart_data = await resp.json()
                        except Exception as e:
                            _LOGGER.error("Failed to parse JSON for device %s: %s", device_id, e)
                            continue
            except Exception as e:
                _LOGGER.warning("Failed to load chart for device %s: %s", device_id, e)
                continue

            if isinstance(chart_data, dict):
                new_chart_data = []
                for key, readings_list in chart_data.items():
                    sensor_type = key.split(":")[0].lower()
                    if sensor_type in IGNORED_SENSOR_TYPES:
                        continue
                    if not isinstance(readings_list, list):
                        _LOGGER.error("Readings for key %s are not a list", key)
                        continue
                    for reading in readings_list:
                        new_chart_data.append({
                            "timestamp": reading.get("x"),
                            "value": reading.get("y"),
                            "sensor_type": sensor_type,
                        })
                chart_data = new_chart_data
            elif not isinstance(chart_data, list):
                _LOGGER.error("Chart data for device %s is not a list or dict: %s", device_id, chart_data)
                continue

            readings_by_type = {}
            for reading in chart_data:
                stype = reading.get("sensor_type")
                if not stype or stype.lower() in IGNORED_SENSOR_TYPES:
                    continue
                if stype not in readings_by_type:
                    readings_by_type[stype] = []
                readings_by_type[stype].append(reading)

            for sensor_type, readings in readings_by_type.items():
                latest = max(readings, key=lambda x: x["timestamp"])
                entity = AroyaSensor(
                    serial_number=serial,
                    device_id=device_id,
                    sensor_type=sensor_type,
                    initial_value=latest["value"],
                    api_key=api_key,
                    seen_timestamps={r["timestamp"] for r in readings},
                )
                entities.append(entity)

    async_add_entities(entities, True)

class AroyaSensor(SensorEntity):
    def __init__(self, serial_number, device_id, sensor_type, initial_value, api_key, seen_timestamps):
        self._serial_number = serial_number
        self._device_id = device_id
        self._sensor_type = sensor_type
        self._state = initial_value
        self._api_key = api_key
        self._seen_timestamps = seen_timestamps

        self._attr_name = f"{serial_number} {sensor_type.capitalize()}"
        self._attr_unique_id = f"aroya_{device_id}_{sensor_type}"

    @property
    def name(self):
        return self._attr_name

    @property
    def state(self):
        return self._state

    @property
    def unique_id(self):
        return self._attr_unique_id

    @property
    def icon(self):
        icons = {
            "temperature": "mdi:thermometer",
            "humidity": "mdi:water-percent",
            "co2": "mdi:molecule-co2",
            "ppfd": "mdi:weather-sunny-alert",
            "abs_hum": "mdi:water",
        }
        return icons.get(self._sensor_type.lower(), "mdi:leaf-circle")

    async def async_update(self):
        headers = {"Authorization": f"Bearer {self._api_key}"}
        url = f"{API_BASE}/devices/{self._device_id}/chart"

        async with aiohttp.ClientSession(headers=headers) as session:
            try:
                async with async_timeout.timeout(15):
                    async with session.get(url) as resp:
                        if resp.status != 200:
                            _LOGGER.warning("Chart update failed for %s: HTTP %s", self.name, resp.status)
                            return
                        try:
                            data = await resp.json()
                        except Exception as e:
                            _LOGGER.error("Failed to parse update JSON for %s: %s", self.name, e)
                            return
            except Exception as e:
                _LOGGER.warning("Failed to update %s: %s", self.name, e)
                return

            if isinstance(data, dict):
                new_data = []
                for key, readings_list in data.items():
                    sensor_type = key.split(":")[0].lower()
                    if sensor_type != self._sensor_type or sensor_type in IGNORED_SENSOR_TYPES:
                        continue
                    if not isinstance(readings_list, list):
                        _LOGGER.error("Readings for key %s are not a list", key)
                        continue
                    for reading in readings_list:
                        new_data.append({
                            "timestamp": reading.get("x"),
                            "value": reading.get("y"),
                            "sensor_type": sensor_type,
                        })
                data = new_data
            elif not isinstance(data, list):
                _LOGGER.error("Update data for %s is not a list or dict: %s", self.name, data)
                return

            new_readings = [
                r for r in data
                if r.get("sensor_type") == self._sensor_type and r.get("timestamp") not in self._seen_timestamps
            ]

            if new_readings:
                latest = max(new_readings, key=lambda x: x["timestamp"])
                self._state = latest["value"]
                self._seen_timestamps.update(r["timestamp"] for r in new_readings)
