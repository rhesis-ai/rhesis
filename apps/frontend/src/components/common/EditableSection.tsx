'use client';

import React, { useState, useCallback, useEffect } from 'react';
import { Box, Button, CircularProgress } from '@mui/material';
import EditIcon from '@mui/icons-material/Edit';
import { SectionCard } from '@/components/common/SectionCard';

interface EditableSectionProps<T> {
  title: string;
  initialValue: T;
  onSave: (draft: T) => Promise<void>;
  isDirty?: (draft: T, initial: T) => boolean;
  children: (ctx: {
    draft: T;
    setDraft: (next: T | ((p: T) => T)) => void;
    isEditing: boolean;
  }) => React.ReactNode;
}

function defaultIsDirty<T>(draft: T, initial: T): boolean {
  return JSON.stringify(draft) !== JSON.stringify(initial);
}

export function EditableSection<T>({
  title,
  initialValue,
  onSave,
  isDirty = defaultIsDirty,
  children,
}: EditableSectionProps<T>) {
  const [isEditing, setIsEditing] = useState(false);
  const [draft, setDraft] = useState<T>(initialValue);
  const [isSaving, setIsSaving] = useState(false);

  useEffect(() => {
    if (!isEditing) {
      setDraft(initialValue);
    }
  }, [initialValue, isEditing]);

  const dirty = isDirty(draft, initialValue);

  const handleEdit = useCallback(() => {
    setDraft(initialValue);
    setIsEditing(true);
  }, [initialValue]);

  const handleCancel = useCallback(() => {
    setDraft(initialValue);
    setIsEditing(false);
  }, [initialValue]);

  const handleSave = useCallback(async () => {
    if (!dirty || isSaving) return;
    setIsSaving(true);
    try {
      await onSave(draft);
      setIsEditing(false);
    } finally {
      setIsSaving(false);
    }
  }, [dirty, isSaving, onSave, draft]);

  const actionButtons = isEditing ? (
    <Box sx={{ display: 'flex', gap: '10px' }}>
      <Button
        size="small"
        variant="outlined"
        onClick={handleCancel}
        disabled={isSaving}
        sx={{ fontWeight: 700, borderWidth: 2, '&:hover': { borderWidth: 2 } }}
      >
        Cancel
      </Button>
      <Button
        size="small"
        variant="contained"
        onClick={handleSave}
        disabled={!dirty || isSaving}
        startIcon={
          isSaving ? <CircularProgress size={14} color="inherit" /> : undefined
        }
        sx={{ fontWeight: 700 }}
      >
        {isSaving ? 'Saving…' : 'Save'}
      </Button>
    </Box>
  ) : (
    <Button
      size="small"
      variant="outlined"
      startIcon={<EditIcon />}
      onClick={handleEdit}
      sx={{ fontWeight: 700, borderWidth: 2, '&:hover': { borderWidth: 2 } }}
    >
      Edit
    </Button>
  );

  return (
    <SectionCard title={title} actions={actionButtons}>
      {children({ draft, setDraft, isEditing })}
    </SectionCard>
  );
}

export default EditableSection;
