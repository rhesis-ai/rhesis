'use client';

/**
 * Create-AuthClient drawer.
 *
 * Mirrors the validation rules of the backend `AuthClientCreate`
 * Pydantic schema so the user gets immediate feedback rather than
 * a round-trip 422. The backend remains the authority -- these are
 * UX-only checks; nothing security-relevant rests on them.
 *
 * Field rationale:
 *
 * - **Client ID** uses `^[a-z0-9][a-z0-9_-]{2,63}$` (the same
 *   regex the backend enforces). We surface a helper string with
 *   the rule so the operator can fix typos in place.
 * - **Name** is optional but encouraged -- the list view orders by
 *   `created_at` and the operator usually wants a readable label
 *   to find a row later.
 * - **Expected `azp`** is the only mitigation against attacker A3
 *   in the threat model (a co-tenant integration replaying its own
 *   valid Keycloak token here). The helper text spells this out so
 *   operators understand the field is non-decorative.
 * - **Allowed scopes** are a multi-checkbox derived from
 *   `V1_SUPPORTED_SCOPES`. Forcing a checkbox UI (vs a free-text
 *   field) means we cannot accidentally send an unsupported scope
 *   the backend would 422 on.
 * - **Default scope** is a single-select narrowed to the currently
 *   selected `allowed_scopes`, mirroring the backend's
 *   "default_scope must be in allowed_scopes" rule. If the user
 *   un-checks the currently selected default, we clear the field
 *   so they have to consciously re-pick.
 */

import * as React from 'react';
import {
  Alert,
  Box,
  Checkbox,
  FormControl,
  FormControlLabel,
  FormGroup,
  FormHelperText,
  InputLabel,
  MenuItem,
  Select,
  Stack,
  TextField,
} from '@mui/material';
import BaseDrawer from '@/components/common/BaseDrawer';
import {
  V1_SUPPORTED_SCOPES,
  type AuthClientCreateRequest,
} from '../types';

/** Mirror of backend `_CLIENT_ID_RE`. Documented next to the field too. */
const CLIENT_ID_RE = /^[a-z0-9][a-z0-9_-]{2,63}$/;

interface CreateApiClientDrawerProps {
  open: boolean;
  onCancel: () => void;
  onSubmit: (body: AuthClientCreateRequest) => Promise<void>;
  /**
   * Surface backend errors here so they display alongside the form
   * (rather than as a top-of-page toast that is easy to miss). The
   * parent owns the error state because the same error may need to
   * persist across re-mounts (e.g. if the drawer briefly closes and
   * re-opens).
   */
  errorMessage?: string | null;
}

const INITIAL_STATE: AuthClientCreateRequest = {
  client_id: '',
  name: '',
  expected_subject_azp: '',
  expected_subject_audience: '',
  allowed_scopes: ['full'],
  default_scope: 'full',
};

export default function CreateApiClientDrawer({
  open,
  onCancel,
  onSubmit,
  errorMessage,
}: CreateApiClientDrawerProps) {
  const [form, setForm] = React.useState<AuthClientCreateRequest>(INITIAL_STATE);
  const [submitting, setSubmitting] = React.useState(false);

  React.useEffect(() => {
    if (open) {
      setForm(INITIAL_STATE);
      setSubmitting(false);
    }
  }, [open]);

  const clientIdValid =
    form.client_id.length === 0 || CLIENT_ID_RE.test(form.client_id);

  const handleScopeToggle = (scope: string) => {
    setForm(prev => {
      const has = prev.allowed_scopes.includes(scope);
      const next = has
        ? prev.allowed_scopes.filter(s => s !== scope)
        : [...prev.allowed_scopes, scope];
      const default_scope = next.includes(prev.default_scope)
        ? prev.default_scope
        : '';
      return { ...prev, allowed_scopes: next, default_scope };
    });
  };

  const canSubmit =
    !submitting &&
    form.client_id.length > 0 &&
    clientIdValid &&
    form.expected_subject_azp.trim().length > 0 &&
    form.expected_subject_audience.trim().length > 0 &&
    form.allowed_scopes.length > 0 &&
    form.default_scope.length > 0 &&
    form.allowed_scopes.includes(form.default_scope);

  const handleSubmit = async () => {
    if (!canSubmit) return;
    setSubmitting(true);
    try {
      const payload: AuthClientCreateRequest = {
        client_id: form.client_id,
        expected_subject_azp: form.expected_subject_azp.trim(),
        expected_subject_audience: form.expected_subject_audience.trim(),
        allowed_scopes: form.allowed_scopes,
        default_scope: form.default_scope,
      };
      if (form.name && form.name.trim()) payload.name = form.name.trim();
      await onSubmit(payload);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <BaseDrawer
      open={open}
      onClose={onCancel}
      title="Create API Client"
      onSave={handleSubmit}
      saveButtonText={submitting ? 'Creating...' : 'Create'}
      saveDisabled={!canSubmit}
      loading={submitting}
      error={errorMessage ?? undefined}
      closeButtonText="Cancel"
    >
      <Stack spacing={2}>
        <TextField
          label="Client ID"
          required
          value={form.client_id}
          onChange={e =>
            setForm({ ...form, client_id: e.target.value.toLowerCase() })
          }
          error={form.client_id.length > 0 && !clientIdValid}
          helperText={
            !clientIdValid
              ? 'Lowercase letters, digits, hyphens or underscores; 3-64 chars; starts alphanumeric.'
              : 'Stable identifier the integration uses in HTTP Basic. Cannot be changed later.'
          }
          inputProps={{ maxLength: 64 }}
          fullWidth
        />

        <TextField
          label="Name"
          value={form.name ?? ''}
          onChange={e => setForm({ ...form, name: e.target.value })}
          helperText="Human-readable label shown in this list."
          inputProps={{ maxLength: 120 }}
          fullWidth
        />

        <TextField
          label="Expected azp"
          required
          value={form.expected_subject_azp}
          onChange={e =>
            setForm({ ...form, expected_subject_azp: e.target.value })
          }
          helperText={
            'The exact azp claim the subject token must carry ' +
            '(typically the Keycloak client_id). The exchange ' +
            'rejects mismatching tokens; this is the only ' +
            'mitigation against a sibling integration replaying ' +
            'their own valid Keycloak token here.'
          }
          inputProps={{ maxLength: 255 }}
          fullWidth
        />

        <TextField
          label="Expected audience"
          required
          value={form.expected_subject_audience ?? ''}
          onChange={e =>
            setForm({
              ...form,
              expected_subject_audience: e.target.value,
            })
          }
          helperText={
            'Required. The exact aud claim the subject token must ' +
            'contain. Many IdPs (notably Keycloak service-account ' +
            'flows) hand the same azp to multiple downstream apps in ' +
            'the same realm, so azp on its own is insufficient -- the ' +
            'audience claim is the disambiguator.'
          }
          inputProps={{ maxLength: 255 }}
          fullWidth
        />

        <FormControl required>
          <Box sx={{ fontWeight: 500, mb: 0.5 }}>Allowed scopes</Box>
          <FormGroup row>
            {V1_SUPPORTED_SCOPES.map(scope => (
              <FormControlLabel
                key={scope}
                control={
                  <Checkbox
                    checked={form.allowed_scopes.includes(scope)}
                    onChange={() => handleScopeToggle(scope)}
                  />
                }
                label={scope}
              />
            ))}
          </FormGroup>
          <FormHelperText>
            Adding <code>offline_access</code> lets the integration
            exchange for a refresh token.
          </FormHelperText>
        </FormControl>

        <FormControl
          required
          disabled={form.allowed_scopes.length === 0}
          error={
            form.default_scope.length > 0 &&
            !form.allowed_scopes.includes(form.default_scope)
          }
        >
          <InputLabel id="default-scope-label">Default scope</InputLabel>
          <Select
            labelId="default-scope-label"
            label="Default scope"
            value={form.default_scope}
            onChange={e =>
              setForm({ ...form, default_scope: String(e.target.value) })
            }
          >
            {form.allowed_scopes.map(scope => (
              <MenuItem key={scope} value={scope}>
                {scope}
              </MenuItem>
            ))}
          </Select>
          <FormHelperText>
            Used when the caller omits the <code>scope</code> form
            parameter. Must be one of the allowed scopes.
          </FormHelperText>
        </FormControl>
      </Stack>
    </BaseDrawer>
  );
}
