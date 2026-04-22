'use client';

import React, {
  forwardRef,
  useCallback,
  useEffect,
  useImperativeHandle,
  useMemo,
  useRef,
  useState,
} from 'react';
import { MentionsInput, Mention, SuggestionDataItem } from 'react-mentions';
import {
  Box,
  IconButton,
  Typography,
  Chip,
  CircularProgress,
  useTheme,
} from '@mui/material';
import { alpha } from '@mui/material/styles';
import SendIcon from '@mui/icons-material/Send';
import AttachFileIcon from '@mui/icons-material/AttachFile';
import CloseIcon from '@mui/icons-material/Close';
import InsertDriveFileIcon from '@mui/icons-material/InsertDriveFile';
import { ApiClientFactory } from '@/utils/api-client/client-factory';

export interface MentionItem {
  type: string;
  id: string;
  display: string;
}

export interface FileAttachment {
  filename: string;
  content_type: string;
  data: string;
  size: number;
}

export interface Attachments {
  mentions?: MentionItem[];
  files?: FileAttachment[];
}

const ENTITY_TYPES: Record<string, { label: string; fetchKey: string }> = {
  endpoint: { label: 'Endpoints', fetchKey: 'endpoints' },
  metric: { label: 'Metrics', fetchKey: 'metrics' },
  test_set: { label: 'Test Sets', fetchKey: 'test-sets' },
  behavior: { label: 'Behaviors', fetchKey: 'behaviors' },
  test_run: { label: 'Test Runs', fetchKey: 'test-runs' },
  source: { label: 'Knowledge Sources', fetchKey: 'sources' },
};

const TYPE_ORDER = Object.keys(ENTITY_TYPES);

const ACCEPTED_FILE_EXTENSIONS = [
  '.pdf',
  '.docx',
  '.pptx',
  '.xlsx',
  '.txt',
  '.md',
  '.csv',
  '.json',
  '.yaml',
  '.yml',
  '.xml',
  '.html',
  '.htm',
  '.py',
  '.js',
  '.ts',
].join(',');

const MAX_FILE_SIZE = 5 * 1024 * 1024;

export interface ArchitectChatInputHandle {
  focus: () => void;
}

interface ArchitectChatInputProps {
  onSend: (message: string, attachments?: Attachments) => void;
  disabled?: boolean;
  isLoading?: boolean;
  isConnected?: boolean;
  sessionToken?: string;
}

interface ExtendedSuggestion extends SuggestionDataItem {
  entityType: string;
}

/**
 * Parse react-mentions markup into clean text and structured mentions.
 *
 * Markup format: `@[Display Name](type:uuid)`
 * Output text:   `@type:Display Name`
 */
export function extractMentions(markup: string): {
  text: string;
  mentions: MentionItem[];
} {
  const mentions: MentionItem[] = [];
  const text = markup.replace(
    /@\[([^\]]+)\]\(([^:]+):([^)]+)\)/g,
    (_match, display, type, id) => {
      mentions.push({ type, id, display });
      return `@${type}:${display}`;
    }
  );
  return { text, mentions };
}

function formatFileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

const ArchitectChatInput = forwardRef<
  ArchitectChatInputHandle,
  ArchitectChatInputProps
>(function ArchitectChatInput(
  {
    onSend,
    disabled = false,
    isLoading = false,
    isConnected = true,
    sessionToken,
  },
  ref
) {
  const theme = useTheme();
  const [value, setValue] = useState('');
  const [files, setFiles] = useState<FileAttachment[]>([]);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const mentionsInputRef = useRef<HTMLTextAreaElement | null>(null);
  const debounceRef = useRef<Record<string, ReturnType<typeof setTimeout>>>({});

  useImperativeHandle(ref, () => ({
    focus: () => mentionsInputRef.current?.focus(),
  }));

  useEffect(() => {
    if (!disabled && isConnected && mentionsInputRef.current) {
      mentionsInputRef.current.focus();
    }
  }, [disabled, isConnected]);

  const typeColors = useMemo(
    () => ({
      endpoint: theme.palette.info.main,
      metric: theme.palette.secondary.main,
      test_set: theme.palette.success.main,
      behavior: theme.palette.warning.main,
      test_run: theme.palette.primary.main,
      source: theme.palette.error.main,
    }),
    [theme]
  );

  const fetchSuggestions = useCallback(
    (search: string, callback: (data: SuggestionDataItem[]) => void) => {
      if (!sessionToken) {
        callback([]);
        return;
      }

      const lowerSearch = search.toLowerCase();
      let targetType: string | null = null;
      let nameQuery = lowerSearch;

      for (const type of TYPE_ORDER) {
        const prefix = `${type}:`;
        if (lowerSearch.startsWith(prefix)) {
          targetType = type;
          nameQuery = lowerSearch.slice(prefix.length);
          break;
        }
      }

      if (!targetType) {
        const typeHints: ExtendedSuggestion[] = TYPE_ORDER.filter(
          t =>
            t.startsWith(lowerSearch) ||
            ENTITY_TYPES[t].label.toLowerCase().startsWith(lowerSearch)
        ).map(t => ({
          id: `_hint_${t}`,
          display: `${t}: (type to search ${ENTITY_TYPES[t].label.toLowerCase()})`,
          entityType: '_hint',
        }));
        callback(typeHints);
        return;
      }

      if (nameQuery.length < 1) {
        callback([]);
        return;
      }

      const debounceKey = `${targetType}:${nameQuery}`;
      if (debounceRef.current[debounceKey]) {
        clearTimeout(debounceRef.current[debounceKey]);
      }

      debounceRef.current[debounceKey] = setTimeout(async () => {
        try {
          const factory = new ApiClientFactory(sessionToken);
          const odataFilter = `contains(tolower(name), '${nameQuery}')`;

          let results: Array<{ id: string; name: string }> = [];

          if (targetType === 'endpoint') {
            const resp = await factory
              .getEndpointsClient()
              .getEndpoints({ skip: 0, limit: 10, $filter: odataFilter });
            results = resp.data;
          } else if (targetType === 'metric') {
            const resp = await factory
              .getMetricsClient()
              .getMetrics({ skip: 0, limit: 10, $filter: odataFilter });
            results = resp.data;
          } else if (targetType === 'test_set') {
            const resp = await factory
              .getTestSetsClient()
              .getTestSets({ skip: 0, limit: 10, $filter: odataFilter });
            results = resp.data;
          } else if (targetType === 'behavior') {
            const items = await factory
              .getBehaviorClient()
              .getBehaviors({ skip: 0, limit: 10, $filter: odataFilter });
            results = items;
          } else if (targetType === 'test_run') {
            const resp = await factory
              .getTestRunsClient()
              .getTestRuns({ skip: 0, limit: 10, filter: odataFilter });
            results = resp.data;
          } else if (targetType === 'source') {
            const resp = await factory
              .getSourcesClient()
              .getSources({
                skip: 0,
                limit: 10,
                $filter: `contains(tolower(title), '${nameQuery}')`,
              });
            results = resp.data.map(s => ({ id: s.id as string, name: s.title }));
          }

          const suggestions: ExtendedSuggestion[] = results
            .filter(r => r.name)
            .map(r => ({
              id: `${targetType}:${r.id}`,
              display: r.name,
              entityType: targetType!,
            }));
          callback(suggestions);
        } catch (err) {
          console.error(`Failed to fetch ${targetType} suggestions:`, err);
          callback([]);
        }
      }, 300);
    },
    [sessionToken]
  );

  const renderSuggestion = useCallback(
    (
      suggestion: SuggestionDataItem,
      _search: string,
      _highlightedDisplay: React.ReactNode,
      _index: number,
      focused: boolean
    ) => {
      const item = suggestion as ExtendedSuggestion;
      const isHint = item.entityType === '_hint';
      const color = isHint
        ? theme.palette.text.secondary
        : (typeColors[item.entityType as keyof typeof typeColors] ??
          theme.palette.text.primary);

      return (
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
            cursor: isHint ? 'default' : 'pointer',
            opacity: isHint ? 0.7 : 1,
          }}
        >
          {!isHint && (
            <Box
              sx={{
                width: theme.spacing(1),
                height: theme.spacing(1),
                borderRadius: '50%',
                backgroundColor: color,
                flexShrink: 0,
              }}
            />
          )}
          <Typography
            variant="body2"
            sx={{ fontStyle: isHint ? 'italic' : 'normal' }}
          >
            {item.display ?? ''}
          </Typography>
        </Box>
      );
    },
    [theme, typeColors]
  );

  const handleSend = useCallback(() => {
    if (!value.trim() || disabled || isLoading) return;

    const { text, mentions } = extractMentions(value);
    const attachments: Attachments = {};

    if (mentions.length > 0) attachments.mentions = mentions;
    if (files.length > 0) attachments.files = files;

    const hasAttachments =
      (attachments.mentions?.length ?? 0) > 0 ||
      (attachments.files?.length ?? 0) > 0;

    onSend(text, hasAttachments ? attachments : undefined);
    setValue('');
    setFiles([]);
  }, [value, files, disabled, isLoading, onSend]);

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent) => {
      if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        handleSend();
      }
    },
    [handleSend]
  );

  const handleFileSelect = useCallback(
    async (e: React.ChangeEvent<HTMLInputElement>) => {
      const selected = e.target.files;
      if (!selected) return;

      const newFiles: FileAttachment[] = [];
      for (const file of Array.from(selected)) {
        if (file.size > MAX_FILE_SIZE) {
          console.warn(
            `File ${file.name} exceeds ${formatFileSize(MAX_FILE_SIZE)} limit`
          );
          continue;
        }
        let data: string;
        try {
          data = await new Promise<string>((resolve, reject) => {
            const reader = new FileReader();
            reader.onload = () => {
              const result = reader.result as string;
              if (!result || !result.includes(',')) {
                reject(new Error('Invalid data URL format'));
                return;
              }
              resolve(result.split(',')[1]);
            };
            reader.onerror = () => reject(new Error('Failed to read file'));
            reader.onabort = () => reject(new Error('File read aborted'));
            reader.readAsDataURL(file);
          });
        } catch (err) {
          console.error(`Failed to read file ${file.name}:`, err);
          continue;
        }
        newFiles.push({
          filename: file.name,
          content_type: file.type || 'application/octet-stream',
          data,
          size: file.size,
        });
      }

      setFiles(prev => [...prev, ...newFiles]);
      if (fileInputRef.current) fileInputRef.current.value = '';
    },
    []
  );

  const removeFile = useCallback((index: number) => {
    setFiles(prev => prev.filter((_, i) => i !== index));
  }, []);

  const mentionStyle = useMemo(
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

  const inputDisabled = disabled || !isConnected || isLoading;
  const canSend = value.trim().length > 0 && !inputDisabled;
  const borderColor = theme.palette.divider;
  const focusBorderColor = theme.palette.primary.main;

  return (
    <Box
      sx={{
        p: 2,
        borderTop: 1,
        borderColor: 'divider',
        bgcolor: 'background.paper',
      }}
    >
      {files.length > 0 && (
        <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.5, mb: 1 }}>
          {files.map((f, i) => (
            <Chip
              key={`${f.filename}-${i}`}
              icon={<InsertDriveFileIcon />}
              label={`${f.filename} (${formatFileSize(f.size)})`}
              size="small"
              variant="outlined"
              onDelete={() => removeFile(i)}
              deleteIcon={<CloseIcon />}
            />
          ))}
        </Box>
      )}

      <Box sx={{ display: 'flex', gap: 1, alignItems: 'flex-end' }}>
        <IconButton
          size="small"
          onClick={() => fileInputRef.current?.click()}
          disabled={inputDisabled}
          sx={{ color: 'text.secondary', mb: 0.5 }}
        >
          <AttachFileIcon fontSize="small" />
        </IconButton>
        <input
          ref={fileInputRef}
          type="file"
          multiple
          accept={ACCEPTED_FILE_EXTENSIONS}
          style={{ display: 'none' }}
          onChange={handleFileSelect}
        />

        <Box sx={{ flex: 1 }}>
          <MentionsInput
            inputRef={mentionsInputRef}
            value={value}
            onChange={e => setValue(e.target.value)}
            onKeyDown={handleKeyDown}
            disabled={inputDisabled}
            placeholder={
              isConnected
                ? 'Describe what you want to test... (@ to mention entities)'
                : 'Waiting for connection...'
            }
            style={{
              control: {
                fontSize: theme.typography.body2.fontSize,
                fontFamily: theme.typography.fontFamily,
                minHeight: theme.spacing(5),
              },
              input: {
                padding: `${theme.spacing(1)} ${theme.spacing(1.5)}`,
                border: `1px solid ${borderColor}`,
                borderRadius: `${theme.shape.borderRadius}px`,
                outline: 'none',
                fontSize: theme.typography.body2.fontSize,
                fontFamily: theme.typography.fontFamily,
                lineHeight: '1.5',
                color: theme.palette.text.primary,
                backgroundColor: 'transparent',
                overflow: 'auto',
                maxHeight: theme.spacing(16),
              },
              highlighter: {
                padding: `${theme.spacing(1)} ${theme.spacing(1.5)}`,
                border: '1px solid transparent',
                borderRadius: `${theme.shape.borderRadius}px`,
                fontSize: theme.typography.body2.fontSize,
                fontFamily: theme.typography.fontFamily,
                lineHeight: '1.5',
                pointerEvents: 'none' as const,
              },
              suggestions: {
                backgroundColor: 'transparent',
                borderRadius: `${(theme.shape.borderRadius as number) * 2}px`,
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
                  minHeight: theme.spacing(5),
                },
                input: {
                  overflow: 'auto',
                  maxHeight: theme.spacing(16),
                },
                highlighter: {
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
                  borderRadius: `${(theme.shape.borderRadius as number) * 2}px`,
                  boxShadow: [
                    `0 0 ${theme.spacing(1)} ${alpha(theme.palette.primary.main, 0.15)}`,
                    `0 0 ${theme.spacing(3)} ${alpha(theme.palette.primary.main, 0.08)}`,
                  ].join(', '),
                }}
              >
                {children}
              </Box>
            )}
            a11ySuggestionsListLabel="Entity suggestions"
            onFocus={e => {
              const target = e.target as HTMLElement;
              if (target.style) {
                target.style.borderColor = focusBorderColor;
                target.style.borderWidth = '2px';
              }
            }}
            onBlur={e => {
              const target = e.target as HTMLElement;
              if (target.style) {
                target.style.borderColor = borderColor;
                target.style.borderWidth = '1px';
              }
            }}
          >
            <Mention
              trigger="@"
              data={fetchSuggestions}
              renderSuggestion={renderSuggestion}
              markup="@[__display__](__id__)"
              displayTransform={(_id: string, display: string) => `@${display}`}
              appendSpaceOnAdd
              style={mentionStyle}
            />
          </MentionsInput>
        </Box>

        <IconButton
          color="primary"
          onClick={handleSend}
          disabled={!canSend}
          sx={{
            width: theme.spacing(5),
            height: theme.spacing(5),
            mb: 0.5,
            bgcolor: 'primary.main',
            color: 'primary.contrastText',
            '&:hover': { bgcolor: 'primary.dark' },
            '&:disabled': {
              bgcolor: 'action.disabledBackground',
              color: 'action.disabled',
            },
          }}
        >
          {isLoading ? (
            <CircularProgress size={20} color="inherit" />
          ) : (
            <SendIcon />
          )}
        </IconButton>
      </Box>
    </Box>
  );
});

export default ArchitectChatInput;
