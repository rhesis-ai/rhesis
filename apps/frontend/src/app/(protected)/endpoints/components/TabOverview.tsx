'use client';

import React, { useState } from 'react';
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
  Stack,
  Link,
  Collapse,
  IconButton,
} from '@mui/material';
import { KeyboardArrowDownIcon, KeyboardArrowUpIcon } from '@/components/icons';
import { useTheme } from '@mui/material/styles';
import FormSectionDivider from '@/components/common/FormSectionDivider';
import { getProjectIcon } from '@/components/common/ProjectIcons';
import { Project } from '@/utils/api-client/interfaces/project';
import { useCan } from '@/components/common/Can';
import { Capability } from '@/constants/capabilities';
import JsonMonacoField from '../[identifier]/components/JsonMonacoField';
import type { FormData } from './EndpointForm';

const VERSION_INFO_DOCS_URL =
  'https://docs.rhesis.ai/docs/endpoints/management#version-information';

const ENVIRONMENTS = ['production', 'staging', 'development', 'local'];

interface TabOverviewProps {
  formData: FormData;
  onChange: (field: keyof FormData, value: unknown) => void;
  projects: Project[];
  loadingProjects: boolean;
  /** Hide project picker — project is inferred from the active project scope */
  hideProjectSelect?: boolean;
  /** Why the version information can't be saved, or null when it can. */
  versionInfoError?: string | null;
}

function ProjectSelect({
  formData,
  onChange,
  projects,
  loadingProjects,
}: TabOverviewProps) {
  const canCreateProject = useCan(Capability.Project.CREATE);

  if (projects.length === 0 && !loadingProjects) {
    return (
      <Alert
        severity="warning"
        // Only offer the shortcut to callers who hold project:create. The
        // built-in Member role does not, so linking them to the wizard just
        // produces a 403 once they reach the end of it.
        action={
          canCreateProject ? (
            <Button
              color="inherit"
              size="small"
              component="a"
              href="/projects/create-new"
            >
              Create Project
            </Button>
          ) : undefined
        }
      >
        {canCreateProject
          ? 'No projects available. Please create a project first.'
          : 'No projects available. Ask an administrator to add you to a project.'}
      </Alert>
    );
  }

  return (
    <FormControl fullWidth required>
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

/** A section heading that wraps to the column's width instead of setting it. */
function SectionHeading(
  props: React.ComponentProps<typeof FormSectionDivider>
) {
  return (
    <Box sx={{ width: 0, minWidth: '100%' }}>
      <FormSectionDivider {...props} />
    </Box>
  );
}

export default function TabOverview({
  formData,
  onChange,
  projects,
  loadingProjects,
  hideProjectSelect = false,
  versionInfoError = null,
}: TabOverviewProps) {
  const theme = useTheme();
  const editorTheme = theme.palette.mode === 'dark' ? 'vs-dark' : 'light';
  // Optional, so the editor starts closed unless there's already something in it.
  const [versionInfoOpen, setVersionInfoOpen] = useState(() =>
    Boolean(formData.version_info.trim())
  );
  // An error blocks Next, so it's never hidden in a closed section.
  const versionInfoExpanded = versionInfoOpen || Boolean(versionInfoError);

  return (
    <Stack spacing={5}>
      <Stack spacing={4}>
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
        />

        <TextField
          fullWidth
          label="Description"
          value={formData.description}
          onChange={e => onChange('description', e.target.value)}
          multiline
          rows={3}
        />
      </Stack>

      <Stack spacing={3} sx={{ alignSelf: 'flex-start' }}>
        <SectionHeading
          headline="Environment"
          descriptiveText="Choose where this endpoint runs."
        />
        <ToggleButtonGroup
          value={formData.environment}
          exclusive
          color="primary"
          onChange={(_, v) => {
            if (v) onChange('environment', v);
          }}
          sx={{
            '& .MuiToggleButton-root': {
              textTransform: 'capitalize',
              fontWeight: 700,
              py: 1,
              px: 2,
              color: 'primary.main',
              borderColor: 'primary.main',
              '&.Mui-selected, &.Mui-selected:hover': {
                bgcolor: 'primary.main',
                color: 'primary.contrastText',
              },
            },
          }}
        >
          {ENVIRONMENTS.map(env => (
            <ToggleButton key={env} value={env}>
              {env}
            </ToggleButton>
          ))}
        </ToggleButtonGroup>
      </Stack>

      <Stack spacing={versionInfoExpanded ? 3 : 0}>
        <Box
          sx={{
            display: 'flex',
            alignItems: 'flex-start',
            justifyContent: 'space-between',
            gap: 2,
          }}
        >
          <FormSectionDivider
            headline="Version Information"
            descriptiveText={
              <>
                Optional JSON describing the system behind this endpoint, such
                as prompt version, model and parameters. Recorded on every test
                run, so past runs keep showing the version that produced them.
                Avoid secrets: this is shown wherever the endpoint is visible.{' '}
                <Link
                  href={VERSION_INFO_DOCS_URL}
                  target="_blank"
                  rel="noopener noreferrer"
                >
                  Learn more
                </Link>
              </>
            }
          />
          <IconButton
            onClick={() => setVersionInfoOpen(o => !o)}
            disabled={Boolean(versionInfoError)}
            aria-expanded={versionInfoExpanded}
            aria-controls="endpoint-version-info-editor"
            aria-label={
              versionInfoExpanded
                ? 'Hide version information'
                : 'Show version information'
            }
          >
            {versionInfoExpanded ? (
              <KeyboardArrowUpIcon />
            ) : (
              <KeyboardArrowDownIcon />
            )}
          </IconButton>
        </Box>
        <Collapse in={versionInfoExpanded} id="endpoint-version-info-editor">
          <JsonMonacoField
            editorKey="create-version-info"
            height="160px"
            theme={editorTheme}
            value={formData.version_info}
            onChange={v => onChange('version_info', v)}
          />
          <FormHelperText error={Boolean(versionInfoError)} sx={{ mx: 1.75 }}>
            {versionInfoError ??
              'e.g. { "prompt_version": "v3.2", "model": "gpt-4o" }'}
          </FormHelperText>
        </Collapse>
      </Stack>

      <Stack spacing={3}>
        <FormSectionDivider
          headline="Timeout"
          descriptiveText="How long Rhesis waits for a response. Leave empty for the default of 30 seconds."
        />
        <TextField
          label="Seconds"
          sx={{ alignSelf: 'flex-start' }}
          type="number"
          value={formData.timeout_seconds}
          onChange={e => onChange('timeout_seconds', e.target.value)}
          placeholder="30"
          slotProps={{
            input: { inputProps: { min: 1 } },
          }}
        />
      </Stack>

      <Stack spacing={3}>
        <FormSectionDivider
          headline="Tracing"
          descriptiveText="Capture traces and telemetry for endpoint invocations."
        />
        <FormControlLabel
          sx={{ ml: 0, gap: 1, alignSelf: 'flex-start' }}
          control={
            <Switch
              checked={!formData.disable_tracing}
              onChange={e => onChange('disable_tracing', !e.target.checked)}
            />
          }
          label="Enable tracing"
        />
      </Stack>
    </Stack>
  );
}
