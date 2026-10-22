'use client';

import React from 'react';
import { Box, Tooltip } from '@mui/material';
import type { SvgIconProps } from '@mui/material/SvgIcon';
import { BuildIcon, ForumIcon, MenuBookIcon } from '@/components/icons';
import TracesIcon from '@/components/TracesIcon';
import type { Endpoint } from '@/utils/api-client/interfaces/endpoint';

// Response keys the backend accepts as a conversation id (see the docs' response variables).
const CONVERSATION_FIELDS = [
  'conversation_id',
  'session_id',
  'thread_id',
  'chat_id',
  'dialog_id',
  'dialogue_id',
  'context_id',
  'interaction_id',
];
const MULTI_TURN_REQUEST_RE = /\{\{\s*(messages|conversation_id)\b/;

const isMapped = (value: unknown) =>
  typeof value === 'string' && value.trim() !== '';

/** Tool calls reach metrics only when the response mapping names them. */
export function hasToolCallMapping(endpoint: Endpoint): boolean {
  return isMapped(endpoint.response_mapping?.tool_calls);
}

/** Multi-turn needs a conversation id back, or the history sent in the request. */
export function supportsMultiTurn(endpoint: Endpoint): boolean {
  const response = endpoint.response_mapping ?? {};
  if (CONVERSATION_FIELDS.some(field => isMapped(response[field]))) {
    return true;
  }
  return MULTI_TURN_REQUEST_RE.test(
    JSON.stringify(endpoint.request_mapping ?? {})
  );
}

export function hasContextMapping(endpoint: Endpoint): boolean {
  return isMapped(endpoint.response_mapping?.context);
}

function CaptureIcon({
  label,
  on,
  tooltip,
  Icon,
}: {
  label: string;
  on: boolean;
  tooltip: string;
  Icon: React.ComponentType<SvgIconProps>;
}) {
  return (
    <Tooltip
      title={
        <>
          <strong>{label}</strong>: {tooltip}
        </>
      }
    >
      <Box
        component="span"
        role="img"
        aria-label={`${label}: ${on ? 'yes' : 'no'}`}
        sx={{ display: 'inline-flex' }}
      >
        <Icon
          fontSize="small"
          sx={{ color: on ? 'success.main' : 'text.disabled' }}
        />
      </Box>
    </Tooltip>
  );
}

/** What an endpoint gives Rhesis beyond its output; grey means not set up. */
export default function EndpointCaptures({ endpoint }: { endpoint: Endpoint }) {
  const tracing = !endpoint.disable_tracing;
  const toolCalls = hasToolCallMapping(endpoint);
  const multiTurn = supportsMultiTurn(endpoint);
  const context = hasContextMapping(endpoint);
  return (
    <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5 }}>
      <CaptureIcon
        label="Tracing"
        Icon={TracesIcon}
        on={tracing}
        tooltip={
          tracing
            ? 'on, calls to this endpoint create traces.'
            : 'off, calls to this endpoint create no traces.'
        }
      />
      <CaptureIcon
        label="Tool calls"
        Icon={BuildIcon}
        on={toolCalls}
        tooltip={
          toolCalls
            ? 'mapped, so tool-use metrics can read them.'
            : 'not in the response mapping, so tool-use metrics have nothing to read.'
        }
      />
      <CaptureIcon
        label="Multi-turn"
        Icon={ForumIcon}
        on={multiTurn}
        tooltip={
          multiTurn
            ? 'the endpoint keeps a conversation, so multi-turn tests can run.'
            : 'no conversation id or message history is mapped, so multi-turn tests cannot run.'
        }
      />
      <CaptureIcon
        label="Context"
        Icon={MenuBookIcon}
        on={context}
        tooltip={
          context
            ? 'mapped, so context metrics such as faithfulness can read it.'
            : 'not in the response mapping, so context metrics have nothing to read.'
        }
      />
    </Box>
  );
}
