// Shared utilities for timeline chart components

export interface TimelineDataItem {
  date: string;
  overall: {
    total: number;
    passed: number;
    failed: number;
    pass_rate: number;
  };
  metrics?: Record<
    string,
    {
      total: number;
      passed: number;
      failed: number;
      pass_rate: number;
    }
  >;
}

export interface PassFailData {
  total: number;
  passed: number;
  failed: number;
  pass_rate: number;
}

export interface ChartDataPoint {
  name: string;
  pass_rate: number;
  total: number;
  passed: number;
  failed: number;
}

/**
 * Format date from "2025-05" to "May 2025"
 */
export const formatTimelineDate = (dateStr: string): string => {
  try {
    const [year, month] = dateStr.split('-');
    const monthNames = [
      'Jan',
      'Feb',
      'Mar',
      'Apr',
      'May',
      'Jun',
      'Jul',
      'Aug',
      'Sep',
      'Oct',
      'Nov',
      'Dec',
    ];
    const monthIndex = parseInt(month) - 1;
    return `${monthNames[monthIndex]} ${year}`;
  } catch {
    return dateStr;
  }
};

/**
 * Transform timeline data into chart-compatible format
 */
export const transformTimelineData = (
  timelineData: TimelineDataItem[],
  dataExtractor: (item: TimelineDataItem) => PassFailData | null,
  filterEmptyData = false
): ChartDataPoint[] => {
  if (!timelineData || timelineData.length === 0) {
    return [];
  }

  return timelineData
    .map(item => {
      const data = dataExtractor(item);
      if (!data) return null;

      return {
        name: formatTimelineDate(item.date || 'Unknown'),
        pass_rate:
          data.pass_rate != null ? Math.round(data.pass_rate * 10) / 10 : 0,
        total: data.total || 0,
        passed: data.passed || 0,
        failed: data.failed || 0,
      };
    })
    .filter((item): item is NonNullable<typeof item> => {
      if (!item) return false;
      if (filterEmptyData && item.total === 0) return false;
      return true;
    })
    .map(item => ({
      ...item,
      pass_rate: isNaN(item.pass_rate) ? 0 : item.pass_rate,
    }));
};

/**
 * Data extractor for overall pass rates
 */
export const extractOverallData = (
  item: TimelineDataItem
): PassFailData | null => {
  return item.overall || null;
};

/**
 * Data extractor factory for specific metrics
 */
export const createMetricExtractor =
  (metricName: string) =>
  (item: TimelineDataItem): PassFailData | null => {
    return item.metrics?.[metricName] || null;
  };

/**
 * Generate mock data for demonstration purposes
 */
export const generateMockTimelineData = (): ChartDataPoint[] => {
  return [
    { name: 'Jan 2024', pass_rate: 85, total: 100, passed: 85, failed: 15 },
    { name: 'Feb 2024', pass_rate: 78, total: 95, passed: 74, failed: 21 },
    { name: 'Mar 2024', pass_rate: 92, total: 88, passed: 81, failed: 7 },
    { name: 'Apr 2024', pass_rate: 88, total: 110, passed: 97, failed: 13 },
    { name: 'May 2024', pass_rate: 95, total: 75, passed: 71, failed: 4 },
    { name: 'Jun 2024', pass_rate: 82, total: 120, passed: 98, failed: 22 },
  ];
};
