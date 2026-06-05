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
import BaseDrawer from '@/components/common/BaseDrawer';
import {
  FieldEditor,
  FieldRowState,
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
 * Schema editor for a project's parameter schema.
 *
 * The field list is the primary surface; clicking a field (or "Add field")
 * opens a BaseDrawer with the FieldEditor. Save Changes PUTs the full schema.
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

  const [drawerKey, setDrawerKey] = useState<string | null>(null);

  useEffect(() => {
    if (drawerKey !== null && !draft.some(f => f._key === drawerKey)) {
      setDrawerKey(null);
    }
  }, [draft, drawerKey]);

  const handleAdd = () => {
    const newKey = addField();
    setDrawerKey(newKey);
  };

  const handleOpenDrawer = (key: string) => setDrawerKey(key);
  const handleCloseDrawer = () => setDrawerKey(null);

  const drawerField: FieldRowState | null =
    drawerKey !== null ? (draft.find(f => f._key === drawerKey) ?? null) : null;

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

  return (
    <>
      <Box>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 2 }}>
          {title && (
            <Typography
              variant="subtitle1"
              sx={{ fontWeight: 'medium', flex: 1 }}
            >
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
              border: '1px solid',
              borderColor: 'divider',
              borderRadius: theme => `${theme.shape.borderRadius}px`,
              overflow: 'hidden',
            }}
          >
            <List dense disablePadding>
              {draft.map((field, index) => {
                const meta = TYPE_META[field.type];
                const Icon = meta.icon;
                const isFirst = index === 0;
                const isLast = index === draft.length - 1;
                return (
                  <ListItemButton
                    key={field._key}
                    onClick={() => handleOpenDrawer(field._key)}
                    sx={{
                      borderLeft: '3px solid',
                      borderLeftColor:
                        drawerKey === field._key
                          ? `${meta.color}.main`
                          : 'transparent',
                      gap: 1,
                      borderBottom:
                        index < draft.length - 1 ? '1px solid' : 'none',
                      borderBottomColor: 'divider',
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
        )}
      </Box>

      <BaseDrawer
        open={!!drawerField}
        onClose={handleCloseDrawer}
        title={
          drawerField?.name
            ? `Edit "${drawerField.name}"`
            : 'New parameter field'
        }
        showHeader
        width={520}
        saveButtonText="Done"
        onSave={handleCloseDrawer}
        closeButtonText="Close"
      >
        {drawerField && (
          <Stack spacing={3}>
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 1 }}>
              {(() => {
                const meta = TYPE_META[drawerField.type];
                const Icon = meta.icon;
                return (
                  <Icon
                    fontSize="small"
                    color={meta.color === 'default' ? 'inherit' : meta.color}
                  />
                );
              })()}
              <Typography
                variant="subtitle1"
                sx={{ fontWeight: 'medium', flex: 1 }}
              >
                Parameter details
              </Typography>
              <Tooltip title="Remove field">
                <IconButton
                  onClick={() => {
                    removeField(drawerField._key);
                    handleCloseDrawer();
                  }}
                  aria-label="Remove field"
                >
                  <DeleteIcon />
                </IconButton>
              </Tooltip>
            </Box>
            <FieldEditor
              field={drawerField}
              onChange={patch => updateField(drawerField._key, patch)}
              onTypeChange={type => changeType(drawerField._key, type)}
            />
            <Box sx={{ pt: 1 }}>
              <Typography variant="caption" color="text.secondary">
                Changes are held locally until you click &ldquo;Save
                Changes&rdquo; on the schema editor.
              </Typography>
            </Box>
          </Stack>
        )}
      </BaseDrawer>

      {!drawerField && draft.length === 0 && (
        <Box
          sx={{
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            justifyContent: 'center',
            py: 6,
            color: 'text.disabled',
          }}
        >
          <TuneIcon sx={{ fontSize: 48, opacity: 0.4, mb: 1 }} />
          <Typography variant="body2" color="text.secondary">
            Click a field to edit it, or add a new one.
          </Typography>
        </Box>
      )}
    </>
  );
}
