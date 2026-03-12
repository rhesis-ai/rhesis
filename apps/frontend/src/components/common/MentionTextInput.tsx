'use client';

import React, { useCallback, useEffect, useMemo, useRef } from 'react';
import { MentionsInput, Mention, SuggestionDataItem } from 'react-mentions';
import { Box, Typography, useTheme, FormHelperText } from '@mui/material';
import { alpha } from '@mui/material/styles';
import {
  REVIEW_TARGET_TYPES,
  type ReviewTargetType,
} from '@/utils/api-client/interfaces/test-results';

export interface MentionOption {
  id: string;
  display: string;
  type: 'user' | 'metric' | 'turn';
}

interface MentionTextInputProps {
  value: string;
  onChange: (value: string) => void;
  mentionableUsers?: MentionOption[];
  mentionableMetrics?: MentionOption[];
  mentionableTurns?: MentionOption[];
  placeholder?: string;
  label?: string;
  minRows?: number;
  disabled?: boolean;
  error?: boolean;
  helperText?: string;
}

interface ExtendedSuggestionDataItem extends SuggestionDataItem {
  type: 'user' | 'metric' | 'turn';
}

const GROUP_LABELS: Record<string, string> = {
  user: 'Users',
  metric: 'Metrics',
  turn: 'Turns',
};

const TYPE_ORDER: Record<string, number> = {
  user: 0,
  metric: 1,
  turn: 2,
};

export default function MentionTextInput({
  value,
  onChange,
  mentionableUsers = [],
  mentionableMetrics = [],
  mentionableTurns = [],
  placeholder = 'Type @ to mention users, metrics, or turns...',
  label,
  minRows = 4,
  disabled = false,
  error = false,
  helperText,
}: MentionTextInputProps) {
  const theme = useTheme();

  const combinedData: ExtendedSuggestionDataItem[] = useMemo(() => {
    const items: ExtendedSuggestionDataItem[] = [
      ...mentionableUsers.map(u => ({
        id: `user:${u.id}`,
        display: u.display,
        type: 'user' as const,
      })),
      ...mentionableMetrics.map(m => ({
        id: `metric:${m.id}`,
        display: m.display,
        type: 'metric' as const,
      })),
      ...mentionableTurns.map(t => ({
        id: `turn:${t.id}`,
        display: t.display,
        type: 'turn' as const,
      })),
    ];
    items.sort(
      (a, b) =>
        TYPE_ORDER[a.type] - TYPE_ORDER[b.type] ||
        (a.display ?? '').localeCompare(b.display ?? '')
    );
    return items;
  }, [mentionableUsers, mentionableMetrics, mentionableTurns]);

  const handleChange = useCallback(
    (_event: { target: { value: string } }) => {
      onChange(_event.target.value);
    },
    [onChange]
  );

  const typeColors = useMemo(
    () => ({
      user: theme.palette.success.main,
      metric: theme.palette.secondary.main,
      turn: theme.palette.info.main,
    }),
    [theme]
  );

  const filteredDataRef = useRef<ExtendedSuggestionDataItem[]>([]);

  const renderSuggestion = useCallback(
    (
      suggestion: SuggestionDataItem,
      _search: string,
      _highlightedDisplay: React.ReactNode,
      index: number,
      focused: boolean
    ) => {
      const item = suggestion as ExtendedSuggestionDataItem;
      const prevItem =
        index > 0 ? filteredDataRef.current[index - 1] : null;
      const showGroupHeader = !prevItem || prevItem.type !== item.type;

      return (
        <Box>
          {showGroupHeader && (
            <Typography
              variant="caption"
              sx={{
                display: 'block',
                px: 1.5,
                pt: index > 0 ? 1 : 0.5,
                pb: 0.5,
                fontWeight: theme.typography.fontWeightBold,
                color: theme.palette.text.secondary,
                textTransform: 'uppercase',
                letterSpacing: 0.5,
                fontSize: theme.typography.caption.fontSize,
                pointerEvents: 'none',
              }}
            >
              {GROUP_LABELS[item.type]}
            </Typography>
          )}
          <Box
            sx={{
              px: 1.5,
              py: 0.75,
              display: 'flex',
              alignItems: 'center',
              gap: 1,
              backgroundColor: focused
                ? theme.palette.action.hover
                : 'transparent',
              cursor: 'pointer',
              '&:hover': {
                backgroundColor: theme.palette.action.hover,
              },
            }}
          >
            <Box
              sx={{
                width: theme.spacing(1),
                height: theme.spacing(1),
                borderRadius: theme.shape.circular,
                backgroundColor: typeColors[item.type],
                flexShrink: 0,
              }}
            />
            <Typography variant="body2">{item.display ?? ''}</Typography>
          </Box>
        </Box>
      );
    },
    [theme, typeColors]
  );

  const mentionHighlightStyle = useMemo(
    () => ({
      backgroundColor: alpha(
        theme.palette.primary.main,
        theme.palette.action.activatedOpacity
      ),
      borderRadius: `${theme.shape.borderRadius}px`,
      position: 'relative' as const,
      zIndex: 1,
    }),
    [theme]
  );

  const containerRef = useRef<HTMLDivElement>(null);

  const mentionTypeMap = useMemo(() => {
    const map = new Map<string, 'user' | 'metric' | 'turn'>();
    const regex = /@\[([^\]]+)\]\(((?:user|metric|turn):[^)]*(?:\([^)]*\))*[^)]*)\)/g;
    let match;
    while ((match = regex.exec(value)) !== null) {
      map.set(`@${match[1]}`, match[2].split(':')[0] as 'user' | 'metric' | 'turn');
    }
    return map;
  }, [value]);

  const applyHighlightColors = useCallback(() => {
    if (!containerRef.current || mentionTypeMap.size === 0) return;
    const mentionElements = containerRef.current.querySelectorAll('strong');
    mentionElements.forEach((el) => {
      const text = el.textContent?.trim();
      if (text && mentionTypeMap.has(text)) {
        const type = mentionTypeMap.get(text)!;
        const color = typeColors[type];
        el.style.backgroundColor = alpha(
          color,
          theme.palette.action.activatedOpacity
        );
        el.style.borderRadius = `${theme.shape.borderRadius}px`;
      }
    });
  }, [mentionTypeMap, typeColors, theme]);

  useEffect(() => {
    applyHighlightColors();
    if (!containerRef.current) return;
    const observer = new MutationObserver(applyHighlightColors);
    observer.observe(containerRef.current, {
      childList: true,
      subtree: true,
      characterData: true,
    });
    return () => observer.disconnect();
  }, [applyHighlightColors]);

  const borderColor = error
    ? theme.palette.error.main
    : theme.palette.divider;

  const focusBorderColor = error
    ? theme.palette.error.main
    : theme.palette.primary.main;

  const verticalPadding = theme.spacing(1.5);
  const minHeight = `calc(${minRows} * ${theme.typography.body2.lineHeight}em + ${verticalPadding} * 2)`;

  return (
    <Box ref={containerRef}>
      {label && (
        <Typography
          variant="body2"
          fontWeight={600}
          sx={{ mb: 1, color: error ? theme.palette.error.main : undefined }}
        >
          {label}
        </Typography>
      )}
      <MentionsInput
        value={value}
        onChange={handleChange}
        placeholder={placeholder}
        disabled={disabled}
        style={{
          control: {
            fontSize: theme.typography.body1.fontSize,
            fontFamily: theme.typography.fontFamily,
            minHeight,
          },
          input: {
            padding: `${theme.spacing(1.5)} ${theme.spacing(1.75)}`,
            border: `1px solid ${borderColor}`,
            borderRadius: `${theme.shape.borderRadius}px`,
            outline: 'none',
            fontSize: theme.typography.body2.fontSize,
            fontFamily: theme.typography.fontFamily,
            lineHeight: String(theme.typography.body2.lineHeight),
            color: theme.palette.text.primary,
            backgroundColor: 'transparent',
            overflow: 'auto',
            minHeight,
          },
          highlighter: {
            padding: `${theme.spacing(1.5)} ${theme.spacing(1.75)}`,
            border: '1px solid transparent',
            borderRadius: `${theme.shape.borderRadius}px`,
            fontSize: theme.typography.body2.fontSize,
            fontFamily: theme.typography.fontFamily,
            lineHeight: String(theme.typography.body2.lineHeight),
            minHeight,
            pointerEvents: 'none' as const,
          },
          suggestions: {
            backgroundColor: 'transparent',
            borderRadius: `${theme.shape.borderRadius * 2}px`,
            overflow: 'hidden',
            zIndex: theme.zIndex.modal + 1,
            list: {
              backgroundColor: 'transparent',
              border: 'none',
              padding: 0,
              margin: 0,
              listStyleType: 'none',
            },
          },
          '&multiLine': {
            control: {
              minHeight,
            },
            input: {
              minHeight,
              overflow: 'auto',
            },
            highlighter: {
              minHeight,
              pointerEvents: 'none' as const,
            },
          },
        }}
        customSuggestionsContainer={(children: React.ReactNode) => (
          <Box
            sx={{
              py: 0.5,
              maxHeight: theme.spacing(30),
              overflow: 'auto',
              backgroundColor: theme.palette.background.paper,
              borderRadius: `${theme.shape.borderRadius * 2}px`,
              boxShadow: [
                `0 0 ${theme.spacing(1)} ${alpha(theme.palette.primary.main, theme.palette.action.selectedOpacity * 2)}`,
                `0 0 ${theme.spacing(3)} ${alpha(theme.palette.primary.main, theme.palette.action.selectedOpacity)}`,
              ].join(', '),
              '&::-webkit-scrollbar': {
                width: theme.spacing(0.75),
              },
              '&::-webkit-scrollbar-thumb': {
                background: theme.palette.divider,
                borderRadius: theme.shape.borderRadius,
              },
            }}
          >
            {children}
          </Box>
        )}
        a11ySuggestionsListLabel="Mention suggestions"
        onFocus={(e) => {
          const target = e.target as HTMLElement;
          if (target.style) {
            target.style.borderColor = focusBorderColor;
            target.style.borderWidth = '2px';
          }
        }}
        onBlur={(e) => {
          const target = e.target as HTMLElement;
          if (target.style) {
            target.style.borderColor = borderColor;
            target.style.borderWidth = '1px';
          }
        }}
      >
        <Mention
          trigger="@"
          data={(search: string, callback: (data: SuggestionDataItem[]) => void) => {
            const filtered = combinedData.filter(item =>
              (item.display ?? '').toLowerCase().includes(search.toLowerCase())
            );
            filteredDataRef.current = filtered;
            callback(filtered);
          }}
          renderSuggestion={renderSuggestion}
          markup="@[__display__](__id__)"
          displayTransform={(_id: string, display: string) => `@${display}`}
          appendSpaceOnAdd
          style={mentionHighlightStyle}
        />
      </MentionsInput>
      {helperText && (
        <FormHelperText error={error} sx={{ mx: 1.75, mt: 0.375 }}>
          {helperText}
        </FormHelperText>
      )}
    </Box>
  );
}

/**
 * Render review text with styled mention chips.
 * Parses @[Display](type:id) patterns and renders them as colored spans.
 */
export function renderMentionText(
  text: string,
  typeColors: Record<string, string>,
  typeBackgrounds: Record<string, string>
): React.ReactNode {
  const mentionRegex = /@\[([^\]]+)\]\(((?:user|metric|turn):.+?)\)(?=\s|@\[|$)/g;
  const parts: React.ReactNode[] = [];
  let lastIndex = 0;
  let match;

  while ((match = mentionRegex.exec(text)) !== null) {
    if (match.index > lastIndex) {
      parts.push(text.slice(lastIndex, match.index));
    }
    const display = match[1];
    const id = match[2];
    const type = id.split(':')[0] as 'user' | 'metric' | 'turn';

    parts.push(
      <Box
        component="span"
        key={`mention-${match.index}`}
        sx={{
          color: typeColors[type] || 'inherit',
          backgroundColor: typeBackgrounds[type] || 'transparent',
          borderRadius: 0.5,
          px: 0.5,
          py: 0.125,
          fontWeight: 600,
          fontSize: 'inherit',
          whiteSpace: 'nowrap',
        }}
      >
        @{display}
      </Box>
    );
    lastIndex = match.index + match[0].length;
  }

  if (lastIndex < text.length) {
    parts.push(text.slice(lastIndex));
  }

  return parts.length > 0 ? <>{parts}</> : text;
}

export interface InferredTarget {
  type: ReviewTargetType;
  reference: string | null;
}

/**
 * Infer the review target from mention markup in comment text.
 * Returns the first metric or turn mention found; defaults to test_result.
 */
export function inferReviewTarget(text: string): InferredTarget {
  const mentionRegex =
    /@\[([^\]]+)\]\(((?:metric|turn):[^)]*(?:\([^)]*\))*[^)]*)\)/g;
  let match;

  while ((match = mentionRegex.exec(text)) !== null) {
    const display = match[1];
    const fullId = match[2];
    const type = fullId.split(':')[0];

    if (type === REVIEW_TARGET_TYPES.METRIC) {
      return { type: REVIEW_TARGET_TYPES.METRIC, reference: display };
    }
    if (type === REVIEW_TARGET_TYPES.TURN) {
      return { type: REVIEW_TARGET_TYPES.TURN, reference: display };
    }
  }

  return { type: REVIEW_TARGET_TYPES.TEST_RESULT, reference: null };
}
