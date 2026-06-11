"""Characterization tests for the PD load-sharing cluster.

These pin the *current* behavior of three methods on the controller so the
upcoming power_distribution.py extraction can be proven to change nothing:
    _distribute_power_by_limits   (proportional allocation)
    _select_batteries_for_operation (min-battery selection + hysteresis + holds)
    _rebalance_expired_load_sharing_hold (deadband hold release)

No hardware, no real Home Assistant. The controller is built with
``ChargeDischargeController.__new__`` and only the attributes/collaborators the
three methods touch are set. The per-battery limit primitive
``_battery_power_limit`` stays on the controller (it is NOT part of this
extraction); it is exercised for real here but configured to resolve to an
identity on each coordinator's ``max_charge_power`` / ``max_discharge_power``
(no active slot, taper not applicable because ``max_soc`` < 100).

When the cluster moves to power_distribution.py, only ``_build`` is retargeted
to construct ``PowerDistribution`` with a stub controller; the assertions below
stay identical, which is the cero-cambio-funcional proof.
"""
from __future__ import annotations

import time

from custom_components.marstek_venus_energy_manager import ChargeDischargeController


# ----------------------------------------------------------------------
# Test doubles
# ----------------------------------------------------------------------

class _Coord:
    """A coordinator stand-in. Identity-hashable (used as dict keys), unlike
    SimpleNamespace which defines __eq__ and is therefore unhashable.
    max_soc<100 keeps the charge limit at identity (taper not applicable)."""

    def __init__(self, name, limit, soc, charge_energy, discharge_energy):
        self.name = name
        self.max_charge_power = limit
        self.max_discharge_power = limit
        self.max_soc = 80
        self.data = {
            "battery_soc": soc,
            "total_charging_energy": charge_energy,
            "total_discharging_energy": discharge_energy,
        }


def _coord(name, limit, *, soc=50, charge_energy=0.0, discharge_energy=0.0):
    return _Coord(name, limit, soc, charge_energy, discharge_energy)


def _build(coords, *, active_charge=None, active_discharge=None,
           charge_holds=None, discharge_holds=None, previous_power=0,
           available=None, set_calls=None):
    """Build a controller with only the attrs/collaborators the cluster reads."""
    c = ChargeDischargeController.__new__(ChargeDischargeController)
    c.enable_system_power_limits = False
    c.coordinators = list(coords)
    c.previous_power = previous_power
    c._active_charge_batteries = list(active_charge or [])
    c._active_discharge_batteries = list(active_discharge or [])
    c._charge_selection_hold_until = dict(charge_holds or {})
    c._discharge_selection_hold_until = dict(discharge_holds or {})

    # Collaborators that stay on the controller (excluded from this extraction),
    # stubbed so _battery_power_limit resolves to an identity on the coordinator
    # power attrs and the I/O paths are observable.
    c._get_active_slot = lambda coordinator, kind: None
    c._is_active_balance_mode_running = lambda coordinator: False
    c._get_available_batteries = lambda is_charging, *a, **k: list(
        available if available is not None else coords
    )
    c._log_power_command_plan = lambda **k: None
    if set_calls is not None:
        async def _set(coordinator, charge, discharge):
            set_calls.append((coordinator.name, charge, discharge))
        c._set_battery_power = _set
    return c


# ----------------------------------------------------------------------
# _distribute_power_by_limits
# ----------------------------------------------------------------------

def test_distribute_no_batteries_is_empty():
    c = _build([])
    assert c._distribute_power_by_limits(1000, [], is_charging=False) == {}


def test_distribute_two_equal_even_split():
    a, b = _coord("a", 1000), _coord("b", 1000)
    c = _build([a, b])
    assert c._distribute_power_by_limits(1000, [a, b], is_charging=False) == {a: 500, b: 500}


def test_distribute_request_over_capacity_clamps_to_limits():
    a, b = _coord("a", 1000), _coord("b", 1000)
    c = _build([a, b])
    # 5000 W requested, 2000 W available -> each pinned to its 1000 W limit.
    assert c._distribute_power_by_limits(5000, [a, b], is_charging=False) == {a: 1000, b: 1000}


def test_distribute_uneven_limits_at_full_capacity():
    a, b = _coord("a", 1500), _coord("b", 500)
    c = _build([a, b])
    assert c._distribute_power_by_limits(2000, [a, b], is_charging=False) == {a: 1500, b: 500}


def test_distribute_uneven_limits_proportional_share():
    a, b = _coord("a", 1500), _coord("b", 500)
    c = _build([a, b])
    # 1000 W < 2000 W capacity -> proportional: 75% / 25%.
    assert c._distribute_power_by_limits(1000, [a, b], is_charging=False) == {a: 750, b: 250}


def test_distribute_single_battery_partial():
    a = _coord("a", 1000)
    c = _build([a])
    assert c._distribute_power_by_limits(600, [a], is_charging=False) == {a: 600}


def test_distribute_zero_capacity_returns_zeros():
    a = _coord("a", 0)
    c = _build([a])
    assert c._distribute_power_by_limits(500, [a], is_charging=False) == {a: 0}


def test_distribute_rounds_to_5w():
    a, b = _coord("a", 1000), _coord("b", 1000)
    c = _build([a, b])
    # 996/2 = 498 -> rounds to nearest 5 W = 500.
    assert c._distribute_power_by_limits(996, [a, b], is_charging=False) == {a: 500, b: 500}


def test_distribute_charge_path_is_identity_on_limit():
    a, b = _coord("a", 1000), _coord("b", 1000)
    c = _build([a, b])
    assert c._distribute_power_by_limits(1000, [a, b], is_charging=True) == {a: 500, b: 500}


# ----------------------------------------------------------------------
# _select_batteries_for_operation
# ----------------------------------------------------------------------

def test_select_zero_power_clears_state():
    a = _coord("a", 2500)
    c = _build([a], active_discharge=[a], discharge_holds={a: time.monotonic() + 100})
    assert c._select_batteries_for_operation(0, [a], is_charging=False) == []
    assert c._active_discharge_batteries == []
    assert c._active_charge_batteries == []
    assert c._discharge_selection_hold_until == {}


def test_select_single_battery_charge_sets_active():
    a = _coord("a", 2500)
    c = _build([a])
    assert c._select_batteries_for_operation(500, [a], is_charging=True) == [a]
    assert c._active_charge_batteries == [a]
    assert c._active_discharge_batteries == []


def test_select_discharge_low_power_picks_one_highest_soc():
    a, b = _coord("a", 2500, soc=90), _coord("b", 2500, soc=50)
    c = _build([a, b])
    # 1000 W <= 2500*0.6 activation -> single battery, highest SOC drained first.
    assert c._select_batteries_for_operation(1000, [a, b], is_charging=False) == [a]
    assert c._active_discharge_batteries == [a]


def test_select_discharge_high_power_picks_two_and_refreshes_holds():
    a, b = _coord("a", 2500, soc=90), _coord("b", 2500, soc=50)
    c = _build([a, b])
    selected = c._select_batteries_for_operation(4000, [a, b], is_charging=False)
    assert set(selected) == {a, b}
    assert set(c._active_discharge_batteries) == {a, b}
    # Split-load holds refreshed into the future for both batteries.
    now = time.monotonic()
    assert set(c._discharge_selection_hold_until) == {a, b}
    assert all(t > now for t in c._discharge_selection_hold_until.values())


def test_select_charge_picks_lowest_soc_first():
    a, b = _coord("a", 2500, soc=20), _coord("b", 2500, soc=80)
    c = _build([a, b])
    assert c._select_batteries_for_operation(1000, [a, b], is_charging=True) == [a]
    assert c._active_charge_batteries == [a]


def test_select_deactivation_hysteresis_retains_active_battery():
    a, b = _coord("a", 2500, soc=90), _coord("b", 2500, soc=50)
    c = _build([a, b], active_discharge=[a, b])
    # 1400 W is below activation (1500) but above deactivation (1250) -> b retained.
    assert set(c._select_batteries_for_operation(1400, [a, b], is_charging=False)) == {a, b}


def test_select_below_deactivation_drops_active_battery():
    a, b = _coord("a", 2500, soc=90), _coord("b", 2500, soc=50)
    c = _build([a, b], active_discharge=[a, b])
    # 1000 W is below deactivation (1250) and b is not held -> dropped.
    assert c._select_batteries_for_operation(1000, [a, b], is_charging=False) == [a]
    assert c._active_discharge_batteries == [a]


def test_select_wallclock_hold_retains_dropped_battery():
    a, b = _coord("a", 2500, soc=90), _coord("b", 2500, soc=50)
    c = _build([a, b], active_discharge=[a, b],
               discharge_holds={b: time.monotonic() + 100})
    # Power would drop b, but its wall-clock hold has not expired -> retained.
    assert set(c._select_batteries_for_operation(500, [a, b], is_charging=False)) == {a, b}


# ----------------------------------------------------------------------
# _rebalance_expired_load_sharing_hold  (async)
# ----------------------------------------------------------------------

async def test_rebalance_noop_when_idle():
    a, b = _coord("a", 2500), _coord("b", 2500)
    calls = []
    c = _build([a, b], previous_power=0, set_calls=calls)
    assert await c._rebalance_expired_load_sharing_hold(grid_w=0, target_w=0) is False
    assert calls == []


async def test_rebalance_noop_with_single_active_battery():
    a, b = _coord("a", 2500), _coord("b", 2500)
    calls = []
    c = _build([a, b], previous_power=-1000, active_discharge=[a], set_calls=calls)
    assert await c._rebalance_expired_load_sharing_hold(grid_w=0, target_w=0) is False
    assert calls == []


async def test_rebalance_noop_while_holds_unexpired():
    a, b = _coord("a", 2500, soc=90), _coord("b", 2500, soc=50)
    calls = []
    c = _build([a, b], previous_power=-1000, active_discharge=[a, b],
               discharge_holds={a: time.monotonic() + 100, b: time.monotonic() + 100},
               set_calls=calls)
    assert await c._rebalance_expired_load_sharing_hold(grid_w=0, target_w=0) is False
    assert calls == []


async def test_rebalance_releases_expired_hold_and_rewrites():
    a, b = _coord("a", 2500, soc=90), _coord("b", 2500, soc=50)
    calls = []
    c = _build([a, b], previous_power=-500, active_discharge=[a, b],
               discharge_holds={a: time.monotonic() - 1, b: time.monotonic() - 1},
               set_calls=calls)
    # Holds expired and load now fits one battery -> reselect to [a], rewrite both.
    assert await c._rebalance_expired_load_sharing_hold(grid_w=-500, target_w=0) is True
    assert calls == [("a", 0, 500), ("b", 0, 0)]
