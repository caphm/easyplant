"""Easier Support for monitoring plants."""
from collections import deque
from datetime import datetime, timedelta
import logging
import csv
import os

import voluptuous as vol

from homeassistant.components import group
from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.components.recorder.util import execute, session_scope
from homeassistant.const import (
    ATTR_ENTITY_PICTURE,
    ATTR_STATE,
    ATTR_UNIT_OF_MEASUREMENT,
    CONF_MINIMUM,
    CONF_MAXIMUM,
    CONF_SENSORS,
    EVENT_STATE_CHANGED,
    STATE_OK,
    STATE_PROBLEM,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
    TEMP_CELSIUS,
)
from homeassistant.core import callback
from homeassistant.exceptions import HomeAssistantError
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.entity_component import EntityComponent


_LOGGER = logging.getLogger(__name__)

DEFAULT_NAME = "easyplant"

PREFIX_MIN = "min_"
PREFIX_MAX = "max_"

CONF_DATABASE_FILE = "database"
CONF_IMAGE_DIR = "images"
CONF_DISABLE_REMOTE_IMAGES = "disable_remote_images"
CONF_PLANTS = "plants"
CONF_DISCOVERY_PREFIX = "discovery_prefix"
CONF_CHECK_DAYS = "check_days"

READING_LIGHT_MMOL = "light_mmol"
READING_LIGHT_LUX = "light_lux"
READING_TEMP = "temp"
READING_ENV_HUMID = "env_humid"
READING_SOIL_MOIST = "soil_moist"
READING_SOIL_EC = "soil_ec"
READING_BATTERY = "battery"

READINGS = {
    # READING_LIGHT_MMOL: "mmol",
    READING_LIGHT_LUX: "lux",
    READING_TEMP: TEMP_CELSIUS,
    READING_ENV_HUMID: "%",
    READING_SOIL_MOIST: "%",
    READING_SOIL_EC: "µS/cm",
    READING_BATTERY: "%",
}

ATTR_PID = "pid"
ATTR_DISPLAY_PID = "display_pid"
ATTR_ALIAS = "alias"
ATTR_IMAGE = "image"
ATTR_FLORAL_LANGUAGE = "floral_language"
ATTR_ORIGIN = "origin"
ATTR_PRODUCTION = "production"
ATTR_CATEGORY = "category"
ATTR_BLOOMING = "blooming"
ATTR_COLOR = "color"
ATTR_SIZE = "size"
ATTR_SOIL = "soil"
ATTR_SUNLIGHT = "sunlight"
ATTR_WATERING = "watering"
ATTR_FERTILIZATION = "fertilization"
ATTR_PRUNING = "pruning"

DATABASE_ATTRIBUTES = [
    ATTR_PID,
    ATTR_DISPLAY_PID,
    ATTR_ALIAS,
    ATTR_IMAGE,
    ATTR_FLORAL_LANGUAGE,
    ATTR_ORIGIN,
    ATTR_PRODUCTION,
    ATTR_CATEGORY,
    ATTR_BLOOMING,
    ATTR_COLOR,
    ATTR_SIZE,
    ATTR_SOIL,
    ATTR_SUNLIGHT,
    ATTR_WATERING,
    ATTR_FERTILIZATION,
    ATTR_PRUNING,
]

ATTR_MAX_LIGHT_MMOL = PREFIX_MAX + READING_LIGHT_MMOL
ATTR_MIN_LIGHT_MMOL = PREFIX_MIN + READING_LIGHT_MMOL
ATTR_MAX_LIGHT_LUX = PREFIX_MAX + READING_LIGHT_LUX
ATTR_MIN_LIGHT_LUX = PREFIX_MIN + READING_LIGHT_LUX
ATTR_MAX_TEMP = PREFIX_MAX + READING_TEMP
ATTR_MIN_TEMP = PREFIX_MIN + READING_TEMP
ATTR_MAX_ENV_HUMID = PREFIX_MAX + READING_ENV_HUMID
ATTR_MIN_ENV_HUMID = PREFIX_MIN + READING_ENV_HUMID
ATTR_MAX_SOIL_MOIST = PREFIX_MAX + READING_SOIL_MOIST
ATTR_MIN_SOIL_MOIST = PREFIX_MIN + READING_SOIL_MOIST
ATTR_MAX_SOIL_EC = PREFIX_MAX + READING_SOIL_EC
ATTR_MIN_SOIL_EC = PREFIX_MIN + READING_SOIL_EC
ATTR_MIN_BATTERY = PREFIX_MIN + READING_BATTERY

ATTR_PROBLEM = "problem"
ATTR_READINGS = "readings"
PROBLEM_NONE = "none"
ATTR_MAX_BRIGHTNESS_HISTORY = "max_brightness"

# we're not returning only one value, we're returning a dict here. So we need
# to have a separate literal for it to avoid confusion.
ATTR_DICT_OF_UNITS_OF_MEASUREMENT = "unit_of_measurement_dict"

DEFAULT_DISABLE_REMOTE_IMAGES = False
DEFAULT_MIN_BATTERY = 20
DEFAULT_CHECK_DAYS = 3

SCHEMA_SENSORS = vol.Schema(
    {
        vol.Optional(READING_LIGHT_LUX): cv.entity_id,
        vol.Optional(READING_TEMP): cv.entity_id,
        vol.Optional(READING_ENV_HUMID): cv.entity_id,
        vol.Optional(READING_SOIL_MOIST): cv.entity_id,
        vol.Optional(READING_SOIL_EC): cv.entity_id,
        vol.Optional(READING_BATTERY): cv.entity_id,
    }
)

PLANT_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_SENSORS): vol.Schema(SCHEMA_SENSORS),
        vol.Optional(ATTR_PID): cv.string,
        vol.Optional(CONF_DISCOVERY_PREFIX): cv.slug,
        vol.Optional(
            ATTR_MIN_BATTERY, default=DEFAULT_MIN_BATTERY
        ): cv.positive_int,
        vol.Optional(ATTR_MAX_LIGHT_MMOL): cv.positive_int,
        vol.Optional(ATTR_MIN_LIGHT_MMOL): cv.positive_int,
        vol.Optional(ATTR_MAX_LIGHT_LUX): cv.positive_int,
        vol.Optional(ATTR_MIN_LIGHT_LUX): cv.positive_int,
        vol.Optional(ATTR_MAX_TEMP): vol.Coerce(float),
        vol.Optional(ATTR_MIN_TEMP): vol.Coerce(float),
        vol.Optional(ATTR_MAX_ENV_HUMID): cv.positive_int,
        vol.Optional(ATTR_MIN_ENV_HUMID): cv.positive_int,
        vol.Optional(ATTR_MAX_SOIL_MOIST): cv.positive_int,
        vol.Optional(ATTR_MIN_SOIL_MOIST): cv.positive_int,
        vol.Optional(ATTR_MAX_SOIL_EC): cv.positive_int,
        vol.Optional(ATTR_MIN_SOIL_EC): cv.positive_int,
        vol.Optional(
            CONF_CHECK_DAYS, default=DEFAULT_CHECK_DAYS
        ): cv.positive_int,
    }
)

DOMAIN = "easyplant"

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: {
            vol.Optional(CONF_DATABASE_FILE): cv.isfile,
            vol.Optional(CONF_IMAGE_DIR): cv.string,
            vol.Optional(
                CONF_DISABLE_REMOTE_IMAGES,
                default=DEFAULT_DISABLE_REMOTE_IMAGES
            ): cv.boolean,
            vol.Optional(CONF_DISCOVERY_PREFIX): cv.slug,
            CONF_PLANTS: vol.Schema(
                {
                    cv.string: PLANT_SCHEMA
                })
        }
    }, extra=vol.ALLOW_EXTRA
)


# Flag for enabling/disabling the loading of the history from the database.
# This feature is turned off right now as its tests are not 100% stable.
ENABLE_LOAD_HISTORY = True


async def async_setup(hass, config):
    """Set up the Plant component."""
    component = EntityComponent(_LOGGER, DOMAIN, hass)
    plantdb = {}
    if config[DOMAIN].get(CONF_DATABASE_FILE):
        with open(config[DOMAIN][CONF_DATABASE_FILE], "r", encoding="utf-8") as csvfile:
            for row in csv.DictReader(csvfile, delimiter=","):
                plantdb[row[ATTR_PID]] = dict(row)

    entities = []
    for plant_name, user_config in config[DOMAIN][CONF_PLANTS].items():
        plant_config = plantdb.get(user_config.get(ATTR_PID), {})
        plant_config.update(user_config)
        plant_config.update(
            {
                CONF_DISABLE_REMOTE_IMAGES:
                    config[DOMAIN][CONF_DISABLE_REMOTE_IMAGES],
                CONF_IMAGE_DIR:
                    config[DOMAIN].get(CONF_IMAGE_DIR),
            }
        )
        if CONF_DISCOVERY_PREFIX not in plant_config:
            plant_config[CONF_DISCOVERY_PREFIX] = (
                config[DOMAIN].get(CONF_DISCOVERY_PREFIX)
            )
        entity = Plant(
            hass,
            plant_name,
            plant_config
        )
        entities.append(entity)
        _LOGGER.info("Added plant %s", plant_name)
        _LOGGER.debug(entity._sensors)
    del plantdb

    await component.async_add_entities(entities)
    return True


class Plant(Entity):
    """Plant monitors the well-being of a plant.

    It also checks the measurements against
    configurable min and max values.
    """

    def __init__(self, hass, name, config):
        """Initialize the Plant component."""
        self._config = config
        self._sensors = dict()
        self._readings = dict()
        self._unit_of_measurement = dict()
        self._state = None
        self._name = name
        self._problems = PROBLEM_NONE
        self._sensor_basename = "{}.{}{}_".format(
            SENSOR_DOMAIN,
            (self._config[CONF_DISCOVERY_PREFIX] + "_"
             if self._config[CONF_DISCOVERY_PREFIX]
             else ""),
            cv.slugify(self._name).lower())
        _LOGGER.debug(
            "Sensors starting with %s will be added to %s",
            self._sensor_basename,
            self._name
        )
        for reading, entity_id in self._config.get("sensors", {}).items():
            _LOGGER.debug(
                "Adding statically defined sensor %s for reading %s on %s",
                entity_id,
                reading,
                self._name
            )
            self._sensors[entity_id] = reading
            self._add_reading(reading, entity_id)

        self._conf_check_days = self._config[CONF_CHECK_DAYS]
        self._brightness_history = DailyHistory(self._conf_check_days)

    def _add_reading(self, reading, entity_id):
        self._readings[reading] = {
            CONF_SENSORS: [entity_id],
            ATTR_STATE: None,
            ATTR_UNIT_OF_MEASUREMENT: READINGS[reading],
            CONF_MINIMUM: self._config.get(PREFIX_MIN + reading),
            CONF_MAXIMUM: self._config.get(PREFIX_MAX + reading),
        }

    def _associate_sensor(self, entity_id):
        _LOGGER.debug(
            "Trying to associate %s to %s",
            entity_id,
            self._name
        )
        for reading in READINGS:
            if reading in entity_id:
                _LOGGER.info(
                    "Associated %s for '%s' reading on %s",
                    entity_id,
                    reading,
                    self._name)
                self._sensors[entity_id] = reading
                if reading in self._readings:
                    self._readings[reading][CONF_SENSORS].append(entity_id)
                else:
                    self._add_reading(reading, entity_id)
                return reading

        raise HomeAssistantError(
            "Cannot extract reading from sensor {}".format(entity_id)
        )

    @callback
    def state_changed(self, entity_id, _, new_state):
        """Update the sensor status.

        This callback is triggered, when the sensor state changes.
        """
        state = new_state.state
        _LOGGER.debug(
            "Received callback from %s with value %s",
            entity_id,
            state)

        reading = self._sensors.get(entity_id) or self._associate_sensor(entity_id)

        if (state == STATE_UNKNOWN
            or (state == STATE_UNAVAILABLE
                and any(
                    not self.hass.states.is_state(sensor, STATE_UNAVAILABLE)
                    for sensor in self._readings[reading]))):
            _LOGGER.debug(
                "Ignoring status '%s' for %s",
                state,
                entity_id)
            return

        state = float(state)
        if reading not in [READING_TEMP, READING_ENV_HUMID]:
            state = int(state)
        self._readings[reading][ATTR_STATE] = state
        if reading == READING_LIGHT_LUX:
            self._brightness_history.add_measurement(
                self._readings[reading][ATTR_STATE], new_state.last_updated
            )
        if ATTR_UNIT_OF_MEASUREMENT in new_state.attributes:
            self._readings[reading][ATTR_UNIT_OF_MEASUREMENT] = (
                new_state.attributes[ATTR_UNIT_OF_MEASUREMENT]
            )

        self._update_state()

    def _update_state(self):
        """Update the state of the class based sensor data."""
        problems = list(
            filter(
                None.__ne__,
                [self._check_reading(reading) for reading in self._readings]
            )
        )

        if problems:
            self._state = (
                STATE_UNAVAILABLE
                if all(STATE_UNAVAILABLE in p for p in problems)
                else STATE_PROBLEM
            )
            self._problems = ", ".join(problems)
        else:
            self._state = STATE_OK
            self._problems = PROBLEM_NONE
        _LOGGER.debug(
            "New data processed for %s",
            self._name
        )
        self.async_schedule_update_ha_state()

    def _check_reading(self, reading):
        state = self._readings[reading][ATTR_STATE]
        if state == STATE_UNAVAILABLE:
            return "{} {}".format(reading, STATE_UNAVAILABLE)
        elif state is not None:
            return self._check_min(reading, state) or self._check_max(reading, state)
        else:
            return None

    def _check_min(self, reading, state):
        """If configured, check the value against the defined minimum value."""
        min_value = self._readings[reading].get(CONF_MINIMUM)
        if reading == READING_LIGHT_LUX:
            state = self._brightness_history.max
        if min_value and state < float(min_value):
            return "{} low".format(reading)

    def _check_max(self, reading, state):
        """If configured, check the value against the defined maximum value."""
        max_value = self._readings[reading].get(CONF_MAXIMUM)
        if max_value and state > float(max_value):
            return "{} high".format(reading)

    async def async_added_to_hass(self):
        """After being added to hass, load from history."""
        @callback
        def state_change_listener(event):
            """Handle specific state changes."""
            entity_id = event.data.get("entity_id", "")
            if (entity_id not in self._sensors
                    and not entity_id.startswith(self._sensor_basename)):
                return

            old_state = event.data.get("old_state")
            if old_state is not None:
                old_state = old_state.state

            new_state = event.data.get("new_state")
            if new_state is not None:
                new_state = new_state.state

            self.hass.async_run_job(
                self.state_changed,
                event.data.get("entity_id"),
                event.data.get("old_state"),
                event.data.get("new_state"),
            )
        self.hass.bus.async_listen(EVENT_STATE_CHANGED, state_change_listener)

        # Update state from statically assigned sensors
        for entity_id in self._sensors:
            state = self.hass.states.get(entity_id)
            if state is not None:
                self.state_changed(entity_id, None, state)

        # Try to update state from dynamically discovered sensors
        for entity_id in self.hass.states.async_entity_ids(SENSOR_DOMAIN):
            if entity_id.startswith(self._sensor_basename):
                self.state_changed(
                    entity_id, None, self.hass.states.get(entity_id))

        if ENABLE_LOAD_HISTORY and "recorder" in self.hass.config.components:
            # only use the database if it's configured
            self.hass.async_add_job(self._load_history_from_db)

    async def _load_history_from_db(self):
        """Load the history of the brightness values from the database.

        This only needs to be done once during startup.
        """
        from homeassistant.components.recorder.models import States

        start_date = datetime.now() - timedelta(days=self._conf_check_days)
        for entity_id in self._readings.get(READING_LIGHT_LUX, []):
            _LOGGER.debug("Initializing values for %s from the database", self._name)
            with session_scope(hass=self.hass) as session:
                query = (
                    session.query(States)
                    .filter(
                        (States.entity_id == entity_id.lower())
                        and (States.last_updated > start_date)
                    )
                    .order_by(States.last_updated.asc())
                )
                states = execute(query)

                for state in states:
                    # filter out all None, NaN and "unknown" states
                    # only keep real values
                    try:
                        self._brightness_history.add_measurement(
                            int(state.state), state.last_updated
                        )
                    except ValueError:
                        pass
        _LOGGER.debug("Initializing from database completed")
        self.async_schedule_update_ha_state()

    @property
    def should_poll(self):
        """No polling needed."""
        return False

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def state(self):
        """Return the state of the entity."""
        return self._state

    @property
    def state_attributes(self):
        """Return the attributes of the entity.

        Provide the individual measurements from the
        sensor in the attributes of the device.
        """
        attrib = {
            ATTR_PROBLEM: self._problems,
            ATTR_READINGS: self._readings,
            ATTR_ENTITY_PICTURE: self._get_entity_picture(),
        }

        for reading in self._readings:
            attrib[reading] = self._readings[reading][ATTR_STATE]

        if self._brightness_history.max is not None:
            attrib[ATTR_MAX_BRIGHTNESS_HISTORY] = self._brightness_history.max

        attrib.update(
            {k: self._config[k] for k in DATABASE_ATTRIBUTES if k in self._config}
        )

        return attrib

    def _get_entity_picture(self):
        local_image = None
        local_path = self._config.get(CONF_IMAGE_DIR)
        pid = self._config.get("pid")
        remote_image = (
            None
            if self._config[CONF_DISABLE_REMOTE_IMAGES]
            else self._config.get(ATTR_IMAGE))
        if local_path and pid:
            local_image = os.path.join(
                self._config.get(CONF_IMAGE_DIR),
                pid + ".jpg")
        return local_image or remote_image


class DailyHistory:
    """Stores one measurement per day for a maximum number of days.

    At the moment only the maximum value per day is kept.
    """

    def __init__(self, max_length):
        """Create new DailyHistory with a maximum length of the history."""
        self.max_length = max_length
        self._days = None
        self._max_dict = dict()
        self.max = None

    def add_measurement(self, value, timestamp=None):
        """Add a new measurement for a certain day."""
        day = (timestamp or datetime.now()).date()
        if not isinstance(value, (int, float)):
            return
        if self._days is None:
            self._days = deque()
            self._add_day(day, value)
        else:
            current_day = self._days[-1]
            if day == current_day:
                self._max_dict[day] = max(value, self._max_dict[day])
            elif day > current_day:
                self._add_day(day, value)
            else:
                _LOGGER.warning("Received old measurement, not storing it")

        self.max = max(self._max_dict.values())

    def _add_day(self, day, value):
        """Add a new day to the history.

        Deletes the oldest day, if the queue becomes too long.
        """
        if len(self._days) == self.max_length:
            oldest = self._days.popleft()
            del self._max_dict[oldest]
        self._days.append(day)
        if not isinstance(value, (int, float)):
            return
        self._max_dict[day] = value
