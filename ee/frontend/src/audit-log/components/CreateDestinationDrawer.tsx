'use client';

import * as React from 'react';
import FormControl from '@mui/material/FormControl';
import InputLabel from '@mui/material/InputLabel';
import MenuItem from '@mui/material/MenuItem';
import Select from '@mui/material/Select';
import Stack from '@mui/material/Stack';
import TextField from '@mui/material/TextField';
import BaseDrawer from '@/components/common/BaseDrawer';
import {
  DATADOG_SITES,
  DESTINATION_KIND_LABELS,
  DESTINATION_LIMITS,
  DestinationKind,
  isHttpsUrl,
  type AuditDestinationCreate,
  type DatadogSite,
} from '../destinations';

interface CreateDestinationDrawerProps {
  open: boolean;
  onCancel: () => void;
  onSubmit: (body: AuditDestinationCreate) => Promise<void>;
  /** The backend's error, shown under the form. */
  errorMessage?: string | null;
}

interface FormState {
  kind: DestinationKind;
  name: string;
  url: string;
  token: string;
  site: DatadogSite;
  apiKey: string;
}

const INITIAL_STATE: FormState = {
  kind: DestinationKind.WEBHOOK,
  name: '',
  url: '',
  token: '',
  site: DATADOG_SITES[0],
  apiKey: '',
};

const KINDS = Object.values(DestinationKind);

/** The request body for the chosen kind, or null while a field is missing. */
export function toCreateBody(form: FormState): AuditDestinationCreate | null {
  const name = form.name.trim();
  const url = form.url.trim();
  if (!name) return null;
  switch (form.kind) {
    case DestinationKind.WEBHOOK:
      return isHttpsUrl(url) ? { kind: form.kind, name, url } : null;
    case DestinationKind.SPLUNK_HEC:
      return isHttpsUrl(url) && form.token.trim()
        ? { kind: form.kind, name, url, token: form.token.trim() }
        : null;
    case DestinationKind.DATADOG:
      return form.apiKey.trim()
        ? {
            kind: form.kind,
            name,
            site: form.site,
            api_key: form.apiKey.trim(),
          }
        : null;
  }
}

export default function CreateDestinationDrawer({
  open,
  onCancel,
  onSubmit,
  errorMessage,
}: CreateDestinationDrawerProps) {
  const [form, setForm] = React.useState<FormState>(INITIAL_STATE);
  const [submitting, setSubmitting] = React.useState(false);

  React.useEffect(() => {
    if (open) {
      setForm(INITIAL_STATE);
      setSubmitting(false);
    }
  }, [open]);

  const set = <K extends keyof FormState>(key: K, value: FormState[K]) =>
    setForm(prev => ({ ...prev, [key]: value }));

  const body = toCreateBody(form);
  const urlInvalid = form.url.trim().length > 0 && !isHttpsUrl(form.url.trim());

  const handleSubmit = async () => {
    if (!body || submitting) return;
    setSubmitting(true);
    try {
      await onSubmit(body);
    } catch {
      // The parent shows the error; keep the form as typed.
    } finally {
      setSubmitting(false);
    }
  };

  const urlField = (label: string, helper: string) => (
    <TextField
      label={label}
      required
      value={form.url}
      onChange={e => set('url', e.target.value)}
      error={urlInvalid}
      helperText={urlInvalid ? 'Use an https:// URL.' : helper}
      placeholder="https://"
      inputProps={{ maxLength: DESTINATION_LIMITS.URL }}
      fullWidth
    />
  );

  const secretField = (
    label: string,
    key: 'token' | 'apiKey',
    helper: string
  ) => (
    <TextField
      label={label}
      required
      type="password"
      autoComplete="off"
      value={form[key]}
      onChange={e => set(key, e.target.value)}
      helperText={helper}
      inputProps={{ maxLength: DESTINATION_LIMITS.SECRET }}
      fullWidth
    />
  );

  return (
    <BaseDrawer
      open={open}
      onClose={onCancel}
      title="Add Destination"
      onSave={handleSubmit}
      saveButtonText={submitting ? 'Adding...' : 'Add'}
      saveDisabled={!body || submitting}
      loading={submitting}
      error={errorMessage ?? undefined}
      closeButtonText="Cancel"
    >
      <Stack spacing={2}>
        <FormControl fullWidth>
          <InputLabel id="destination-kind-label">Type</InputLabel>
          <Select
            labelId="destination-kind-label"
            label="Type"
            value={form.kind}
            onChange={e => set('kind', e.target.value as DestinationKind)}
          >
            {KINDS.map(kind => (
              <MenuItem key={kind} value={kind}>
                {DESTINATION_KIND_LABELS[kind]}
              </MenuItem>
            ))}
          </Select>
        </FormControl>

        <TextField
          label="Name"
          required
          value={form.name}
          onChange={e => set('name', e.target.value)}
          helperText="Shown in this list and in the audit log."
          inputProps={{ maxLength: DESTINATION_LIMITS.NAME }}
          fullWidth
        />

        {form.kind === DestinationKind.WEBHOOK &&
          urlField(
            'URL',
            'Rhesis signs each request and shows the signing secret once, after you add it.'
          )}

        {form.kind === DestinationKind.SPLUNK_HEC && (
          <>
            {urlField(
              'HEC URL',
              'The HEC event endpoint, ending in /services/collector/event.'
            )}
            {secretField(
              'HEC token',
              'token',
              'Stored encrypted and never shown again.'
            )}
          </>
        )}

        {form.kind === DestinationKind.DATADOG && (
          <>
            <FormControl fullWidth>
              <InputLabel id="datadog-site-label">Site</InputLabel>
              <Select
                labelId="datadog-site-label"
                label="Site"
                value={form.site}
                onChange={e => set('site', e.target.value as DatadogSite)}
              >
                {DATADOG_SITES.map(site => (
                  <MenuItem key={site} value={site}>
                    {site}
                  </MenuItem>
                ))}
              </Select>
            </FormControl>
            {secretField(
              'API key',
              'apiKey',
              'Stored encrypted and never shown again.'
            )}
          </>
        )}
      </Stack>
    </BaseDrawer>
  );
}
