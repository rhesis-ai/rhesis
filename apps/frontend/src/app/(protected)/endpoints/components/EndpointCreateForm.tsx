'use client';

import { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import {
  Box,
  FormControl,
  Grid,
  IconButton,
  InputAdornment,
  InputLabel,
  MenuItem,
  Select,
  TextField,
  Typography,
} from '@mui/material';
import { LoadingButton } from '@mui/lab';
import {
  LockIcon,
  VisibilityIcon,
  VisibilityOffIcon,
} from '@/components/icons';
import { SectionCard } from '@/components/common/SectionCard';
import { useNotifications } from '@/components/common/NotificationContext';
import { ApiClientFactory } from '@/utils/api-client/client-factory';
import { Project } from '@/utils/api-client/interfaces/project';
import { createEndpoint } from '@/actions/endpoints';
import { normalizeUrl } from '@/utils/validation';
import { useSession } from 'next-auth/react';

const ENVIRONMENTS = ['development', 'staging', 'production', 'local'] as const;
const METHODS = ['POST', 'GET', 'PUT', 'PATCH', 'DELETE'] as const;
const CONNECTION_TYPES = ['REST', 'SDK'] as const;

interface FormValues {
  name: string;
  description: string;
  connection_type: 'REST' | 'SDK';
  url: string;
  method: string;
  environment: 'development' | 'staging' | 'production' | 'local';
  project_id: string;
  auth_token: string;
}

const DEFAULT_FORM: FormValues = {
  name: '',
  description: '',
  connection_type: 'REST',
  url: '',
  method: 'POST',
  environment: 'development',
  project_id: '',
  auth_token: '',
};

export default function EndpointCreateForm() {
  const router = useRouter();
  const notifications = useNotifications();
  const { data: session } = useSession();
  const [form, setForm] = useState<FormValues>(DEFAULT_FORM);
  const [projects, setProjects] = useState<Project[]>([]);
  const [isSaving, setIsSaving] = useState(false);
  const [showToken, setShowToken] = useState(false);
  const [errors, setErrors] = useState<
    Partial<Record<keyof FormValues, string>>
  >({});

  useEffect(() => {
    const loadProjects = async () => {
      if (!session?.session_token) return;
      try {
        const factory = new ApiClientFactory(session.session_token);
        const client = factory.getProjectsClient();
        const data = await client.getAllProjects();
        setProjects(data);
      } catch {
        // Projects are optional — silently ignore
      }
    };
    loadProjects();
  }, [session?.session_token]);

  function set<K extends keyof FormValues>(key: K, value: FormValues[K]) {
    setForm(prev => ({ ...prev, [key]: value }));
    if (errors[key]) setErrors(prev => ({ ...prev, [key]: undefined }));
  }

  function validate(): boolean {
    const next: Partial<Record<keyof FormValues, string>> = {};
    if (!form.name.trim()) next.name = 'Name is required';
    if (form.connection_type === 'REST' && !form.url.trim())
      next.url = 'URL is required for REST endpoints';
    setErrors(next);
    return Object.keys(next).length === 0;
  }

  async function handleCreate() {
    if (!validate()) return;
    setIsSaving(true);
    try {
      const result = await createEndpoint({
        name: form.name.trim(),
        description: form.description.trim() || undefined,
        connection_type: form.connection_type,
        url:
          form.connection_type === 'REST' ? normalizeUrl(form.url) : undefined,
        method: form.connection_type === 'REST' ? form.method : undefined,
        environment: form.environment,
        project_id: form.project_id || undefined,
        auth_token: form.auth_token.trim() || undefined,
        config_source: 'manual',
        response_format: 'json',
      });

      if (result.success && result.data) {
        notifications.show('Endpoint created successfully', {
          severity: 'success',
        });
        router.push(`/endpoints/${result.data.id}`);
      } else {
        throw new Error(result.error || 'Failed to create endpoint');
      }
    } catch (err) {
      notifications.show((err as Error).message, { severity: 'error' });
    } finally {
      setIsSaving(false);
    }
  }

  return (
    <Box>
      {/* Basic Info */}
      <SectionCard title="Basic info">
        <Grid container spacing={2}>
          <Grid item xs={12} md={6}>
            <TextField
              fullWidth
              required
              label="Name"
              value={form.name}
              onChange={e => set('name', e.target.value)}
              error={!!errors.name}
              helperText={errors.name}
            />
          </Grid>
          <Grid item xs={12} md={6}>
            <TextField
              fullWidth
              label="Description"
              value={form.description}
              onChange={e => set('description', e.target.value)}
              multiline
              minRows={1}
            />
          </Grid>
          <Grid item xs={12} md={6}>
            <FormControl fullWidth>
              <InputLabel>Environment</InputLabel>
              <Select
                value={form.environment}
                label="Environment"
                onChange={e =>
                  set(
                    'environment',
                    e.target.value as FormValues['environment']
                  )
                }
              >
                {ENVIRONMENTS.map(env => (
                  <MenuItem key={env} value={env}>
                    {env.charAt(0).toUpperCase() + env.slice(1)}
                  </MenuItem>
                ))}
              </Select>
            </FormControl>
          </Grid>
          {projects.length > 0 && (
            <Grid item xs={12} md={6}>
              <FormControl fullWidth>
                <InputLabel>Project (optional)</InputLabel>
                <Select
                  value={form.project_id}
                  label="Project (optional)"
                  onChange={e => set('project_id', e.target.value)}
                >
                  <MenuItem value="">
                    <em>None</em>
                  </MenuItem>
                  {projects.map(p => (
                    <MenuItem key={p.id} value={p.id}>
                      {p.name}
                    </MenuItem>
                  ))}
                </Select>
              </FormControl>
            </Grid>
          )}
        </Grid>
      </SectionCard>

      {/* Connection */}
      <SectionCard title="Connection">
        <Grid container spacing={2}>
          <Grid item xs={12} md={4}>
            <FormControl fullWidth>
              <InputLabel>Type</InputLabel>
              <Select
                value={form.connection_type}
                label="Type"
                onChange={e =>
                  set(
                    'connection_type',
                    e.target.value as FormValues['connection_type']
                  )
                }
              >
                {CONNECTION_TYPES.map(t => (
                  <MenuItem key={t} value={t}>
                    {t}
                  </MenuItem>
                ))}
              </Select>
            </FormControl>
          </Grid>

          {form.connection_type === 'REST' && (
            <>
              <Grid item xs={12} md={6}>
                <TextField
                  fullWidth
                  required
                  label="URL"
                  placeholder="api.example.com/v1/chat"
                  helperText={
                    errors.url ||
                    'https:// will be added automatically if omitted'
                  }
                  value={form.url}
                  onChange={e => set('url', e.target.value)}
                  error={!!errors.url}
                />
              </Grid>
              <Grid item xs={12} md={2}>
                <FormControl fullWidth>
                  <InputLabel>Method</InputLabel>
                  <Select
                    value={form.method}
                    label="Method"
                    onChange={e => set('method', e.target.value)}
                  >
                    {METHODS.map(m => (
                      <MenuItem key={m} value={m}>
                        {m}
                      </MenuItem>
                    ))}
                  </Select>
                </FormControl>
              </Grid>
            </>
          )}

          {form.connection_type === 'SDK' && (
            <Grid item xs={12}>
              <Typography variant="body2" color="text.secondary">
                SDK endpoints are configured through the Rhesis SDK. Install the
                SDK and use the <code>@endpoint</code> decorator to connect your
                function.
              </Typography>
            </Grid>
          )}
        </Grid>
      </SectionCard>

      {/* Authentication (REST only) */}
      {form.connection_type === 'REST' && (
        <SectionCard
          title="Authentication"
          subtitle="Optional. Token will be encrypted and sent as Authorization: Bearer <token>."
        >
          <TextField
            fullWidth
            label="API Token"
            type={showToken ? 'text' : 'password'}
            value={form.auth_token}
            onChange={e => set('auth_token', e.target.value)}
            placeholder="sk-..."
            helperText="Leave empty if your endpoint does not require authentication"
            InputProps={{
              startAdornment: (
                <InputAdornment position="start">
                  <LockIcon color="action" />
                </InputAdornment>
              ),
              endAdornment: (
                <InputAdornment position="end">
                  <IconButton
                    aria-label="toggle token visibility"
                    onClick={() => setShowToken(v => !v)}
                    edge="end"
                  >
                    {showToken ? <VisibilityOffIcon /> : <VisibilityIcon />}
                  </IconButton>
                </InputAdornment>
              ),
            }}
          />
        </SectionCard>
      )}

      <Box sx={{ display: 'flex', justifyContent: 'flex-end', gap: 2 }}>
        <LoadingButton
          variant="contained"
          color="primary"
          loading={isSaving}
          onClick={handleCreate}
        >
          Create endpoint
        </LoadingButton>
      </Box>
    </Box>
  );
}
