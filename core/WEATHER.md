# Conditional macro weather (#87)

Weather changes simulated conditions, never probabilities of the real future.
Legacy events and their defaults remain supported. Neutral is exactly the current
assumption set. The rail sends only a type and a qualitative level; the engine owns
the magnitudes. Selecting a perspective resets the specific factors. A specific
factor overrides its channel in the perspective, independent of request order.
Only one perspective and one level of each factor are accepted.

## Internal mapping

Except FX, choices start at month 0 and last 24 months by default, clipped to the
horizon. Market crash is a one-off at the start; FX lasts to the horizon. Optional
integer start/duration fields are supported by the engine, not exposed by the rail.

| choice | internal assumptions |
|---|---|
| Pessimistic | inflation 3%/year; real wage growth 0%; portfolio annual return shift -5 percentage points; job-loss hazard multiplier 2 |
| Neutral | no overrides |
| Optimistic | inflation 0.5%/year; real wage growth 2%; portfolio annual return shift +3 points; job-loss hazard multiplier 0.5 |
| Inflation high / low | inflation 3% / 0%; wages keep their own path |
| CHF strong / weak | EURCHF factor 0.9 / 1.1 |
| Markets crash / boom | invested balance factor 0.7 once, then base returns / portfolio annual return shift +5 points during the window |
| Jobs weak / strong | real wage growth 0% / 2%; job-loss hazard multiplier 2 / 0.5 |
| Rates up / down | cash savings annual rate shift +1 / -1 percentage point, floored at zero |

Rates do not reprice existing fixed-rate loans, 3a accounts or BVG. Job hazards
change only the optional stochastic lens; wage changes also affect the primary
deterministic path. A market move has no direct effect without invested savings.
A franc move affects only EUR income/costs. No perspective promises a better
result for every profile (for example, low inflation also slows nominal pay).

## Source context and verification

**All exact scenario magnitudes, windows and their combinations are team modelling
choices (`verified: false`), not estimated forecasts or empirically verified joint
scenarios.** Sources provide historical scale and economic channel context:

- [FSO CPI 2023 graphic](https://dam-api.bfs.admin.ch/hub/api/dam/assets/30525764/master): annual Swiss inflation 2.8% in 2022 and 2.1% in 2023, context for the 3% high scenario; zero is an illustrative low-price-growth case.
- [SNB September 2025 policy discussion](https://www.snb.ch/en/publications/communication/summaries/zus_20251023): context for inflation, employment, rates and FX channels. It does not establish a one-for-one retail savings-rate pass-through or the job-hazard multipliers.
- [Pictet 2025 shares and bonds study](https://www.pictet.com/content/dam/www/documents/publications/shares-and-bonds-in-switzerland/2025/PWM_Performance-Swiss-shares-and-bonds-EN.pdf): context for market variability, not verification of the selected crash or return shifts.
- [ECB EURCHF reference series](https://data.ecb.europa.eu/data/datasets/EXR/EXR.D.CHF.EUR.SP00.A): context for the exchange-rate channel; the symmetric FX factors are stress choices.

Sources checked 2026-11-21. None of these mappings is fitted to the synthetic UBS
ledgers. Live numeric inputs remain available through the existing assumption
editor; the weather control remains qualitative.

## Output and compatibility

`weather_options` preserves old `{type: description}` entries and adds entries
keyed `type:level`, with label, description, defaults, assumptions, source URLs and
verification status. Resolved events appear in simulation `weather` and in path
report `weather_assumptions`. The rail is keyboard/touch accessible and translated
in EN/ES/FR/DE. Its `weather:change` event keeps legacy types for the existing sky
visual layer and exposes the actual request in `selected_weather`; these aliases
are visual only and are never submitted to the engine.
