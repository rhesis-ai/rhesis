import {
  ArchitectChartSpec,
  buildSeries,
  dataColumns,
  formatMeasure,
  formatPeriod,
  heatPosition,
  valueBounds,
  xCategories,
} from '../charts';

const base: ArchitectChartSpec = {
  title: 't',
  chart_type: 'line',
  x: 'period',
  measures: [{ key: 'pass_rate', kind: 'rate' }],
  time_grain: 'week',
  rows: [],
};

describe('architect chart helpers', () => {
  it('formats measures by kind', () => {
    expect(formatMeasure(66.666, 'rate')).toBe('66.7%');
    expect(formatMeasure(0.6429, 'score')).toBe('0.64');
    expect(formatMeasure(1200, 'count')).toBe((1200).toLocaleString());
    expect(formatMeasure(null, 'rate')).toBe('');
    expect(formatMeasure(850.4, 'duration')).toBe('850 ms');
    expect(formatMeasure(1500, 'duration')).toBe('1.5 s');
    expect(formatMeasure(0.0123456, 'currency')).toBe('$0.0123');
    expect(formatMeasure(12.5, 'currency')).toBe('$12.50');
  });

  it('labels periods by their grain', () => {
    expect(formatPeriod('2026-08-31', 'week')).toBe('Week of Aug 31');
    expect(formatPeriod('2026-09-01', 'month')).toBe('Sep 2026');
    expect(formatPeriod('2026-07-01', 'quarter')).toBe('Q3 2026');
    expect(formatPeriod('2026-01-01', 'year')).toBe('2026');
    expect(formatPeriod('2026-09-15', 'day')).toBe('Sep 15, 2026');
  });

  it('builds one series per measure without a series dimension', () => {
    const spec: ArchitectChartSpec = {
      ...base,
      measures: [
        { key: 'passed', kind: 'count' },
        { key: 'failed', kind: 'count' },
      ],
      rows: [
        { period: '2026-08-31', passed: 4, failed: 2 },
        { period: '2026-09-14', passed: 3, failed: 3 },
      ],
    };

    expect(xCategories(spec)).toEqual(['Week of Aug 31', 'Week of Sep 14']);
    expect(buildSeries(spec).map(s => [s.label, s.data])).toEqual([
      ['Passed', [4, 3]],
      ['Failed', [2, 3]],
    ]);
  });

  it('pivots a series dimension and leaves gaps as null', () => {
    const spec: ArchitectChartSpec = {
      ...base,
      series: 'endpoint',
      rows: [
        { period: '2026-08-31', endpoint: 'A', pass_rate: 66.67 },
        { period: '2026-09-14', endpoint: 'B', pass_rate: 50 },
      ],
    };

    expect(buildSeries(spec).map(s => [s.label, s.data])).toEqual([
      ['A', [66.67, null]],
      ['B', [null, 50]],
    ]);
  });

  it('bounds rates and scores so bars compare honestly', () => {
    expect(valueBounds('rate')).toEqual({ min: 0, max: 100 });
    expect(valueBounds('score')).toEqual({ min: 0, max: 1 });
    expect(valueBounds('count')).toEqual({ min: 0 });
  });

  it('places heat values between bad and good', () => {
    expect(heatPosition(25, 'rate', 0)).toBe(0.25);
    expect(heatPosition(0.9, 'score', 0)).toBe(0.9);
    expect(heatPosition(5, 'count', 10)).toBe(0.5);
    expect(heatPosition(300, 'duration', 1200)).toBe(0.25);
  });

  it('lists data columns as dimensions then measures', () => {
    expect(dataColumns({ ...base, series: 'endpoint' })).toEqual([
      'period',
      'endpoint',
      'pass_rate',
    ]);
  });
});
