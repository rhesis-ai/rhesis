'use client';

import * as React from 'react';
import Grid from '@mui/material/Grid';
import { MenuItem, TextField } from '@mui/material';
import BaseFreesoloAutocomplete, {
  AutocompleteOption,
} from '@/components/common/BaseFreesoloAutocomplete';
import ViewField from '@/components/common/ViewField';
import EditableSection from '@/components/common/EditableSection';
import { ApiClientFactory } from '@/utils/api-client/client-factory';
import { TestDetail } from '@/utils/api-client/interfaces/tests';
import { useNotifications } from '@/components/common/NotificationContext';
import { useRouter } from 'next/navigation';
import { formatDate } from '@/utils/date';
import { UUID } from 'crypto';

interface TestDetailOption {
  id: UUID;
  name: string;
}

interface MetadataDraft {
  behavior_id: UUID | null;
  behavior_name: string;
  topic_id: UUID | null;
  topic_name: string;
  category_id: UUID | null;
  category_name: string;
  priority: number;
}

function priorityLabel(n: number): string {
  switch (n) {
    case 0:
      return 'Low';
    case 2:
      return 'High';
    case 3:
      return 'Urgent';
    default:
      return 'Medium';
  }
}

interface TestMetadataCardProps {
  sessionToken: string;
  test: TestDetail;
  onUpdate?: () => void;
}

export default function TestMetadataCard({
  sessionToken,
  test,
  onUpdate,
}: TestMetadataCardProps) {
  const router = useRouter();
  const notifications = useNotifications();

  const [behaviors, setBehaviors] = React.useState<TestDetailOption[]>([]);
  const [topics, setTopics] = React.useState<TestDetailOption[]>([]);
  const [categories, setCategories] = React.useState<TestDetailOption[]>([]);

  React.useEffect(() => {
    if (!sessionToken) return;
    const apiFactory = new ApiClientFactory(sessionToken);

    const run = async () => {
      const [behaviorsData, topicsData, categoriesData] = await Promise.all([
        apiFactory
          .getBehaviorClient()
          .getBehaviors({ sort_by: 'name', sort_order: 'asc' }),
        apiFactory.getTopicClient().getTopics({
          entity_type: 'Test',
          sort_by: 'name',
          sort_order: 'asc',
        }),
        apiFactory.getCategoryClient().getCategories({
          entity_type: 'Test',
          sort_by: 'name',
          sort_order: 'asc',
        }),
      ]);
      setBehaviors(
        behaviorsData
          .filter((b: { id: UUID; name: string }) => b.id && b.name?.trim())
          .map((b: { id: UUID; name: string }) => ({ id: b.id, name: b.name }))
      );
      setTopics(
        topicsData.map((t: { id: UUID; name: string }) => ({
          id: t.id,
          name: t.name,
        }))
      );
      setCategories(
        categoriesData.map((c: { id: UUID; name: string }) => ({
          id: c.id,
          name: c.name,
        }))
      );
    };
    run();
  }, [sessionToken]);

  const initialDraft: MetadataDraft = {
    behavior_id: (test.behavior?.id ?? null) as UUID | null,
    behavior_name: test.behavior?.name ?? '',
    topic_id: (test.topic?.id ?? null) as UUID | null,
    topic_name: test.topic?.name ?? '',
    category_id: (test.category?.id ?? null) as UUID | null,
    category_name: test.category?.name ?? '',
    priority: test.priority ?? 1,
  };

  const handleSave = async (draft: MetadataDraft) => {
    const apiFactory = new ApiClientFactory(sessionToken);
    const testsClient = apiFactory.getTestsClient();
    await testsClient.updateTest(test.id, {
      behavior_id: draft.behavior_id ?? undefined,
      topic_id: draft.topic_id ?? undefined,
      category_id: draft.category_id ?? undefined,
      priority: draft.priority,
    });
    notifications.show('Test details updated', {
      severity: 'success',
      autoHideDuration: 4000,
    });
    onUpdate?.();
    router.refresh();
  };

  return (
    <EditableSection
      title="Test details"
      initialValue={initialDraft}
      onSave={handleSave}
    >
      {({ draft, setDraft, isEditing }) => (
        <Grid
          container
          columnSpacing={isEditing ? 2 : '30px'}
          rowSpacing={isEditing ? 2 : '50px'}
        >
          {/* Row 1: Behavior, Type, Topic, Category */}
          <Grid size={{ xs: 12, sm: 6, md: 3 }}>
            {isEditing ? (
              <BaseFreesoloAutocomplete
                options={behaviors}
                value={draft.behavior_name}
                onChange={(val: AutocompleteOption | string | null) => {
                  if (val && typeof val === 'object') {
                    setDraft(d => ({
                      ...d,
                      behavior_id: val.id,
                      behavior_name: val.name,
                    }));
                  } else if (typeof val === 'string') {
                    const match = behaviors.find(b => b.name === val);
                    setDraft(d => ({
                      ...d,
                      behavior_id: match?.id ?? null,
                      behavior_name: val,
                    }));
                  } else {
                    setDraft(d => ({
                      ...d,
                      behavior_id: null,
                      behavior_name: '',
                    }));
                  }
                }}
                label="Behavior"
                popperWidth="100%"
              />
            ) : (
              <ViewField
                label="Behavior"
                value={draft.behavior_name}
                helperText="Infotext"
              />
            )}
          </Grid>

          <Grid size={{ xs: 12, sm: 6, md: 3 }}>
            <ViewField
              label="Type"
              value={test.test_type?.type_value ?? ''}
              helperText="Infotext"
            />
          </Grid>

          <Grid size={{ xs: 12, sm: 6, md: 3 }}>
            {isEditing ? (
              <BaseFreesoloAutocomplete
                options={topics}
                value={draft.topic_name}
                onChange={(val: AutocompleteOption | string | null) => {
                  if (val && typeof val === 'object') {
                    setDraft(d => ({
                      ...d,
                      topic_id: val.id,
                      topic_name: val.name,
                    }));
                  } else if (typeof val === 'string') {
                    const match = topics.find(t => t.name === val);
                    setDraft(d => ({
                      ...d,
                      topic_id: match?.id ?? null,
                      topic_name: val,
                    }));
                  } else {
                    setDraft(d => ({ ...d, topic_id: null, topic_name: '' }));
                  }
                }}
                label="Topic"
                popperWidth="100%"
              />
            ) : (
              <ViewField
                label="Topic"
                value={draft.topic_name}
                helperText="Infotext"
              />
            )}
          </Grid>

          <Grid size={{ xs: 12, sm: 6, md: 3 }}>
            {isEditing ? (
              <BaseFreesoloAutocomplete
                options={categories}
                value={draft.category_name}
                onChange={(val: AutocompleteOption | string | null) => {
                  if (val && typeof val === 'object') {
                    setDraft(d => ({
                      ...d,
                      category_id: val.id,
                      category_name: val.name,
                    }));
                  } else if (typeof val === 'string') {
                    const match = categories.find(c => c.name === val);
                    setDraft(d => ({
                      ...d,
                      category_id: match?.id ?? null,
                      category_name: val,
                    }));
                  } else {
                    setDraft(d => ({
                      ...d,
                      category_id: null,
                      category_name: '',
                    }));
                  }
                }}
                label="Category"
                popperWidth="100%"
              />
            ) : (
              <ViewField
                label="Category"
                value={draft.category_name}
                helperText="Infotext"
              />
            )}
          </Grid>

          {/* Row 2: Created (read-only), Priority */}
          <Grid size={{ xs: 12, sm: 6 }}>
            <ViewField
              label="Created"
              value={formatDate(test.created_at)}
              helperText="Infotext"
            />
          </Grid>

          <Grid size={{ xs: 12, sm: 6 }}>
            {isEditing ? (
              <TextField
                select
                fullWidth
                label="Priority"
                value={draft.priority}
                onChange={e =>
                  setDraft(d => ({ ...d, priority: Number(e.target.value) }))
                }
                variant="outlined"
                helperText="Infotext"
              >
                {[0, 1, 2, 3].map(v => (
                  <MenuItem key={v} value={v}>
                    {priorityLabel(v)}
                  </MenuItem>
                ))}
              </TextField>
            ) : (
              <ViewField
                label="Priority"
                value={priorityLabel(draft.priority)}
                helperText="Infotext"
              />
            )}
          </Grid>
        </Grid>
      )}
    </EditableSection>
  );
}
