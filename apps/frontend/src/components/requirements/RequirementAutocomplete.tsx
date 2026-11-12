'use client';

import React, { useEffect, useRef, useState } from 'react';
import { Autocomplete, CircularProgress, TextField } from '@mui/material';
import type { SxProps, Theme } from '@mui/material/styles';
import { ApiClientFactory } from '@/utils/api-client/client-factory';
import type { RequirementOption } from '@/utils/api-client/interfaces/requirement';
import { escapeODataValue } from '@/utils/odata-filter';
import { useIsAuthenticated } from '@/hooks/useIsAuthenticated';

const SEARCH_DELAY_MS = 250;
const RESULT_LIMIT = 20;

interface RequirementAutocompleteProps {
  label: string;
  value: RequirementOption | null;
  onChange: (value: RequirementOption | null) => void;
  /** Ids never offered, e.g. the requirement being edited. */
  excludeIds?: string[];
  /** Offer only requirements without a parent, i.e. ones that can be a parent. */
  topLevelOnly?: boolean;
  helperText?: string;
  placeholder?: string;
  disabled?: boolean;
  /** Field styling, e.g. `drawerOutlinedFieldSx` inside a drawer. */
  sx?: SxProps<Theme>;
}

/** Picks one requirement, searching by name on the server as you type. */
export default function RequirementAutocomplete({
  label,
  value,
  onChange,
  excludeIds = [],
  topLevelOnly = false,
  helperText,
  placeholder = 'Search requirements…',
  disabled = false,
  sx,
}: RequirementAutocompleteProps) {
  const isAuthenticated = useIsAuthenticated();
  const [open, setOpen] = useState(false);
  const [input, setInput] = useState('');
  const [options, setOptions] = useState<RequirementOption[]>([]);
  const [loading, setLoading] = useState(false);
  const defaultOptions = useRef<RequirementOption[]>([]);

  // Eagerly load the initial list so the first dropdown open is instant.
  useEffect(() => {
    if (!isAuthenticated || defaultOptions.current.length > 0) return;
    let cancelled = false;
    const clauses = topLevelOnly ? ['parent_id eq null'] : [];
    new ApiClientFactory()
      .getRequirementClient()
      .getRequirements<RequirementOption>({
        limit: RESULT_LIMIT,
        sort_by: 'name',
        sort_order: 'asc',
        $select: 'id,name',
        ...(clauses.length > 0 ? { $filter: clauses.join(' and ') } : {}),
      })
      .then(rows => {
        if (!cancelled) {
          defaultOptions.current = rows;
          setOptions(rows);
        }
      })
      .catch(() => {});
    return () => {
      cancelled = true;
    };
  }, [isAuthenticated, topLevelOnly]);

  // Search as the user types while the dropdown is open.
  useEffect(() => {
    if (!open || !isAuthenticated) return;
    const term = input.trim();
    const searching = term && term !== value?.name;
    if (!searching) {
      if (defaultOptions.current.length > 0) {
        setOptions(defaultOptions.current);
        return;
      }
    }
    let cancelled = false;
    const handle = setTimeout(async () => {
      setLoading(true);
      try {
        const clauses = [
          ...(searching
            ? [`contains(tolower(name), tolower('${escapeODataValue(term)}'))`]
            : []),
          ...(topLevelOnly ? ['parent_id eq null'] : []),
        ];
        const rows = await new ApiClientFactory()
          .getRequirementClient()
          .getRequirements<RequirementOption>({
            limit: RESULT_LIMIT,
            sort_by: 'name',
            sort_order: 'asc',
            $select: 'id,name',
            ...(clauses.length > 0 ? { $filter: clauses.join(' and ') } : {}),
          });
        if (!cancelled) setOptions(rows);
      } catch {
        if (!cancelled) setOptions([]);
      } finally {
        if (!cancelled) setLoading(false);
      }
    }, SEARCH_DELAY_MS);
    return () => {
      cancelled = true;
      clearTimeout(handle);
    };
  }, [open, input, isAuthenticated, value?.name, topLevelOnly]);

  const visible = options.filter(o => !excludeIds.includes(String(o.id)));

  return (
    <Autocomplete
      open={open}
      onOpen={() => setOpen(true)}
      onClose={() => setOpen(false)}
      value={value}
      onChange={(_event, next) => onChange(next)}
      inputValue={input}
      onInputChange={(_event, next) => setInput(next)}
      options={visible}
      filterOptions={x => x}
      getOptionLabel={option => option.name}
      isOptionEqualToValue={(a, b) => String(a.id) === String(b.id)}
      loading={loading}
      disabled={disabled}
      renderInput={params => (
        <TextField
          {...params}
          label={label}
          placeholder={placeholder}
          sx={sx}
          helperText={helperText}
          slotProps={{
            input: {
              ...params.InputProps,
              endAdornment: (
                <>
                  {loading ? (
                    <CircularProgress color="inherit" size={18} />
                  ) : null}
                  {params.InputProps.endAdornment}
                </>
              ),
            },
          }}
        />
      )}
    />
  );
}
