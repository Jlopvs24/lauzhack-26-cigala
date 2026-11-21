export const money = value => Number.isFinite(value)
  ? new Intl.NumberFormat('en-CH', { style: 'currency', currency: 'CHF', maximumFractionDigits: 0 }).format(value)
  : 'Not available';
export const percent = value => Number.isFinite(value)
  ? new Intl.NumberFormat('en', { style: 'percent', maximumFractionDigits: 1 }).format(value)
  : 'Not available';

export function bandGeometry(bands) {
  const { p10, p50, p90 } = bands || {};
  if (![p10, p50, p90].every(series => Array.isArray(series) && series.length >= 2
    && series.length === p50?.length && series.every(Number.isFinite))
    || p10.some((value, i) => value > p50[i] || p50[i] > p90[i])) return null;
  let low = Math.min(0, ...p10);
  let high = Math.max(0, ...p90);
  if (low === high) { low -= 1; high += 1; }
  const x = i => 76 + i / (p50.length - 1) * 600;
  const y = value => 230 - (value - low) / (high - low) * 200;
  const points = series => series.map((value, i) => `${x(i)},${y(value)}`);
  return { low, high, zeroY: y(0), median: points(p50).join(' '),
    area: [...points(p90), ...points(p10).reverse()].join(' ') };
}

export function strongestSensitivity(sensitivity = []) {
  return (sensitivity || []).filter(item => Number.isFinite(item.delta_final_net_worth))
    .reduce((largest, item) => !largest || Math.abs(item.delta_final_net_worth) > Math.abs(largest.delta_final_net_worth)
      ? item : largest, null);
}

export function healthFraction(health) {
  if (!Number.isFinite(health?.score)) return null;
  // Core v1 scores out of 100; the v0 mock scores out of 1.
  const core = Object.values(health.components || {}).some(value => value && typeof value === 'object');
  return health.score / (core ? 100 : 1);
}

export function assumptionOverrides(assumptions, values) {
  return assumptions.filter(item => item.editable).map(item => {
    const raw = values[item.id];
    if (raw === undefined || String(raw).trim() === '' || !Number.isFinite(Number(raw))) {
      throw new Error(`Enter a finite number for ${item.param || item.id}.`);
    }
    const value = Number(raw);
    if ((/volatility|_vol$|_sd$|prob|noise/.test(item.param) && value < 0)
      || ((/prob|noise/.test(item.param) || item.unit?.startsWith('share')) && (value < 0 || value > 1))
      || (item.unit === 'flag' && ![0, 1].includes(value))) {
      throw new Error(`Check the range for ${item.param}. Probabilities and shares must be between 0 and 1; volatility cannot be negative.`);
    }
    return { id: item.id, value };
  });
}
