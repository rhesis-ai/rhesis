'use client';

import React, { useRef, useState } from 'react';
import { Alert, Box, Button, Typography } from '@mui/material';
import { useRouter } from 'next/navigation';
import { Organization } from '@/utils/api-client/interfaces/organization';
import { ApiClientFactory } from '@/utils/api-client/client-factory';
import { useNotifications } from '@/components/common/NotificationContext';
import { SectionCard } from '@/components/common/SectionCard';
import { useCan } from '@/components/common/Can';
import { Capability } from '@/constants/capabilities';
import {
  DEFAULT_FAVICON_URL,
  ORG_FAVICON_URL,
  getDeploymentBranding,
  withAssetVersion,
} from '@/config/branding';
import {
  FAVICON_ACCEPT,
  MAX_FAVICON_BYTES,
  RECOMMENDED_FAVICON_DIMENSION,
  brandingOf,
  describeFaviconSize,
  faviconWarning,
  formatBytes,
} from './branding-constants';

interface BrandingFaviconFormProps {
  organization: Organization;
  onUpdate: () => void;
}

/**
 * Favicon upload. Kept out of the `EditableSection` draft flow the other forms
 * use: a file upload is its own request with its own failure mode, so an
 * explicit upload/remove pair is clearer than folding it into a Save button.
 */
export default function BrandingFaviconForm({
  organization,
  onUpdate,
}: BrandingFaviconFormProps) {
  const router = useRouter();
  const notifications = useNotifications();
  const canUpdateOrg = useCan(Capability.Organization.UPDATE);
  const inputRef = useRef<HTMLInputElement>(null);
  const [busy, setBusy] = useState(false);

  const favicon = brandingOf(organization)?.favicon;
  const warning = faviconWarning(favicon);
  // What is actually on screen when this organisation sets nothing: the
  // deployment's BRAND_FAVICON_URL, or the shipped Rhesis icon.
  const inheritedUrl =
    getDeploymentBranding().faviconUrl || DEFAULT_FAVICON_URL;

  const runUpdate = async (action: () => Promise<unknown>, message: string) => {
    setBusy(true);
    try {
      await action();
      notifications.show(message, { severity: 'success' });
      router.refresh();
      onUpdate();
    } catch (err: unknown) {
      notifications.show(
        err instanceof Error ? err.message : 'Failed to update favicon',
        { severity: 'error' }
      );
    } finally {
      setBusy(false);
    }
  };

  const handleFileSelected = async (
    event: React.ChangeEvent<HTMLInputElement>
  ) => {
    const file = event.target.files?.[0];
    // Clear first: picking the same file twice must still fire a change event.
    event.target.value = '';
    if (!file) return;

    if (file.size > MAX_FAVICON_BYTES) {
      notifications.show(
        `Favicon must be at most ${formatBytes(MAX_FAVICON_BYTES)}`,
        { severity: 'error' }
      );
      return;
    }

    await runUpdate(
      () =>
        new ApiClientFactory()
          .getOrganizationsClient()
          .uploadBrandingFavicon(file),
      'Favicon updated successfully'
    );
  };

  const handleRemove = () =>
    runUpdate(
      () =>
        new ApiClientFactory().getOrganizationsClient().deleteBrandingFavicon(),
      'Favicon removed'
    );

  return (
    <SectionCard
      title="Favicon"
      subtitle={
        `The browser-tab icon and the brand mark in the sidebar. Use a square ` +
        `SVG, or a PNG at ${RECOMMENDED_FAVICON_DIMENSION} x ${RECOMMENDED_FAVICON_DIMENSION} ` +
        `(it is scaled down for the tab and up to 92 px in onboarding). ` +
        `SVG, PNG, WebP, ICO, JPEG or GIF, up to ${formatBytes(MAX_FAVICON_BYTES)}.`
      }
    >
      <Box>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 3 }}>
          <Box
            sx={{
              width: 64,
              height: 64,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              flexShrink: 0,
              borderRadius: 1,
              border: theme => `1px solid ${theme.palette.greyscale.border}`,
              bgcolor: theme => theme.palette.greyscale.fieldSurface,
            }}
          >
            <img
              src={
                favicon
                  ? withAssetVersion(ORG_FAVICON_URL, favicon.sha256)
                  : inheritedUrl
              }
              alt={favicon ? 'Organization favicon' : 'Inherited favicon'}
              width={40}
              height={40}
              style={{ width: 40, height: 40, objectFit: 'contain' }}
            />
          </Box>

          <Box
            sx={{
              display: 'flex',
              alignItems: 'center',
              gap: 1.5,
              flexGrow: 1,
              minWidth: 0,
            }}
          >
            <Typography
              variant="body2"
              sx={{ color: theme => theme.palette.greyscale.body }}
            >
              {favicon ? favicon.filename : 'Using the deployment default'}
            </Typography>

            {canUpdateOrg && (
              <>
                <Button
                  variant="outlined"
                  size="small"
                  disabled={busy}
                  onClick={() => inputRef.current?.click()}
                >
                  {favicon ? 'Replace' : 'Upload'}
                </Button>
                {favicon && (
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
              </>
            )}
          </Box>
        </Box>

        {favicon && (
          <Typography
            variant="caption"
            sx={{ color: theme => theme.palette.greyscale.subtitle, mt: 0.5 }}
          >
            {describeFaviconSize(favicon)}
          </Typography>
        )}
      </Box>

      {/* A warning, not a block — the icon works, it just will not look its
          best, and that is the operator's call to make. */}
      {warning && (
        <Alert severity="warning" sx={{ mt: 2 }}>
          {warning}
        </Alert>
      )}

      <input
        ref={inputRef}
        type="file"
        accept={FAVICON_ACCEPT}
        hidden
        onChange={handleFileSelected}
      />
    </SectionCard>
  );
}
