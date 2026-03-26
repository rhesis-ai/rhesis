import React from 'react';
import ChatBubbleOutlineIcon from '@mui/icons-material/ChatBubbleOutline';
import MessageIcon from '@mui/icons-material/Message';
import TurnedInIcon from '@mui/icons-material/TurnedIn';
import TimelineIcon from '@mui/icons-material/Timeline';

/**
 * Supported metric scope values — single source of truth for the frontend.
 * Add new scopes here as the backend introduces them.
 */
export const METRIC_SCOPES = {
  SINGLE_TURN: 'Single-Turn',
  MULTI_TURN: 'Multi-Turn',
  TRACE: 'Trace',
} as const;

export type MetricScopeValue =
  (typeof METRIC_SCOPES)[keyof typeof METRIC_SCOPES];

/**
 * Returns the icon component for a given metric scope value.
 * Falls back to a generic bookmark icon for unknown/future scopes.
 */
export function getMetricScopeIcon(scope: string): React.ReactElement {
  switch (scope) {
    case METRIC_SCOPES.SINGLE_TURN:
      return <ChatBubbleOutlineIcon fontSize="small" />;
    case METRIC_SCOPES.MULTI_TURN:
      return <MessageIcon fontSize="small" />;
    case METRIC_SCOPES.TRACE:
      return <TimelineIcon fontSize="small" />;
    default:
      return <TurnedInIcon fontSize="small" />;
  }
}
