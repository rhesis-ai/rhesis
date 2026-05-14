'use client';

import * as React from 'react';
import { useCallback, useEffect, useMemo, useState } from 'react';
import {
  Alert,
  Box,
  Button,
  Chip,
  CircularProgress,
  FormControl,
  InputLabel,
  MenuItem,
  Paper,
  Select,
  Stack,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Typography,
} from '@mui/material';
import { useRouter } from 'next/navigation';
import { PageContainer } from '@toolpad/core/PageContainer';
import { ApiClientFactory } from '@/utils/api-client/client-factory';
import {
  ExperimentRead,
  shortVersion,
} from '@/utils/api-client/interfaces/parameters';
import { Project } from '@/utils/api-client/interfaces/project';
import { AddIcon, BiotechIcon } from '@/components/icons';
import CreateExperimentDialog from './CreateExperimentDialog';

interface ExperimentsClientWrapperProps {
  sessionToken: string;
}

interface ExperimentRow extends ExperimentRead {
  projectName: string;
}

/**
 * Index page for experiments across all projects the user can see.
 *
 * Lists shared + my-private experiments per project (the backend
 * filter handles visibility — the UI is just a renderer). A Project
 * filter narrows the view, and a "Create" button drops the user
 * straight into the new-experiment dialog with the active project
 * pre-selected so the per-project happy path stays one click.
 */
export default function ExperimentsClientWrapper({
  sessionToken,
}: ExperimentsClientWrapperProps) {
  const router = useRouter();

  const [projects, setProjects] = useState<Project[]>([]);
  const [experiments, setExperiments] = useState<ExperimentRow[]>([]);
  const [selectedProjectId, setSelectedProjectId] = useState<string>('all');
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [createOpen, setCreateOpen] = useState(false);

  const apiFactory = useMemo(
    () => new ApiClientFactory(sessionToken),
    [sessionToken]
  );

  const refresh = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const projectsClient = apiFactory.getProjectsClient();
      const projectsResp = await projectsClient.getAllProjects({
        sort_by: 'name',
        sort_order: 'asc',
      });
      setProjects(projectsResp);

      const parametersClient = apiFactory.getParametersClient();
      // Fan-out: one list call per project. Project counts in
      // practice are small (tens, not thousands) so this stays
      // cheap; if it ever doesn't, we add a top-level
      // /experiments list endpoint.
      const all: ExperimentRow[] = [];
      await Promise.all(
        projectsResp.map(async project => {
          try {
            const rows = await parametersClient.listProjectExperiments(
              String(project.id),
              { limit: 200 }
            );
            for (const row of rows) {
              all.push({ ...row, projectName: project.name });
            }
          } catch (e) {
            // Per-project failures shouldn't bring down the whole list.
            console.warn(
              `Failed to load experiments for project ${project.id}`,
              e
            );
          }
        })
      );
      all.sort((a, b) => {
        const ta = a.created_at ? Date.parse(a.created_at) : 0;
        const tb = b.created_at ? Date.parse(b.created_at) : 0;
        return tb - ta;
      });
      setExperiments(all);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to load experiments');
    } finally {
      setLoading(false);
    }
  }, [apiFactory]);

  useEffect(() => {
    refresh();
  }, [refresh]);

  const visibleExperiments = useMemo(() => {
    if (selectedProjectId === 'all') return experiments;
    return experiments.filter(e => e.project_id === selectedProjectId);
  }, [experiments, selectedProjectId]);

  const handleRowClick = (experimentId: string) => {
    router.push(`/experiments/${experimentId}`);
  };

  return (
    <PageContainer title="Experiments" breadcrumbs={[]}>
      <Stack spacing={3} sx={{ mt: 1 }}>
        <Box
          sx={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            gap: 2,
            flexWrap: 'wrap',
          }}
        >
          <Typography color="text.secondary">
            Named bundles of parameter values that test runs and SDK
            consumers resolve through. Each save mints an immutable
            version; environments (default, production, staging) point
            at one (experiment, version) pair.
          </Typography>
          <Button
            variant="contained"
            startIcon={<AddIcon />}
            onClick={() => setCreateOpen(true)}
            disabled={projects.length === 0}
          >
            New experiment
          </Button>
        </Box>

        <Paper variant="outlined" sx={{ p: 2 }}>
          <Stack
            direction={{ xs: 'column', sm: 'row' }}
            spacing={2}
            alignItems={{ sm: 'center' }}
            sx={{ mb: 2 }}
          >
            <FormControl size="small" sx={{ minWidth: 240 }}>
              <InputLabel>Project</InputLabel>
              <Select
                label="Project"
                value={selectedProjectId}
                onChange={e => setSelectedProjectId(e.target.value)}
              >
                <MenuItem value="all">All projects</MenuItem>
                {projects.map(p => (
                  <MenuItem key={String(p.id)} value={String(p.id)}>
                    {p.name}
                  </MenuItem>
                ))}
              </Select>
            </FormControl>
            <Box sx={{ flex: 1 }} />
            <Typography color="text.secondary" variant="body2">
              {visibleExperiments.length} experiment
              {visibleExperiments.length === 1 ? '' : 's'}
            </Typography>
          </Stack>

          {loading ? (
            <Box sx={{ display: 'flex', alignItems: 'center', p: 3, gap: 2 }}>
              <CircularProgress size={20} />
              <Typography color="text.secondary">
                Loading experiments...
              </Typography>
            </Box>
          ) : error ? (
            <Alert severity="error">{error}</Alert>
          ) : visibleExperiments.length === 0 ? (
            <Box
              sx={{
                py: 6,
                textAlign: 'center',
                color: 'text.secondary',
              }}
            >
              <BiotechIcon sx={{ fontSize: 40, mb: 1, opacity: 0.5 }} />
              <Typography variant="body2">
                No experiments here yet. Create one to start versioning a
                project's parameter values.
              </Typography>
            </Box>
          ) : (
            <TableContainer>
              <Table size="small">
                <TableHead>
                  <TableRow>
                    <TableCell>Name</TableCell>
                    <TableCell>Project</TableCell>
                    <TableCell>Visibility</TableCell>
                    <TableCell align="right">Versions</TableCell>
                    <TableCell>Latest</TableCell>
                    <TableCell>Created</TableCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {visibleExperiments.map(row => (
                    <TableRow
                      key={row.id}
                      hover
                      sx={{ cursor: 'pointer' }}
                      onClick={() => handleRowClick(row.id)}
                    >
                      <TableCell>
                        <Stack
                          direction="row"
                          alignItems="center"
                          spacing={1}
                        >
                          <BiotechIcon fontSize="small" color="action" />
                          <Box>
                            <Typography variant="body2">
                              {row.name}
                            </Typography>
                            {row.description && (
                              <Typography
                                variant="caption"
                                color="text.secondary"
                              >
                                {row.description}
                              </Typography>
                            )}
                          </Box>
                        </Stack>
                      </TableCell>
                      <TableCell>{row.projectName}</TableCell>
                      <TableCell>
                        <Chip
                          size="small"
                          label={row.visibility}
                          color={
                            row.visibility === 'shared' ? 'primary' : 'default'
                          }
                          variant="outlined"
                        />
                      </TableCell>
                      <TableCell align="right">{row.versions_count}</TableCell>
                      <TableCell>
                        {row.latest_version ? (
                          <Chip
                            size="small"
                            label={shortVersion(row.latest_version)}
                            sx={{ fontFamily: 'monospace' }}
                          />
                        ) : (
                          <Typography
                            variant="caption"
                            color="text.secondary"
                          >
                            (no versions)
                          </Typography>
                        )}
                      </TableCell>
                      <TableCell>
                        {row.created_at
                          ? new Date(row.created_at).toLocaleDateString()
                          : '—'}
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </TableContainer>
          )}
        </Paper>
      </Stack>

      <CreateExperimentDialog
        open={createOpen}
        onClose={() => setCreateOpen(false)}
        sessionToken={sessionToken}
        projects={projects}
        defaultProjectId={
          selectedProjectId === 'all' ? undefined : selectedProjectId
        }
        onCreated={async experiment => {
          setCreateOpen(false);
          router.push(`/experiments/${experiment.id}`);
        }}
      />
    </PageContainer>
  );
}
