import {
  SEMANTIC_LAYER_ICONS,
  SEMANTIC_LAYER_COLORS,
} from '@/constants/semantic-layer-icons';
import { GENERIC_SPAN_TYPE, getSpanTypeInfo } from '@/constants/span-types';
import type { SpanNode } from '@/utils/api-client/interfaces/telemetry';

type SpanLike = Pick<SpanNode, 'span_name'> & {
  span_type?: string | null;
};

// Generic spans fall back to the name prefix, so function./db./http. spans keep
// their own icons rather than all turning grey.
function hasSpecificType(span: SpanLike): span is SpanLike & {
  span_type: string;
} {
  return !!span.span_type && span.span_type !== GENERIC_SPAN_TYPE;
}

export function getSpanIcon(span: SpanLike): React.ComponentType {
  if (hasSpecificType(span)) {
    return getSpanTypeInfo(span.span_type).icon;
  }

  const spanName = span.span_name;

  // Check for exact matches first
  if (spanName in SEMANTIC_LAYER_ICONS) {
    return SEMANTIC_LAYER_ICONS[spanName as keyof typeof SEMANTIC_LAYER_ICONS];
  }

  // Check for pattern matches
  for (const [pattern, icon] of Object.entries(SEMANTIC_LAYER_ICONS)) {
    if (pattern !== 'default' && spanName.startsWith(pattern)) {
      return icon;
    }
  }

  return SEMANTIC_LAYER_ICONS.default;
}

export function getSpanColor(span: SpanLike, statusCode: string): string {
  // Error state takes priority
  if (statusCode === 'ERROR') {
    return SEMANTIC_LAYER_COLORS.error;
  }

  if (hasSpecificType(span)) {
    return getSpanTypeInfo(span.span_type).color;
  }

  const spanName = span.span_name;

  // Check for exact matches
  if (spanName in SEMANTIC_LAYER_COLORS) {
    return SEMANTIC_LAYER_COLORS[
      spanName as keyof typeof SEMANTIC_LAYER_COLORS
    ];
  }

  // Check for pattern matches
  for (const [pattern, color] of Object.entries(SEMANTIC_LAYER_COLORS)) {
    if (
      pattern !== 'default' &&
      pattern !== 'error' &&
      spanName.includes(pattern)
    ) {
      return color;
    }
  }

  return SEMANTIC_LAYER_COLORS.default;
}
