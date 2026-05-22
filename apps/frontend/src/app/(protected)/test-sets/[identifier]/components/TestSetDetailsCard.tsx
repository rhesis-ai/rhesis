'use client';

import * as React from 'react';
import { Box, TextField, Typography } from '@mui/material';
import Grid from '@mui/material/Grid';
import ViewField from '@/components/common/ViewField';
import { BadgeRow } from '@/components/common/GridBadge';
import EditableSection from '@/components/common/EditableSection';
import { ApiClientFactory } from '@/utils/api-client/client-factory';
import { TestSet } from '@/utils/api-client/interfaces/test-set';
import { useNotifications } from '@/components/common/NotificationContext';
import { useRouter } from 'next/navigation';
import { GREYSCALE } from '@/styles/theme';

interface DetailsDraft {
  name: string;
  description: string;
}

// ── Section divider (matches Figma node 1228:5851) ────────────────────────────

interface SectionDividerProps {
  headline: string;
  description?: string;
}

function SectionDivider({ headline, description }: SectionDividerProps) {
  return (
    <Box sx={{ mb: '20px' }}>
      <Typography
        sx={{
          fontSize: 18,
          fontWeight: 700,
          lineHeight: '25px',
          color: 'text.primary',
        }}
      >
        {headline}
      </Typography>
      {description && (
        <Typography
          sx={{
            fontSize: 12,
            lineHeight: '18px',
            color: theme => theme.palette.greyscale?.subtitle ?? '#7f8a9b',
          }}
        >
          {description}
        </Typography>
      )}
    </Box>
  );
}

// ── Source document card ───────────────────────────────────────────────────────

interface SourceCardProps {
  name: string;
  description: string;
}

function SourceCard({ name, description }: SourceCardProps) {
  return (
    <Box
      sx={{
        border: theme =>
          `1px solid ${
            theme.palette.mode === 'light'
              ? GREYSCALE.light.border
              : GREYSCALE.dark.border
          }`,
        borderRadius: '8px',
        p: 2,
        mb: 1,
      }}
    >
      <Typography sx={{ fontWeight: 600, fontSize: 14, mb: 0.5 }}>
        {name}
      </Typography>
      <Typography sx={{ fontSize: 13, color: 'text.secondary' }}>
        {description}
      </Typography>
    </Box>
  );
}

// ── Main component ─────────────────────────────────────────────────────────────

interface TestSetDetailsCardProps {
  sessionToken: string;
  testSet: TestSet;
  onUpdate?: () => void;
}

export default function TestSetDetailsCard({
  sessionToken,
  testSet,
  onUpdate,
}: TestSetDetailsCardProps) {
  const router = useRouter();
  const notifications = useNotifications();

  const metadata = testSet.attributes?.metadata;
  const behaviors = metadata?.behaviors ?? [];
  const topics = metadata?.topics ?? [];
  const categories = metadata?.categories ?? [];
  const sources = metadata?.sources ?? [];

  const initialDraft: DetailsDraft = {
    name: testSet.name ?? '',
    description: testSet.description ?? '',
  };

  const handleSave = async (draft: DetailsDraft) => {
    const factory = new ApiClientFactory(sessionToken);
    await factory.getTestSetsClient().updateTestSet(testSet.id as string, {
      name: draft.name,
      description: draft.description || undefined,
    });
    notifications.show('Test set details updated', {
      severity: 'success',
      autoHideDuration: 4000,
    });
    onUpdate?.();
    router.refresh();
  };

  return (
    <EditableSection
      title="Test set details"
      initialValue={initialDraft}
      onSave={handleSave}
    >
      {({ draft, setDraft, isEditing }) => (
        <Box sx={{ display: 'flex', flexDirection: 'column', gap: '50px' }}>
          {/* ── Name & Description ────────────────────────────────────────── */}
          <Box sx={{ display: 'flex', flexDirection: 'column', gap: 3 }}>
            <Grid
              container
              columnSpacing={isEditing ? 2 : '30px'}
              rowSpacing={isEditing ? 2 : 3}
            >
              <Grid size={12}>
                {isEditing ? (
                  <TextField
                    fullWidth
                    label="Name"
                    value={draft.name}
                    onChange={e =>
                      setDraft(d => ({ ...d, name: e.target.value }))
                    }
                    variant="outlined"
                  />
                ) : (
                  <ViewField label="Name" value={draft.name} />
                )}
              </Grid>

              <Grid size={12}>
                {isEditing ? (
                  <TextField
                    fullWidth
                    multiline
                    minRows={3}
                    label="Description"
                    value={draft.description}
                    onChange={e =>
                      setDraft(d => ({ ...d, description: e.target.value }))
                    }
                    variant="outlined"
                  />
                ) : (
                  <ViewField
                    label="Description"
                    value={draft.description}
                    multiline
                  />
                )}
              </Grid>
            </Grid>
          </Box>

          {/* ── Behaviors ─────────────────────────────────────────────────── */}
          <Box>
            <SectionDivider
              headline="Behaviors"
              description="The behaviors covered by tests in this set"
            />
            <BadgeRow items={behaviors} />
          </Box>

          {/* ── Topics ────────────────────────────────────────────────────── */}
          <Box>
            <SectionDivider
              headline="Topics"
              description="The topics covered by tests in this set"
            />
            <BadgeRow items={topics} />
          </Box>

          {/* ── Categories ────────────────────────────────────────────────── */}
          <Box>
            <SectionDivider
              headline="Categories"
              description="The categories covered by tests in this set"
            />
            <BadgeRow items={categories} />
          </Box>

          {/* ── Sources (conditional) ─────────────────────────────────────── */}
          {sources.length > 0 && (
            <Box>
              <SectionDivider
                headline="Sources"
                description="Documents from which this test set was generated"
              />
              {sources.map((src, idx) => (
                <SourceCard
                  key={src.document ?? idx}
                  name={src.name}
                  description={src.description}
                />
              ))}
            </Box>
          )}
        </Box>
      )}
    </EditableSection>
  );
}
