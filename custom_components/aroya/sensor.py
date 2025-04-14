import logging
import aiohttp
import async_timeout

from homeassistant.components.sensor import SensorEntity
from homeassistant.const import CONF_API_KEY, PERCENTAGE
from homeassistant.components.sensor.const import UnitOfTemperature

from .const import DOMAIN, API_BASE

_LOGGER = logging.getLogger(__name__)

IGNORED_MODELS = {
    "gateway", 
    "sink"
}

IGNORED_SENSOR_TYPES = {
    "battery_v",
    "link_quality",
    "radio_power",
    "signal",
    "travel_time"
}

async def async_setup_entry(hass, entry, async_add_entities):
    api_key = entry.data[CONF_API_KEY]
    headers = {"Authorization": f"Bearer {api_key}"}
    entities = []

    async with aiohttp.ClientSession(headers=headers) as session:
        try:
            async with async_timeout.timeout(15):
                async with session.get(f"{API_BASE}/devices") as resp:
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
                        resp_json = await resp.json()
            except Exception as e:
                _LOGGER.warning("Failed to load chart for device %s: %s", device_id, e)
                continue

            chart_data = []

            if isinstance(resp_json, dict):
                for key, values in resp_json.items():
                    parts = key.split(":")
                    if not parts:
                        _LOGGER.warning("Could not parse sensor_type from key: %s", key)
                        continue

                    sensor_type = parts[0].lower()
                    if sensor_type in IGNORED_SENSOR_TYPES:
                        _LOGGER.debug("Ignoring sensor type: %s", sensor_type)
                        continue

                    for point in values:
                        chart_data.append({
                            "sensor_type": sensor_type,
                            "timestamp": point["x"],
                            "value": point["y"],
                        })
            elif isinstance(resp_json, list):
                chart_data = resp_json
            else:
                _LOGGER.error("Unexpected chart data format for device %s: %s", device_id, resp_json)
                continue

            readings_by_type = {}
            for reading in chart_data:
                stype = reading["sensor_type"]
                if stype not in readings_by_type:
                    readings_by_type[stype] = []
                readings_by_type[stype].append(reading)

            for sensor_type, readings in readings_by_type.items():
                latest = max(readings, key=lambda x: x["timestamp"])
                value = latest["value"]
                if sensor_type.lower() in ["temperature", "soil_temp", "air_temp"]:
                    value = (value - 32) * 5.0 / 9.0
                entity = AroyaSensor(
                    serial_number=serial,
                    device_id=device_id,
                    sensor_type=sensor_type,
                    initial_value=round(value, 2),
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
        self._attr_state_class = "measurement"

        sensor_type_lc = self._sensor_type.lower()
        if sensor_type_lc in ["temperature", "soil_temp", "air_temp"]:
            self._attr_unit_of_measurement = UnitOfTemperature.CELSIUS
            self._attr_device_class = "temperature"
        elif sensor_type_lc in ["humidity", "rel_hum", "soil_moist"]:
            self._attr_unit_of_measurement = PERCENTAGE
            self._attr_device_class = "humidity"
        elif sensor_type_lc == "abs_hum":
            self._attr_unit_of_measurement = "g/m³"
            self._attr_device_class = "humidity"
        elif sensor_type_lc == "co2":
            self._attr_unit_of_measurement = "ppm"
            self._attr_device_class = "carbon_dioxide"
        elif sensor_type_lc == "ppfd":
            self._attr_unit_of_measurement = "µmol/m²/s"
            self._attr_device_class = "illuminance"
        elif sensor_type_lc == "pore_ec":
            self._attr_unit_of_measurement = "mS/cm"
            self._attr_device_class = "voltage"

    @property
    def state(self):
        return self._state

    async def async_update(self):
        headers = {"Authorization": f"Bearer {self._api_key}"}
        url = f"{API_BASE}/devices/{self._device_id}/chart"

        async with aiohttp.ClientSession(headers=headers) as session:
            try:
                async with async_timeout.timeout(15):
                    async with session.get(url) as resp:
                        resp_json = await resp.json()
            except Exception as e:
                _LOGGER.warning("Failed to update %s: %s", self._attr_name, e)
                return

            if isinstance(resp_json, dict):
                data = []
                for key, values in resp_json.items():
                    parts = key.split(":")
                    if not parts:
                        continue
                    sensor_type = parts[0].lower()
                    if sensor_type != self._sensor_type:
                        continue
                    for point in values:
                        data.append({
                            "sensor_type": sensor_type,
                            "timestamp": point["x"],
                            "value": point["y"],
                        })
            elif isinstance(resp_json, list):
                data = [r for r in resp_json if r.get("sensor_type") == self._sensor_type]
            else:
                _LOGGER.warning("Unexpected update data format for %s: %s", self._attr_name, resp_json)
                return

            new_readings = [
                r for r in data
                if r["timestamp"] not in self._seen_timestamps
            ]

            if new_readings:
                latest = max(new_readings, key=lambda x: x["timestamp"])
                value = latest["value"]
                if self._sensor_type.lower() in ["temperature", "soil_temp", "air_temp"]:
                    value = (value - 32) * 5.0 / 9.0
                self._state = round(value, 2)
                self._seen_timestamps.update(r["timestamp"] for r in new_readings)
