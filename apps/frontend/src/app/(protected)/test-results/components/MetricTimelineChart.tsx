'use client';

import React from 'react';
import BaseTimelineChart from './BaseTimelineChart';
import { TimelineDataItem, createMetricExtractor } from './timelineUtils';

interface MetricTimelineChartProps {
  metricName: string;
  timelineData: TimelineDataItem[];
}

export default function MetricTimelineChart({ metricName, timelineData }: MetricTimelineChartProps) {
  const contextInfo = (data: any[]) => {
    if (data.length === 0) {
      return 'No data available for this metric in the selected period';
    }
    const totalTests = data.reduce((sum, item) => sum + item.total, 0);
    return `${data.length} data points, ${totalTests} total tests`;
  };

  return (
    <BaseTimelineChart
      title={metricName}
      data={timelineData}
      dataExtractor={createMetricExtractor(metricName)}
      height={300}
      contextInfo={contextInfo}
      filterEmptyData={true}
      titleVariant="h6"
      titleFontSize="1rem"
      subtitleFontSize="0.8rem"
    />
  );
}
