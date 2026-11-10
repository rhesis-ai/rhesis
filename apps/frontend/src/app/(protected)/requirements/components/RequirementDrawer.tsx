'use client';

import React from 'react';
import {
  Typography,
  TextField,
  Button,
  Stack,
  Divider,
  Autocomplete,
  Chip,
  Link,
  MenuItem,
} from '@mui/material';
import DeleteIcon from '@mui/icons-material/Delete';
import ContentCopyIcon from '@mui/icons-material/ContentCopy';
import BaseDrawer from '@/components/common/BaseDrawer';
import { drawerOutlinedFieldSx } from '@/components/common/drawerFormFieldSx';
import { useCan } from '@/components/common/Can';
import { Capability } from '@/constants/capabilities';
import RequirementOptionsDrawer from './RequirementOptionsDrawer';
import { useFormChangeDetection } from '@/hooks/useFormChangeDetection';
import RequirementAutocomplete from '@/components/requirements/RequirementAutocomplete';
import type { RequirementOption } from '@/utils/api-client/interfaces/requirement';
import type { UUID } from 'crypto';
import { useRequirementImpacts } from './requirement-lookups';

/** The optional fields, filled in over time. Null means none. */
export interface RequirementDetailsInput {
  impact_id: UUID | null;
  parent_id: UUID | null;
}

const NONE = '';

// Stable default, so the reset-on-open effect does not rerun every render.
const NO_TAGS: string[] = [];

interface RequirementDrawerProps {
  open: boolean;
  onClose: () => void;
  name: string;
  description: string;
  initialTagNames?: string[];
  tagSuggestions?: string[];
  initialImpactId?: string | null;
  initialParent?: RequirementOption | null;
  /** The requirement being edited, so it is never offered as its own parent. */
  selfId?: string;
  /** A requirement with children stays top-level: requirements nest one level deep. */
  hasChildren?: boolean;
  onSave: (
    name: string,
    description: string,
    tagNames: string[],
    details: RequirementDetailsInput
  ) => void;
  onDuplicate?: () => void;
  onDelete?: () => void;
  isNew?: boolean;
  loading?: boolean;
  error?: string;
}

const sortedUnique = (values: string[]) =>
  Array.from(new Set(values.filter(v => v.trim().length > 0))).sort();

const RequirementDrawer = ({
  open,
  onClose,
  name: initialName,
  description: initialDescription,
  initialTagNames = NO_TAGS,
  tagSuggestions = [],
  initialImpactId = null,
  initialParent = null,
  selfId,
  hasChildren = false,
  onSave,
  onDuplicate,
  onDelete,
  isNew = false,
  loading = false,
  error,
}: RequirementDrawerProps) => {
  const [currentName, setCurrentName] = React.useState(initialName);
  const [currentDescription, setCurrentDescription] =
    React.useState(initialDescription);
  const [currentTagNames, setCurrentTagNames] =
    React.useState<string[]>(initialTagNames);
  const [validationError, setValidationError] = React.useState<string>('');
  const [impactId, setImpactId] = React.useState<string>(
    initialImpactId ?? NONE
  );
  const [parent, setParent] = React.useState<RequirementOption | null>(
    initialParent
  );
  const [optionsOpen, setOptionsOpen] = React.useState(false);
  const canManageOptions = useCan(Capability.Requirement.UPDATE);
  const { data: impactOptions = [] } = useRequirementImpacts(open);

  const initialTagsSorted = React.useMemo(
    () => sortedUnique(initialTagNames),
    [initialTagNames]
  );
  const currentTagsSorted = React.useMemo(
    () => sortedUnique(currentTagNames),
    [currentTagNames]
  );

  const { hasChanges } = useFormChangeDetection({
    initialData: {
      name: initialName,
      description: initialDescription,
      tags: initialTagsSorted.join('\u0001'),
      impactId: initialImpactId ?? NONE,
      parentId: initialParent ? String(initialParent.id) : NONE,
    },
    currentData: {
      name: currentName,
      description: currentDescription,
      tags: currentTagsSorted.join('\u0001'),
      impactId,
      parentId: parent ? String(parent.id) : NONE,
    },
  });

  React.useEffect(() => {
    if (open) {
      setCurrentName(initialName);
      setCurrentDescription(initialDescription);
      setCurrentTagNames(initialTagNames);
      setImpactId(initialImpactId ?? NONE);
      setParent(initialParent);
      setValidationError('');
    }
    // Keyed on the parent's id: callers build the object inline, and a new
    // object each render must not wipe a parent picked in the drawer.
    // eslint-disable-next-line react-hooks/exhaustive-deps -- see above
  }, [
    initialName,
    initialDescription,
    initialTagNames,
    initialImpactId,
    initialParent?.id,
    open,
  ]);

  const handleSaveInternal = () => {
    setValidationError('');

    if (!isNew && !hasChanges) {
      return;
    }

    const trimmedName = currentName.trim();

    if (!trimmedName) {
      setValidationError('Requirement name is required');
      return;
    }

    if (trimmedName.length < 2) {
      setValidationError('Requirement name must be at least 2 characters');
      return;
    }

    onSave(
      trimmedName,
      currentDescription.trim(),
      sortedUnique(currentTagNames),
      {
        impact_id: (impactId || null) as UUID | null,
        parent_id: parent ? (parent.id as UUID) : null,
      }
    );
  };

  const drawerTitle = isNew ? 'Add New Requirement' : 'Edit Requirement';
  const saveButtonText = isNew ? 'Add Requirement' : 'Save Changes';

  return (
    <BaseDrawer
      open={open}
      onClose={onClose}
      title={drawerTitle}
      onSave={handleSaveInternal}
      saveButtonText={saveButtonText}
      saveDisabled={!isNew && !hasChanges}
      loading={loading}
      error={error}
      width={600}
    >
      <Stack
        spacing={{ xs: 2, sm: 3 }}
        divider={!isNew && (onDelete || onDuplicate) ? <Divider /> : null}
        useFlexGap
      >
        {/* Main Section */}
        <Stack spacing={2}>
          <TextField
            label="Name"
            value={currentName}
            onChange={e => {
              setCurrentName(e.target.value);
              if (validationError) setValidationError('');
            }}
            fullWidth
            required
            variant="outlined"
            disabled={loading}
            error={!!validationError}
            helperText={
              validationError ||
              'A clear, descriptive name for this requirement'
            }
            sx={drawerOutlinedFieldSx}
          />

          <TextField
            label="Description"
            value={currentDescription}
            onChange={e => setCurrentDescription(e.target.value)}
            multiline
            rows={4}
            fullWidth
            variant="outlined"
            disabled={loading}
            helperText="Describe what this requirement measures and why it matters"
          />

          <TextField
            select
            label="Impact"
            value={impactId}
            onChange={e => setImpactId(e.target.value)}
            disabled={loading}
            fullWidth
            helperText={
              <>
                What it costs if the assistant gets this wrong. If several
                apply, pick the worst
                {canManageOptions && (
                  <>
                    {' · '}
                    <Link
                      component="button"
                      type="button"
                      variant="caption"
                      underline="hover"
                      onClick={() => setOptionsOpen(true)}
                      sx={{ verticalAlign: 'baseline' }}
                    >
                      Manage impact options
                    </Link>
                  </>
                )}
              </>
            }
            sx={drawerOutlinedFieldSx}
          >
            <MenuItem value={NONE}>None</MenuItem>
            {impactOptions.map(option => (
              <MenuItem key={option.id} value={String(option.id)}>
                {option.type_value}
              </MenuItem>
            ))}
          </TextField>
          <RequirementAutocomplete
            label="Parent requirement"
            value={parent}
            onChange={setParent}
            excludeIds={selfId ? [selfId] : []}
            topLevelOnly
            helperText={
              hasChildren
                ? 'It has its own children, so it stays at the top level'
                : 'Group this requirement under a broader one'
            }
            disabled={loading || hasChildren}
            sx={drawerOutlinedFieldSx}
          />

          <Autocomplete
            multiple
            freeSolo
            options={tagSuggestions}
            value={currentTagNames}
            onChange={(_event, value) => {
              const normalized = value
                .map(v => v.trim())
                .filter(v => v.length > 0);
              setCurrentTagNames(Array.from(new Set(normalized)));
            }}
            disabled={loading}
            renderTags={(value: readonly string[], getTagProps) =>
              value.map((option, index) => {
                const { key, ...chipProps } = getTagProps({ index });
                return (
                  <Chip key={key} label={option} size="small" {...chipProps} />
                );
              })
            }
            renderInput={params => (
              <TextField
                {...params}
                sx={drawerOutlinedFieldSx}
                label="Tags"
                placeholder={
                  currentTagNames.length === 0
                    ? 'Add tags to group requirements (e.g. Marketing, US 1)'
                    : ''
                }
                helperText="Press Enter to add. Reuse tags from other requirements to group them."
              />
            )}
          />
        </Stack>

        {/* Duplicate Section */}
        {!isNew && onDuplicate && (
          <Stack spacing={1.5}>
            <Typography variant="body2" color="text.secondary">
              Create a copy of this requirement
            </Typography>
            <Button
              variant="outlined"
              startIcon={<ContentCopyIcon />}
              onClick={onDuplicate}
              fullWidth
              disabled={loading}
            >
              Duplicate Requirement
            </Button>
          </Stack>
        )}

        {/* Delete Section */}
        {!isNew && onDelete && (
          <Stack spacing={1.5}>
            <Typography variant="body2" color="text.secondary">
              Delete this requirement (only available if no metrics are
              assigned)
            </Typography>
            <Button
              variant="outlined"
              color="error"
              startIcon={<DeleteIcon />}
              onClick={onDelete}
              fullWidth
              disabled={loading}
            >
              Delete Requirement
            </Button>
          </Stack>
        )}
      </Stack>
      <RequirementOptionsDrawer
        open={optionsOpen}
        onClose={() => setOptionsOpen(false)}
      />
    </BaseDrawer>
  );
};

export default RequirementDrawer;
