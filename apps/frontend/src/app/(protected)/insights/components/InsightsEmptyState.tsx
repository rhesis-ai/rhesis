'use client';

import React from 'react';
import { Box } from '@mui/material';
import { useRouter } from 'next/navigation';
import EntityEmptyState from '@/components/common/EntityEmptyState';
import EndpointsIcon from '@/components/EndpointsIcon';
import { PlayArrowIcon } from '@/components/icons';

export type InsightsEmptyStateVariant = 'no-endpoints' | 'no-test-results';

export interface InsightsEndpointOption {
  id: string;
  name: string;
}

interface InsightsEmptyStateProps {
  variant: InsightsEmptyStateVariant;
  /** The endpoint the page is showing; names it in the no-results copy. */
  endpointName?: string;
  /** Other endpoints in the project that do have results in the time range. */
  endpointsWithResults?: InsightsEndpointOption[];
  /** Whether the project has endpoints besides the selected one. */
  hasOtherEndpoints?: boolean;
  onSelectEndpoint?: (endpointId: string) => void;
  /** Opens the filter drawer to pick any endpoint. */
  onSwitchEndpoint?: () => void;
}

const VARIANT_CONFIG = {
  'no-endpoints': {
    icon: EndpointsIcon,
    title: 'No endpoints in this project',
    description:
      'Create an endpoint to view requirement insights for your AI application.',
    actionLabel: 'Go to Endpoints',
    href: '/endpoints',
  },
  'no-test-results': {
    icon: PlayArrowIcon,
    title: 'No test results yet',
    description:
      'Run a test set against your endpoint to generate your first test run and view requirement insights.',
    actionLabel: 'Go to Test Sets',
    href: '/test-sets',
  },
} as const;

function noResultsCopy(
  endpointName: string | undefined,
  endpointsWithResults: InsightsEndpointOption[],
  hasOtherEndpoints: boolean
): { title: string; description: string } {
  if (!endpointName) return VARIANT_CONFIG['no-test-results'];
  const title = `No test results for ${endpointName} yet`;
  if (endpointsWithResults.length > 0) {
    return {
      title,
      description: `Insights show one endpoint at a time. Switch to an endpoint that has results, or run a test set against ${endpointName}.`,
    };
  }
  return {
    title,
    description: hasOtherEndpoints
      ? `Run a test set against ${endpointName}, or switch to another endpoint.`
      : `Run a test set against ${endpointName} to generate your first test run and view requirement insights.`,
  };
}

export default function InsightsEmptyState({
  variant,
  endpointName,
  endpointsWithResults = [],
  hasOtherEndpoints = false,
  onSelectEndpoint,
  onSwitchEndpoint,
}: InsightsEmptyStateProps) {
  const router = useRouter();
  const config = VARIANT_CONFIG[variant];
  const copy =
    variant === 'no-test-results'
      ? noResultsCopy(endpointName, endpointsWithResults, hasOtherEndpoints)
      : config;
  const showSwitch =
    variant === 'no-test-results' && hasOtherEndpoints && !!onSwitchEndpoint;
  const secondaryActions = [
    ...(showSwitch && onSwitchEndpoint
      ? [
          {
            id: 'switch-endpoint',
            label: 'Switch endpoint',
            onAction: onSwitchEndpoint,
          },
        ]
      : []),
    ...(onSelectEndpoint
      ? endpointsWithResults.map(endpoint => ({
          id: `show-${endpoint.id}`,
          label: `Show ${endpoint.name}`,
          onAction: () => onSelectEndpoint(endpoint.id),
        }))
      : []),
  ];

  return (
    <Box sx={{ mt: 2, mb: 2, width: '100%' }}>
      <EntityEmptyState
        card
        icon={config.icon}
        title={copy.title}
        description={copy.description}
        actionLabel={config.actionLabel}
        onAction={() => router.push(config.href)}
        showAddIcon={false}
        secondaryActions={secondaryActions}
      />
    </Box>
  );
}
