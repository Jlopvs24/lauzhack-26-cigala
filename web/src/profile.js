export const profileFields = [
  { key: 'display_name', label: 'Name', type: 'text' },
  { key: 'city', label: 'City', type: 'text' },
  { key: 'age', label: 'Age', type: 'number', min: 0, step: 1 },
  { key: 'cash', label: 'Starting cash (CHF)', type: 'number', step: 'any' },
  { key: 'monthly_net_income', label: 'Monthly income after social contributions (CHF)', type: 'number', min: 0, step: 'any' },
  { key: 'monthly_rent', label: 'Monthly rent (CHF)', type: 'number', min: 0, step: 'any' },
  { key: 'monthly_other_expenses', label: 'Other monthly expenses (CHF)', type: 'number', min: 0, step: 'any' },
];

export function profileFromForm(base, values, edited = []) {
  if (base.currency && base.currency !== 'CHF') throw new Error('This demo accepts CHF profiles. Convert the input amounts to CHF first.');
  const next = { ...base, provenance: { ...base.provenance } };
  for (const field of profileFields) {
    const raw = String(values[field.key] ?? '').trim();
    if (!raw) throw new Error(`Please fill in ${field.label.toLowerCase()}.`);
    const value = field.type === 'number' ? Number(raw) : raw;
    if (field.type === 'number' && (!Number.isFinite(value) || (field.min !== undefined && value < field.min)
      || (field.key === 'age' && (!Number.isInteger(value) || value > 120)))) throw new Error(`Check ${field.label.toLowerCase()}.`);
    next[field.key] = value;
    if (edited.includes(field.key)) next.provenance[field.key] = { source: 'questionnaire', confidence: 1 };
  }
  next.synthetic = true;
  return next;
}
