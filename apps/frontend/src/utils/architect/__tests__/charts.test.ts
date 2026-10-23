import {
  ArchitectChartSpec,
  ChartPalette,
  buildSeries,
  categoryColors,
  dataColumns,
  focusLabels,
  legendEntries,
  seriesColors,
  seriesMark,
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

describe('architect chart colors', () => {
  const palette: ChartPalette = {
    neutral: 'gray',
    neutralLine: 'dark-gray',
    series: ['clay', 'violet', 'ochre', 'sage'],
  };
  const topics: ArchitectChartSpec = {
    title: 't',
    chart_type: 'horizontal_bar',
    x: 'topic',
    measures: [{ key: 'pass_rate', kind: 'rate' }],
    rows: [
      { topic: 'Visa', pass_rate: 56 },
      { topic: 'Baggage', pass_rate: 92 },
    ],
  };
  const byEndpoint: ArchitectChartSpec = {
    ...base,
    series: 'endpoint',
    rows: [
      { period: '2026-09-07', endpoint: 'v1', pass_rate: 70 },
      { period: '2026-09-07', endpoint: 'v2', pass_rate: 80 },
      { period: '2026-09-07', endpoint: 'v3', pass_rate: 75 },
    ],
  };

  it('keeps a lone bar series gray and a lone line in the accent', () => {
    expect(seriesColors(topics, ['Pass rate'], palette, 'fill')).toEqual([
      'gray',
    ]);
    expect(seriesColors(base, ['Pass rate'], palette, 'line')).toEqual([
      'clay',
    ]);
  });

  it('gives several series the palette in order', () => {
    expect(
      seriesColors(byEndpoint, ['v1', 'v2', 'v3'], palette, 'line')
    ).toEqual(['clay', 'violet', 'ochre']);
  });

  it('puts a focused series in the accent and the rest in gray', () => {
    const spec = { ...byEndpoint, focus: ['v2'] };
    expect(seriesColors(spec, ['v1', 'v2', 'v3'], palette, 'line')).toEqual([
      'dark-gray',
      'clay',
      'dark-gray',
    ]);
  });

  it('colors focused bars by category, and none without a focus', () => {
    const categories = xCategories(topics);
    expect(categoryColors(topics, categories, palette)).toBeNull();
    expect(
      categoryColors({ ...topics, focus: ['Visa'] }, categories, palette)
    ).toEqual(['clay', 'gray']);
  });

  it('matches a period focus by its ISO date', () => {
    const spec = { ...byEndpoint, focus: ['2026-09-07'] };
    expect([...focusLabels(spec, 'period')]).toEqual(['Week of Sep 7']);
    expect(focusLabels(spec, 'endpoint').size).toBe(0);
  });

  it('lists legend entries only for two or more series', () => {
    expect(legendEntries(topics, palette)).toEqual([]);
    expect(legendEntries(byEndpoint, palette)).toEqual([
      { label: 'v1', color: 'clay' },
      { label: 'v2', color: 'violet' },
      { label: 'v3', color: 'ochre' },
    ]);
  });

  it('draws lines, areas and radar shapes as lines', () => {
    expect(seriesMark('area')).toBe('line');
    expect(seriesMark('stacked_bar')).toBe('fill');
  });
});
