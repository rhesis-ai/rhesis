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
  KeyboardArrowDownIcon,
  KeyboardArrowUpIcon,
  TuneIcon,
} from '@/components/icons';
import BaseDrawer from '@/components/common/BaseDrawer';
import FormSectionDivider from '@/components/common/FormSectionDivider';
import {
  drawerFieldsSx,
  drawerSectionSx,
} from '@/components/common/drawerFormFieldSx';
import { SectionCard } from '@/components/common/SectionCard';
import { sectionEditButtonSx } from '@/components/common/SectionCardActions';
import {
  FieldEditor,
  FieldRowState,
  ParametersEmptyState,
  TYPE_META,
  useParameterSchema,
} from './parameter-schema-shared';
import { useCan } from '@/components/common/Can';
import { Capability } from '@/constants/capabilities';

interface ProjectParametersProps {
  projectId: string;
  title?: string;
  headerAction?: React.ReactNode;
  /** Wrap content in a SectionCard with actions aligned in the header. */
  embedInSectionCard?: boolean;
}

/**
 * Schema editor for a project's parameter schema.
 *
 * The field list is the primary surface; clicking a field (or "Add Parameter")
 * opens a BaseDrawer with the FieldEditor. Save Changes PUTs the full schema.
 */
export default function ProjectParameters({
  projectId,
  title,
  headerAction,
  embedInSectionCard = false,
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
  } = useParameterSchema(projectId);

  const canUpdate = useCan(Capability.Project.UPDATE);
  const [drawerKey, setDrawerKey] = useState<string | null>(null);
  const [newFieldKeys, setNewFieldKeys] = useState<Set<string>>(
    () => new Set()
  );

  useEffect(() => {
    if (drawerKey !== null && !draft.some(f => f._key === drawerKey)) {
      setDrawerKey(null);
    }
  }, [draft, drawerKey]);

  const handleAdd = () => {
    const newKey = addField();
    setNewFieldKeys(prev => new Set(prev).add(newKey));
    setDrawerKey(newKey);
  };

  const handleOpenDrawer = (key: string) => setDrawerKey(key);
  const handleCloseDrawer = () => setDrawerKey(null);

  const drawerField: FieldRowState | null =
    drawerKey !== null ? (draft.find(f => f._key === drawerKey) ?? null) : null;

  const isNewParameter = drawerKey !== null && newFieldKeys.has(drawerKey);

  const handleDrawerClose = () => {
    if (drawerKey && newFieldKeys.has(drawerKey)) {
      removeField(drawerKey);
      setNewFieldKeys(prev => {
        const next = new Set(prev);
        next.delete(drawerKey);
        return next;
      });
    }
    handleCloseDrawer();
  };

  const handleDrawerSave = async () => {
    const ok = await handleSave();
    if (!ok) return;
    if (drawerKey) {
      setNewFieldKeys(prev => {
        const next = new Set(prev);
        next.delete(drawerKey);
        return next;
      });
    }
    handleCloseDrawer();
  };

  const handleDrawerDelete = async () => {
    if (!drawerKey) return;
    const updatedDraft = draft
      .filter(f => f._key !== drawerKey)
      .map((row, i) => ({ ...row, display_order: i }));
    removeField(drawerKey);
    setNewFieldKeys(prev => {
      const next = new Set(prev);
      next.delete(drawerKey);
      return next;
    });
    const ok = await handleSave(updatedDraft);
    if (!ok) {
      handleRevert();
      return;
    }
    handleCloseDrawer();
  };

  const drawerCloseButtonText = isNewParameter || isDirty ? 'Cancel' : 'Close';

  const useHeaderActions = embedInSectionCard;

  if (loading) {
    const loadingContent = (
      <Box sx={{ display: 'flex', alignItems: 'center', p: 3, gap: 2 }}>
        <CircularProgress size={24} />
        <Typography color="text.secondary">
          Loading parameter schema...
        </Typography>
      </Box>
    );
    return embedInSectionCard ? (
      <SectionCard title="Parameters">{loadingContent}</SectionCard>
    ) : (
      loadingContent
    );
  }

  if (error) {
    const errorContent = <Alert severity="error">{error}</Alert>;
    return embedInSectionCard ? (
      <SectionCard title="Parameters">{errorContent}</SectionCard>
    ) : (
      errorContent
    );
  }

  const sectionActions = (
    <Box sx={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
      {headerAction}
      {canUpdate && (
        <Button
          variant="outlined"
          size="small"
          startIcon={<AddIcon sx={{ fontSize: 20 }} />}
          onClick={handleAdd}
          sx={sectionEditButtonSx}
        >
          Add Parameter
        </Button>
      )}
    </Box>
  );

  const content = (
    <Box>
      {!useHeaderActions && (
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
        </Box>
      )}

      {draft.length === 0 ? (
        <ParametersEmptyState
          onAdd={canUpdate ? handleAdd : undefined}
          showAddButton={!useHeaderActions && canUpdate}
        />
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
                  onClick={
                    canUpdate ? () => handleOpenDrawer(field._key) : undefined
                  }
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
                  {canUpdate && (
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
                  )}
                </ListItemButton>
              );
            })}
          </List>
          {!useHeaderActions && canUpdate && (
            <Box sx={{ p: 1, borderTop: '1px solid', borderColor: 'divider' }}>
              <Button
                fullWidth
                variant="text"
                startIcon={<AddIcon />}
                onClick={handleAdd}
              >
                Add Parameter
              </Button>
            </Box>
          )}
        </Box>
      )}
    </Box>
  );

  return (
    <>
      {embedInSectionCard ? (
        <SectionCard title="Parameters" actions={sectionActions}>
          {content}
        </SectionCard>
      ) : (
        content
      )}

      <BaseDrawer
        open={!!drawerField}
        onClose={handleDrawerClose}
        title={
          drawerField?.name ? `Edit "${drawerField.name}"` : 'New parameter'
        }
        saveButtonText="Save"
        onSave={handleDrawerSave}
        saveDisabled={saving || (!isDirty && !isNewParameter)}
        loading={saving}
        closeButtonText={drawerCloseButtonText}
        onDelete={isNewParameter ? undefined : handleDrawerDelete}
        deleteButtonText="Delete"
      >
        {drawerField && (
          <Box sx={drawerSectionSx}>
            <FormSectionDivider
              headline="Parameter details"
              descriptiveText="Define the field name, type, and default value."
            />
            <Box sx={drawerFieldsSx}>
              <FieldEditor
                field={drawerField}
                onChange={patch => updateField(drawerField._key, patch)}
                onTypeChange={type => changeType(drawerField._key, type)}
              />
              <Typography
                sx={{
                  fontSize: 12,
                  lineHeight: '18px',
                  color: theme => theme.palette.greyscale.subtitle,
                }}
              >
                Click Save to persist this parameter schema.
              </Typography>
            </Box>
          </Box>
        )}
      </BaseDrawer>
    </>
  );
}
