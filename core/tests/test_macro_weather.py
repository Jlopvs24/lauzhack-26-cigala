"""Conditional macro weather; magnitudes are assumptions, never forecasts."""
import numpy as np
import pytest
import core
from core.weather import QUALITATIVE, build_weather, weather_catalog


def test_neutral_reproduces_default_and_macro_moves_deterministic_path():
    base = core.simulate(None, '1', exploration=False, sensitivity=False)
    neutral = core.simulate(None, '1', weather=[{'type': 'scenario', 'level': 'neutral'}], exploration=False, sensitivity=False)
    assert neutral['metrics'] == base['metrics']
    values = {}
    for level in ('pessimistic', 'optimistic'):
        r = core.simulate(None, '1', weather=[{'type': 'scenario', 'level': level}], exploration=False, sensitivity=False)
        assert all(c['passed'] for c in r['checks'])
        assert r['weather'][0]['verified'] is False
        values[level] = r['metrics']['final_net_worth']
    assert values['pessimistic'] < base['metrics']['final_net_worth'] < values['optimistic']


def test_factors_override_macro_channels_independent_of_order_and_clip_window():
    events = [{'type': 'scenario', 'level': 'pessimistic'}, {'type': 'inflation', 'level': 'low'}]
    a, b = build_weather(events, 12), build_weather(events[::-1], 12)
    np.testing.assert_array_equal(a.inflation_override, np.zeros(12))
    np.testing.assert_array_equal(a.inflation_override, b.inflation_override)
    np.testing.assert_array_equal(a.return_shift, b.return_shift)
    assert all(w['end_month'] == 12 for w in a.applied)
    for typ, levels in QUALITATIVE.items():
        for level in levels:
            w = build_weather([{'type': typ, 'level': level}], 6)
            assert w.applied[0]['sources'] and w.applied[0]['assumptions'] is not None


@pytest.mark.parametrize('event', [
    {'type': 'scenario', 'level': 'unknown'}, {'type': 'scenario', 'level': {}},
    {'type': 'fx', 'level': 'up'}, {'type': 'scenario'}, {'type': []},
    {'type': 'rates', 'level': 'up', 'cash_rate_shift': 99},
    {'type': 'jobs', 'level': 'weak', 'duration_months': 1.5},
    {'type': 'markets', 'level': 'crash', 'duration_months': 0},
])
def test_invalid_qualitative_inputs_are_rejected(event):
    with pytest.raises(ValueError):
        build_weather([event], 120)


def test_opposite_levels_of_one_factor_are_rejected():
    with pytest.raises(ValueError, match='more than one'):
        build_weather([{'type': 'rates', 'level': 'up'}, {'type': 'rates', 'level': 'down'}], 120)


def test_rate_shift_moves_savings_but_never_reprices_fixed_loans():
    profile = {**core.load_profile(), 'cash': 20000, 'monthly_net_income': 4200,
               'liabilities': [{'type': 'loan', 'balance': 5000, 'annual_rate': 0.05, 'monthly_payment': 100}]}
    results = {level: core.simulate_node(profile, [], weather=[{'type': 'rates', 'level': level}],
                sensitivity=False, exploration=False) for level in ('up', 'down')}
    base = core.simulate_node(profile, [], sensitivity=False, exploration=False)
    assert results['up']['metrics']['final_net_worth'] > base['metrics']['final_net_worth'] > results['down']['metrics']['final_net_worth']
    for r in results.values():
        assert r['deterministic']['debt'] == base['deterministic']['debt']
        assert all(c['passed'] for c in r['checks'])


def test_new_catalog_and_report_assumptions_are_additive():
    events = [{'type': 'scenario', 'level': 'optimistic'}, {'type': 'rates', 'level': 'up'}]
    out = core.expand(None, ['1'], weather=events, exploration=False, sensitivity=False)
    assert isinstance(out['weather_options']['recession'], str)
    assert out['weather_options']['scenario:optimistic']['level'] == 'optimistic'
    report = core.report_data(None, ['1'], weather=events)
    assert [w['type'] for w in report['weather_assumptions']] == ['scenario', 'rates']
    assert all(w['source'] and w['sources'] for w in report['weather_assumptions'])
    assert len(weather_catalog()) == 19
