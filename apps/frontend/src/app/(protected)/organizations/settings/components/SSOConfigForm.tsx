'use client';

import React, { useState, useEffect, useMemo, useCallback } from 'react';
import {
  Box,
  TextField,
  Button,
  Alert,
  CircularProgress,
  Grid,
  Switch,
  FormControlLabel,
  Chip,
  IconButton,
  Tooltip,
  Typography,
  Divider,
  Collapse,
} from '@mui/material';
import {
  Save as SaveIcon,
  Delete as DeleteIcon,
  PlayArrow as TestIcon,
  CheckCircle as SuccessIcon,
  Error as ErrorIcon,
  Add as AddIcon,
  ContentCopy as CopyIcon,
} from '@mui/icons-material';
import { Organization, SSOConfig, SSOTestResult } from '@/utils/api-client/interfaces/organization';
import { ApiClientFactory } from '@/utils/api-client/client-factory';
import { useNotifications } from '@/components/common/NotificationContext';
const SSO_DISPLAY_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:8080';

interface SSOConfigFormProps {
  organization: Organization;
  sessionToken: string;
  onUpdate: () => void;
}

const DEFAULT_SSO_CONFIG: SSOConfig = {
  enabled: false,
  provider_type: 'oidc',
  issuer_url: '',
  client_id: '',
  client_secret: '',
  scopes: 'openid email profile',
  auto_provision_users: false,
  allowed_domains: null,
  allowed_auth_methods: null,
  allow_insecure_tls: false,
  slug: '',
};

export default function SSOConfigForm({
  organization,
  sessionToken,
  onUpdate,
}: SSOConfigFormProps) {
  const notifications = useNotifications();
  const [formData, setFormData] = useState<SSOConfig>(DEFAULT_SSO_CONFIG);
  const [initialData, setInitialData] = useState<string>('');
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [testing, setTesting] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [testResult, setTestResult] = useState<SSOTestResult | null>(null);
  const [hasExistingConfig, setHasExistingConfig] = useState(false);
  const [domainInput, setDomainInput] = useState('');

  const hasChanges = useMemo(() => {
    return JSON.stringify(formData) !== initialData;
  }, [formData, initialData]);

  const loadSSOConfig = useCallback(async () => {
    try {
      const apiFactory = new ApiClientFactory(sessionToken);
      const client = apiFactory.getOrganizationsClient();
      const config = await client.getSSOConfig(organization.id);
      if (config) {
        const loaded: SSOConfig = {
          ...DEFAULT_SSO_CONFIG,
          ...config,
          client_secret: '',
          slug: config.slug || '',
        };
        setFormData(loaded);
        setInitialData(JSON.stringify(loaded));
        setHasExistingConfig(true);
      } else {
        setInitialData(JSON.stringify(DEFAULT_SSO_CONFIG));
      }
    } catch {
      setInitialData(JSON.stringify(DEFAULT_SSO_CONFIG));
    } finally {
      setLoading(false);
    }
  }, [sessionToken, organization.id]);

  useEffect(() => {
    loadSSOConfig();
  }, [loadSSOConfig]);

  const handleChange = (field: keyof SSOConfig) =>
    (e: React.ChangeEvent<HTMLInputElement>) => {
      setFormData({ ...formData, [field]: e.target.value });
      setError(null);
      setTestResult(null);
    };

  const handleToggle = (field: 'enabled' | 'auto_provision_users' | 'allow_insecure_tls') =>
    (_: React.ChangeEvent<HTMLInputElement>, checked: boolean) => {
      setFormData({ ...formData, [field]: checked });
      setError(null);
    };

  const handleAddDomain = () => {
    const domain = domainInput.trim().toLowerCase().replace(/^\./, '');
    if (!domain) return;
    const current = formData.allowed_domains || [];
    if (!current.includes(domain)) {
      setFormData({
        ...formData,
        allowed_domains: [...current, domain],
      });
    }
    setDomainInput('');
  };

  const handleRemoveDomain = (domain: string) => {
    const current = formData.allowed_domains || [];
    const updated = current.filter(d => d !== domain);
    setFormData({
      ...formData,
      allowed_domains: updated.length > 0 ? updated : null,
    });
  };

  const handleDomainKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter') {
      e.preventDefault();
      handleAddDomain();
    }
  };

  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault();
    setSaving(true);
    setError(null);

    try {
      const apiFactory = new ApiClientFactory(sessionToken);
      const client = apiFactory.getOrganizationsClient();

      const configToSave: Partial<SSOConfig> = {
        ...formData,
        client_secret: formData.client_secret || undefined,
        slug: formData.slug || undefined,
      };

      if (hasExistingConfig && !formData.client_secret) {
        delete configToSave.client_secret;
      }
      delete configToSave.login_url;

      await client.updateSSOConfig(organization.id, configToSave as SSOConfig);
      notifications.show('SSO configuration saved', { severity: 'success', autoHideDuration: 3000 });

      const loaded: SSOConfig = {
        ...formData,
        client_secret: '',
      };
      setInitialData(JSON.stringify(loaded));
      setFormData(loaded);
      setHasExistingConfig(true);
      onUpdate();
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : 'Failed to save SSO configuration';
      setError(message);
      notifications.show(message, { severity: 'error', autoHideDuration: 3000 });
    } finally {
      setSaving(false);
    }
  };

  const handleTest = async () => {
    setTesting(true);
    setTestResult(null);

    try {
      const apiFactory = new ApiClientFactory(sessionToken);
      const client = apiFactory.getOrganizationsClient();
      const result = await client.testSSOConnection(organization.id);
      setTestResult(result);
    } catch {
      setTestResult({ success: false, message: 'Connection test failed' });
    } finally {
      setTesting(false);
    }
  };

  const handleDelete = async () => {
    setDeleting(true);
    setError(null);

    try {
      const apiFactory = new ApiClientFactory(sessionToken);
      const client = apiFactory.getOrganizationsClient();
      await client.deleteSSOConfig(organization.id);
      notifications.show('SSO configuration removed', { severity: 'success', autoHideDuration: 3000 });
      setFormData(DEFAULT_SSO_CONFIG);
      setInitialData(JSON.stringify(DEFAULT_SSO_CONFIG));
      setHasExistingConfig(false);
      setTestResult(null);
      onUpdate();
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : 'Failed to remove SSO configuration';
      setError(message);
      notifications.show(message, { severity: 'error', autoHideDuration: 3000 });
    } finally {
      setDeleting(false);
    }
  };

  if (loading) {
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center', p: 3 }}>
        <CircularProgress size={24} />
      </Box>
    );
  }

  return (
    <Box component="form" onSubmit={handleSave}>
      {error && (
        <Alert severity="error" sx={{ mb: 2 }}>
          {error}
        </Alert>
      )}

      <Grid container spacing={2}>
        <Grid size={12}>
          <FormControlLabel
            control={
              <Switch
                checked={formData.enabled}
                onChange={handleToggle('enabled')}
                color="primary"
              />
            }
            label="Enable SSO"
          />
        </Grid>

        <Collapse in={formData.enabled} sx={{ width: '100%' }}>
          <Grid container spacing={2} sx={{ px: 2, pt: 1 }}>
            <Grid size={12}>
              <TextField
                fullWidth
                label="SSO Slug"
                placeholder="acme-corp"
                value={formData.slug || ''}
                onChange={handleChange('slug')}
                helperText="Used in the SSO login URL. Lowercase letters, numbers, and hyphens (3-50 chars)."
                slotProps={{
                  htmlInput: { pattern: '[a-z0-9][a-z0-9-]*[a-z0-9]', maxLength: 50 },
                }}
              />
            </Grid>

            {formData.slug && (
              <Grid size={12}>
                <Box
                  sx={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: 1,
                    p: 1.5,
                    bgcolor: 'action.hover',
                    borderRadius: 1,
                  }}
                >
                  <Typography variant="body2" color="text.secondary" sx={{ flexShrink: 0 }}>
                    SSO Login URL:
                  </Typography>
                  <Typography
                    variant="body2"
                    sx={{ fontFamily: 'monospace', wordBreak: 'break-all', flexGrow: 1 }}
                  >
                    {`${SSO_DISPLAY_BASE_URL}/auth/sso/${formData.slug}`}
                  </Typography>
                  <Tooltip title="Copy URL">
                    <IconButton
                      size="small"
                      onClick={() => {
                        const url = `${SSO_DISPLAY_BASE_URL}/auth/sso/${formData.slug}`;
                        navigator.clipboard.writeText(url);
                        notifications.show('URL copied to clipboard', { severity: 'success', autoHideDuration: 3000 });
                      }}
                    >
                      <CopyIcon fontSize="small" />
                    </IconButton>
                  </Tooltip>
                </Box>
              </Grid>
            )}

            <Grid size={12}>
              <Divider sx={{ my: 1 }} />
            </Grid>

            <Grid size={12}>
              <TextField
                fullWidth
                label="Issuer URL"
                placeholder="https://your-idp.example.com/realms/your-realm"
                value={formData.issuer_url}
                onChange={handleChange('issuer_url')}
                helperText="The OIDC issuer URL from your identity provider"
                required={formData.enabled}
              />
            </Grid>

            <Grid size={{ xs: 12, md: 6 }}>
              <TextField
                fullWidth
                label="Client ID"
                value={formData.client_id}
                onChange={handleChange('client_id')}
                required={formData.enabled}
              />
            </Grid>

            <Grid size={{ xs: 12, md: 6 }}>
              <TextField
                fullWidth
                label="Client Secret"
                type="password"
                value={formData.client_secret}
                onChange={handleChange('client_secret')}
                placeholder={hasExistingConfig ? '(unchanged)' : ''}
                required={!hasExistingConfig && formData.enabled}
                helperText={
                  hasExistingConfig
                    ? 'Leave empty to keep current secret'
                    : 'Client secret from your identity provider'
                }
              />
            </Grid>

            <Grid size={12}>
              <TextField
                fullWidth
                label="Scopes"
                value={formData.scopes}
                onChange={handleChange('scopes')}
                helperText="Space-separated OIDC scopes"
              />
            </Grid>

            <Grid size={12}>
              <Divider sx={{ my: 1 }} />
              <Typography variant="subtitle2" sx={{ mt: 1, mb: 1 }}>
                User Provisioning
              </Typography>
            </Grid>

            <Grid size={12}>
              <FormControlLabel
                control={
                  <Switch
                    checked={formData.auto_provision_users}
                    onChange={handleToggle('auto_provision_users')}
                    color="primary"
                  />
                }
                label="Auto-provision new users on first SSO login"
              />
            </Grid>

            <Grid size={12}>
              <FormControlLabel
                control={
                  <Switch
                    checked={formData.allow_insecure_tls}
                    onChange={handleToggle('allow_insecure_tls')}
                    color="warning"
                  />
                }
                label="Allow self-signed / untrusted TLS certificates (use only for on-premise IdPs)"
              />
            </Grid>

            <Grid size={12}>
              <Divider sx={{ my: 1 }} />
              <Typography variant="subtitle2" sx={{ mt: 1, mb: 1 }}>
                Allowed Email Domains
              </Typography>
              <Typography variant="body2" color="text.secondary" sx={{ mb: 1 }}>
                If set, only users with email addresses from these domains can sign in via SSO.
              </Typography>
            </Grid>

            <Grid size={12}>
              <Box sx={{ display: 'flex', gap: 1, mb: 1 }}>
                <TextField
                  size="small"
                  placeholder="example.com"
                  value={domainInput}
                  onChange={e => setDomainInput(e.target.value)}
                  onKeyDown={handleDomainKeyDown}
                  sx={{ flexGrow: 1 }}
                />
                <IconButton
                  size="small"
                  onClick={handleAddDomain}
                  disabled={!domainInput.trim()}
                >
                  <AddIcon />
                </IconButton>
              </Box>
              <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.5 }}>
                {(formData.allowed_domains || []).map(domain => (
                  <Chip
                    key={domain}
                    label={domain}
                    size="small"
                    onDelete={() => handleRemoveDomain(domain)}
                  />
                ))}
              </Box>
            </Grid>

            {/* Test Connection */}
            {hasExistingConfig && (
              <Grid size={12}>
                <Divider sx={{ my: 1 }} />
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 2, mt: 1 }}>
                  <Button
                    variant="outlined"
                    startIcon={
                      testing ? <CircularProgress size={16} /> : <TestIcon />
                    }
                    onClick={handleTest}
                    disabled={testing || !hasExistingConfig}
                  >
                    Test Connection
                  </Button>
                  {testResult && (
                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
                      {testResult.success ? (
                        <SuccessIcon color="success" fontSize="small" />
                      ) : (
                        <ErrorIcon color="error" fontSize="small" />
                      )}
                      <Typography
                        variant="body2"
                        color={testResult.success ? 'success.main' : 'error.main'}
                      >
                        {testResult.message}
                      </Typography>
                    </Box>
                  )}
                </Box>
              </Grid>
            )}
          </Grid>
        </Collapse>

        {/* Actions */}
        <Grid size={12}>
          <Divider sx={{ my: 2 }} />
          <Box sx={{ display: 'flex', gap: 2, justifyContent: 'space-between' }}>
            <Box>
              {hasExistingConfig && (
                <Tooltip title="Remove SSO configuration entirely">
                  <Button
                    variant="outlined"
                    color="error"
                    startIcon={
                      deleting ? <CircularProgress size={16} /> : <DeleteIcon />
                    }
                    onClick={handleDelete}
                    disabled={deleting || saving}
                  >
                    Remove SSO
                  </Button>
                </Tooltip>
              )}
            </Box>
            <Button
              type="submit"
              variant="contained"
              startIcon={
                saving ? <CircularProgress size={16} /> : <SaveIcon />
              }
              disabled={saving || !hasChanges}
            >
              Save
            </Button>
          </Box>
        </Grid>
      </Grid>
    </Box>
  );
}
