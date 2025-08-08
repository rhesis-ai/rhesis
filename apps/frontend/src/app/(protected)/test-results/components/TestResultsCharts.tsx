'use client';

import React, { useState } from 'react';
import { BaseChartsGrid } from '@/components/common/BaseCharts';
import { TestResultsStatsOptions } from '@/utils/api-client/interfaces/common';
import { Box, Tabs, Tab, Paper } from '@mui/material';
import PassRateTimelineChart from './PassRateTimelineChart';
import LatestResultsPieChart from './LatestResultsPieChart';
import LatestTestRunsChart from './LatestTestRunsChart';
import DimensionRadarChart from './DimensionRadarChart';
import MetricTimelineChartsGrid from './MetricTimelineChartsGrid';
import TestResultsSummary from './TestResultsSummary';

interface TestResultsChartsProps {
  sessionToken: string;
  filters: Partial<TestResultsStatsOptions>;
}

interface TabPanelProps {
  children?: React.ReactNode;
  index: number;
  value: number;
}

function TabPanel(props: TabPanelProps) {
  const { children, value, index, ...other } = props;

  return (
    <div
      role="tabpanel"
      hidden={value !== index}
      id={`charts-tabpanel-${index}`}
      aria-labelledby={`charts-tab-${index}`}
      {...other}
    >
      {value === index && (
        <Box>
          {children}
        </Box>
      )}
    </div>
  );
}

function a11yProps(index: number) {
  return {
    id: `charts-tab-${index}`,
    'aria-controls': `charts-tabpanel-${index}`,
  };
}

export default function TestResultsCharts({ sessionToken, filters }: TestResultsChartsProps) {
  const [value, setValue] = useState(0);

  const handleChange = (event: React.SyntheticEvent, newValue: number) => {
    setValue(newValue);
  };

  return (
    <Box>
      <Tabs 
        value={value} 
        onChange={handleChange} 
        aria-label="test results charts tabs"
        sx={{ 
          borderBottom: 1, 
          borderColor: 'divider',
          mb: 2
        }}
      >
        <Tab label="Summary" {...a11yProps(0)} />
        <Tab label="At a Glance" {...a11yProps(1)} />
        <Tab label="In Detail" {...a11yProps(2)} />
        <Tab label="Metrics Over Time" {...a11yProps(3)} />
      </Tabs>

      <TabPanel value={value} index={0}>
        {/* Summary Tab - Test Run Summary and Metadata */}
        <TestResultsSummary 
          sessionToken={sessionToken} 
          filters={filters} 
        />
      </TabPanel>

      <TabPanel value={value} index={1}>
        {/* At a Glance Tab - Timeline, Test Runs, and Overall Results */}
        <Box sx={{ 
          display: 'grid', 
          gridTemplateColumns: { xs: '1fr', md: '1fr 1fr', lg: '1fr 1fr 1fr' }, 
          gap: 3 
        }}>
          {/* Pass Rate Timeline - Independent API call with 'timeline' mode */}
          <PassRateTimelineChart 
            sessionToken={sessionToken} 
            filters={filters} 
          />

          {/* Latest Test Runs - Independent API call with 'test_runs' mode */}
          <LatestTestRunsChart 
            sessionToken={sessionToken} 
            filters={filters} 
          />

          {/* Overall Results - Independent API call with 'summary' mode */}
          <LatestResultsPieChart 
            sessionToken={sessionToken} 
            filters={filters} 
          />
        </Box>
      </TabPanel>

      <TabPanel value={value} index={2}>
        {/* In Detail Tab - Radar Charts */}
        <Box sx={{ display: 'grid', gridTemplateColumns: { xs: '1fr', lg: '1fr 1fr 1fr' }, gap: 3 }}>
          <DimensionRadarChart 
            sessionToken={sessionToken} 
            filters={filters} 
            dimension="behavior" 
            title="Behavior" 
          />
          <DimensionRadarChart 
            sessionToken={sessionToken} 
            filters={filters} 
            dimension="category" 
            title="Category" 
          />
          <DimensionRadarChart 
            sessionToken={sessionToken} 
            filters={filters} 
            dimension="topic" 
            title="Topic" 
          />
        </Box>
      </TabPanel>

      <TabPanel value={value} index={3}>
        {/* Metrics Over Time Tab - Dynamic Metric Timeline Charts */}
        <MetricTimelineChartsGrid 
          sessionToken={sessionToken} 
          filters={filters} 
        />
      </TabPanel>
    </Box>
  );
}