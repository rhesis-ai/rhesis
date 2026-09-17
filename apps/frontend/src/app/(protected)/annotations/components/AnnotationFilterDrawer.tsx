'use client';

import * as React from 'react';
import { Autocomplete, Box, TextField, Typography } from '@mui/material';
import {
  FilterDrawerShell,
  FilterSection,
  filterChipSx,
  filterDrawerTextFieldSx,
  useFilterDrawerDraft,
} from '@/components/common/FilterDrawer';
import {
  ANNOTATION_ENTITY_LABELS,
  ANNOTATION_ENTITY_TYPES,
  ANNOTATION_TARGET_LABELS,
  ANNOTATION_TARGET_TYPES,
  type AnnotationEntityType,
  type AnnotationTargetType,
} from '@/utils/api-client/interfaces/annotation';
import { useRunTestSets, useAnnotationFacets } from '@/hooks/useLookups';

export interface AnnotationFilters {
  rating: '' | 'Pass' | 'Fail';
  entity_type: '' | AnnotationEntityType;
  target_type: '' | AnnotationTargetType;
  test_set_id: string;
  endpoint_id: string;
  metric: string;
  annotator_id: string;
  requirement_id: string;
  date_from: string;
  date_to: string;
}

export const EMPTY_ANNOTATION_FILTERS: AnnotationFilters = {
  rating: '',
  entity_type: '',
  target_type: '',
  test_set_id: '',
  endpoint_id: '',
  metric: '',
  annotator_id: '',
  requirement_id: '',
  date_from: '',
  date_to: '',
};

export function hasActiveAnnotationFilters(f: AnnotationFilters): boolean {
  return (
    f.rating !== '' ||
    f.entity_type !== '' ||
    f.target_type !== '' ||
    f.test_set_id !== '' ||
    f.endpoint_id !== '' ||
    f.metric !== '' ||
    f.annotator_id !== '' ||
    f.requirement_id !== '' ||
    f.date_from !== '' ||
    f.date_to !== ''
  );
}

export function countActiveAnnotationFilters(f: AnnotationFilters): number {
  return (
    (f.rating !== '' ? 1 : 0) +
    (f.entity_type !== '' ? 1 : 0) +
    (f.target_type !== '' ? 1 : 0) +
    (f.test_set_id !== '' ? 1 : 0) +
    (f.endpoint_id !== '' ? 1 : 0) +
    (f.metric !== '' ? 1 : 0) +
    (f.annotator_id !== '' ? 1 : 0) +
    (f.requirement_id !== '' ? 1 : 0) +
    (f.date_from !== '' ? 1 : 0) +
    (f.date_to !== '' ? 1 : 0)
  );
}

const RATING_OPTIONS: { label: string; value: 'Pass' | 'Fail' }[] = [
  { label: 'Passed', value: 'Pass' },
  { label: 'Failed', value: 'Fail' },
];

const ENTITY_OPTIONS: { label: string; value: AnnotationEntityType }[] = [
  ANNOTATION_ENTITY_TYPES.TEST_RESULT,
  ANNOTATION_ENTITY_TYPES.TRACE,
].map(value => ({ label: ANNOTATION_ENTITY_LABELS[value], value }));

const TARGET_OPTIONS: { label: string; value: AnnotationTargetType }[] = [
  ANNOTATION_TARGET_TYPES.TEST_RESULT,
  ANNOTATION_TARGET_TYPES.TRACE,
  ANNOTATION_TARGET_TYPES.METRIC,
  ANNOTATION_TARGET_TYPES.TURN,
].map(value => ({ label: ANNOTATION_TARGET_LABELS[value], value }));

const textFieldSx = filterDrawerTextFieldSx;

interface AnnotationFilterDrawerProps {
  open: boolean;
  onClose: () => void;
  filters: AnnotationFilters;
  onApply: (filters: AnnotationFilters) => void;
}

export default function AnnotationFilterDrawer({
  open,
  onClose,
  filters,
  onApply,
}: AnnotationFilterDrawerProps) {
  const { draft, setDraft, handleReset, handleApply } = useFilterDrawerDraft(
    open,
    filters,
    EMPTY_ANNOTATION_FILTERS,
    onApply,
    onClose
  );

  const { data: rawTestSets, isLoading: loadingTestSets } =
    useRunTestSets(open);
  const { data: facets, isLoading: loadingFacets } = useAnnotationFacets(open);

  const testSetOptions = React.useMemo(
    () =>
      (rawTestSets ?? [])
        .filter(ts => ts.id && ts.name)
        .map(ts => ({ id: ts.id as string, label: ts.name as string })),
    [rawTestSets]
  );

  const endpointOptions = React.useMemo(
    () =>
      (facets?.endpoints ?? []).map(ep => ({
        id: ep.id,
        label: ep.name,
      })),
    [facets]
  );

  const metricOptions = React.useMemo(() => facets?.metrics ?? [], [facets]);

  const annotatorOptions = React.useMemo(
    () =>
      (facets?.annotators ?? []).map(a => ({
        id: a.id,
        label: a.name,
      })),
    [facets]
  );

  const requirementOptions = React.useMemo(
    () =>
      (facets?.requirements ?? []).map(r => ({
        id: r.id,
        label: r.name,
      })),
    [facets]
  );

  const selectedTestSet =
    testSetOptions.find(o => o.id === draft.test_set_id) ?? null;
  const selectedEndpoint =
    endpointOptions.find(o => o.id === draft.endpoint_id) ?? null;
  const selectedAnnotator =
    annotatorOptions.find(o => o.id === draft.annotator_id) ?? null;
  const selectedRequirement =
    requirementOptions.find(o => o.id === draft.requirement_id) ?? null;

  return (
    <FilterDrawerShell
      open={open}
      onClose={onClose}
      onReset={handleReset}
      onApply={handleApply}
      title="Filter"
    >
      {/* ── Basic ── */}
      <Typography variant="overline" sx={{ mb: -2 }}>
        Basic
      </Typography>

      <FilterSection title="Rating">
        <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap' }}>
          {RATING_OPTIONS.map(opt => (
            <Box
              key={opt.value}
              component="button"
              type="button"
              onClick={() =>
                setDraft(prev => ({
                  ...prev,
                  rating: prev.rating === opt.value ? '' : opt.value,
                }))
              }
              sx={filterChipSx(draft.rating === opt.value)}
            >
              {opt.label}
            </Box>
          ))}
        </Box>
      </FilterSection>

      <FilterSection title="Annotator">
        <Autocomplete
          options={annotatorOptions}
          getOptionLabel={o => o.label}
          value={selectedAnnotator}
          loading={loadingFacets}
          isOptionEqualToValue={(o, v) => o.id === v.id}
          onChange={(_, value) =>
            setDraft(prev => ({ ...prev, annotator_id: value?.id ?? '' }))
          }
          renderInput={params => (
            <TextField
              {...params}
              placeholder="Select annotator..."
              sx={textFieldSx}
            />
          )}
        />
      </FilterSection>

      <FilterSection title="Date Range">
        <Box sx={{ display: 'flex', gap: 1 }}>
          <TextField
            label="From"
            type="date"
            size="small"
            fullWidth
            value={draft.date_from}
            onChange={e =>
              setDraft(prev => ({ ...prev, date_from: e.target.value }))
            }
            InputLabelProps={{ shrink: true }}
            sx={textFieldSx}
          />
          <TextField
            label="To"
            type="date"
            size="small"
            fullWidth
            value={draft.date_to}
            onChange={e =>
              setDraft(prev => ({ ...prev, date_to: e.target.value }))
            }
            InputLabelProps={{ shrink: true }}
            sx={textFieldSx}
          />
        </Box>
      </FilterSection>

      <FilterSection title="Requirement">
        <Autocomplete
          options={requirementOptions}
          getOptionLabel={o => o.label}
          value={selectedRequirement}
          loading={loadingFacets}
          isOptionEqualToValue={(o, v) => o.id === v.id}
          onChange={(_, value) =>
            setDraft(prev => ({
              ...prev,
              requirement_id: value?.id ?? '',
            }))
          }
          renderInput={params => (
            <TextField
              {...params}
              placeholder="Select requirement..."
              sx={textFieldSx}
            />
          )}
        />
      </FilterSection>

      {/* ── Advanced ── */}
      <Typography variant="overline" sx={{ mb: -2 }}>
        Advanced
      </Typography>

      <FilterSection title="Type">
        <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap' }}>
          {ENTITY_OPTIONS.map(opt => (
            <Box
              key={opt.value}
              component="button"
              type="button"
              onClick={() =>
                setDraft(prev => ({
                  ...prev,
                  entity_type: prev.entity_type === opt.value ? '' : opt.value,
                }))
              }
              sx={filterChipSx(draft.entity_type === opt.value)}
            >
              {opt.label}
            </Box>
          ))}
        </Box>
      </FilterSection>

      <FilterSection title="Target">
        <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap' }}>
          {TARGET_OPTIONS.map(opt => (
            <Box
              key={opt.value}
              component="button"
              type="button"
              onClick={() =>
                setDraft(prev => ({
                  ...prev,
                  target_type: prev.target_type === opt.value ? '' : opt.value,
                }))
              }
              sx={filterChipSx(draft.target_type === opt.value)}
            >
              {opt.label}
            </Box>
          ))}
        </Box>
      </FilterSection>

      <FilterSection title="Test Set">
        <Autocomplete
          options={testSetOptions}
          getOptionLabel={o => o.label}
          value={selectedTestSet}
          loading={loadingTestSets}
          isOptionEqualToValue={(o, v) => o.id === v.id}
          onChange={(_, value) =>
            setDraft(prev => ({ ...prev, test_set_id: value?.id ?? '' }))
          }
          renderInput={params => (
            <TextField
              {...params}
              placeholder="Select test set..."
              sx={textFieldSx}
            />
          )}
        />
      </FilterSection>

      <FilterSection title="Endpoint">
        <Autocomplete
          options={endpointOptions}
          getOptionLabel={o => o.label}
          value={selectedEndpoint}
          loading={loadingFacets}
          isOptionEqualToValue={(o, v) => o.id === v.id}
          onChange={(_, value) =>
            setDraft(prev => ({ ...prev, endpoint_id: value?.id ?? '' }))
          }
          renderInput={params => (
            <TextField
              {...params}
              placeholder="Select endpoint..."
              sx={textFieldSx}
            />
          )}
        />
      </FilterSection>

      <FilterSection title="Metric">
        <Autocomplete
          freeSolo
          options={metricOptions}
          value={draft.metric || null}
          loading={loadingFacets}
          onChange={(_, value) =>
            setDraft(prev => ({ ...prev, metric: (value as string) || '' }))
          }
          onInputChange={(_, value) =>
            setDraft(prev => ({ ...prev, metric: value }))
          }
          renderInput={params => (
            <TextField
              {...params}
              placeholder="Select metric..."
              sx={textFieldSx}
            />
          )}
        />
      </FilterSection>
    </FilterDrawerShell>
  );
}
