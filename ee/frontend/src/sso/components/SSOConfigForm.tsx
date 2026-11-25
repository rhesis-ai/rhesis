'use client';

import React, {
  useState,
  useEffect,
  useMemo,
  useCallback,
  useRef,
} from 'react';
import Alert from '@mui/material/Alert';
import Box from '@mui/material/Box';
import Button from '@mui/material/Button';
import Chip from '@mui/material/Chip';
import CircularProgress from '@mui/material/CircularProgress';
import Collapse from '@mui/material/Collapse';
import Divider from '@mui/material/Divider';
import FormControlLabel from '@mui/material/FormControlLabel';
import Grid from '@mui/material/Grid';
import IconButton from '@mui/material/IconButton';
import Link from '@mui/material/Link';
import Menu from '@mui/material/Menu';
import MenuItem from '@mui/material/MenuItem';
import Switch from '@mui/material/Switch';
import TextField from '@mui/material/TextField';
import Tooltip from '@mui/material/Tooltip';
import Typography from '@mui/material/Typography';
import {
  Save as SaveIcon,
  Delete as DeleteIcon,
  PlayArrow as TestIcon,
  CheckCircle as SuccessIcon,
  Error as ErrorIcon,
  Add as AddIcon,
  ContentCopy as CopyIcon,
} from '@mui/icons-material';
import { useNotifications } from '@/components/common/NotificationContext';
import { useOrgSettings } from '@/contexts/OrgSettingsContext';
import { getBaseUrl } from '@/utils/url-resolver';
import { DetailTabNav } from '@/components/common/DetailTabNav';
import { SSOClient } from '../api/sso-client';
import type {
  MappingRule,
  ProviderInfo,
  RoleMapping,
  SSOConfig,
  SSOTestResult,
} from '../types';
import { EMPTY_ROLE_MAPPING } from '../role-mapping/mapping-json';
import { findProvider, GENERIC_PROVIDER } from '../role-mapping/providers';
import RoleMappingTab from '../role-mapping/RoleMappingTab';
import { DeleteModal } from '@/components/common/DeleteModal';
import { useAccessibilityMode } from '@/hooks/useAccessibilityMode';

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
  provider: GENERIC_PROVIDER.key,
};

const TAB_LABELS = ['Connection', 'Sign-in', 'Role mapping'];
const DETECT_DELAY_MS = 300;
// Which saved fields live on which tab, for the unsaved-changes dot.
const TAB_FIELDS: (keyof SSOConfig)[][] = [
  [
    'slug',
    'issuer_url',
    'client_id',
    'client_secret',
    'scopes',
    'allow_insecure_tls',
    'provider',
  ],
  ['auto_provision_users', 'allowed_domains'],
];

function CopyableUrl({
  label,
  url,
  onCopied,
}: {
  label: string;
  url: string;
  onCopied: () => void;
}) {
  return (
    <Box
      sx={{
        display: 'flex',
        alignItems: 'center',
        gap: 1,
        p: 1.5,
        bgcolor: 'action.hover',
        borderRadius: theme => `${theme.shape.borderRadius}px`,
      }}
    >
      <Typography variant="body2" color="text.secondary" sx={{ flexShrink: 0 }}>
        {label}
      </Typography>
      <Typography
        variant="body2"
        sx={{ fontFamily: 'monospace', wordBreak: 'break-all', flexGrow: 1 }}
      >
        {url}
      </Typography>
      <Tooltip title="Copy URL">
        <IconButton
          size="small"
          onClick={() => {
            navigator.clipboard.writeText(url);
            onCopied();
          }}
        >
          <CopyIcon fontSize="small" />
        </IconButton>
      </Tooltip>
    </Box>
  );
}

export default function SSOConfigForm() {
  const { organization, onUpdate } = useOrgSettings();
  const notifications = useNotifications();
  // SSO runs through the same-origin BFF, so login and callback live on this host.
  // Only read once loaded (client-side): on the server getBaseUrl() is BACKEND_URL.
  const ssoBaseUrl = getBaseUrl();
  const showCopied = () =>
    notifications.show('URL copied to clipboard', {
      severity: 'success',
      autoHideDuration: 3000,
    });
  const [formData, setFormData] = useState<SSOConfig>(DEFAULT_SSO_CONFIG);
  const [initialData, setInitialData] = useState<string>('');
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [testing, setTesting] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [confirmRemoveOpen, setConfirmRemoveOpen] = useState(false);
  const accessibilityMode = useAccessibilityMode();
  const [error, setError] = useState<string | null>(null);
  const [testResult, setTestResult] = useState<SSOTestResult | null>(null);
  const [hasExistingConfig, setHasExistingConfig] = useState(false);
  const [domainInput, setDomainInput] = useState('');
  const [roleMapping, setRoleMapping] =
    useState<RoleMapping>(EMPTY_ROLE_MAPPING);
  const [initialMapping, setInitialMapping] = useState(
    JSON.stringify(EMPTY_ROLE_MAPPING)
  );
  const [mappingJsonErrors, setMappingJsonErrors] = useState(false);
  const [ssoTab, setSsoTab] = useState(0);
  const [providerAnchor, setProviderAnchor] = useState<HTMLElement | null>(
    null
  );

  const hasChanges = useMemo(() => {
    return (
      JSON.stringify(formData) !== initialData ||
      JSON.stringify(roleMapping) !== initialMapping
    );
  }, [formData, initialData, roleMapping, initialMapping]);
  const isComplete = (r: MappingRule) =>
    Boolean(r.role_id) || r.projects.length > 0;
  const incompleteRule =
    roleMapping.enabled && !roleMapping.rules.every(isComplete);
  const [providers, setProviders] = useState<ProviderInfo[]>([]);
  const [detected, setDetected] = useState<string | null>(null);
  // Set when the admin edits the issuer, so the next detection replaces the stored
  // provider; a provider loaded from the server keeps any earlier correction.
  const issuerEdited = useRef(false);
  const provider = findProvider(providers, formData.provider);

  useEffect(() => {
    new SSOClient()
      .getProviders(organization.id)
      .then(setProviders)
      .catch(() => setProviders([]));
  }, [organization.id]);

  // The backend owns the detection rules; ask it shortly after the last keystroke.
  useEffect(() => {
    const issuer = formData.issuer_url.trim();
    if (!issuer) {
      setDetected(null);
      return;
    }
    let cancelled = false;
    const timer = setTimeout(() => {
      new SSOClient()
        .detectProvider(organization.id, issuer)
        .then(key => {
          if (cancelled) return;
          setDetected(key);
          if (issuerEdited.current) {
            issuerEdited.current = false;
            setFormData(f => ({ ...f, provider: key ?? GENERIC_PROVIDER.key }));
          }
        })
        .catch(() => !cancelled && setDetected(null));
    }, DETECT_DELAY_MS);
    return () => {
      cancelled = true;
      clearTimeout(timer);
    };
  }, [organization.id, formData.issuer_url]);

  const loadSSOConfig = useCallback(async () => {
    try {
      const client = new SSOClient();
      const config = await client.getSSOConfig(organization.id);
      if (config) {
        const loaded: SSOConfig = {
          ...DEFAULT_SSO_CONFIG,
          ...config,
          client_secret: '',
          slug: config.slug || '',
        };
        delete loaded.role_mapping;
        const mapping = config.role_mapping ?? EMPTY_ROLE_MAPPING;
        setFormData(loaded);
        setInitialData(JSON.stringify(loaded));
        setRoleMapping(mapping);
        setInitialMapping(JSON.stringify(mapping));
        setHasExistingConfig(true);
      } else {
        setInitialData(JSON.stringify(DEFAULT_SSO_CONFIG));
      }
    } catch {
      setInitialData(JSON.stringify(DEFAULT_SSO_CONFIG));
    } finally {
      setLoading(false);
    }
  }, [organization.id]);

  useEffect(() => {
    loadSSOConfig();
  }, [loadSSOConfig]);

  const handleChange =
    (field: keyof SSOConfig) => (e: React.ChangeEvent<HTMLInputElement>) => {
      const next = { ...formData, [field]: e.target.value };
      // A new issuer replaces any earlier guess or correction.
      if (field === 'issuer_url') issuerEdited.current = true;
      setFormData(next);
      setError(null);
      setTestResult(null);
    };

  const handleToggle =
    (field: 'enabled' | 'auto_provision_users' | 'allow_insecure_tls') =>
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
      const client = new SSOClient();

      // While mapping is off its rules are hidden, so half-made ones are dropped.
      const mappingToSave = {
        ...roleMapping,
        rules: roleMapping.rules.filter(isComplete),
      };
      const configToSave: Partial<SSOConfig> = {
        ...formData,
        client_secret: formData.client_secret || undefined,
        slug: formData.slug || undefined,
        role_mapping:
          roleMapping.enabled || mappingToSave.rules.length
            ? mappingToSave
            : null,
      };

      if (hasExistingConfig && !formData.client_secret) {
        delete configToSave.client_secret;
      }
      delete configToSave.login_url;

      await client.updateSSOConfig(organization.id, configToSave as SSOConfig);
      notifications.show('SSO configuration saved', {
        severity: 'success',
        autoHideDuration: 3000,
      });

      const loaded: SSOConfig = {
        ...formData,
        client_secret: '',
      };
      setInitialData(JSON.stringify(loaded));
      setFormData(loaded);
      setInitialMapping(JSON.stringify(roleMapping));
      setHasExistingConfig(true);
      onUpdate();
    } catch (err: unknown) {
      const message =
        err instanceof Error ? err.message : 'Failed to save SSO configuration';
      setError(message);
      notifications.show(message, {
        severity: 'error',
        autoHideDuration: 3000,
      });
    } finally {
      setSaving(false);
    }
  };

  const handleTest = async () => {
    setTesting(true);
    setTestResult(null);

    try {
      const client = new SSOClient();
      const result = await client.testSSOConnection(organization.id);
      setTestResult(result);
      // Discovery catches custom domains the URL alone can't; never override a correction.
      const discovered = result.provider;
      if (
        discovered &&
        formData.provider === (detected ?? GENERIC_PROVIDER.key)
      )
        setFormData(f => ({ ...f, provider: discovered }));
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
      const client = new SSOClient();
      await client.deleteSSOConfig(organization.id);
      notifications.show('SSO configuration removed', {
        severity: 'success',
        autoHideDuration: 3000,
      });
      setFormData(DEFAULT_SSO_CONFIG);
      setInitialData(JSON.stringify(DEFAULT_SSO_CONFIG));
      setRoleMapping(EMPTY_ROLE_MAPPING);
      setInitialMapping(JSON.stringify(EMPTY_ROLE_MAPPING));
      setHasExistingConfig(false);
      setTestResult(null);
      onUpdate();
    } catch (err: unknown) {
      const message =
        err instanceof Error
          ? err.message
          : 'Failed to remove SSO configuration';
      setError(message);
      notifications.show(message, {
        severity: 'error',
        autoHideDuration: 3000,
      });
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

  const initialParsed = initialData
    ? (JSON.parse(initialData) as SSOConfig)
    : formData;
  const tabDirty = [
    ...TAB_FIELDS.map(fields =>
      fields.some(
        f => JSON.stringify(formData[f]) !== JSON.stringify(initialParsed[f])
      )
    ),
    JSON.stringify(roleMapping) !== initialMapping,
  ];
  const tabs = TAB_LABELS.map((label, i) => ({
    key: label,
    label,
    id: `sso-tab-${i}`,
    'aria-controls': `sso-tabpanel-${i}`,
    badge: tabDirty[i] ? (
      <Box
        component="span"
        aria-label="Unsaved changes"
        sx={{
          width: 6,
          height: 6,
          borderRadius: '50%',
          bgcolor: 'warning.main',
          flexShrink: 0,
        }}
      />
    ) : undefined,
  }));
  const dirtyTabs = TAB_LABELS.filter((_, i) => tabDirty[i]);
  const corrected = !!detected && formData.provider !== detected;
  const issuerHelper = !detected ? (
    'The issuer address from your identity provider. Rhesis recognises the provider from it.'
  ) : (
    <Box
      component="span"
      sx={{
        display: 'inline-flex',
        flexWrap: 'wrap',
        alignItems: 'center',
        columnGap: 0.5,
      }}
    >
      <SuccessIcon
        color={provider.supports_groups ? 'success' : 'warning'}
        sx={{ fontSize: 'inherit' }}
      />
      <span>
        {provider.key === GENERIC_PROVIDER.key
          ? 'Standard OIDC provider.'
          : `${corrected ? 'Set to' : 'Detected'} ${provider.title}.`}
        {provider.supports_groups
          ? ''
          : ' It doesn’t send groups, so role mapping isn’t available.'}
      </span>
      <Link
        component="button"
        type="button"
        variant="caption"
        onClick={e => setProviderAnchor(e.currentTarget)}
      >
        Not right?
      </Link>
    </Box>
  );

  return (
    <Box component="form" onSubmit={handleSave}>
      {error && (
        <Alert severity="error" sx={{ mb: 2 }}>
          {error}
        </Alert>
      )}

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

      <Collapse in={formData.enabled}>
        <Box
          sx={{
            mt: 2,
            height: theme => theme.spacing(5.5),
            borderBottom: 1,
            borderColor: 'divider',
          }}
        >
          <DetailTabNav
            tabs={tabs}
            activeIndex={ssoTab}
            onChange={setSsoTab}
            aria-label="SSO settings sections"
            tabGap="32px"
            size="compact"
            sx={{ height: '100%' }}
          />
        </Box>

        <Box
          role="tabpanel"
          id={`sso-tabpanel-${ssoTab}`}
          aria-labelledby={`sso-tab-${ssoTab}`}
          sx={{ pt: 3 }}
        >
          {ssoTab === 0 && (
            <Grid container spacing={2}>
              <Grid size={12}>
                <TextField
                  fullWidth
                  label="SSO Slug"
                  placeholder="acme-corp"
                  value={formData.slug || ''}
                  onChange={handleChange('slug')}
                  helperText="Used in the SSO login URL. Lowercase letters, numbers, and hyphens (3-50 chars)."
                  slotProps={{
                    htmlInput: {
                      pattern: '[a-z0-9][a-z0-9\\-]*[a-z0-9]',
                      maxLength: 50,
                    },
                  }}
                />
              </Grid>

              {formData.slug && (
                <Grid size={12}>
                  <CopyableUrl
                    label="SSO Login URL:"
                    url={`${ssoBaseUrl}/auth/sso/${formData.slug}`}
                    onCopied={showCopied}
                  />
                </Grid>
              )}

              <Grid size={12}>
                <CopyableUrl
                  label="Redirect URI:"
                  url={`${ssoBaseUrl}/auth/sso/callback`}
                  onCopied={showCopied}
                />
              </Grid>

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
                  helperText={issuerHelper}
                  required={formData.enabled}
                />
                <Menu
                  anchorEl={providerAnchor}
                  open={!!providerAnchor}
                  onClose={() => setProviderAnchor(null)}
                >
                  {providers.map(({ key: k, title }) => (
                    <MenuItem
                      key={k}
                      selected={k === formData.provider}
                      onClick={() => {
                        setFormData({ ...formData, provider: k });
                        setProviderAnchor(null);
                      }}
                    >
                      {title}
                    </MenuItem>
                  ))}
                </Menu>
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

              {hasExistingConfig && (
                <Grid size={12}>
                  <Box
                    sx={{
                      display: 'flex',
                      alignItems: 'center',
                      gap: 2,
                      mt: 1,
                    }}
                  >
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
                      <Box
                        sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}
                      >
                        {testResult.success ? (
                          <SuccessIcon color="success" fontSize="small" />
                        ) : (
                          <ErrorIcon color="error" fontSize="small" />
                        )}
                        <Typography
                          variant="body2"
                          color={
                            testResult.success ? 'success.main' : 'error.main'
                          }
                        >
                          {testResult.message}
                        </Typography>
                      </Box>
                    )}
                  </Box>
                </Grid>
              )}
            </Grid>
          )}
          {ssoTab === 1 && (
            <Grid container spacing={2}>
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
                <Divider sx={{ my: 1 }} />
                <Typography variant="subtitle2" sx={{ mt: 1, mb: 1 }}>
                  Allowed Email Domains
                </Typography>
                <Typography
                  variant="body2"
                  color="text.secondary"
                  sx={{ mb: 1 }}
                >
                  If set, only users with email addresses from these domains can
                  sign in via SSO.
                </Typography>
              </Grid>

              <Grid size={12}>
                <Box sx={{ display: 'flex', gap: 1, mb: 1 }}>
                  <TextField
                    size="small"
                    placeholder="example.com"
                    slotProps={{
                      htmlInput: { 'aria-label': 'Allowed domain' },
                    }}
                    value={domainInput}
                    onChange={e => setDomainInput(e.target.value)}
                    onKeyDown={handleDomainKeyDown}
                    sx={{ flexGrow: 1 }}
                  />
                  <IconButton
                    aria-label="Add domain"
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
            </Grid>
          )}
          {ssoTab === 2 && (
            <RoleMappingTab
              value={roleMapping}
              onChange={setRoleMapping}
              provider={provider}
              onJsonErrors={setMappingJsonErrors}
            />
          )}
        </Box>
      </Collapse>

      <Box>
        <Divider sx={{ my: 2 }} />
        <Box
          sx={{
            display: 'flex',
            gap: 2,
            justifyContent: 'space-between',
            flexWrap: 'wrap',
          }}
        >
          <Box>
            {hasExistingConfig && (
              <Tooltip title="Remove SSO configuration entirely">
                <Button
                  variant="outlined"
                  color="error"
                  startIcon={
                    deleting ? <CircularProgress size={16} /> : <DeleteIcon />
                  }
                  // Removing SSO can lock members out; confirm first (3.3.4).
                  onClick={
                    accessibilityMode
                      ? () => setConfirmRemoveOpen(true)
                      : handleDelete
                  }
                  disabled={deleting || saving}
                >
                  Remove SSO
                </Button>
              </Tooltip>
            )}
          </Box>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
            {hasChanges && (
              <Typography
                variant="body2"
                color="text.secondary"
                aria-live="polite"
              >
                {mappingJsonErrors
                  ? 'Fix the role mapping JSON to save'
                  : incompleteRule
                    ? 'Each group needs a role or a project'
                    : dirtyTabs.length
                      ? `Unsaved changes in ${dirtyTabs.join(', ')}`
                      : ''}
              </Typography>
            )}
            <Button
              type="submit"
              variant="contained"
              startIcon={saving ? <CircularProgress size={16} /> : <SaveIcon />}
              disabled={
                saving || !hasChanges || mappingJsonErrors || incompleteRule
              }
            >
              Save
            </Button>
          </Box>
        </Box>
      </Box>
      <DeleteModal
        open={confirmRemoveOpen}
        onClose={() => setConfirmRemoveOpen(false)}
        onConfirm={async () => {
          await handleDelete();
          setConfirmRemoveOpen(false);
        }}
        isLoading={deleting}
        title="Remove SSO configuration"
        message="Members who sign in with SSO will no longer be able to use it. This cannot be undone."
        confirmButtonText={deleting ? 'Removing...' : 'Remove SSO'}
      />
    </Box>
  );
}
