'use client';

import * as React from 'react';
import { Box, Button, Chip, Stack, Typography } from '@mui/material';
import Link from 'next/link';
import { SectionCard } from '@/components/common/SectionCard';
import { ArrowOutwardIcon, TuneIcon } from '@/components/icons';
import { ParameterSchema } from '@/utils/api-client/interfaces/parameters';

const TYPE_LABELS: Record<string, string> = {
  text: 'Text (multi-line)',
  string: 'String (single-line)',
  integer: 'Integer',
  number: 'Number',
  boolean: 'Boolean',
  enum: 'Enum',
  model_ref: 'Model reference',
  secret_ref: 'Secret reference',
};

interface ExperimentParametersTabProps {
  schema: ParameterSchema;
  projectId: string;
  projectName?: string | null;
}

export default function ExperimentParametersTab({
  schema,
  projectId,
  projectName,
}: ExperimentParametersTabProps) {
  const label = projectName ?? 'Project';

  return (
    <Stack spacing={3}>
      <SectionCard
        actions={
          schema.fields.length > 0 ? (
            <Button
              component={Link}
              href={`/projects/${projectId}?tab=parameters`}
              target="_blank"
              rel="noopener noreferrer"
              size="small"
              endIcon={<ArrowOutwardIcon fontSize="small" />}
              variant="outlined"
            >
              Edit in {label}
            </Button>
          ) : undefined
        }
        subtitle={
          schema.fields.length > 0
            ? 'This schema is shared by all experiments in the project. Edit it on the project page.'
            : undefined
        }
      >
        {schema.fields.length === 0 ? (
          <Box
            sx={{
              display: 'flex',
              flexDirection: 'column',
              alignItems: 'center',
              gap: 2.5,
              px: { xs: 2, md: '200px' },
              py: 2,
            }}
          >
            <Box
              sx={{
                display: 'flex',
                flexDirection: 'column',
                alignItems: 'center',
                gap: 1.25,
              }}
            >
              <TuneIcon
                sx={{
                  fontSize: 32,
                  color: 'primary.main',
                }}
              />
              <Typography
                sx={{
                  fontSize: 20,
                  fontWeight: 600,
                  lineHeight: '24px',
                  color: 'primary.main',
                  whiteSpace: 'nowrap',
                }}
              >
                No parameter schema defined yet
              </Typography>
            </Box>

            <Typography
              variant="body2"
              sx={{
                fontSize: 14,
                lineHeight: '22px',
                color: 'text.primary',
                textAlign: 'center',
              }}
            >
              The parameter schema is defined at the project level and shared
              across all experiments. Head to the project page to define the
              slots your experiments will fill.
            </Typography>

            <Button
              component={Link}
              href={`/projects/${projectId}?tab=parameters`}
              target="_blank"
              rel="noopener noreferrer"
              variant="contained"
              startIcon={<ArrowOutwardIcon />}
              sx={{
                fontSize: 18,
                fontWeight: 700,
                lineHeight: '25px',
                px: '20px',
                py: '12px',
                borderRadius: '12px',
                textTransform: 'none',
                gap: 1,
              }}
            >
              Define schema in {label}
            </Button>
          </Box>
        ) : (
          <Stack spacing={1}>
            {schema.fields.map(field => (
              <Box
                key={field.name}
                sx={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: 2,
                  px: 2,
                  py: 1.5,
                  border: '1px solid',
                  borderColor: 'divider',
                  borderRadius: 1,
                }}
              >
                <Typography
                  variant="body2"
                  sx={{ fontFamily: 'monospace', fontWeight: 600, flex: 1 }}
                >
                  {field.name}
                </Typography>
                <Chip
                  label={TYPE_LABELS[field.type] ?? field.type}
                  size="small"
                  variant="outlined"
                />
                {field.required && (
                  <Chip label="required" size="small" color="primary" />
                )}
                {field.description && (
                  <Typography
                    variant="caption"
                    color="text.secondary"
                    sx={{
                      maxWidth: 200,
                      overflow: 'hidden',
                      textOverflow: 'ellipsis',
                      whiteSpace: 'nowrap',
                    }}
                    title={field.description}
                  >
                    {field.description}
                  </Typography>
                )}
              </Box>
            ))}
          </Stack>
        )}
      </SectionCard>
    </Stack>
  );
}
