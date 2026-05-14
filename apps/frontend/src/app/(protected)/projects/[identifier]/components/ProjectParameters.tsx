'use client';

import * as React from 'react';
import { useCallback, useEffect, useMemo, useState } from 'react';
import {
  Alert,
  Box,
  Button,
  Checkbox,
  CircularProgress,
  FormControl,
  FormControlLabel,
  IconButton,
  InputLabel,
  MenuItem,
  Paper,
  Select,
  Stack,
  TextField,
  Tooltip,
  Typography,
} from '@mui/material';
import {
  AddIcon,
  ArrowBackIcon,
  ArrowOutwardIcon,
  CloseIcon,
  SaveIcon,
} from '@/components/icons';
import { ApiClientFactory } from '@/utils/api-client/client-factory';
import {
  ParameterField,
  ParameterSchema,
  ParameterType,
  ParameterValue,
  emptyParameterSchema,
} from '@/utils/api-client/interfaces/parameters';
import { useNotifications } from '@/components/common/NotificationContext';

interface ProjectParametersProps {
  projectId: string;
  sessionToken: string;
}

/** Closed list of supported types, paired with a human label. */
const TYPE_OPTIONS: ReadonlyArray<{ value: ParameterType; label: string }> = [
  { value: 'text', label: 'Text (multiline)' },
  { value: 'string', label: 'String (single-line)' },
  { value: 'integer', label: 'Integer' },
  { value: 'number', label: 'Number' },
  { value: 'boolean', label: 'Boolean' },
  { value: 'enum', label: 'Enum' },
  { value: 'model_ref', label: 'Model reference' },
  { value: 'secret_ref', label: 'Secret reference' },
];

/** Empty default for each type. Keeps the typed-default contract tight. */
function defaultForType(type: ParameterType): ParameterValue | null {
  switch (type) {
    case 'text':
      return { type: 'text', value: '' };
    case 'string':
      return { type: 'string', value: '' };
    case 'integer':
      return { type: 'integer', value: 0 };
    case 'number':
      return { type: 'number', value: 0 };
    case 'boolean':
      return { type: 'boolean', value: false };
    case 'enum':
      return null;
    case 'model_ref':
    case 'secret_ref':
      return null;
  }
}

function blankField(displayOrder: number): ParameterField {
  return {
    name: '',
    type: 'string',
    required: false,
    description: '',
    default: null,
    options: null,
    display_order: displayOrder,
  };
}

/** Stable client-side key for React lists. Keys never reach the server. */
function stableKey(prefix: string): string {
  return `${prefix}_${Math.random().toString(36).slice(2, 10)}`;
}

interface FieldRowState extends ParameterField {
  _key: string;
}

/**
 * Editor for a project's parameter schema.
 *
 * The component owns a draft list of fields; saving submits the full
 * schema in a single `PUT`. Reorder + add + remove are local-only until
 * the user explicitly clicks Save, mirroring how the backend treats the
 * resource as one atomic document.
 */
export default function ProjectParameters({
  projectId,
  sessionToken,
}: ProjectParametersProps) {
  const notifications = useNotifications();

  const [serverSchema, setServerSchema] = useState<ParameterSchema | null>(
    null
  );
  const [draft, setDraft] = useState<FieldRowState[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [saving, setSaving] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  const apiFactory = useMemo(
    () => new ApiClientFactory(sessionToken),
    [sessionToken]
  );

  const fetchSchema = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const client = apiFactory.getParametersClient();
      const schema = await client.getSchema(projectId);
      setServerSchema(schema);
      setDraft(
        schema.fields.map(field => ({ ...field, _key: stableKey('f') }))
      );
    } catch (err) {
      const message =
        err instanceof Error ? err.message : 'Failed to load parameter schema';
      setError(message);
    } finally {
      setLoading(false);
    }
  }, [apiFactory, projectId]);

  useEffect(() => {
    fetchSchema();
  }, [fetchSchema]);

  const isDirty = useMemo(() => {
    if (serverSchema === null) return false;
    return JSON.stringify(serverSchema.fields) !== JSON.stringify(stripKeys(draft));
  }, [serverSchema, draft]);

  const updateRow = useCallback(
    (index: number, patch: Partial<FieldRowState>) => {
      setDraft(prev =>
        prev.map((row, i) => (i === index ? { ...row, ...patch } : row))
      );
    },
    []
  );

  const handleTypeChange = useCallback(
    (index: number, newType: ParameterType) => {
      setDraft(prev =>
        prev.map((row, i) => {
          if (i !== index) return row;
          return {
            ...row,
            type: newType,
            // Type changed, so the previous default and options no longer
            // make sense — start from a clean per-type baseline.
            default: defaultForType(newType),
            options: newType === 'enum' ? row.options ?? [] : null,
          };
        })
      );
    },
    []
  );

  const handleAdd = useCallback(() => {
    setDraft(prev => [
      ...prev,
      { ...blankField(prev.length), _key: stableKey('f') },
    ]);
  }, []);

  const handleRemove = useCallback((index: number) => {
    setDraft(prev =>
      prev
        .filter((_, i) => i !== index)
        // Re-pack display_order so it stays a contiguous 0..n-1 sequence.
        .map((row, i) => ({ ...row, display_order: i }))
    );
  }, []);

  const move = useCallback((index: number, direction: -1 | 1) => {
    setDraft(prev => {
      const target = index + direction;
      if (target < 0 || target >= prev.length) return prev;
      const copy = [...prev];
      const [removed] = copy.splice(index, 1);
      copy.splice(target, 0, removed);
      return copy.map((row, i) => ({ ...row, display_order: i }));
    });
  }, []);

  const handleSave = useCallback(async () => {
    setSaving(true);
    try {
      const payload: ParameterSchema = {
        fields: stripKeys(draft),
      };
      const client = apiFactory.getParametersClient();
      const saved = await client.putSchema(projectId, payload);
      setServerSchema(saved);
      setDraft(saved.fields.map(field => ({ ...field, _key: stableKey('f') })));
      notifications.show('Parameter schema saved', { severity: 'success' });
    } catch (err) {
      const message =
        err instanceof Error ? err.message : 'Failed to save parameter schema';
      notifications.show(message, { severity: 'error' });
    } finally {
      setSaving(false);
    }
  }, [apiFactory, draft, notifications, projectId]);

  const handleRevert = useCallback(() => {
    if (!serverSchema) return;
    setDraft(
      serverSchema.fields.map(field => ({
        ...field,
        _key: stableKey('f'),
      }))
    );
  }, [serverSchema]);

  if (loading) {
    return (
      <Box sx={{ display: 'flex', alignItems: 'center', p: 3, gap: 2 }}>
        <CircularProgress size={24} />
        <Typography color="text.secondary">
          Loading parameter schema...
        </Typography>
      </Box>
    );
  }

  if (error) {
    return (
      <Alert severity="error" sx={{ my: 2 }}>
        {error}
      </Alert>
    );
  }

  return (
    <Box>
      <Box
        sx={{
          display: 'flex',
          justifyContent: 'flex-end',
          gap: 1,
          mb: 2,
        }}
      >
        <Button
          variant="text"
          startIcon={<ArrowBackIcon />}
          onClick={handleRevert}
          disabled={!isDirty || saving}
        >
          Discard changes
        </Button>
        <Button
          variant="contained"
          startIcon={<SaveIcon />}
          onClick={handleSave}
          disabled={!isDirty || saving}
        >
          {saving ? 'Saving...' : 'Save schema'}
        </Button>
      </Box>

      {draft.length === 0 ? (
        <Box
          sx={{
            py: 4,
            px: 2,
            border: '1px dashed',
            borderColor: 'divider',
            borderRadius: theme => theme.shape.borderRadius,
            textAlign: 'center',
            bgcolor: 'background.default',
          }}
        >
          <Typography color="text.secondary" variant="body2" sx={{ mb: 2 }}>
            No parameter slots yet. Add a field to start defining the project's
            parameter schema.
          </Typography>
          <Button
            variant="outlined"
            startIcon={<AddIcon />}
            onClick={handleAdd}
          >
            Add field
          </Button>
        </Box>
      ) : (
        <Stack spacing={1.5}>
          {draft.map((row, index) => (
            <FieldRow
              key={row._key}
              field={row}
              isFirst={index === 0}
              isLast={index === draft.length - 1}
              onChange={patch => updateRow(index, patch)}
              onTypeChange={type => handleTypeChange(index, type)}
              onMoveUp={() => move(index, -1)}
              onMoveDown={() => move(index, 1)}
              onRemove={() => handleRemove(index)}
            />
          ))}
          <Box>
            <Button
              variant="outlined"
              startIcon={<AddIcon />}
              onClick={handleAdd}
            >
              Add field
            </Button>
          </Box>
        </Stack>
      )}
    </Box>
  );
}

interface FieldRowProps {
  field: FieldRowState;
  isFirst: boolean;
  isLast: boolean;
  onChange: (patch: Partial<FieldRowState>) => void;
  onTypeChange: (type: ParameterType) => void;
  onMoveUp: () => void;
  onMoveDown: () => void;
  onRemove: () => void;
}

function FieldRow({
  field,
  isFirst,
  isLast,
  onChange,
  onTypeChange,
  onMoveUp,
  onMoveDown,
  onRemove,
}: FieldRowProps) {
  return (
    <Paper variant="outlined" sx={{ p: 2 }}>
      <Stack
        direction={{ xs: 'column', md: 'row' }}
        spacing={2}
        alignItems={{ xs: 'stretch', md: 'flex-start' }}
      >
        <TextField
          label="Name"
          value={field.name}
          onChange={e => onChange({ name: e.target.value })}
          size="small"
          helperText="snake_case identifier"
          sx={{ minWidth: 220, flex: 1 }}
        />
        <FormControl size="small" sx={{ minWidth: 200 }}>
          <InputLabel>Type</InputLabel>
          <Select
            label="Type"
            value={field.type}
            onChange={e => onTypeChange(e.target.value as ParameterType)}
          >
            {TYPE_OPTIONS.map(opt => (
              <MenuItem key={opt.value} value={opt.value}>
                {opt.label}
              </MenuItem>
            ))}
          </Select>
        </FormControl>
        <FormControlLabel
          control={
            <Checkbox
              checked={!!field.required}
              onChange={e => onChange({ required: e.target.checked })}
            />
          }
          label="Required"
          sx={{ alignSelf: { md: 'center' } }}
        />
        <Box sx={{ display: 'flex', gap: 0.5, alignSelf: { md: 'center' } }}>
          <Tooltip title="Move up">
            <span>
              <IconButton
                size="small"
                onClick={onMoveUp}
                disabled={isFirst}
                aria-label="Move up"
              >
                <ArrowBackIcon
                  fontSize="small"
                  sx={{ transform: 'rotate(90deg)' }}
                />
              </IconButton>
            </span>
          </Tooltip>
          <Tooltip title="Move down">
            <span>
              <IconButton
                size="small"
                onClick={onMoveDown}
                disabled={isLast}
                aria-label="Move down"
              >
                <ArrowOutwardIcon
                  fontSize="small"
                  sx={{ transform: 'rotate(45deg)' }}
                />
              </IconButton>
            </span>
          </Tooltip>
          <Tooltip title="Remove field">
            <IconButton
              size="small"
              onClick={onRemove}
              aria-label="Remove field"
              sx={{
                '&:hover': { color: 'error.main', bgcolor: 'error.50' },
              }}
            >
              <CloseIcon fontSize="small" />
            </IconButton>
          </Tooltip>
        </Box>
      </Stack>
      <Box sx={{ mt: 2 }}>
        <TextField
          label="Description"
          value={field.description ?? ''}
          onChange={e => onChange({ description: e.target.value })}
          size="small"
          fullWidth
        />
      </Box>
      {field.type === 'enum' && (
        <Box sx={{ mt: 2 }}>
          <TextField
            label="Options (comma-separated)"
            value={(field.options ?? []).join(', ')}
            onChange={e =>
              onChange({
                options: e.target.value
                  .split(',')
                  .map(o => o.trim())
                  .filter(Boolean),
              })
            }
            size="small"
            fullWidth
            helperText="The closed set of values this enum accepts"
          />
        </Box>
      )}
      <Box sx={{ mt: 2 }}>
        <DefaultValueEditor field={field} onChange={onChange} />
      </Box>
    </Paper>
  );
}

interface DefaultValueEditorProps {
  field: FieldRowState;
  onChange: (patch: Partial<FieldRowState>) => void;
}

/**
 * Type-aware default editor. Each variant produces a fully-typed
 * `ParameterValue` so the wire shape is correct without an extra
 * coercion step on save.
 */
function DefaultValueEditor({ field, onChange }: DefaultValueEditorProps) {
  const setDefault = (value: ParameterValue | null) => onChange({ default: value });

  switch (field.type) {
    case 'text': {
      const current =
        field.default && field.default.type === 'text'
          ? field.default.value
          : '';
      return (
        <TextField
          label="Default"
          value={current}
          onChange={e => setDefault({ type: 'text', value: e.target.value })}
          size="small"
          fullWidth
          multiline
          minRows={2}
        />
      );
    }
    case 'string': {
      const current =
        field.default && field.default.type === 'string'
          ? field.default.value
          : '';
      return (
        <TextField
          label="Default"
          value={current}
          onChange={e => setDefault({ type: 'string', value: e.target.value })}
          size="small"
          fullWidth
        />
      );
    }
    case 'integer': {
      const current =
        field.default && field.default.type === 'integer'
          ? field.default.value
          : '';
      return (
        <TextField
          label="Default"
          type="number"
          value={current}
          onChange={e => {
            const v = e.target.value;
            setDefault(
              v === '' ? null : { type: 'integer', value: parseInt(v, 10) }
            );
          }}
          size="small"
          inputProps={{ step: 1 }}
        />
      );
    }
    case 'number': {
      const current =
        field.default && field.default.type === 'number'
          ? field.default.value
          : '';
      return (
        <TextField
          label="Default"
          type="number"
          value={current}
          onChange={e => {
            const v = e.target.value;
            setDefault(v === '' ? null : { type: 'number', value: parseFloat(v) });
          }}
          size="small"
          inputProps={{ step: 'any' }}
        />
      );
    }
    case 'boolean': {
      const current =
        field.default && field.default.type === 'boolean'
          ? field.default.value
          : false;
      return (
        <FormControlLabel
          control={
            <Checkbox
              checked={current}
              onChange={e =>
                setDefault({ type: 'boolean', value: e.target.checked })
              }
            />
          }
          label="Default value"
        />
      );
    }
    case 'enum': {
      const options = field.options ?? [];
      const current =
        field.default && field.default.type === 'enum'
          ? field.default.value
          : '';
      return (
        <FormControl size="small" sx={{ minWidth: 220 }}>
          <InputLabel>Default</InputLabel>
          <Select
            label="Default"
            value={options.includes(current) ? current : ''}
            onChange={e => {
              const v = e.target.value as string;
              setDefault(v ? { type: 'enum', value: v } : null);
            }}
          >
            <MenuItem value="">
              <em>(none)</em>
            </MenuItem>
            {options.map(opt => (
              <MenuItem key={opt} value={opt}>
                {opt}
              </MenuItem>
            ))}
          </Select>
        </FormControl>
      );
    }
    case 'model_ref': {
      const current =
        field.default && field.default.type === 'model_ref'
          ? String(field.default.value)
          : '';
      return (
        <TextField
          label="Default model id"
          value={current}
          onChange={e => {
            const v = e.target.value.trim();
            setDefault(v ? { type: 'model_ref', value: v } : null);
          }}
          size="small"
          fullWidth
          helperText="UUID of a Model row"
        />
      );
    }
    case 'secret_ref': {
      const current =
        field.default && field.default.type === 'secret_ref'
          ? String(field.default.value)
          : '';
      return (
        <TextField
          label="Default secret id"
          value={current}
          onChange={e => {
            const v = e.target.value.trim();
            setDefault(v ? { type: 'secret_ref', value: v } : null);
          }}
          size="small"
          fullWidth
          helperText="UUID of a secret record"
        />
      );
    }
  }
}

function stripKeys(draft: FieldRowState[]): ParameterField[] {
  return draft.map(({ _key: _omit, ...rest }) => rest);
}
