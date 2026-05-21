'use client';

import React, { useState, useCallback, useEffect } from 'react';
import { SectionCard } from '@/components/common/SectionCard';
import {
  SectionEditButton,
  SectionSaveCancelActions,
} from '@/components/common/SectionCardActions';

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
    <SectionSaveCancelActions
      onSave={handleSave}
      onCancel={handleCancel}
      isSaving={isSaving}
      saveDisabled={!dirty}
    />
  ) : (
    <SectionEditButton onClick={handleEdit} />
  );

  return (
    <SectionCard title={title} actions={actionButtons}>
      {children({ draft, setDraft, isEditing })}
    </SectionCard>
  );
}

export default EditableSection;
