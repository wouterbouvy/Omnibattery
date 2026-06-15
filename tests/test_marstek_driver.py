"""Unit tests for the Marstek Modbus driver (driver abstraction Phase 1).

The driver is exercised with an injected fake Modbus client, so no hardware and
no Home Assistant are needed. These pin the brand-specific logic that later
phases move out of the coordinator and control loop:

* capabilities derived from the firmware version,
* the logical-key -> register telemetry read,
* the signed-net-power -> force_mode + charge/discharge translation.
"""
from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from custom_components.marstek_venus_energy_manager.drivers import (
    DriverCapabilities,
    MarstekModbusDriver,
    SetpointResult,
)
from custom_components.marstek_venus_energy_manager.const import REGISTER_MAP


def _fake_client():
    client = AsyncMock()
    client.async_write_register = AsyncMock(return_value=True)
    client.async_read_register = AsyncMock(return_value=0)
    return client


def _driver(version="v3", definitions=None, client=None, **kw):
    return MarstekModbusDriver(
        "1.2.3.4", 502, version,
        definitions=definitions or [],
        client=client or _fake_client(),
        **kw,
    )


_DEFS = [
    {"key": "battery_soc", "register": 37005, "data_type": "uint16"},
    {"key": "battery_power", "register": 30001, "data_type": "int16", "count": 1},
    {"key": "no_register", "name": "calc-only"},  # no register -> not indexed
]


# ----------------------------------------------------------------------
# capabilities
# ----------------------------------------------------------------------
def test_v2_reports_hardware_soc_cutoff():
    assert _driver("v2").capabilities.hardware_soc_cutoff is True


@pytest.mark.parametrize("version", ["v3", "vA", "vD"])
def test_v3_family_has_no_hardware_cutoff(version):
    assert _driver(version).capabilities.hardware_soc_cutoff is False


def test_capabilities_carry_power_envelope_and_force_mode():
    caps = _driver("v3", max_charge_power_w=800, max_discharge_power_w=1200).capabilities
    assert isinstance(caps, DriverCapabilities)
    assert caps.max_charge_power_w == 800
    assert caps.max_discharge_power_w == 1200
    assert caps.has_force_mode is True
    assert caps.push_telemetry is False


# ----------------------------------------------------------------------
# read_telemetry
# ----------------------------------------------------------------------
async def test_read_telemetry_reads_requested_keys_unscaled():
    client = _fake_client()
    client.async_read_register = AsyncMock(side_effect=[47, -612])
    drv = _driver("v3", definitions=_DEFS, client=client)

    snap = await drv.read_telemetry(["battery_soc", "battery_power"])

    assert snap == {"battery_soc": 47, "battery_power": -612}
    # battery_power read uses the int16 type / count from the definition.
    call = client.async_read_register.call_args_list[1]
    assert call.kwargs["register"] == 30001
    assert call.kwargs["data_type"] == "int16"


async def test_read_telemetry_skips_unknown_and_failed_keys():
    client = _fake_client()
    # battery_soc returns a value; battery_power read fails (None).
    client.async_read_register = AsyncMock(side_effect=[47, None])
    drv = _driver("v3", definitions=_DEFS, client=client)

    snap = await drv.read_telemetry(["battery_soc", "battery_power", "not_a_key"])

    assert snap == {"battery_soc": 47}  # None dropped, unknown key skipped


async def test_read_telemetry_defaults_to_all_indexed_keys():
    drv = _driver("v3", definitions=_DEFS, client=_fake_client())
    snap = await drv.read_telemetry()
    assert set(snap) == {"battery_soc", "battery_power"}  # no_register excluded


# ----------------------------------------------------------------------
# apply_setpoint
# ----------------------------------------------------------------------
async def test_apply_setpoint_charge_sets_force_mode_1():
    client = _fake_client()
    drv = _driver("v3", client=client)

    res = await drv.apply_setpoint(600, read_back=False)

    assert res == SetpointResult(ok=True, net_power_w=600, confirmed=False)
    reg = REGISTER_MAP["v3"]
    writes = {c.args[0]: c.args[1] for c in client.async_write_register.call_args_list}
    assert writes[reg["set_charge_power"]] == 600
    assert writes[reg["set_discharge_power"]] == 0
    assert writes[reg["force_mode"]] == 1


async def test_apply_setpoint_discharge_sets_force_mode_2():
    client = _fake_client()
    drv = _driver("v3", client=client)

    res = await drv.apply_setpoint(-450, read_back=False)

    assert res.net_power_w == -450
    reg = REGISTER_MAP["v3"]
    writes = {c.args[0]: c.args[1] for c in client.async_write_register.call_args_list}
    assert writes[reg["set_discharge_power"]] == 450
    assert writes[reg["set_charge_power"]] == 0
    assert writes[reg["force_mode"]] == 2


async def test_apply_setpoint_zero_idles_force_mode_0():
    client = _fake_client()
    drv = _driver("v3", client=client)

    await drv.apply_setpoint(0, read_back=False)

    reg = REGISTER_MAP["v3"]
    writes = {c.args[0]: c.args[1] for c in client.async_write_register.call_args_list}
    assert writes[reg["force_mode"]] == 0
    assert writes[reg["set_charge_power"]] == 0
    assert writes[reg["set_discharge_power"]] == 0


async def test_apply_setpoint_clamps_to_envelope():
    drv = _driver("v3", max_charge_power_w=800, client=_fake_client())
    res = await drv.apply_setpoint(5000, read_back=False)
    assert res.net_power_w == 800


async def test_apply_setpoint_reports_write_failure():
    client = _fake_client()
    client.async_write_register = AsyncMock(return_value=False)
    drv = _driver("v3", client=client)

    res = await drv.apply_setpoint(600)

    assert res.ok is False
    assert res.failure_reason == "write_failed"


async def test_apply_setpoint_confirms_on_matching_readback():
    client = _fake_client()
    # readback order in driver: force, charge, discharge
    client.async_read_register = AsyncMock(side_effect=[1, 600, 0])
    drv = _driver("v3", client=client)

    res = await drv.apply_setpoint(600, read_back=True)

    assert res.ok is True and res.confirmed is True


async def test_apply_setpoint_unconfirmed_on_mismatched_readback():
    client = _fake_client()
    client.async_read_register = AsyncMock(side_effect=[1, 500, 0])  # charge != 600
    drv = _driver("v3", client=client)

    res = await drv.apply_setpoint(600, read_back=True)

    assert res.ok is True and res.confirmed is False
