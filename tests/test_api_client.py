"""Tests for the Beurer CosyNight API client (sync test compat shims removed).

The original sync tests have been replaced by test_api_client_async.py.
This file now contains only the dataclass tests which are still relevant.
"""

from __future__ import annotations

import dataclasses

from custom_components.beurer_cosynight.beurer_cosynight import (
    Device,
    Quickstart,
    Status,
)


class TestDataclasses:
    """Test data classes."""

    def test_device_fields(self):
        """Device dataclass should hold all fields."""
        d = Device(active=True, id="d1", name="Pad", requiresUpdate=False)
        assert d.active is True
        assert d.id == "d1"
        assert d.name == "Pad"
        assert d.requiresUpdate is False

    def test_status_fields(self):
        """Status dataclass should hold all fields."""
        s = Status(
            active=True,
            bodySetting=3,
            feetSetting=5,
            heartbeat=100,
            id="d1",
            name="Pad",
            requiresUpdate=False,
            timer=1800,
        )
        assert s.timer == 1800
        assert s.bodySetting == 3

    def test_quickstart_fields(self):
        """Quickstart dataclass should hold all fields."""
        q = Quickstart(bodySetting=3, feetSetting=5, id="d1", timespan=3600)
        assert dataclasses.asdict(q) == {
            "bodySetting": 3,
            "feetSetting": 5,
            "id": "d1",
            "timespan": 3600,
        }
