'use client';

import React, { useState, useCallback, useEffect, useRef } from 'react';
import { SectionCard } from '@/components/common/SectionCard';
import {
  SectionEditButton,
  SectionSaveCancelActions,
} from '@/components/common/SectionCardActions';

interface EditableSectionProps<T> {
  title: string;
  subtitle?: React.ReactNode;
  headerActions?: React.ReactNode;
  /**
   * When false the edit button is hidden and the section is permanently
   * read-only. Defaults to true. Pass `can(entity, Capability.X.UPDATE)` to
   * gate editing on server-driven affordances.
   */
  editable?: boolean;
  initialValue: T;
  onSave: (draft: T) => Promise<boolean | void>;
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
  subtitle,
  headerActions,
  editable = true,
  initialValue,
  onSave,
  isDirty = defaultIsDirty,
  children,
}: EditableSectionProps<T>) {
  const [isEditing, setIsEditing] = useState(false);
  const [draft, setDraft] = useState<T>(initialValue);
  const [isSaving, setIsSaving] = useState(false);

  // After a successful save, `initialValue` still reflects the pre-save prop
  // until the caller's data refetch resolves. Without this, the effect below
  // would snap the field back to the old value for a moment, which reads as
  // "the save didn't stick" even though it did.
  const pendingSaveRef = useRef<{ staleValue: T; savedValue: T } | null>(null);

  const resolveValue = useCallback((value: T) => {
    const pending = pendingSaveRef.current;
    if (
      pending &&
      JSON.stringify(value) === JSON.stringify(pending.staleValue)
    ) {
      return pending.savedValue;
    }
    pendingSaveRef.current = null;
    return value;
  }, []);

  useEffect(() => {
    if (!isEditing) {
      setDraft(resolveValue(initialValue));
    }
  }, [initialValue, isEditing, resolveValue]);

  const dirty = isDirty(draft, initialValue);

  const handleEdit = useCallback(() => {
    setDraft(resolveValue(initialValue));
    setIsEditing(true);
  }, [initialValue, resolveValue]);

  const handleCancel = useCallback(() => {
    pendingSaveRef.current = null;
    setDraft(initialValue);
    setIsEditing(false);
  }, [initialValue]);

  const handleSave = useCallback(async () => {
    if (!dirty || isSaving) return;
    setIsSaving(true);
    try {
      const ok = await onSave(draft);
      if (ok !== false) {
        pendingSaveRef.current = {
          staleValue: initialValue,
          savedValue: draft,
        };
        setIsEditing(false);
      }
    } finally {
      setIsSaving(false);
    }
  }, [dirty, isSaving, onSave, draft, initialValue]);

  const actionButtons = isEditing ? (
    <SectionSaveCancelActions
      onSave={handleSave}
      onCancel={handleCancel}
      isSaving={isSaving}
      saveDisabled={!dirty}
    />
  ) : editable ? (
    <SectionEditButton onClick={handleEdit} />
  ) : null;

  return (
    <SectionCard
      title={title}
      subtitle={subtitle}
      actions={
        headerActions || actionButtons ? (
          <>
            {headerActions}
            {actionButtons}
          </>
        ) : undefined
      }
    >
      {children({ draft, setDraft, isEditing })}
    </SectionCard>
  );
}

export default EditableSection;
