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
import SubsectionHeader from '@/components/common/SubsectionHeader';
import BorderedInfoCard from '@/components/common/BorderedInfoCard';

interface DetailsDraft {
  name: string;
  description: string;
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
            <SubsectionHeader
              headline="Behaviors"
              description="The behaviors covered by tests in this set"
            />
            <BadgeRow items={behaviors} />
          </Box>

          {/* ── Topics ────────────────────────────────────────────────────── */}
          <Box>
            <SubsectionHeader
              headline="Topics"
              description="The topics covered by tests in this set"
            />
            <BadgeRow items={topics} />
          </Box>

          {/* ── Categories ────────────────────────────────────────────────── */}
          <Box>
            <SubsectionHeader
              headline="Categories"
              description="The categories covered by tests in this set"
            />
            <BadgeRow items={categories} />
          </Box>

          {/* ── Sources (conditional) ─────────────────────────────────────── */}
          {sources.length > 0 && (
            <Box>
              <SubsectionHeader
                headline="Sources"
                description="Documents from which this test set was generated"
              />
              {sources.map((src, idx) => (
                <BorderedInfoCard
                  key={src.document ?? idx}
                  title={src.name}
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
