"""Control cycles must launch as config-entry background tasks.

Timer/state-change trackers run their callbacks as HA-tracked tasks, and HA
startup waits for tracked tasks. A cycle stuck in Modbus retries against a slow
gateway blocked the whole bootstrap ("Something is blocking Home Assistant...")
and delayed every integration set up after this one. Background tasks are
exempt from the startup gate; entry unload still cancels them.

Exercised unbound with light stubs (same pattern as test_no_pd_tracking).
"""
from __future__ import annotations

from types import SimpleNamespace

from custom_components.omnibattery import ChargeDischargeController


def _stub_controller(calls):
    def _bg(hass, coro, name):
        calls.append((hass, coro, name))
        coro.close()  # never awaited in this test

    async def _cycle(now=None):
        pass

    return SimpleNamespace(
        hass=object(),
        config_entry=SimpleNamespace(async_create_background_task=_bg),
        async_update_charge_discharge=_cycle,
        _run_no_pd_debounced_cycle=_cycle,
        _no_pd_debounce_unsub=object(),
    )


def test_schedule_control_cycle_launches_background_task():
    calls = []
    ctl = _stub_controller(calls)
    ChargeDischargeController.schedule_control_cycle(ctl, now=None)
    assert len(calls) == 1
    hass, _coro, name = calls[0]
    assert hass is ctl.hass
    assert name == "omnibattery_control_cycle"


def test_no_pd_debounce_fire_launches_background_task():
    calls = []
    ctl = _stub_controller(calls)
    ChargeDischargeController._fire_no_pd_debounced_run(ctl, None)
    assert ctl._no_pd_debounce_unsub is None
    assert len(calls) == 1
    assert calls[0][2] == "omnibattery_no_pd_cycle"
