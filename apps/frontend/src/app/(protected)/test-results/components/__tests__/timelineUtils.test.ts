import {
  formatTimelineDate,
  transformTimelineData,
  extractOverallData,
  createMetricExtractor,
  generateMockTimelineData,
  type TimelineDataItem,
} from '../timelineUtils';

describe('formatTimelineDate', () => {
  it('formats "2025-05" to "May 2025"', () => {
    expect(formatTimelineDate('2025-05')).toBe('May 2025');
  });

  it('formats "2024-01" to "Jan 2024"', () => {
    expect(formatTimelineDate('2024-01')).toBe('Jan 2024');
  });

  it('formats "2024-12" to "Dec 2024"', () => {
    expect(formatTimelineDate('2024-12')).toBe('Dec 2024');
  });

  it('handles invalid input without crashing', () => {
    const result = formatTimelineDate('invalid');
    expect(typeof result).toBe('string');
  });
});

describe('transformTimelineData', () => {
  const sampleData: TimelineDataItem[] = [
    {
      date: '2024-01',
      overall: { total: 100, passed: 85, failed: 15, pass_rate: 85 },
    },
    {
      date: '2024-02',
      overall: { total: 50, passed: 40, failed: 10, pass_rate: 80 },
    },
  ];

  it('returns empty array for empty input', () => {
    expect(transformTimelineData([], extractOverallData)).toEqual([]);
  });

  it('returns empty array for null input', () => {
    expect(
      transformTimelineData(
        null as unknown as TimelineDataItem[],
        extractOverallData
      )
    ).toEqual([]);
  });

  it('transforms timeline data with overall extractor', () => {
    const result = transformTimelineData(sampleData, extractOverallData);
    expect(result).toHaveLength(2);
    expect(result[0].name).toBe('Jan 2024');
    expect(result[0].total).toBe(100);
    expect(result[0].passed).toBe(85);
    expect(result[0].failed).toBe(15);
    expect(result[0].pass_rate).toBe(85);
  });

  it('filters empty data when filterEmptyData is true', () => {
    const dataWithEmpty: TimelineDataItem[] = [
      ...sampleData,
      {
        date: '2024-03',
        overall: { total: 0, passed: 0, failed: 0, pass_rate: 0 },
      },
    ];
    const result = transformTimelineData(
      dataWithEmpty,
      extractOverallData,
      true
    );
    expect(result).toHaveLength(2);
  });

  it('filters out null extractor results', () => {
    const result = transformTimelineData(sampleData, () => null);
    expect(result).toEqual([]);
  });
});

describe('extractOverallData', () => {
  it('returns overall data from item', () => {
    const item: TimelineDataItem = {
      date: '2024-01',
      overall: { total: 10, passed: 8, failed: 2, pass_rate: 80 },
    };
    expect(extractOverallData(item)).toEqual(item.overall);
  });
});

describe('createMetricExtractor', () => {
  it('extracts data for a specific metric', () => {
    const item: TimelineDataItem = {
      date: '2024-01',
      overall: { total: 10, passed: 8, failed: 2, pass_rate: 80 },
      metrics: {
        accuracy: { total: 5, passed: 4, failed: 1, pass_rate: 80 },
      },
    };
    const extractor = createMetricExtractor('accuracy');
    expect(extractor(item)).toEqual(item.metrics!.accuracy);
  });

  it('returns null for missing metric', () => {
    const item: TimelineDataItem = {
      date: '2024-01',
      overall: { total: 10, passed: 8, failed: 2, pass_rate: 80 },
    };
    const extractor = createMetricExtractor('nonexistent');
    expect(extractor(item)).toBeNull();
  });
});

describe('generateMockTimelineData', () => {
  it('returns an array of chart data points', () => {
    const data = generateMockTimelineData();
    expect(data.length).toBeGreaterThan(0);
    expect(data[0]).toHaveProperty('name');
    expect(data[0]).toHaveProperty('pass_rate');
    expect(data[0]).toHaveProperty('total');
    expect(data[0]).toHaveProperty('passed');
    expect(data[0]).toHaveProperty('failed');
  });
});
