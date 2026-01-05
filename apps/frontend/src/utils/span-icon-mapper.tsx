import {
  SEMANTIC_LAYER_ICONS,
  SEMANTIC_LAYER_COLORS,
} from '@/constants/semantic-layer-icons';

export function getSpanIcon(spanName: string): React.ComponentType {
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

export function getSpanColor(spanName: string, statusCode: string): string {
  // Error state takes priority
  if (statusCode === 'ERROR') {
    return SEMANTIC_LAYER_COLORS.error;
  }

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
