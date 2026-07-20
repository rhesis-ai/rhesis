'use client';

import React from 'react';
import { Paper } from '@mui/material';
import type { Theme } from '@mui/material/styles';
import TestRunFilterBar, { FilterState } from './TestRunFilterBar';
import TestsTableView from './TestsTableView';
import { TestResultDetail } from '@/utils/api-client/interfaces/test-results';
import { BORDER_RADIUS, ELEVATION } from '@/styles/theme';

interface TestRunLinkedEntitiesTabProps {
  filteredTests: TestResultDetail[];
  filter: FilterState;
  onFilterChange: (filter: FilterState) => void;
  availableBehaviors: Array<{
    id: string;
    name: string;
    description?: string;
    metrics: Array<{ name: string; description?: string }>;
  }>;
  availableMetrics: string[];
  isDownloading: boolean;
  onDownload: () => void;
  onCompare: () => void;
  canCompare?: boolean;
  onRerun: () => void;
  isRerunning: boolean;
  canRerun: boolean;
  totalTests: number;
  testRunId: string;
  sessionToken: string;
  loading?: boolean;
  prompts: Record<string, { content: string; name?: string }>;
  behaviors: Array<{
    id: string;
    name: string;
    description?: string;
    metrics: Array<{ name: string; description?: string }>;
  }>;
  onTestResultUpdate: (updated: TestResultDetail) => void;
  currentUserId: string;
  currentUserName: string;
  currentUserPicture?: string;
  initialSelectedTestId?: string;
  initialDetailTab?: string;
  testSetType?: string;
  project?: { icon?: string; useCase?: string; name?: string };
  projectName?: string;
  metricsSource?: string;
}

export default function TestRunLinkedEntitiesTab({
  filteredTests,
  filter,
  onFilterChange,
  availableBehaviors,
  availableMetrics,
  isDownloading,
  onDownload,
  onCompare,
  canCompare = true,
  onRerun,
  isRerunning,
  canRerun,
  totalTests,
  testRunId,
  sessionToken,
  loading = false,
  prompts,
  behaviors,
  onTestResultUpdate,
  currentUserId,
  currentUserName,
  currentUserPicture,
  initialSelectedTestId,
  initialDetailTab,
  testSetType,
  project,
  projectName,
  metricsSource,
}: TestRunLinkedEntitiesTabProps) {
  return (
    <Paper
      elevation={0}
      sx={{
        p: '30px',
        borderRadius: BORDER_RADIUS.md,
        boxShadow: (theme: Theme) =>
          theme.palette.mode === 'light' ? ELEVATION.xs : 'none',
        border: (theme: Theme) => `1px solid ${theme.palette.greyscale.border}`,
        bgcolor: (theme: Theme) =>
          theme.palette.mode === 'light'
            ? '#ffffff'
            : theme.palette.greyscale.surface1,
        display: 'flex',
        flexDirection: 'column',
        gap: '30px',
        minWidth: 0,
      }}
    >
      <TestRunFilterBar
        filter={filter}
        onFilterChange={onFilterChange}
        availableBehaviors={availableBehaviors}
        availableMetrics={availableMetrics.map(name => ({ name }))}
        onDownload={onDownload}
        onCompare={onCompare}
        canCompare={canCompare}
        isDownloading={isDownloading}
        totalTests={totalTests}
        filteredTests={filteredTests.length}
        onRerun={onRerun}
        isRerunning={isRerunning}
        canRerun={canRerun}
        variant="linkedEntities"
        hideViewModeToggle
      />

      <TestsTableView
        tests={filteredTests}
        prompts={prompts}
        behaviors={behaviors}
        testRunId={testRunId}
        sessionToken={sessionToken}
        loading={loading}
        onTestResultUpdate={onTestResultUpdate}
        currentUserId={currentUserId}
        currentUserName={currentUserName}
        currentUserPicture={currentUserPicture}
        initialSelectedTestId={initialSelectedTestId}
        initialDetailTab={initialDetailTab}
        testSetType={testSetType}
        project={project}
        projectName={projectName}
        metricsSource={metricsSource}
        embedded
      />
    </Paper>
  );
}
