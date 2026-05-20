'use client';

import * as React from 'react';
import { useEffect, useState } from 'react';
import {
  Alert,
  Box,
  Button,
  CircularProgress,
  IconButton,
  List,
  ListItemButton,
  Paper,
  Stack,
  Tooltip,
  Typography,
} from '@mui/material';
import {
  AddIcon,
  DeleteIcon,
  KeyboardArrowDownIcon,
  KeyboardArrowUpIcon,
  TuneIcon,
} from '@/components/icons';
import {
  FieldEditor,
  ParametersEmptyState,
  ParametersSaveBar,
  TYPE_META,
  useParameterSchema,
} from './parameter-schema-shared';

interface ProjectParametersProps {
  projectId: string;
  sessionToken: string;
  title?: string;
  headerAction?: React.ReactNode;
}

/**
 * Two-pane editor for a project's parameter schema.
 *
 * Left rail lists every field as a compact tile (type icon + name +
 * short type label + reorder controls). Right pane shows the full
 * editor for the selected field. Pattern borrowed from Strapi /
 * DatoCMS / Notion-database. Scales to large schemas without forcing
 * the user to scroll past long form bodies.
 *
 * Saving submits the full schema in a single `PUT`; add / remove /
 * reorder are local-only until the user clicks Save Changes.
 */
export default function ProjectParameters({
  projectId,
  sessionToken,
  title,
  headerAction,
}: ProjectParametersProps) {
  const {
    loading,
    error,
    saving,
    isDirty,
    draft,
    updateField,
    changeType,
    addField,
    removeField,
    move,
    handleSave,
    handleRevert,
  } = useParameterSchema(projectId, sessionToken);

  const [selectedKey, setSelectedKey] = useState<string | null>(null);

  useEffect(() => {
    if (selectedKey === null && draft.length > 0) {
      setSelectedKey(draft[0]._key);
      return;
    }
    if (selectedKey !== null && !draft.some(f => f._key === selectedKey)) {
      setSelectedKey(draft[0]?._key ?? null);
    }
  }, [draft, selectedKey]);

  const handleAdd = () => {
    const newKey = addField();
    setSelectedKey(newKey);
  };

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
    return <Alert severity="error">{error}</Alert>;
  }

  const selectedField = draft.find(f => f._key === selectedKey) ?? null;

  return (
    <Paper elevation={2} sx={{ p: 2 }}>
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 2 }}>
        {title && (
          <Typography variant="subtitle1" sx={{ fontWeight: 'medium', flex: 1 }}>
            {title}
          </Typography>
        )}
        {headerAction}
        <ParametersSaveBar
          isDirty={isDirty}
          saving={saving}
          onSave={handleSave}
          onRevert={handleRevert}
        />
      </Box>

      {draft.length === 0 ? (
        <ParametersEmptyState onAdd={handleAdd} />
      ) : (
        <Box
          sx={{
            display: 'grid',
            gridTemplateColumns: { xs: '1fr', md: '280px 1fr' },
            gap: 2,
            minHeight: 360,
          }}
        >
          <Box
            sx={{
              border: '1px solid',
              borderColor: 'divider',
              borderRadius: theme => `${theme.shape.borderRadius}px`,
              overflow: 'hidden',
              display: 'flex',
              flexDirection: 'column',
            }}
          >
            <List dense disablePadding sx={{ flex: 1, overflowY: 'auto' }}>
              {draft.map((field, index) => {
                const meta = TYPE_META[field.type];
                const Icon = meta.icon;
                const selected = field._key === selectedKey;
                const isFirst = index === 0;
                const isLast = index === draft.length - 1;
                return (
                  <ListItemButton
                    key={field._key}
                    selected={selected}
                    onClick={() => setSelectedKey(field._key)}
                    sx={{
                      borderLeft: '3px solid',
                      borderLeftColor: selected
                        ? `${meta.color}.main`
                        : 'transparent',
                      gap: 1,
                    }}
                  >
                    <Icon
                      fontSize="small"
                      color={meta.color === 'default' ? 'inherit' : meta.color}
                    />
                    <Box sx={{ flex: 1, minWidth: 0 }}>
                      <Typography
                        variant="body2"
                        sx={{
                          fontWeight: 500,
                          fontFamily: 'monospace',
                          overflow: 'hidden',
                          textOverflow: 'ellipsis',
                          whiteSpace: 'nowrap',
                        }}
                      >
                        {field.name || (
                          <Typography
                            component="span"
                            variant="body2"
                            color="text.disabled"
                            sx={{ fontStyle: 'italic' }}
                          >
                            unnamed field
                          </Typography>
                        )}
                      </Typography>
                      <Typography
                        variant="caption"
                        color="text.secondary"
                        sx={{ display: 'block' }}
                      >
                        {meta.shortLabel}
                        {field.required ? ' · required' : ''}
                      </Typography>
                    </Box>
                    <Stack direction="row" spacing={0}>
                      <Tooltip title="Move up">
                        <span>
                          <IconButton
                            size="small"
                            disabled={isFirst}
                            onClick={e => {
                              e.stopPropagation();
                              move(field._key, -1);
                            }}
                            aria-label="Move up"
                          >
                            <KeyboardArrowUpIcon fontSize="small" />
                          </IconButton>
                        </span>
                      </Tooltip>
                      <Tooltip title="Move down">
                        <span>
                          <IconButton
                            size="small"
                            disabled={isLast}
                            onClick={e => {
                              e.stopPropagation();
                              move(field._key, 1);
                            }}
                            aria-label="Move down"
                          >
                            <KeyboardArrowDownIcon fontSize="small" />
                          </IconButton>
                        </span>
                      </Tooltip>
                    </Stack>
                  </ListItemButton>
                );
              })}
            </List>
            <Box sx={{ p: 1, borderTop: '1px solid', borderColor: 'divider' }}>
              <Button
                fullWidth
                variant="text"
                startIcon={<AddIcon />}
                onClick={handleAdd}
              >
                Add field
              </Button>
            </Box>
          </Box>

          <Box
            sx={{
              border: '1px solid',
              borderColor: 'divider',
              borderRadius: theme => `${theme.shape.borderRadius}px`,
              p: 2,
              minHeight: 360,
            }}
          >
            {selectedField ? (
              <Box>
                <Stack
                  direction="row"
                  spacing={1}
                  alignItems="center"
                  sx={{ mb: 2 }}
                >
                  {(() => {
                    const meta = TYPE_META[selectedField.type];
                    const Icon = meta.icon;
                    return (
                      <Icon
                        fontSize="small"
                        color={meta.color === 'default' ? 'inherit' : meta.color}
                      />
                    );
                  })()}
                  <Typography variant="subtitle1" sx={{ fontWeight: 'medium', flex: 1 }}>
                    Parameter details
                  </Typography>
                  <Tooltip title="Remove field">
                    <IconButton
                      onClick={() => removeField(selectedField._key)}
                      aria-label="Remove field"
                    >
                      <DeleteIcon />
                    </IconButton>
                  </Tooltip>
                </Stack>
                <FieldEditor
                  field={selectedField}
                  onChange={patch => updateField(selectedField._key, patch)}
                  onTypeChange={type => changeType(selectedField._key, type)}
                />
              </Box>
            ) : (
              <Box
                sx={{
                  height: '100%',
                  display: 'flex',
                  flexDirection: 'column',
                  alignItems: 'center',
                  justifyContent: 'center',
                  color: 'text.disabled',
                  textAlign: 'center',
                  py: 6,
                }}
              >
                <TuneIcon sx={{ fontSize: 48, opacity: 0.4, mb: 1 }} />
                <Typography variant="body2" color="text.secondary">
                  Select a field on the left to edit it.
                </Typography>
              </Box>
            )}
          </Box>
        </Box>
      )}
    </Paper>
  );
}
