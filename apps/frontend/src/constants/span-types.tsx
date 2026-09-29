import type React from 'react';
import SortIcon from '@mui/icons-material/Sort';
import FactCheckIcon from '@mui/icons-material/FactCheck';
import ShieldIcon from '@mui/icons-material/Shield';
import TransformIcon from '@mui/icons-material/Transform';
import {
  SEMANTIC_LAYER_COLORS,
  SEMANTIC_LAYER_ICONS,
} from '@/constants/semantic-layer-icons';

export interface SpanTypeInfo {
  label: string;
  icon: React.ComponentType;
  /** Theme colour path, e.g. 'success.main'. */
  color: string;
}

/** The generic type the backend gives a span with no operation type and no model. */
export const GENERIC_SPAN_TYPE = 'span';

/**
 * Label, icon and colour per `span_type` (the backend's Trace.span_type values).
 * Icons and colours come from the span-name map so the two cannot drift.
 */
export const SPAN_TYPES: Record<string, SpanTypeInfo> = {
  'llm.invoke': {
    label: 'LLM call',
    icon: SEMANTIC_LAYER_ICONS['ai.llm.invoke'],
    color: SEMANTIC_LAYER_COLORS['ai.llm.invoke'],
  },
  'tool.invoke': {
    label: 'Tool',
    icon: SEMANTIC_LAYER_ICONS['ai.tool.invoke'],
    color: SEMANTIC_LAYER_COLORS['ai.tool.invoke'],
  },
  'agent.invoke': {
    label: 'Agent',
    icon: SEMANTIC_LAYER_ICONS['ai.agent.invoke'],
    color: SEMANTIC_LAYER_COLORS['ai.agent.invoke'],
  },
  'agent.handoff': {
    label: 'Agent handoff',
    icon: SEMANTIC_LAYER_ICONS['ai.agent.handoff'],
    color: SEMANTIC_LAYER_COLORS['ai.agent.handoff'],
  },
  retrieval: {
    label: 'Retrieval',
    icon: SEMANTIC_LAYER_ICONS['ai.retrieval'],
    color: SEMANTIC_LAYER_COLORS['ai.retrieval'],
  },
  'embedding.create': {
    label: 'Embedding',
    icon: SEMANTIC_LAYER_ICONS['ai.embedding'],
    color: SEMANTIC_LAYER_COLORS['ai.embedding'],
  },
  rerank: { label: 'Rerank', icon: SortIcon, color: 'info.light' },
  evaluation: {
    label: 'Evaluation',
    icon: FactCheckIcon,
    color: 'success.dark',
  },
  guardrail: { label: 'Guardrail', icon: ShieldIcon, color: 'warning.light' },
  transform: {
    label: 'Transform',
    icon: TransformIcon,
    color: 'primary.light',
  },
  [GENERIC_SPAN_TYPE]: {
    label: 'Span',
    icon: SEMANTIC_LAYER_ICONS.default,
    color: SEMANTIC_LAYER_COLORS.default,
  },
};

/** Info for a span type. An unknown type keeps its raw key as the label. */
export function getSpanTypeInfo(type: string | null | undefined): SpanTypeInfo {
  if (!type) {
    return SPAN_TYPES[GENERIC_SPAN_TYPE];
  }
  if (Object.hasOwn(SPAN_TYPES, type)) {
    return SPAN_TYPES[type];
  }
  return {
    label: type,
    icon: SEMANTIC_LAYER_ICONS.default,
    color: SEMANTIC_LAYER_COLORS.default,
  };
}

export function spanTypeLabel(type: string | null | undefined): string {
  return getSpanTypeInfo(type).label;
}
