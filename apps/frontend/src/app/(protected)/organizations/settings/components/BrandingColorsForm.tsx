'use client';

import React, { useContext, useEffect, useMemo, useRef, useState } from 'react';
import { Box, Button, Grid, InputAdornment, Tooltip } from '@mui/material';
import { useRouter } from 'next/navigation';
import { Organization } from '@/utils/api-client/interfaces/organization';
import { ApiClientFactory } from '@/utils/api-client/client-factory';
import { useNotifications } from '@/components/common/NotificationContext';
import { BrandPreviewContext } from '@/components/providers/ThemeProvider';
import { SECTION_GRID } from '@/styles/theme-constants';
import { SectionCard } from '@/components/common/SectionCard';
import EditableField from '@/components/common/EditableField';
import { useCan } from '@/components/common/Can';
import { Capability } from '@/constants/capabilities';
import { DEFAULT_PRODUCT_NAME, getDeploymentBranding } from '@/config/branding';
import {
  HEX_COLOR_PATTERN,
  MAX_PRODUCT_NAME_LENGTH,
  RHESIS_PRIMARY_COLOR,
  RHESIS_SECONDARY_COLOR,
  brandingOf,
} from './branding-constants';

interface BrandingDraft {
  primary_color: string;
  secondary_color: string;
  product_name: string;
}

interface BrandingColorsFormProps {
  organization: Organization;
  onUpdate: () => void;
}

/** Delay before the page-wide refresh fires after the last field save. */
const REFRESH_DELAY_MS = 1000;

/** Delay before a colour-picker drag fires an API save. */
const PICKER_SAVE_DELAY_MS = 300;

type ColorDraftField = 'primary_color' | 'secondary_color';

const BRAND_COLOR_KEY: Record<ColorDraftField, 'primary' | 'secondary'> = {
  primary_color: 'primary',
  secondary_color: 'secondary',
};

/**
 * Colours and product name. Each field persists on blur (or on colour-picker
 * close). The page-wide refresh that makes the theme reflect the change is
 * debounced so editing several fields in a row does not flicker the UI.
 */
export default function BrandingColorsForm({
  organization,
  onUpdate,
}: BrandingColorsFormProps) {
  const router = useRouter();
  const notifications = useNotifications();
  const canUpdateOrg = useCan(Capability.Organization.UPDATE);
  const { previewBrandColors, clearBrandPreview } =
    useContext(BrandPreviewContext);
  const [resetting, setResetting] = useState(false);

  const branding = brandingOf(organization);
  const stored = useMemo(
    () => ({
      primary_color: branding?.primary_color || '',
      secondary_color: branding?.secondary_color || '',
      product_name: branding?.product_name || '',
    }),
    [branding?.primary_color, branding?.secondary_color, branding?.product_name]
  );

  const hasCustomBranding =
    stored.primary_color || stored.secondary_color || stored.product_name;

  const [draft, setDraftState] = useState<BrandingDraft>(stored);
  const draftRef = useRef<BrandingDraft>(stored);

  // Sync when the server-side values change (after a refresh propagates the
  // new org prop). Avoids the flash that firing on saving/resetting caused.
  useEffect(() => {
    setDraftState(stored);
    draftRef.current = stored;
  }, [stored]);

  // Keeps draftRef in sync synchronously so a blur handler that fires in the
  // same React batch as a preceding onChange still reads the latest value
  // (matters for the native colour picker whose change + blur can batch).
  const setDraft = (
    next: BrandingDraft | ((prev: BrandingDraft) => BrandingDraft)
  ) => {
    const resolved = typeof next === 'function' ? next(draftRef.current) : next;
    draftRef.current = resolved;
    setDraftState(resolved);
  };

  // --- debounced page refresh -------------------------------------------
  const refreshTimer = useRef<ReturnType<typeof setTimeout>>(null);
  const saveTimers = useRef<Record<string, ReturnType<typeof setTimeout>>>({});

  useEffect(
    () => () => {
      if (refreshTimer.current) clearTimeout(refreshTimer.current);
      for (const t of Object.values(saveTimers.current)) clearTimeout(t);
    },
    []
  );

  const scheduleRefresh = () => {
    if (refreshTimer.current) clearTimeout(refreshTimer.current);
    refreshTimer.current = setTimeout(() => {
      router.refresh();
      onUpdate();
    }, REFRESH_DELAY_MS);
  };

  // --- per-field save ---------------------------------------------------
  const saveField = async (field: keyof BrandingDraft) => {
    const trimmed = draftRef.current[field].trim();

    if (
      (field === 'primary_color' || field === 'secondary_color') &&
      trimmed &&
      !HEX_COLOR_PATTERN.test(trimmed)
    ) {
      return;
    }
    if (field === 'product_name' && trimmed.length > MAX_PRODUCT_NAME_LENGTH) {
      notifications.show(
        `Product name must be at most ${MAX_PRODUCT_NAME_LENGTH} characters`,
        { severity: 'error' }
      );
      return;
    }

    if (trimmed === stored[field]) return;

    try {
      await new ApiClientFactory()
        .getOrganizationsClient()
        .updateOrganizationSettings({
          branding: { [field]: trimmed || null },
        });
      scheduleRefresh();
    } catch (err: unknown) {
      notifications.show(
        err instanceof Error ? err.message : 'Failed to update branding',
        { severity: 'error' }
      );
    }
  };

  // --- colour-picker live preview + debounced save -----------------------
  const handlePickerChange = (field: ColorDraftField, value: string) => {
    setDraft(prev => ({ ...prev, [field]: value }));
    previewBrandColors({ [BRAND_COLOR_KEY[field]]: value });
    if (saveTimers.current[field]) clearTimeout(saveTimers.current[field]);
    saveTimers.current[field] = setTimeout(
      () => saveField(field),
      PICKER_SAVE_DELAY_MS
    );
  };

  const flushPickerSave = (field: ColorDraftField) => {
    if (saveTimers.current[field]) {
      clearTimeout(saveTimers.current[field]);
      delete saveTimers.current[field];
    }
    saveField(field);
  };

  // --- reset (explicit action → immediate refresh) ----------------------
  const handleReset = async () => {
    if (refreshTimer.current) clearTimeout(refreshTimer.current);
    for (const t of Object.values(saveTimers.current)) clearTimeout(t);
    saveTimers.current = {};
    clearBrandPreview();
    setResetting(true);
    try {
      await new ApiClientFactory()
        .getOrganizationsClient()
        .updateOrganizationSettings({
          branding: {
            primary_color: null,
            secondary_color: null,
            product_name: null,
          },
        });
      notifications.show('Brand identity reset to defaults', {
        severity: 'success',
      });
      router.refresh();
      onUpdate();
    } catch (err: unknown) {
      notifications.show(
        err instanceof Error ? err.message : 'Failed to reset branding',
        { severity: 'error' }
      );
    } finally {
      setResetting(false);
    }
  };

  return (
    <SectionCard
      title="Brand Identity"
      subtitle="Applies to everyone in your organization. Leave a field empty to use this deployment's default."
      actions={
        canUpdateOrg && hasCustomBranding ? (
          <Button
            variant="text"
            size="small"
            color="error"
            disabled={resetting}
            onClick={handleReset}
          >
            Reset
          </Button>
        ) : undefined
      }
    >
      <BrandingFields
        draft={draft}
        setDraft={setDraft}
        editable={canUpdateOrg}
        disabled={resetting}
        onSave={saveField}
        onPickerChange={handlePickerChange}
        onPickerBlur={flushPickerSave}
      />
    </SectionCard>
  );
}

function BrandingFields({
  draft,
  setDraft,
  editable,
  disabled,
  onSave,
  onPickerChange,
  onPickerBlur,
}: {
  draft: BrandingDraft;
  setDraft: (
    next: BrandingDraft | ((p: BrandingDraft) => BrandingDraft)
  ) => void;
  editable: boolean;
  disabled: boolean;
  onSave: (field: keyof BrandingDraft) => void;
  onPickerChange: (field: ColorDraftField, value: string) => void;
  onPickerBlur: (field: ColorDraftField) => void;
}) {
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});
  const deployment = getDeploymentBranding();

  const setField = (field: keyof BrandingDraft, value: string) => {
    setDraft(prev => ({ ...prev, [field]: value }));
    if (fieldErrors[field]) {
      const trimmed = value.trim();
      if (
        !trimmed ||
        ((field === 'primary_color' || field === 'secondary_color') &&
          HEX_COLOR_PATTERN.test(trimmed))
      ) {
        setFieldErrors(prev => ({ ...prev, [field]: '' }));
      }
    }
  };

  const handleColorBlur =
    (field: 'primary_color' | 'secondary_color') => () => {
      const value = draft[field].trim();
      if (value && !HEX_COLOR_PATTERN.test(value)) {
        setFieldErrors(prev => ({
          ...prev,
          [field]: 'Use a 6-digit hex value, for example #6A1B9A', // Intentional: example colour in validation text
        }));
      }
      onSave(field);
    };

  return (
    <Grid
      container
      columnSpacing={SECTION_GRID.columnSpacing}
      rowSpacing={SECTION_GRID.rowSpacing}
    >
      <Grid size={{ xs: 12, md: 6 }}>
        <ColorField
          label="Primary Colour"
          value={draft.primary_color}
          onChange={value => setField('primary_color', value)}
          onBlur={handleColorBlur('primary_color')}
          onPickerChange={value => onPickerChange('primary_color', value)}
          onPickerBlur={() => onPickerBlur('primary_color')}
          editable={editable}
          disabled={disabled}
          error={fieldErrors.primary_color}
          helperText="App bar, buttons and brand-tinted surfaces"
          inherited={deployment.primaryColor || RHESIS_PRIMARY_COLOR}
        />
      </Grid>

      <Grid size={{ xs: 12, md: 6 }}>
        <ColorField
          label="Secondary Colour"
          value={draft.secondary_color}
          onChange={value => setField('secondary_color', value)}
          onBlur={handleColorBlur('secondary_color')}
          onPickerChange={value => onPickerChange('secondary_color', value)}
          onPickerBlur={() => onPickerBlur('secondary_color')}
          editable={editable}
          disabled={disabled}
          error={fieldErrors.secondary_color}
          helperText="Secondary and call-to-action buttons"
          inherited={deployment.secondaryColor || RHESIS_SECONDARY_COLOR}
        />
      </Grid>

      <Grid size={{ xs: 12, md: 6 }}>
        <EditableField
          fullWidth
          editing={editable}
          disabled={disabled}
          label="Product Name"
          value={draft.product_name}
          onChange={e => setField('product_name', e.target.value)}
          onBlur={() => onSave('product_name')}
          placeholder={deployment.productName || DEFAULT_PRODUCT_NAME}
          InputLabelProps={{ shrink: true }}
          helperText={`Shown in page titles and the sidebar. Max ${MAX_PRODUCT_NAME_LENGTH} characters`}
        />
      </Grid>
    </Grid>
  );
}

/** Swatch edge length, matched to the field's inner height. */
const SWATCH_SIZE = 24;

/**
 * Hex field with the colour swatch inside it. The swatch is a live colour
 * picker when the user has edit permission, not only while an Edit button
 * is toggled.
 */
function ColorField({
  label,
  value,
  onChange,
  onBlur,
  onPickerChange,
  onPickerBlur,
  editable,
  disabled,
  error,
  helperText,
  inherited,
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
  /** Text-field blur: shows validation errors, then saves. */
  onBlur: () => void;
  /** Colour-picker change: updates draft + previews theme + debounced save. */
  onPickerChange: (value: string) => void;
  /** Colour-picker blur: flushes any pending debounced save. */
  onPickerBlur: () => void;
  editable: boolean;
  disabled: boolean;
  error?: string;
  helperText: string;
  inherited?: string;
}) {
  const trimmed = value.trim();
  const isValid = HEX_COLOR_PATTERN.test(trimmed);

  return (
    <EditableField
      fullWidth
      editing={editable}
      disabled={disabled}
      label={label}
      value={value}
      onChange={e => onChange(e.target.value)}
      onBlur={onBlur}
      placeholder={inherited ?? '#6A1B9A'}
      error={editable && !!error}
      helperText={editable ? error || helperText : helperText}
      slotProps={{
        input: {
          startAdornment: (
            <InputAdornment position="start">
              <ColorSwatch
                label={label}
                color={isValid ? trimmed : undefined}
                inherited={inherited}
                editable={editable}
                onChange={onPickerChange}
                onBlur={onPickerBlur}
              />
            </InputAdornment>
          ),
        },
      }}
    />
  );
}

/**
 * The colour chip. Unset fields show the inherited colour with a dashed
 * border. When editable, it is a native `<input type="color">`.
 */
function ColorSwatch({
  label,
  color,
  inherited,
  editable,
  onChange,
  onBlur,
}: {
  label: string;
  color?: string;
  inherited?: string;
  editable: boolean;
  onChange: (value: string) => void;
  onBlur: () => void;
}) {
  const shared = {
    width: SWATCH_SIZE,
    height: SWATCH_SIZE,
    flexShrink: 0,
    borderRadius: 0.75,
    boxSizing: 'border-box' as const,
  };

  if (!editable) {
    return (
      <Tooltip title={label}>
        <Box
          aria-label={
            color
              ? `${label} ${color}`
              : `${label} inherited ${inherited ?? 'default'}`
          }
          sx={{
            ...shared,
            bgcolor: color ?? inherited ?? 'transparent',
            border: theme =>
              color
                ? `1px solid ${theme.palette.greyscale.border}`
                : `1px dashed ${theme.palette.greyscale.subtitle}`,
          }}
        />
      </Tooltip>
    );
  }

  return (
    <Box
      component="input"
      type="color"
      aria-label={`${label} picker`}
      value={color ?? inherited ?? '#000000'}
      onChange={(e: React.ChangeEvent<HTMLInputElement>) =>
        onChange(e.target.value.toUpperCase())
      }
      onBlur={onBlur}
      sx={{
        ...shared,
        p: 0,
        cursor: 'pointer',
        appearance: 'none',
        WebkitAppearance: 'none',
        bgcolor: 'transparent',
        border: theme =>
          color
            ? `1px solid ${theme.palette.greyscale.border}`
            : `1px dashed ${theme.palette.greyscale.border}`,
        '&::-webkit-color-swatch-wrapper': { p: 0 },
        '&::-webkit-color-swatch': { border: 'none', borderRadius: 2 },
        '&::-moz-color-swatch': { border: 'none', borderRadius: 2 },
      }}
    />
  );
}
