'use client';

import React, { useEffect, useState } from 'react';
import { Box, Button, IconButton, TextField, Tooltip } from '@mui/material';
import { useQueryClient } from '@tanstack/react-query';
import BaseDrawer from '@/components/common/BaseDrawer';
import FormSectionDivider from '@/components/common/FormSectionDivider';
import {
  drawerOutlineButtonSx,
  drawerSectionSx,
} from '@/components/common/drawerFormFieldSx';
import { AddIcon, DeleteIcon } from '@/components/icons';
import { ApiClientFactory } from '@/utils/api-client/client-factory';
import type { TypeLookup } from '@/utils/api-client/interfaces/type-lookup';
import { typeLookupKeys } from '@/constants/query-keys';
import {
  REQUIREMENT_IMPACT_NAME,
  REQUIREMENT_TYPE_NAME,
  lookupFilter,
  useRequirementImpacts,
  useRequirementTypes,
} from './requirement-lookups';

interface DraftOption {
  /** Undefined for a row added in this drawer. */
  id?: string;
  key: string;
  value: string;
}

// Stable fallback: a fresh [] each render would re-run the reset effects forever.
const NO_OPTIONS: TypeLookup[] = [];

let draftKeySeed = 0;
const newDraftKey = () => `new-${(draftKeySeed += 1)}`;

const toDraft = (options: TypeLookup[]): DraftOption[] =>
  options.map(o => ({
    id: String(o.id),
    key: String(o.id),
    value: o.type_value,
  }));

/** The writes that turn `options` into `draft`. */
function diffWrites(
  typeName: string,
  options: TypeLookup[],
  draft: DraftOption[]
): Promise<unknown>[] {
  const client = new ApiClientFactory().getTypeLookupClient();
  const kept = new Set(draft.filter(d => d.id).map(d => d.id));
  const removed = options.filter(o => !kept.has(String(o.id)));
  const renamed = draft.filter(d => {
    if (!d.id || !d.value.trim()) return false;
    return (
      options.find(o => String(o.id) === d.id)?.type_value !== d.value.trim()
    );
  });
  const added = draft.filter(d => !d.id && d.value.trim());
  return [
    ...removed.map(o => client.deleteTypeLookup(String(o.id))),
    ...renamed.map(d =>
      client.updateTypeLookup(String(d.id), { type_value: d.value.trim() })
    ),
    ...added.map(d =>
      client.createTypeLookup({
        type_name: typeName,
        type_value: d.value.trim(),
      })
    ),
  ];
}

/** One list of values, laid out like the model drawer's settings rows. */
function OptionsSection({
  headline,
  description,
  addLabel,
  draft,
  setDraft,
  disabled,
}: {
  headline: string;
  description: string;
  addLabel: string;
  draft: DraftOption[];
  setDraft: React.Dispatch<React.SetStateAction<DraftOption[]>>;
  disabled: boolean;
}) {
  return (
    <Box sx={drawerSectionSx}>
      <FormSectionDivider headline={headline} descriptiveText={description} />
      <Box sx={{ display: 'flex', flexDirection: 'column' }}>
        {draft.map(option => (
          <Box
            key={option.key}
            sx={{
              borderTop: 1,
              borderColor: theme => theme.palette.greyscale.border,
              py: 1.5,
              display: 'flex',
              alignItems: 'center',
              gap: 1,
            }}
          >
            <TextField
              variant="standard"
              fullWidth
              value={option.value}
              placeholder="Name"
              disabled={disabled}
              slotProps={{
                input: { disableUnderline: true },
                htmlInput: { 'aria-label': `${headline} option` },
              }}
              onChange={e =>
                setDraft(prev =>
                  prev.map(d =>
                    d.key === option.key ? { ...d, value: e.target.value } : d
                  )
                )
              }
            />
            <Tooltip title="Remove">
              <IconButton
                size="small"
                aria-label={`Remove ${option.value || 'option'}`}
                disabled={disabled}
                onClick={() =>
                  setDraft(prev => prev.filter(d => d.key !== option.key))
                }
              >
                <DeleteIcon fontSize="small" />
              </IconButton>
            </Tooltip>
          </Box>
        ))}
        <Box sx={{ mt: 1 }}>
          <Button
            variant="outlined"
            startIcon={<AddIcon />}
            disabled={disabled}
            onClick={() =>
              setDraft(prev => [...prev, { key: newDraftKey(), value: '' }])
            }
            sx={drawerOutlineButtonSx}
          >
            {addLabel}
          </Button>
        </Box>
      </Box>
    </Box>
  );
}

interface RequirementOptionsDrawerProps {
  open: boolean;
  onClose: () => void;
}

/** Add, rename and remove the project's requirement types and impacts. */
export default function RequirementOptionsDrawer({
  open,
  onClose,
}: RequirementOptionsDrawerProps) {
  const queryClient = useQueryClient();
  const { data: types = NO_OPTIONS } = useRequirementTypes(open);
  const { data: impacts = NO_OPTIONS } = useRequirementImpacts(open);
  const [typeDraft, setTypeDraft] = useState<DraftOption[]>([]);
  const [impactDraft, setImpactDraft] = useState<DraftOption[]>([]);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | undefined>();

  useEffect(() => {
    if (open) setTypeDraft(toDraft(types));
  }, [open, types]);
  useEffect(() => {
    if (open) setImpactDraft(toDraft(impacts));
  }, [open, impacts]);
  useEffect(() => {
    if (open) setError(undefined);
  }, [open]);

  const handleSave = async () => {
    setSaving(true);
    setError(undefined);
    const results = await Promise.allSettled([
      ...diffWrites(REQUIREMENT_TYPE_NAME, types, typeDraft),
      ...diffWrites(REQUIREMENT_IMPACT_NAME, impacts, impactDraft),
    ]);
    // Refetch either way: a partial save still changed the lists.
    await Promise.all(
      [REQUIREMENT_TYPE_NAME, REQUIREMENT_IMPACT_NAME].map(name =>
        queryClient.invalidateQueries({
          queryKey: typeLookupKeys.list(lookupFilter(name)),
        })
      )
    );
    setSaving(false);
    if (results.some(r => r.status === 'rejected')) {
      setError(
        'Some changes failed. An option still used by a requirement may not be removable.'
      );
      return;
    }
    onClose();
  };

  return (
    <BaseDrawer
      open={open}
      onClose={onClose}
      title="Requirement Options"
      onSave={handleSave}
      saveButtonText="Save"
      loading={saving}
      error={error}
    >
      <OptionsSection
        headline="Types"
        description="What kind of rule a requirement is."
        addLabel="Add type"
        draft={typeDraft}
        setDraft={setTypeDraft}
        disabled={saving}
      />
      <OptionsSection
        headline="Impacts"
        description="What it costs when the assistant gets a requirement wrong."
        addLabel="Add impact"
        draft={impactDraft}
        setDraft={setImpactDraft}
        disabled={saving}
      />
    </BaseDrawer>
  );
}
