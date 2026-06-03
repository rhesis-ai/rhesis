'use client';

import * as React from 'react';
import { Typography, Box, Paper, Grid, Avatar } from '@mui/material';
import { Project } from '@/utils/api-client/interfaces/project';
import { AVATAR_SIZES } from '@/constants/avatar-sizes';
import PersonIcon from '@mui/icons-material/Person';
import GridBadge from '@/components/common/GridBadge';
import Tag from '@/components/common/Tag';

export default function ProjectContent({ project }: { project: Project }) {
  return (
    <Paper sx={{ p: 3 }}>
      <Grid container spacing={4}>
        {/* Description Section */}
        <Grid
          size={{
            xs: 12,
            md: 6,
          }}
        >
          <Box>
            <Typography
              variant="overline"
              sx={{ color: 'text.secondary', letterSpacing: 1 }}
            >
              Description
            </Typography>
            <Typography variant="body1" sx={{ mt: 1, color: 'text.primary' }}>
              {project.description || 'No description provided'}
            </Typography>
          </Box>
        </Grid>

        {/* Metadata Section */}
        <Grid
          size={{
            xs: 12,
            md: 6,
          }}
        >
          <Box sx={{ display: 'flex', flexDirection: 'column', gap: 3 }}>
            {/* Status & Environment */}
            <Box>
              <Typography
                variant="overline"
                sx={{ color: 'text.secondary', letterSpacing: 1 }}
              >
                Status
              </Typography>
              <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap', mt: 1 }}>
                {project.is_active !== undefined && (
                  <GridBadge
                    size="detail"
                    label={project.is_active ? 'Active' : 'Inactive'}
                  />
                )}
                {project.environment && (
                  <GridBadge size="detail" label={project.environment} />
                )}
                {project.useCase && (
                  <GridBadge size="detail" label={project.useCase} />
                )}
              </Box>
            </Box>

            {/* Owner */}
            {project.owner && (
              <Box>
                <Typography
                  variant="overline"
                  sx={{ color: 'text.secondary', letterSpacing: 1 }}
                >
                  Owner
                </Typography>
                <Box
                  sx={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: 1.5,
                    mt: 1,
                  }}
                >
                  <Avatar
                    src={project.owner.picture}
                    alt={project.owner.name || project.owner.email}
                    sx={{
                      width: AVATAR_SIZES.MEDIUM,
                      height: AVATAR_SIZES.MEDIUM,
                    }}
                  >
                    <PersonIcon />
                  </Avatar>
                  <Typography variant="body1">
                    {project.owner.name || project.owner.email}
                  </Typography>
                </Box>
              </Box>
            )}

            {/* Created Date */}
            {project.createdAt && (
              <Box>
                <Typography
                  variant="overline"
                  sx={{ color: 'text.secondary', letterSpacing: 1 }}
                >
                  Created
                </Typography>
                <Typography variant="body1" sx={{ mt: 1 }}>
                  {new Date(project.createdAt).toLocaleDateString(undefined, {
                    year: 'numeric',
                    month: 'long',
                    day: 'numeric',
                  })}
                </Typography>
              </Box>
            )}
          </Box>
        </Grid>

        {/* Tags Section */}
        {project.tags && project.tags.length > 0 && (
          <Grid size={12}>
            <Box>
              <Typography
                variant="overline"
                sx={{ color: 'text.secondary', letterSpacing: 1 }}
              >
                Tags
              </Typography>
              <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1, mt: 1 }}>
                {project.tags.map((tag: string) => (
                  <Tag key={tag} label={tag} />
                ))}
              </Box>
            </Box>
          </Grid>
        )}
      </Grid>
    </Paper>
  );
}
