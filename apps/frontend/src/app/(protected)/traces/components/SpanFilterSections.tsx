'use client';

import * as React from 'react';
import { Autocomplete, Box, TextField, Typography } from '@mui/material';
import {
  FilterSection,
  filterChipSx,
  filterDrawerTextFieldSx,
} from '@/components/common/FilterDrawer';
import { getSpanTypeInfo, SPAN_TYPES } from '@/constants/span-types';
import { readActiveProjectId } from '@/utils/active-project';
import { ApiClientFactory } from '@/utils/api-client/client-factory';
import type {
  SpanFacetsResponse,
  SpanFacetValue,
} from '@/utils/api-client/interfaces/telemetry';
import {
  buildSpanQueryParams,
  type TraceDrawerFilters,
} from './trace-filter-params';

const ROOT_OPTIONS = [
  { label: 'Root spans', value: true },
  { label: 'Child spans', value: false },
] as const;

/** Undefined rather than [], so "none picked" reads as no filter everywhere. */
function listOrUndefined(values: string[]): string[] | undefined {
  return values.length ? values : undefined;
}

/** Facet values first, then anything picked that the facets no longer list. */
function withSelected(
  facet: SpanFacetValue[],
  selected: string[] | undefined
): SpanFacetValue[] {
  const listed = new Set(facet.map(f => f.value));
  const extra = (selected ?? [])
    .filter(value => !listed.has(value))
    .map(value => ({ value, count: 0 }));
  return [...facet, ...extra];
}

/**
 * Fetches facets for *draft* while *enabled*. Keyed on the draft's content, not
 * on the query params: a preset time range turns into a fresh timestamp on
 * every build, which would refetch forever.
 */
function useSpanFacets(
  draft: TraceDrawerFilters,
  enabled: boolean
): { facets: SpanFacetsResponse | null; failed: boolean } {
  const [facets, setFacets] = React.useState<SpanFacetsResponse | null>(null);
  const [failed, setFailed] = React.useState(false);
  const draftKey = JSON.stringify(draft);

  React.useEffect(() => {
    if (!enabled) return;
    let cancelled = false;
    const current = JSON.parse(draftKey) as TraceDrawerFilters;
    const params = buildSpanQueryParams(current, '');
    // Same fallback as the spans list, so facets and rows share one scope.
    const scopedProjectId = readActiveProjectId();
    if (!params.project_id && scopedProjectId) {
      params.project_id = scopedProjectId;
    }

    new ApiClientFactory()
      .getTelemetryClient()
      .getSpanFacets(params)
      .then(result => {
        if (cancelled) return;
        setFacets(result);
        setFailed(false);
      })
      .catch(() => {
        if (cancelled) return;
        // Drop the last good facets: they were for other filters.
        setFacets(null);
        setFailed(true);
      });

    return () => {
      cancelled = true;
    };
  }, [enabled, draftKey]);

  return { facets, failed };
}

interface SpanFilterSectionsProps {
  /** Facets load only while the drawer is open. */
  open: boolean;
  draft: TraceDrawerFilters;
  setDraft: React.Dispatch<React.SetStateAction<TraceDrawerFilters>>;
}

/** The spans view's own filters: type, name and root/child. */
export default function SpanFilterSections({
  open,
  draft,
  setDraft,
}: SpanFilterSectionsProps) {
  const { facets, failed } = useSpanFacets(draft, open);
  const typesLoading = !facets && !failed;

  // If facets fail, offer every known type (no counts) so the filter still works.
  const typeOptions = withSelected(
    facets && !failed
      ? facets.span_types
      : failed
        ? Object.keys(SPAN_TYPES).map(value => ({ value, count: 0 }))
        : [],
    draft.spanTypes
  );
  const nameOptions = withSelected(facets?.span_names ?? [], draft.spanNames);
  const nameCounts = new Map(nameOptions.map(o => [o.value, o.count]));

  const toggleType = (type: string) =>
    setDraft(prev => {
      const current = prev.spanTypes ?? [];
      const next = current.includes(type)
        ? current.filter(value => value !== type)
        : [...current, type];
      return { ...prev, spanTypes: listOrUndefined(next) };
    });

  return (
    <>
      <FilterSection title="Span type">
        {typeOptions.length === 0 && (
          <Typography variant="body2" color="text.secondary">
            {typesLoading ? 'Loading…' : 'No spans match the other filters.'}
          </Typography>
        )}
        <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap' }}>
          {typeOptions.map(({ value, count }) => {
            const info = getSpanTypeInfo(value);
            const selected = (draft.spanTypes ?? []).includes(value);
            return (
              <Box
                key={value}
                component="button"
                type="button"
                aria-pressed={selected}
                onClick={() => toggleType(value)}
                sx={filterChipSx(selected)}
              >
                <Box
                  component={info.icon}
                  sx={{ fontSize: theme => theme.spacing(2), mr: 0.75 }}
                />
                {info.label}
                {count > 0 && (
                  <Box component="span" sx={{ ml: 0.75, opacity: 0.7 }}>
                    {count}
                  </Box>
                )}
              </Box>
            );
          })}
        </Box>
      </FilterSection>

      <FilterSection title="Span name">
        <Autocomplete
          multiple
          freeSolo
          size="small"
          options={nameOptions.map(o => o.value)}
          value={draft.spanNames ?? []}
          onChange={(_event, values) =>
            setDraft(prev => ({
              ...prev,
              spanNames: listOrUndefined(values),
            }))
          }
          renderOption={(props, option) => {
            const { key, ...rest } = props;
            const count = nameCounts.get(option) ?? 0;
            return (
              <Box
                component="li"
                key={key}
                {...rest}
                sx={{ display: 'flex', justifyContent: 'space-between' }}
              >
                <Typography
                  variant="body2"
                  sx={{ fontFamily: 'monospace' }}
                  noWrap
                >
                  {option}
                </Typography>
                {count > 0 && (
                  <Typography
                    variant="body2"
                    color="text.secondary"
                    sx={{ ml: 1 }}
                  >
                    {count}
                  </Typography>
                )}
              </Box>
            );
          }}
          renderInput={params => (
            <TextField
              {...params}
              placeholder="Pick or type an exact name"
              sx={filterDrawerTextFieldSx}
            />
          )}
        />
        {facets?.span_names_truncated && (
          <Typography
            variant="caption"
            color="text.secondary"
            sx={{ display: 'block', mt: 1 }}
          >
            Showing the most common names. Type a name to match it exactly, or
            use search for part of a name.
          </Typography>
        )}
      </FilterSection>

      <FilterSection title="Root">
        <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap' }}>
          {ROOT_OPTIONS.map(opt => (
            <Box
              key={opt.label}
              component="button"
              type="button"
              aria-pressed={draft.isRoot === opt.value}
              onClick={() =>
                setDraft(prev => ({
                  ...prev,
                  isRoot: prev.isRoot === opt.value ? undefined : opt.value,
                }))
              }
              sx={filterChipSx(draft.isRoot === opt.value)}
            >
              {opt.label}
            </Box>
          ))}
        </Box>
      </FilterSection>
    </>
  );
}
