'use client';

import React from 'react';
import {
  Box,
  TextField,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  Alert,
  Button,
  ToggleButton,
  ToggleButtonGroup,
  FormControlLabel,
  Switch,
  CircularProgress,
  ListItemIcon,
  ListItemText,
  FormHelperText,
  Grid,
  Stack,
  Typography,
} from '@mui/material';
import { SectionCard } from '@/components/common/SectionCard';
import FormSectionDivider from '@/components/common/FormSectionDivider';
import { getProjectIcon } from '@/components/common/ProjectIcons';
import { Project } from '@/utils/api-client/interfaces/project';
import type { FormData } from '../EndpointForm';

const ENVIRONMENTS = ['production', 'staging', 'development', 'local'];

interface TabBasicsProps {
  formData: FormData;
  onChange: (field: keyof FormData, value: unknown) => void;
  projects: Project[];
  loadingProjects: boolean;
  /** Hide project picker — project is inferred from the active project scope */
  hideProjectSelect?: boolean;
}

function ProjectSelect({
  formData,
  onChange,
  projects,
  loadingProjects,
}: TabBasicsProps) {
  if (projects.length === 0 && !loadingProjects) {
    return (
      <Alert
        severity="warning"
        sx={{ mb: 2 }}
        action={
          <Button
            color="inherit"
            size="small"
            component="a"
            href="/projects/create-new"
          >
            Create Project
          </Button>
        }
      >
        No projects available. Please create a project first.
      </Alert>
    );
  }

  return (
    <FormControl fullWidth required sx={{ mb: 2 }}>
      <InputLabel>Select Project</InputLabel>
      <Select
        value={formData.project_id}
        onChange={e => onChange('project_id', e.target.value)}
        label="Select Project"
        disabled={loadingProjects}
        renderValue={selected => {
          const p = projects.find(pr => pr.id === selected);
          return (
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
              {p && getProjectIcon(p)}
              {p?.name || 'No project selected'}
            </Box>
          );
        }}
      >
        {loadingProjects
          ? [
              formData.project_id ? (
                <MenuItem
                  key="__current"
                  value={formData.project_id}
                  sx={{ display: 'none' }}
                />
              ) : null,
              <MenuItem key="__loading" disabled value="">
                <CircularProgress size={20} sx={{ mr: 1 }} />
                Loading projects...
              </MenuItem>,
            ].filter(Boolean)
          : projects.map(p => (
              <MenuItem key={p.id} value={p.id}>
                <ListItemIcon>{getProjectIcon(p)}</ListItemIcon>
                <ListItemText primary={p.name} secondary={p.description} />
              </MenuItem>
            ))}
      </Select>
      {!formData.project_id && <FormHelperText>Required</FormHelperText>}
    </FormControl>
  );
}

export default function TabBasics({
  formData,
  onChange,
  projects,
  loadingProjects,
  hideProjectSelect = false,
}: TabBasicsProps) {
  const validateUrl = (url: string) => {
    try {
      new URL(url);
      return true;
    } catch {
      return false;
    }
  };

  return (
    <Box>
      <SectionCard
        title="Overview"
        subtitle={
          hideProjectSelect
            ? 'Name your endpoint and configure how Rhesis connects to it.'
            : 'Choose a project, name your endpoint, and configure how Rhesis connects to it.'
        }
      >
        {!hideProjectSelect && (
          <ProjectSelect
            formData={formData}
            onChange={onChange}
            projects={projects}
            loadingProjects={loadingProjects}
          />
        )}

        {hideProjectSelect && !loadingProjects && !formData.project_id && (
          <Alert
            severity="warning"
            sx={{ mb: 2 }}
            action={
              <Button
                color="inherit"
                size="small"
                component="a"
                href="/projects"
              >
                Select project
              </Button>
            }
          >
            No active project selected. Choose a project before creating an
            endpoint.
          </Alert>
        )}

        <TextField
          fullWidth
          required
          name="name"
          label="Endpoint Name"
          value={formData.name}
          onChange={e => onChange('name', e.target.value)}
          sx={{ mb: 2 }}
        />

        <TextField
          fullWidth
          label="Description"
          value={formData.description}
          onChange={e => onChange('description', e.target.value)}
          multiline
          rows={2}
          sx={{ mb: 2 }}
        />

        <FormSectionDivider
          headline="Connection"
          descriptiveText="Enter the API URL of the AI application you want to test. Rhesis will send test prompts to this endpoint and evaluate how it responds."
        />

        <Grid container spacing={2} sx={{ mt: 2, mb: 2 }}>
          <Grid size={{ xs: 12, sm: 3, md: 2 }}>
            <TextField
              fullWidth
              label="Method"
              value={formData.method}
              onChange={e => onChange('method', e.target.value)}
              slotProps={{
                input: {
                  readOnly: true,
                  sx: { fontFamily: 'monospace', fontWeight: 700 },
                },
              }}
            />
          </Grid>
          <Grid size={{ xs: 12, sm: 9, md: 10 }}>
            <TextField
              fullWidth
              required
              name="url"
              label="Endpoint URL"
              value={formData.url}
              onChange={e => onChange('url', e.target.value)}
              placeholder="https://api.example.com/chat"
              error={Boolean(formData.url && !validateUrl(formData.url))}
              helperText={
                formData.url && !validateUrl(formData.url)
                  ? 'Enter a valid URL'
                  : undefined
              }
            />
          </Grid>
        </Grid>

        <FormSectionDivider
          headline="Additional settings"
          descriptiveText="Environment and telemetry options for this endpoint."
        />

        <Stack spacing={3} sx={{ mt: 2 }}>
          <Box>
            <Typography variant="body2" color="text.secondary" sx={{ mb: 1 }}>
              Environment
            </Typography>
            <ToggleButtonGroup
              value={formData.environment}
              exclusive
              onChange={(_, v) => {
                if (v) onChange('environment', v);
              }}
              sx={{
                width: '100%',
                display: 'flex',
                flexWrap: 'wrap',
                '& .MuiToggleButton-root': {
                  flex: '1 1 auto',
                  textTransform: 'capitalize',
                },
              }}
            >
              {ENVIRONMENTS.map(env => (
                <ToggleButton key={env} value={env}>
                  {env}
                </ToggleButton>
              ))}
            </ToggleButtonGroup>
          </Box>

          <Box>
            <FormControlLabel
              sx={{
                ml: 0,
                alignItems: 'flex-start',
                gap: 1,
              }}
              control={
                <Switch
                  checked={formData.disable_tracing}
                  onChange={e => onChange('disable_tracing', e.target.checked)}
                  sx={{ mt: 0.25 }}
                />
              }
              label={
                <Box>
                  <Typography variant="body2">Disable tracing</Typography>
                  <FormHelperText sx={{ mt: 0.5, mx: 0 }}>
                    When enabled, invocations will not generate traces or
                    telemetry data
                  </FormHelperText>
                </Box>
              }
            />
          </Box>
        </Stack>
      </SectionCard>
    </Box>
  );
}
