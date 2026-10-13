import {
  isPresetRetention,
  parseRetentionDays,
  retentionLabel,
} from '../retention';

describe('retentionLabel', () => {
  it('names whole years and leaves other spans in days', () => {
    expect(retentionLabel(365)).toBe('1 year');
    expect(retentionLabel(1095)).toBe('3 years');
    expect(retentionLabel(3650)).toBe('10 years');
    expect(retentionLabel(90)).toBe('90 days');
    expect(retentionLabel(400)).toBe('400 days');
  });
});

describe('parseRetentionDays', () => {
  it('accepts whole days from 90 to 3650', () => {
    expect(parseRetentionDays('90')).toBe(90);
    expect(parseRetentionDays(' 3650 ')).toBe(3650);
  });

  it('rejects values the API would refuse', () => {
    expect(parseRetentionDays('89')).toBeNull();
    expect(parseRetentionDays('3651')).toBeNull();
    expect(parseRetentionDays('120.5')).toBeNull();
    expect(parseRetentionDays('')).toBeNull();
  });
});

it('knows the presets', () => {
  expect(isPresetRetention(365)).toBe(true);
  expect(isPresetRetention(400)).toBe(false);
});
