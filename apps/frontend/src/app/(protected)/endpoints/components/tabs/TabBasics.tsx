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
  Typography,
  ToggleButton,
  ToggleButtonGroup,
  FormControlLabel,
  Switch,
  CircularProgress,
  ListItemIcon,
  ListItemText,
  FormHelperText,
  Accordion,
  AccordionSummary,
  AccordionDetails,
  Chip,
} from '@mui/material';
import { SectionCard } from '@/components/common/SectionCard';
import { getProjectIcon } from '@/components/common/ProjectIcons';
import { BORDER_RADIUS } from '@/styles/theme-constants';
import { Project } from '@/utils/api-client/interfaces/project';
import { KeyboardArrowDownIcon } from '@/components/icons';
import type { FormData } from '../EndpointForm';

const ENVIRONMENTS = ['production', 'staging', 'development', 'local'];

interface TabBasicsProps {
  formData: FormData;
  onChange: (field: keyof FormData, value: unknown) => void;
  projects: Project[];
  loadingProjects: boolean;
}

export default function TabBasics({
  formData,
  onChange,
  projects,
  loadingProjects,
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
        title="Connect your model under test"
        subtitle="Enter the API URL of the AI application you want to test. Rhesis will send test prompts to this endpoint and evaluate how it responds."
      >
        {/* URL */}
        <Box sx={{ display: 'flex', gap: 1, mb: 2, alignItems: 'flex-start' }}>
          <Chip
            label="POST"
            size="small"
            sx={{
              mt: 2,
              fontFamily: 'monospace',
              fontWeight: 600,
              bgcolor: 'primary.main',
              color: 'primary.contrastText',
              borderRadius: 1,
              flexShrink: 0,
            }}
          />
          <TextField
            fullWidth
            required
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
        </Box>

        {/* Name */}
        <TextField
          fullWidth
          required
          label="Endpoint Name"
          value={formData.name}
          onChange={e => onChange('name', e.target.value)}
          sx={{ mb: 2 }}
        />

        {/* Description — directly under name */}
        <TextField
          fullWidth
          label="Description"
          value={formData.description}
          onChange={e => onChange('description', e.target.value)}
          multiline
          rows={2}
          sx={{ mb: 2 }}
        />

        {/* Project */}
        {projects.length === 0 && !loadingProjects ? (
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
        ) : (
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
                      <ListItemText
                        primary={p.name}
                        secondary={p.description}
                      />
                    </MenuItem>
                  ))}
            </Select>
            {!formData.project_id && <FormHelperText>Required</FormHelperText>}
          </FormControl>
        )}

        {/* Advanced */}
        <Accordion
          disableGutters
          elevation={0}
          sx={{
            border: 1,
            borderColor: 'divider',
            borderRadius: `${BORDER_RADIUS.sm}px !important`,
            mb: 2,
          }}
        >
          <AccordionSummary expandIcon={<KeyboardArrowDownIcon />}>
            <Typography variant="body2" color="text.secondary">
              Additional settings
            </Typography>
          </AccordionSummary>
          <AccordionDetails>
            <Typography
              variant="caption"
              color="text.secondary"
              sx={{ display: 'block', mb: 1 }}
            >
              Environment
            </Typography>
            <ToggleButtonGroup
              value={formData.environment}
              exclusive
              onChange={(_, v) => {
                if (v) onChange('environment', v);
              }}
              sx={{ mb: 2 }}
            >
              {ENVIRONMENTS.map(env => (
                <ToggleButton
                  key={env}
                  value={env}
                  sx={{ textTransform: 'capitalize' }}
                >
                  {env}
                </ToggleButton>
              ))}
            </ToggleButtonGroup>

            <FormControlLabel
              control={
                <Switch
                  checked={formData.disable_tracing}
                  onChange={e => onChange('disable_tracing', e.target.checked)}
                />
              }
              label="Disable tracing"
            />
            <FormHelperText sx={{ mb: 2 }}>
              When enabled, invocations will not generate traces or telemetry
              data
            </FormHelperText>
          </AccordionDetails>
        </Accordion>
      </SectionCard>
    </Box>
  );
}
