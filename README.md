# 🌿 AroyaGo Integration for Home Assistant

Integrate your Aroya environmental sensors into Home Assistant!  
This custom integration automatically discovers all Aroya devices and creates sensors based on their telemetry.

![Aroya Logo](aroya_logo_merged_256x256.png)

---

## 🔧 Features

- Auto-discovers Aroya devices using your API key.
![Aroya Logo](screen-1.png)
- Creates individual sensors for:
  - Temperature (`air_temp`, `soil_temp`)
  ![Aroya Logo](screen-air-temp.png)
  ![Aroya Logo](screen-soil-temp.png)

  - Humidity (`rel_hum`)
  ![Aroya Logo](screen-rel-hum-temp.png)

  - CO2, EC, Soil Moisture, and more
  ![Aroya Logo](screen-co2.png)
  ![Aroya Logo](screen-pore-ec.png)
  ![Aroya Logo](screen-soil-moist.png)

- Ignores irrelevant sensor types like travel time or battery info.
- Converts Fahrenheit values to Celsius automatically.
- Beautiful icons to match each sensor type.

---

## 📦 Installation

### 1. Download

📥 [Download the latest ZIP here](#)  
(or clone this repository if you're using Git)

### 2. Extract and Place

Unzip or copy the folder:

```
custom_components/aroya/
```

...into your Home Assistant configuration folder, typically at:

```
/config/custom_components/aroya/
```

Make sure your file structure looks like this:

```
config/
└── custom_components/
    └── aroya/
        ├── __init__.py
        ├── sensor.py
        ├── config_flow.py
        ├── const.py
        ├── manifest.json
        ├── README.md
```

---

### 3. Restart Home Assistant

Head to **Developer Tools > YAML** and click **Restart**.

---

### 4. Add the Integration

- Go to **Settings > Devices & Services**
- Click **Add Integration**
- Search for **Aroya**
- Enter your Aroya API Key

That’s it! Your devices and sensors will be discovered and added automatically.

---

## 🧠 Notes

- Some device models like `"sink"` or `"gateway"` are ignored.
- Duplicate data is filtered automatically, even though Aroya’s `/chart` endpoint only returns the last 24 hours.
- The following sensor types are currently **excluded**:
  - `travel_time`, `link_quality`, `radio_power`, `signal`, `battery_v`

---

## 🧰 Advanced

If you want to customize icons or add new sensor mappings, you can edit the `icon()` method inside `sensor.py`.

---

## 👨‍💻 Maintainer

Created by [@JustGav](https://github.com/JustGav)  

For more information about the Aroya API:  
🔗 [https://www.cannabus.io/aroya](https://www.cannabus.io/aroya)
