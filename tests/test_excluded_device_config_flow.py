"""Excluded-device fields shared by the initial and options flows."""

from types import SimpleNamespace

from custom_components.omnibattery.config_flow import (
    MarstekVenusConfigFlow,
    OptionsFlowHandler,
)


def _schema_defaults(result) -> dict[str, object]:
    """Return the defaults keyed by field name for a flow form."""
    return {
        marker.schema: marker.default()
        for marker in result["data_schema"].schema
        if callable(marker.default)
    }


async def test_initial_flow_exposes_and_saves_excluded_device_controls():
    flow = MarstekVenusConfigFlow()

    form = await flow.async_step_add_excluded_device()
    defaults = _schema_defaults(form)

    assert defaults["dynamic_power_control"] is False
    assert defaults["cover_home_when_active"] is False

    await flow.async_step_add_excluded_device(
        {
            "power_sensor": "sensor.wallbox_power",
            "dynamic_power_control": True,
            "cover_home_when_active": True,
        }
    )

    assert flow.excluded_devices[0]["dynamic_power_control"] is True
    assert flow.excluded_devices[0]["cover_home_when_active"] is True


async def test_options_flow_restores_and_saves_excluded_device_controls():
    entry = SimpleNamespace(
        entry_id="test-entry",
        data={
            "excluded_devices": [
                {
                    "power_sensor": "sensor.wallbox_power",
                    "dynamic_power_control": True,
                    "cover_home_when_active": True,
                }
            ]
        },
    )
    flow = OptionsFlowHandler(entry)
    flow._config_entry = entry

    form = await flow.async_step_add_excluded_device()
    defaults = _schema_defaults(form)

    assert defaults["dynamic_power_control"] is True
    assert defaults["cover_home_when_active"] is True

    await flow.async_step_add_excluded_device(
        {
            "power_sensor": "sensor.wallbox_power",
            "dynamic_power_control": True,
            "cover_home_when_active": True,
        }
    )

    assert flow.excluded_devices[0]["dynamic_power_control"] is True
    assert flow.excluded_devices[0]["cover_home_when_active"] is True
