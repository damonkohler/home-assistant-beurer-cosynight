# Beurer CosyNight

Home Assistant custom integration for controlling [Beurer CosyNight](https://www.beurer.com/) heated mattress pads via the Beurer cloud API.

## Installation

### HACS (recommended)

1. Open HACS in Home Assistant
2. Go to **Integrations** > **Custom repositories**
3. Add this repository URL: `https://github.com/damonkohler/home-assistant-beurer-cosynight`
4. Select **Integration** as the category
5. Install **Beurer CosyNight** and restart Home Assistant

### Manual

1. Copy the `custom_components/beurer_cosynight` folder into your `config/custom_components/` directory
2. Restart Home Assistant

## Configuration

This integration is configured through the Home Assistant UI:

1. Go to **Settings** > **Devices & services** > **Add integration**
2. Search for **Beurer CosyNight**
3. Enter your Beurer account email and password

### Re-authentication

If your Beurer account credentials change or expire, the integration will detect the authentication failure and prompt you to re-authenticate:

1. A "Re-authenticate" notification will appear in **Settings** > **Devices & services** for the Beurer CosyNight integration
2. Click **Re-authenticate** and enter your updated email and password
3. The integration will validate the new credentials and resume normal operation

If the new credentials belong to a different account than the original setup, the re-authentication will be aborted to prevent accidental account switching.

## Entities

Each connected mattress pad creates the following entities:

| Entity | Type | Description |
|--------|------|-------------|
| **Body Zone** | Select (0–9) | Heating level for the body zone. `0` is off. |
| **Feet Zone** | Select (0–9) | Heating level for the feet zone. `0` is off. |
| **Timer** | Number (1–240 min) | Session duration in minutes. Defaults to 60. Input via numeric box. |
| **Remaining Time** | Sensor (seconds) | Time remaining in the current heating session. |
| **Stop** | Button | Immediately stops the active heating session. |

Changing a zone level or timer starts (or updates) a heating session on the device. The **Stop** button sets both zones to 0 and ends the session.

## Services

### `beurer_cosynight.quickstart`

Start heating with explicit body and feet zone levels in a single API call. This is the preferred method for automations that need to set both zones simultaneously, as it avoids race conditions from concurrent zone updates.

| Parameter | Required | Description |
|-----------|----------|-------------|
| `device_id` | Yes | The HA device ID of the Beurer CosyNight device. |
| `body` | Yes | Heating level for the body zone (0-9). |
| `feet` | Yes | Heating level for the feet zone (0-9). |
| `timer` | No | Session duration in minutes (1-240). Defaults to 60. |

**Example automation:**

```yaml
- action: beurer_cosynight.quickstart
  data:
    device_id: your_device_id_here
    body: 3
    feet: 3
    timer: 90
```

**Why use quickstart instead of zone selects?** When you call `select.select_option` on the body and feet zone entities sequentially, each call sends a separate API request to the Beurer cloud. The second request can race with the first, potentially overwriting the body setting back to its prior value. The quickstart service sets both zones in a single API request, eliminating this race condition. Both methods acquire the same per-device lock to prevent interleaving with other operations.

## License

[Apache 2.0](LICENSE)
