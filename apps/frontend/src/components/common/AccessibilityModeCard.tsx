'use client';

import React, { useContext, useEffect, useId, useState } from 'react';
import { FormControlLabel, FormHelperText, Switch } from '@mui/material';
import { useRouter } from 'next/navigation';
import { SectionCard } from '@/components/common/SectionCard';
import { useNotifications } from '@/components/common/NotificationContext';
import { BrandPreviewContext } from '@/components/providers/ThemeProvider';

interface AccessibilityModeCardProps {
  /** Whose setting this is. */
  subtitle: string;
  /** The stored value at this level. */
  checked: boolean;
  /** Whether another level keeps the mode on even when this one is off. */
  onElsewhere: boolean;
  /** Shown, and the switch locked, when a higher level forces the mode on. */
  lockedReason?: string;
  disabled?: boolean;
  save: (checked: boolean) => Promise<void>;
}

/**
 * The accessibility mode switch, shared by the organization and the personal
 * settings. Previews the change at once and refreshes the page once it is
 * saved, so the server-rendered theme catches up.
 */
export default function AccessibilityModeCard({
  subtitle,
  checked,
  onElsewhere,
  lockedReason,
  disabled = false,
  save,
}: AccessibilityModeCardProps) {
  const router = useRouter();
  const notifications = useNotifications();
  const { previewBrandColors } = useContext(BrandPreviewContext);
  const helpId = useId();
  // The new value until `checked` catches up after the save.
  const [pending, setPending] = useState<boolean | null>(null);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    setPending(null);
  }, [checked]);

  const handleChange = async (next: boolean) => {
    setPending(next);
    setSaving(true);
    previewBrandColors({ accessibilityMode: next || onElsewhere });
    try {
      await save(next);
      router.refresh();
    } catch (err: unknown) {
      setPending(null);
      previewBrandColors({ accessibilityMode: checked || onElsewhere });
      notifications.show(
        err instanceof Error ? err.message : 'Could not save the setting',
        { severity: 'error' }
      );
    } finally {
      setSaving(false);
    }
  };

  const locked = Boolean(lockedReason);

  return (
    <SectionCard title="Accessibility" subtitle={subtitle}>
      <FormControlLabel
        control={
          <Switch
            checked={locked || (pending ?? checked)}
            onChange={e => handleChange(e.target.checked)}
            disabled={disabled || locked || saving}
            slotProps={{ input: { 'aria-describedby': helpId } }}
          />
        }
        label="Accessibility mode"
      />
      <FormHelperText id={helpId}>
        Raises text, buttons and field borders to WCAG 2.1 AA contrast in light
        and dark mode, shows results by shape as well as colour, and asks before
        removing things. Brand colours keep their hue but may be shown darker or
        lighter.
        {lockedReason && ` ${lockedReason}`}
      </FormHelperText>
    </SectionCard>
  );
}
