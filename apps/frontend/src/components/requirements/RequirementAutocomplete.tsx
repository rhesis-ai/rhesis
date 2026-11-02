'use client';

import React, { useEffect, useState } from 'react';
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

  useEffect(() => {
    if (!open || !isAuthenticated) return;
    let cancelled = false;
    const handle = setTimeout(async () => {
      setLoading(true);
      try {
        const term = input.trim();
        // The input shows the selected name; searching for it would hide
        // every other option.
        const searching = term && term !== value?.name;
        const rows = await new ApiClientFactory()
          .getRequirementClient()
          .getRequirements<RequirementOption>({
            limit: RESULT_LIMIT,
            sort_by: 'name',
            sort_order: 'asc',
            $select: 'id,name',
            ...(searching
              ? {
                  $filter: `contains(tolower(name), tolower('${escapeODataValue(term)}'))`,
                }
              : {}),
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
  }, [open, input, isAuthenticated, value?.name]);

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
