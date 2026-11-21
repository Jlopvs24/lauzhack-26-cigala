import test from 'node:test';
import assert from 'node:assert/strict';
import { CLEAR, buildWeather, eventDetail, intensity, optionNodes, stormLine, stormSummary, toggle, weatherOptions } from './weatherModel.js';
import { W_I18N } from './weatherI18n.js';

const OPTS = { recession: 'r', inflation: 'i', market_crash: 'm', chf_strengthens: 's', chf_weakens: 'w', job_loss: 'j', new_thing: 'n' };
const node = (id, status, feasible) => ({ node_id: id, status, result: { plan_check: { feasible, level: feasible ? 'holds' : 'needs_financing' } } });
const TREE = { current: '2', weather_options: OPTS, weather: [{ type: 'recession', start_month: 11 }],
  nodes: [node('0', 'chosen', true), node('2', 'chosen', false), node('1', 'sibling', true),
    node('2.1', 'child', false), node('2.2', 'child', true), node('2.3', 'child', true)] };

test('chips come from the engine catalog, known ones first, unknown ones kept', () => {
  const o = weatherOptions(TREE, 'en');
  assert.deepEqual(o.map((x) => x.type), ['recession', 'inflation', 'market_crash', 'job_loss', 'chf_strengthens', 'chf_weakens', 'new_thing']);
  assert.equal(o[0].label, 'Recession');
  assert.equal(o.at(-1).label, 'new thing');
  assert.equal(weatherOptions({}, 'en').length, 0);
});

test('toggle is multi-select, the two FX directions exclude each other', () => {
  let s = toggle(CLEAR, 'recession');
  s = toggle(s, 'market_crash');
  assert.deepEqual(s.types, ['recession', 'market_crash']);
  s = toggle(toggle(s, 'chf_strengthens'), 'chf_weakens');
  assert.deepEqual(s.types, ['recession', 'market_crash', 'chf_weakens']);
  assert.deepEqual(toggle(s, 'recession').types, ['market_crash', 'chf_weakens']);
});

test('request shape: shared start month, duration only where it applies, clamped', () => {
  assert.deepEqual(buildWeather(CLEAR), []);
  const w = buildWeather({ types: ['recession', 'market_crash'], start: 99, duration: 50 });
  assert.deepEqual(w, [{ type: 'recession', start_month: 60, duration_months: 36 }, { type: 'market_crash', start_month: 60 }]);
  assert.deepEqual(buildWeather({ types: ['job_loss'], start: 3, duration: null }), [{ type: 'job_loss', start_month: 3 }]);
});

test('options = children of the current node, else it and its siblings; counts from plan_check', () => {
  assert.deepEqual(optionNodes(TREE).map((n) => n.node_id), ['2.1', '2.2', '2.3']);
  assert.deepEqual(stormSummary(TREE), { held: 2, of: 3, holding: ['2.2', '2.3'], breaking: ['2.1'] });
  const leaf = { current: '2.1', nodes: [node('2.1', 'chosen', false), node('2.2', 'sibling', true)] };
  assert.deepEqual(stormSummary(leaf), { held: 1, of: 2, holding: ['2.2'], breaking: ['2.1'] });
});

test('conditional wording in every language, never a forecast', () => {
  const s = stormSummary(TREE);
  assert.equal(stormLine('en', TREE.weather, s), 'If a recession starts in month 12: 2 of 3 options still hold.');
  assert.equal(stormLine('en', [{ type: 'recession', start_month: 0 }, { type: 'market_crash', start_month: 0 }], s),
    'If a recession and a market crash start in month 1: 2 of 3 options still hold.');
  assert.equal(stormLine('es', TREE.weather, s), 'Si una recesión empieza en el mes 12: 2 de 3 opciones aún se sostienen.');
  assert.equal(stormLine('fr', TREE.weather, s), 'Si une récession commence au mois 12 : 2 options sur 3 tiennent encore.');
  assert.equal(stormLine('de', TREE.weather, s), 'Wenn eine Rezession in Monat 12 beginnt, halten noch 2 von 3 Optionen.');
  assert.equal(stormLine('en', [], s), null);
  const one = { held: 1, of: 3 }, none = { held: 0, of: 3 };
  assert.equal(stormLine('en', TREE.weather, one), 'If a recession starts in month 12: 1 of 3 options still holds.');
  assert.equal(stormLine('fr', TREE.weather, one), 'Si une récession commence au mois 12 : 1 option sur 3 tient encore.');
  assert.equal(stormLine('de', TREE.weather, none), 'Wenn eine Rezession in Monat 12 beginnt, hält keine der 3 Optionen.');
  assert.equal(stormLine('es', TREE.weather, none), 'Si una recesión empieza en el mes 12: ninguna de las 3 opciones se sostiene.');
  for (const lang of Object.keys(W_I18N)) {
    const line = stormLine(lang, TREE.weather, s);
    assert.doesNotMatch(line, /will|wird|va |sera|será|forecast|prévision|Prognose/i, lang);
    assert.ok(Object.keys(W_I18N.en.names).every((k) => W_I18N[lang].names[k] && W_I18N[lang].phrase[k]), lang);
  }
});

test('event detail for the visual layer', () => {
  assert.equal(intensity([]), 0);
  assert.equal(intensity([{ type: 'recession' }, { type: 'market_crash' }]), 1);
  assert.equal(intensity([{ type: 'inflation' }]), 0.5);
  const p = eventDetail([{ type: 'inflation', start_month: 0 }], null, true);
  assert.deepEqual(p, { weather: [{ type: 'inflation', start_month: 0 }], selected_weather: [{ type: 'inflation', start_month: 0 }], intensity: 0.5, clear: false, pending: true,
    start_month: 0, holds: null, holding_node_ids: [], breaking_node_ids: [] });
  const d = eventDetail(TREE.weather, TREE, false);
  assert.deepEqual(d.holds, { held: 2, of: 3 });
  assert.deepEqual(d.breaking_node_ids, ['2.1']);
  assert.equal(eventDetail([], TREE, false).clear, true);
});

test('macro controls send only qualitative levels; reset and opposing factors are exclusive', async () => {
  const { MACRO_CLEAR, selectScenario, toggleFactor, buildMacroWeather } = await import('./weatherModel.js');
  assert.deepEqual(buildMacroWeather(MACRO_CLEAR), []);
  let s = selectScenario('pessimistic');
  s = toggleFactor(s, 'inflation', 'high');
  s = toggleFactor(s, 'inflation', 'low');
  assert.deepEqual(buildMacroWeather(s), [{ type: 'scenario', level: 'pessimistic' }, { type: 'inflation', level: 'low' }]);
  assert.deepEqual(buildMacroWeather(toggleFactor(s, 'inflation', 'low')), [{ type: 'scenario', level: 'pessimistic' }]);
  assert.deepEqual(selectScenario('neutral'), MACRO_CLEAR);
});

test('macro options and labels are complete in every language, without magnitudes', async () => {
  const { macroOptions } = await import('./weatherModel.js');
  const { M_I18N } = await import('./weatherI18n.js');
  const ids = ['scenario:pessimistic', 'scenario:neutral', 'scenario:optimistic', 'inflation:high', 'inflation:low',
    'fx:chf_strong', 'fx:chf_weak', 'markets:crash', 'markets:boom', 'jobs:weak', 'jobs:strong', 'rates:up', 'rates:down'];
  for (const L of Object.values(M_I18N)) for (const id of ids) {
    assert.ok(L.labels[id]); assert.doesNotMatch(L.labels[id], /[0-9%]/);
  }
  const tree = { weather_options: { recession: 'old', 'scenario:neutral': { type: 'scenario', level: 'neutral' } } };
  assert.equal(macroOptions(tree, 'scenario').length, 1);
  assert.equal(weatherOptions(tree).length, 1);
  for (const lang of Object.keys(M_I18N)) assert.doesNotMatch(stormLine(lang, [{ type: 'scenario', level: 'optimistic' }]), /[0-9%]/);
});

test('qualitative events retain the legacy visual layer and expose the actual selected weather', () => {
  const request = [{ type: 'scenario', level: 'pessimistic' }, { type: 'markets', level: 'crash' }];
  const d = eventDetail(request, TREE, false);
  assert.deepEqual(d.selected_weather, request);
  assert.deepEqual(d.weather.map((w) => w.type), ['recession', 'inflation', 'market_crash']);
  assert.equal(d.intensity, 1);
  assert.deepEqual(d.breaking_node_ids, ['2.1']);
});
