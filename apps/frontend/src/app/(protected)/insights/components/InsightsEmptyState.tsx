'use client';

import React from 'react';
import { Box } from '@mui/material';
import { useRouter } from 'next/navigation';
import EntityEmptyState from '@/components/common/EntityEmptyState';
import EndpointsIcon from '@/components/EndpointsIcon';
import { PlayArrowIcon } from '@/components/icons';

export type InsightsEmptyStateVariant = 'no-endpoints' | 'no-test-results';

interface InsightsEmptyStateProps {
  variant: InsightsEmptyStateVariant;
}

const VARIANT_CONFIG = {
  'no-endpoints': {
    icon: EndpointsIcon,
    title: 'No endpoints in this project',
    description:
      'Create an endpoint to view behavior insights for your AI application.',
    actionLabel: 'Go to Endpoints',
    href: '/endpoints',
  },
  'no-test-results': {
    icon: PlayArrowIcon,
    title: 'No test results yet',
    description:
      'Run a test set against your endpoint to generate your first test run and view behavior insights.',
    actionLabel: 'Go to Test Sets',
    href: '/test-sets',
  },
} as const;

export default function InsightsEmptyState({
  variant,
}: InsightsEmptyStateProps) {
  const router = useRouter();
  const config = VARIANT_CONFIG[variant];

  return (
    <Box
      sx={{
        flex: 1,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        minHeight: 320,
        width: '100%',
      }}
    >
      <EntityEmptyState
        icon={config.icon}
        title={config.title}
        description={config.description}
        actionLabel={config.actionLabel}
        onAction={() => router.push(config.href)}
        showAddIcon={false}
      />
    </Box>
  );
}
