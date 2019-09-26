[EasyPlant Custom Component](https://github.com/caphm/easyplant) for homeassistant

# What This Is:
This is a custom component to allow for an easier integration and setup of plant monitoring in [Homeassistant](https://home-assistant.io). It is originally based on the built-in [Plant Monitor](https://www.home-assistant.io/components/plant/) component but has been heavily modified to add features and simplify setup.

# What It Does:
This custom component basically does the same job as the built-in plant component, but provides the following additional features:

* Easier setup (convention over configuration - see below)
* Automatic discovery of new sensors for plants
* Pull information from a plant database (e.g. [MiFlora DB](https://github.com/khronimo/MiFloraDB))
* Redundant sensor support - use multiple sensors for a single reading, so you can for example setup multiple ESPHome nodes with identical MiFlora configs and move plants within the house without changing Home Assistant config
* Add support for more sensors on a plant (environment humidity, more to come)

# Installation
Install via [HACS](https://github.com/custom-components/hacs).

In order to find EasyPlant, you first need to add the repository:
1. Open HACS
2. Go to Settings
3. Enter `https://github.com/caphm/easyplant`in **ADD CUSTOM REPOSITORY**. Select type `integration`.

# Configuration
## Quick Start
Best thing to get started is with a full example. I have the following in my `configuration.yaml`:
```
easyplant:
  database: /config/PlantDB_5335_U0.csv
  images: /local/flower-images
  disable_remote_images: true
  discovery_prefix: plant
  plants:
    curcuma:
      pid: curcuma 'alismatifolia'
      min_light_lux: 0
      sensors:
        env_humid: sensor.master_bedroom_humidity
    howea:
      pid: howea forsteriana
      min_light_lux: 0
      sensors:
        env_humid: sensor.living_room_humidity
    monstera:
      pid: monstera deliciosa
      min_light_lux: 0
      sensors:
        env_humid: sensor.master_bedroom_humidity
    zantedeschia:
      pid: zantedeschia aethiopica (l.)spreng.
      min_light_lux: 0
      sensors:
        env_humid: sensor.living_room_humidity

```
My plant database is in my Home Assistant config folder and the flower images in a subfolder `flower-images` under my `www` folder.
The setup above
- creates 4 plants
- pulls the info for them from the database file
- uses locally hosted images
- overrides the minimum value for light intensity / brightness to 0 (because I don't want problems being reported when it's too dark
- assigns a static sensor for environment humidity to each plant, because I only have one humidty sensor per room and not per plant

## Basic configuration for autodiscovery

```
easyplant:
  discovery_prefix: plant
  plants:
    monstera_deliciosa:
```

If you have the following sensors available in Home Assistant
* `sensor.plant_monstera_deliciosa_soil_moist_1`
* `sensor.plant_monstera_deliciosa_soil_moist_2`
* `sensor.plant_monstera_deliciosa_soil_ec_1`
* `sensor.plant_monstera_deliciosa_soil_ec_2`
the component will create a plant called `Monstera Deliciosa` and monitor its soil moisture and soil conductivity from two redundant sources each. The soure sensors for each reading can come for example from two separate ESPHome nodes using the MiFlora sensor. This way, once on of the nodes is out of bluetooth range, the component will ignore the `unavailable` status of that sensor and use the reading from the other one.
If you then later make another sensor `sensor.plant_monstera_deliciosa_temp` available in Home Assistant, this will automatically be added to your `Monstera Deliciosa` plant and the component wll monitor its temperature. But since it is not setup redundantly (only one sensor for the temperature reading), it might show unavailable when out of range.

## YAML configuration
The same setup as above (with some extensions) can be statically configured in `configuration.yaml` like this:
```
easyplant:
  discovery_prefix: plant
  plants:
    monstera_deliciosa:
      min_soil_moist: 20
      max_soil_moist: 60
      sensors:
        temp: sensor.plant_monstera_deliciosa_temp
        soil_moist: sensor.plant_monstera_deliciosa_soil_moist_1
        soil_ec: sensor.plant_monstera_deliciosa_soil_ec_1
        env_humid: sensor.living_room_humidity
```
Because the sensor names adhere to the naming pattern and the proper discovery prefix is set, additional sensors will dynamicaly be discovered and added to the plant. You can also specify sensor names that do not conform the naming pattern. This is useful for example in the case of environment humidity (`env_humid`), where you usually don't have a dedicated humidity sensor for each plant, but rather one for an entire room.
The example above also adds a minimum and maximum value for soil moisture to be monitored.

## Using a plant database
The following configuration is the same as above, but will pull data like minimum and maximum values for soil moisture, temperature etc. and much more data from a plant database.
You just need to specifiy where your database is located using `database` and provide the attribute `pid` to the plant. The `pid` must be the value from the first column in your database.
```
easyplant:
  database: /config/PlantDB_5335_U0.csv
  images: /local/flower-images
  disable_remote_images: true
  discovery_prefix: plant
  plants:
    monstera_deliciosa:
      pid: monstera deliciosa
      min_temp: 0
      sensors:
        temp: sensor.plant_monstera_deliciosa_temp
        soil_moist: sensor.plant_monstera_deliciosa_soil_moist_1
        soil_ec: sensor.plant_monstera_deliciosa_soil_ec_1
        env_humid: sensor.living_room_humidity
```
You can override the minimum or maximum values from the database by specifying them yourself, as done above with `min_temp: 0`.
In this example, we have also set up the use of local images. If you have a local collection of all the plant images (named by their `pid` with extension `jpg`), you can point the component to this directory using `images` and set `disable_remote_images` to `true` to make it images served from you local machine. If you omit these two options, the component will use images pulled from the remote location given in the plant database.

## Configuration Options
### Global configuration options
| Option                  | Required? | Default | Description                                                                             |
|-------------------------|-----------|---------|-----------------------------------------------------------------------------------------|
| `database`              | optional  |         | Path to your plant database file                                                        |
| `images`                | optional  |         | Path to your local plant images folder (under `www`starting with `/local/`              |
| `disable_remote_images` | optional  | False   | Do not use plant images from remote locations (as given in plant database)              |
| `discovery_prefix`      | optional  |         | Prefix to use for autodiscovery of sensors. If not sepcified, autodiscovery won't work. |
| `plants`                | required  |         | Dictionary of the plants to be setup. See plant configuration options.                  |

### Plant configuration options
| Option | Required? | Default | Description |
|--------------------|-----------|---------|-------------------------------------------------------------------------|
| `pid` | optional |  | `pid` to associate with data from the plant database |
| `discovery_prefix` | optional |  | Override the global discovery prefix only for this plant |
| `min_battery` | optional | 20 | Minimum battery level reading |
| `max_light_mmol` | optional |  | Maximum light energy in MMOL reading (overrides database info if given) |
| `min_light_mmol` | optional |  | Minimum light energy in MMOL reading (overrides database info if given) |
| `max_light_lux` | optional |  | Maximum light intensity / brightness reading (overrides database info if given) |
| `min_light_lux` | optional |  | Minimum light intensity / brightness reading (overrides database info if given) |
| `max_temp` | optional |  | Maximum temperature reading (overrides database info if given) |
| `min_temp` | optional |  | Minimum temperature reading (overrides database info if given) |
| `max_env_humid` | optional |  | Maximum environment humidity reading (overrides database info if given) |
| `min_env_humid` | optional |  | Minimum environment humidity reading (overrides database info if given) |
| `max_soil_moist` | optional |  | Maximum soil moisture reading (overrides database info if given) |
| `min_soil_moist` | optional |  | Minimum soil moisture reading (overrides database info if given) |
| `max_soil_ec` | optional |  | Maximum soil conductivity reading (overrides database info if given) |
| `min_soil_ec` | optional |  | Minimum soil conductivity reading (overrides database info if given) |
| `check_days` | optional | 3 | Number of days in the past to consider for restoring max brightness value after reboot |
| `sensors` | optional |  | Statically defined sensors for the readings of this plant. See sensor configuration options. |

### Sensor configuration options
| Option | Required? | Default | Description |
|--------------|-----------|---------|------------------------------------------------------------------------|
| `battery` | optional |  | Entity ID o the sensor to use for battery level reading |
| `light_lux` | optional |  | Entity ID o the sensor to use for light intensity / brightness reading |
| `temp` | optional |  | Entity ID o the sensor to use for temperature reading |
| `env_humid` | optional |  | Entity ID o the sensor to use for environment humidity reading |
| `soil_moist` | optional |  | Entity ID o the sensor to use for soil moisture reading |
| `soil_ec` | optional |  | Entity ID o the sensor to use for soil conductivity reading |
