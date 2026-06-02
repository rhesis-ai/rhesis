'use client';

import React from 'react';
import { Paper } from '@mui/material';
import TestRunFilterBar, { FilterState } from './TestRunFilterBar';
import TestsTableView from './TestsTableView';
import { TestResultDetail } from '@/utils/api-client/interfaces/test-results';

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
  testSetType,
  project,
  projectName,
  metricsSource,
}: TestRunLinkedEntitiesTabProps) {
  return (
    <>
      <TestRunFilterBar
        filter={filter}
        onFilterChange={onFilterChange}
        availableBehaviors={availableBehaviors}
        availableMetrics={availableMetrics.map(name => ({ name }))}
        onDownload={onDownload}
        onCompare={onCompare}
        isDownloading={isDownloading}
        totalTests={totalTests}
        filteredTests={filteredTests.length}
        onRerun={onRerun}
        isRerunning={isRerunning}
        canRerun={canRerun}
        variant="linkedEntities"
        hideViewModeToggle
      />

      <Paper
        elevation={0}
        sx={{
          border: 1,
          borderColor: 'divider',
          borderRadius: 2,
          overflow: 'hidden',
        }}
      >
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
          testSetType={testSetType}
          project={project}
          projectName={projectName}
          metricsSource={metricsSource}
        />
      </Paper>
    </>
  );
}
