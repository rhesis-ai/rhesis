'use client';

import React, { useContext, useEffect, useState } from 'react';
import {
  Autocomplete,
  Box,
  Button,
  CircularProgress,
  createFilterOptions,
  Grid,
  Link,
  TextField,
  ToggleButton,
  ToggleButtonGroup,
  Typography,
} from '@mui/material';
import { useRouter } from 'next/navigation';
import { Organization } from '@/utils/api-client/interfaces/organization';
import { ApiClientFactory } from '@/utils/api-client/client-factory';
import { useNotifications } from '@/components/common/NotificationContext';
import { BrandPreviewContext } from '@/components/providers/ThemeProvider';
import { SectionCard } from '@/components/common/SectionCard';
import { useCan } from '@/components/common/Can';
import { Capability } from '@/constants/capabilities';
import { getDeploymentBranding } from '@/config/branding';
import {
  FONT_ACCEPT,
  FONT_WEIGHTS,
  FONT_WEIGHT_LABELS,
  MAX_FONT_BYTES,
  MAX_FONT_FAMILY_LENGTH,
  SAFE_FONT_FAMILY_PATTERN,
  brandingOf,
  formatBytes,
  type FontWeight,
} from './branding-constants';

type SelectedFiles = Partial<Record<FontWeight, File>>;
type FontSource = 'google' | 'upload';

interface BrandingFontFormProps {
  organization: Organization;
  onUpdate: () => void;
}

/** Shared family-name rules, checked here so the error lands next to the field. */
function familyError(family: string): string | null {
  const trimmed = family.trim();
  if (!trimmed) return 'Enter the font family name';
  if (trimmed.length > MAX_FONT_FAMILY_LENGTH) {
    return `Font family must be at most ${MAX_FONT_FAMILY_LENGTH} characters`;
  }
  if (!SAFE_FONT_FAMILY_PATTERN.test(trimmed)) {
    return 'Font family may only contain letters, digits, spaces and hyphens';
  }
  return null;
}

const fontFilterOptions = createFilterOptions<string>({ limit: 50 });

const previewFontsLoaded = new Set<string>();

function loadFontPreview(family: string) {
  if (previewFontsLoaded.has(family)) return;
  previewFontsLoaded.add(family);
  const link = document.createElement('link');
  link.rel = 'stylesheet';
  link.href = `https://fonts.googleapis.com/css2?family=${encodeURIComponent(family)}&text=${encodeURIComponent(family)}&display=swap`;
  document.head.appendChild(link);
}

function FontPreviewOption({
  family,
  ...liProps
}: React.HTMLAttributes<HTMLLIElement> & { family: string }) {
  useEffect(() => {
    loadFontPreview(family);
  }, [family]);

  return (
    <li
      {...liProps}
      style={{ ...liProps.style, fontFamily: `"${family}", sans-serif` }}
    >
      {family}
    </li>
  );
}

/**
 * Brand font: either a family from Google Fonts, or files the organization
 * uploads itself.
 *
 * Google covers the common case in one field and leaves the licensing to
 * Google. Uploading is for a licensed typeface Google does not carry, and for
 * deployments whose browsers cannot reach Google at all.
 */
export default function BrandingFontForm({
  organization,
  onUpdate,
}: BrandingFontFormProps) {
  const router = useRouter();
  const notifications = useNotifications();
  const canUpdateOrg = useCan(Capability.Organization.UPDATE);
  const { previewBrandColors, clearBrandPreview } =
    useContext(BrandPreviewContext);

  const font = brandingOf(organization)?.font;
  // The typeface in use when this organisation sets none.
  const inheritedFamily = getDeploymentBranding().fontFamily;

  const [source, setSource] = useState<FontSource>(font?.source ?? 'google');
  const [family, setFamily] = useState(font?.family ?? '');
  const [files, setFiles] = useState<SelectedFiles>({});
  const [busy, setBusy] = useState(false);

  const hasSelection = Object.values(files).some(Boolean);
  const disabled = !canUpdateOrg || busy;

  const run = async (action: () => Promise<unknown>, message: string) => {
    setBusy(true);
    try {
      await action();
      notifications.show(message, { severity: 'success' });
      router.refresh();
      onUpdate();
      return true;
    } catch (err: unknown) {
      notifications.show(
        err instanceof Error ? err.message : 'Failed to update the brand font',
        { severity: 'error' }
      );
      return false;
    } finally {
      setBusy(false);
    }
  };

  const handleFileSelected =
    (weight: FontWeight) => (event: React.ChangeEvent<HTMLInputElement>) => {
      const file = event.target.files?.[0];
      event.target.value = '';
      if (!file) return;

      if (file.size > MAX_FONT_BYTES) {
        notifications.show(
          `${FONT_WEIGHT_LABELS[weight]} must be at most ${formatBytes(MAX_FONT_BYTES)}`,
          { severity: 'error' }
        );
        return;
      }

      setFiles(prev => ({ ...prev, [weight]: file }));
    };

  const handleFontCommit = async (selectedFamily: string) => {
    const trimmed = selectedFamily.trim();
    if (!trimmed) return;

    const error = familyError(trimmed);
    if (error) {
      notifications.show(error, { severity: 'error' });
      return;
    }

    previewBrandColors({ fontFamily: trimmed });

    try {
      await new ApiClientFactory()
        .getOrganizationsClient()
        .updateOrganizationSettings({
          branding: { font: { source: 'google', family: trimmed } },
        });
      router.refresh();
      onUpdate();
    } catch (err: unknown) {
      notifications.show(
        err instanceof Error ? err.message : 'Failed to update the brand font',
        { severity: 'error' }
      );
    }
  };

  const handleUploadFont = async () => {
    const error = familyError(family);
    if (error) {
      notifications.show(error, { severity: 'error' });
      return;
    }
    if (!hasSelection) {
      notifications.show('Choose at least one font file', {
        severity: 'error',
      });
      return;
    }

    const ok = await run(
      () =>
        new ApiClientFactory()
          .getOrganizationsClient()
          .uploadBrandingFont(family.trim(), files),
      'Brand font updated successfully'
    );
    if (ok) setFiles({});
  };

  const handleRemove = async () => {
    clearBrandPreview();
    const ok = await run(
      () =>
        new ApiClientFactory()
          .getOrganizationsClient()
          .updateOrganizationSettings({ branding: { font: null } }),
      'Brand font removed'
    );
    if (ok) {
      setFamily('');
      setFiles({});
    }
  };

  return (
    <SectionCard
      title="Brand Font"
      subtitle={
        inheritedFamily && !font
          ? `Currently using ${inheritedFamily} from this deployment. Pick a family from Google Fonts, or upload your own files, to override it.`
          : 'Replaces the built-in typeface across the app. Pick a family from Google Fonts, or upload your own files.'
      }
    >
      <Grid container spacing={3}>
        <Grid size={12}>
          <ToggleButtonGroup
            exclusive
            size="small"
            value={source}
            onChange={(_event, next: FontSource | null) =>
              next && setSource(next)
            }
            disabled={disabled}
            aria-label="Font source"
          >
            <ToggleButton value="google">Google Fonts</ToggleButton>
            <ToggleButton value="upload">Upload files</ToggleButton>
          </ToggleButtonGroup>
        </Grid>

        {source === 'google' ? (
          <GoogleFontFields
            family={family}
            onFamilyChange={setFamily}
            onCommit={handleFontCommit}
            disabled={disabled}
            inheritedFamily={inheritedFamily}
          />
        ) : (
          <UploadFontFields
            family={family}
            onFamilyChange={setFamily}
            inheritedFamily={inheritedFamily}
            files={files}
            uploadedWeights={font?.source === 'upload' ? font.weights : []}
            disabled={disabled}
            onSelect={handleFileSelected}
            onClear={weight =>
              setFiles(({ [weight]: _removed, ...rest }) => rest)
            }
          />
        )}

        {canUpdateOrg && (source === 'upload' || font) && (
          <Grid size={12}>
            <Box sx={{ display: 'flex', gap: 1.5 }}>
              {source === 'upload' && (
                <Button
                  variant="contained"
                  size="small"
                  disabled={busy || !hasSelection}
                  onClick={handleUploadFont}
                >
                  Upload font
                </Button>
              )}
              {font && (
                <Button
                  variant="text"
                  size="small"
                  color="error"
                  disabled={busy}
                  onClick={handleRemove}
                >
                  Reset
                </Button>
              )}
            </Box>
          </Grid>
        )}
      </Grid>
    </SectionCard>
  );
}

/**
 * The Google Fonts catalogue, fetched once per mount.
 *
 * Returns an empty list when it cannot be loaded. That is the same answer the
 * backend gives an air-gapped deployment, and the field works without it — the
 * suggestions are a convenience, not the validation.
 */
function useGoogleFontFamilies(enabled: boolean) {
  const [families, setFamilies] = useState<string[]>([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!enabled) return;

    let cancelled = false;
    setLoading(true);

    new ApiClientFactory()
      .getOrganizationsClient()
      .getGoogleFontFamilies()
      .then(result => {
        if (!cancelled) setFamilies(result);
      })
      .catch(() => {
        if (!cancelled) setFamilies([]);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [enabled]);

  return { families, loading };
}

function GoogleFontFields({
  family,
  onFamilyChange,
  onCommit,
  disabled,
  inheritedFamily,
}: {
  family: string;
  onFamilyChange: (value: string) => void;
  onCommit: (family: string) => void;
  disabled: boolean;
  /** The deployment's family, shown as the placeholder when nothing is set. */
  inheritedFamily?: string;
}) {
  const { families, loading } = useGoogleFontFamilies(true);

  return (
    <>
      <Grid size={{ xs: 12, md: 6 }}>
        <Autocomplete
          freeSolo
          options={families}
          filterOptions={fontFilterOptions}
          loading={loading}
          value={family}
          onChange={(_event, next) => {
            const value = next ?? '';
            onFamilyChange(value);
            if (value) onCommit(value);
          }}
          onInputChange={(_event, next) => onFamilyChange(next)}
          disabled={disabled}
          renderOption={({ key, ...optionProps }, option) => (
            <FontPreviewOption
              key={key as string}
              {...optionProps}
              family={option as string}
            />
          )}
          renderInput={params => (
            <TextField
              {...params}
              label="Google Font Family"
              placeholder={inheritedFamily || 'Roboto'}
              helperText={
                'Any family published on Google Fonts. ' +
                'Pick one from the list or type a name and press Enter.'
              }
              slotProps={{
                input: {
                  ...params.InputProps,
                  endAdornment: (
                    <>
                      {loading ? <CircularProgress size={16} /> : null}
                      {params.InputProps.endAdornment}
                    </>
                  ),
                },
              }}
            />
          )}
        />
      </Grid>

      <Grid size={12}>
        <Typography
          variant="body2"
          sx={{ color: theme => theme.palette.greyscale.subtitle }}
        >
          Browse the catalogue at{' '}
          <Link
            href="https://fonts.google.com"
            target="_blank"
            rel="noopener noreferrer"
          >
            fonts.google.com
          </Link>
          . The font loads from Google in each visitor&apos;s browser, so this
          needs outbound access to fonts.googleapis.com. Upload the files
          instead if your deployment is air-gapped.
        </Typography>
      </Grid>
    </>
  );
}

function UploadFontFields({
  family,
  onFamilyChange,
  inheritedFamily,
  files,
  uploadedWeights,
  disabled,
  onSelect,
  onClear,
}: {
  family: string;
  onFamilyChange: (value: string) => void;
  /** The deployment's family, shown as the placeholder when nothing is set. */
  inheritedFamily?: string;
  files: SelectedFiles;
  uploadedWeights: string[];
  disabled: boolean;
  onSelect: (
    weight: FontWeight
  ) => (event: React.ChangeEvent<HTMLInputElement>) => void;
  onClear: (weight: FontWeight) => void;
}) {
  return (
    <>
      <Grid size={{ xs: 12, md: 6 }}>
        <TextField
          fullWidth
          label="Font Family"
          value={family}
          onChange={e => onFamilyChange(e.target.value)}
          disabled={disabled}
          placeholder={inheritedFamily || 'Inria Sans'}
          helperText="Must match the name inside the font files. Letters, digits, spaces and hyphens only"
        />
      </Grid>

      <Grid size={12}>
        <Typography
          variant="body2"
          sx={{ mb: 1.5, color: theme => theme.palette.greyscale.subtitle }}
        >
          WOFF2 is smallest and widely supported; TTF, OTF and WOFF also work,
          up to {formatBytes(MAX_FONT_BYTES)} per file. Regular carries nearly
          all body text; Bold is used for headings and emphasis, and Light for
          muted labels. Upload only the weights you have — the browser derives
          the rest from the nearest one.
        </Typography>
        <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1.5 }}>
          {FONT_WEIGHTS.map(weight => (
            <FontWeightRow
              key={weight}
              weight={weight}
              selected={files[weight]}
              uploaded={uploadedWeights.includes(weight)}
              disabled={disabled}
              onSelect={onSelect(weight)}
              onClear={() => onClear(weight)}
            />
          ))}
        </Box>
      </Grid>
    </>
  );
}

function FontWeightRow({
  weight,
  selected,
  uploaded,
  disabled,
  onSelect,
  onClear,
}: {
  weight: FontWeight;
  selected?: File;
  uploaded: boolean;
  disabled: boolean;
  onSelect: (event: React.ChangeEvent<HTMLInputElement>) => void;
  onClear: () => void;
}) {
  const inputId = `brand-font-${weight}`;

  const status = selected
    ? selected.name
    : uploaded
      ? 'Uploaded'
      : 'Not uploaded';

  return (
    <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
      <Typography variant="body2" sx={{ width: 120, flexShrink: 0 }}>
        {FONT_WEIGHT_LABELS[weight]}
      </Typography>

      <Typography
        variant="body2"
        sx={{
          flexGrow: 1,
          minWidth: 0,
          overflow: 'hidden',
          textOverflow: 'ellipsis',
          whiteSpace: 'nowrap',
          color: theme =>
            selected || uploaded
              ? theme.palette.greyscale.body
              : theme.palette.greyscale.subtitle,
        }}
      >
        {status}
      </Typography>

      <Button
        component="label"
        htmlFor={inputId}
        variant="outlined"
        size="small"
        disabled={disabled}
      >
        Choose file
        <input
          id={inputId}
          type="file"
          accept={FONT_ACCEPT}
          hidden
          onChange={onSelect}
        />
      </Button>

      {selected && (
        <Button
          variant="text"
          size="small"
          disabled={disabled}
          onClick={onClear}
        >
          Clear
        </Button>
      )}
    </Box>
  );
}
