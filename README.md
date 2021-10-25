# Kodak Smart Home
Provides a Kodak Smart Home platform for Home Assistant

[![License](https://img.shields.io/github/license/kairoaraujo/kodak-smart-home.svg?style=for-the-badge)](LICENSE)
[![hacs_badge](https://img.shields.io/badge/HACS-Custom-orange.svg?style=for-the-badge)](https://github.com/custom-components/hacs)

## Installation

---
**NOTE**

The camera is not live streaming. It is only a snapshot from the last motion detection recorded.
To make it work, enable in the camera the motion detection.

---

You can install this through [HACS](https://github.com/custom-components/hacs) by adding https://github.com/kairoaraujo/kodak-smart-home as a custom repository.

Using your HA configuration directory (folder) as a starting point you should now also have this:
```
custom_components/kodak_smart_home/__init__.py
custom_components/kodak_smart_home/manifest.json
custom_components/kodak_smart_home/camera.py
custom_components/kodak_smart_home/services.yaml
```




## Example configuration.yaml

Integration configuration
```yaml
kodak_smart_home:
  username: !secret kodak_portal_email
  password: !secret kodak_portal_password
  region: 'EU'
```

Camera configuration
```yaml
camera:
  - platform: kodak_smart_home

```
