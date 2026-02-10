'use client';

import React from 'react';
import {
  Autocomplete,
  TextField,
  createFilterOptions,
  FormControl,
  Popper,
  PopperProps,
} from '@mui/material';
import { UUID } from 'crypto';

export interface AutocompleteOption {
  id: UUID;
  name: string;
  inputValue?: string;
}

interface BaseFreesoloAutocompleteProps {
  options: AutocompleteOption[];
  value: UUID | string | null | undefined;
  onChange: (value: AutocompleteOption | string | null) => void;
  label: string;
  required?: boolean;
  popperWidth?: number | string;
  disabled?: boolean;
}

// Extend PopperProps to include our custom popperWidth property
interface CustomPopperProps extends PopperProps {
  popperWidth?: number | string;
}

// Custom Popper component defined outside the render function
const CustomPopper = React.forwardRef<HTMLDivElement, CustomPopperProps>(
  (props, ref) => {
    const { popperWidth, ...other } = props;

    return (
      <Popper
        {...other}
        ref={ref}
        placement="bottom-start"
        modifiers={[
          {
            name: 'preventOverflow',
            enabled: true,
            options: {
              altAxis: true,
              tether: true,
              padding: 8,
            },
          },
          {
            name: 'flip',
            enabled: true,
            options: {
              padding: 8,
            },
          },
          {
            name: 'offset',
            options: {
              offset: [0, 8],
            },
          },
          {
            name: 'computeStyles',
            options: {
              adaptive: false,
              gpuAcceleration: false,
            },
          },
          {
            name: 'setWidth',
            enabled: true,
            phase: 'beforeWrite',
            fn: ({ state }) => {
              const referenceWidth = state.rects.reference.width;
              if (popperWidth === '100%') {
                state.styles.popper.width = `${referenceWidth}px`;
              } else if (typeof popperWidth === 'number') {
                state.styles.popper.width = `${popperWidth}px`;
              } else if (popperWidth) {
                state.styles.popper.width = popperWidth;
              }
              return state;
            },
          },
        ]}
      />
    );
  }
);

CustomPopper.displayName = 'CustomPopper';

export default function BaseFreesoloAutocomplete({
  options,
  value,
  onChange,
  label,
  required = false,
  popperWidth,
  disabled = false,
}: BaseFreesoloAutocompleteProps) {
  // Create filter for autocomplete
  const filter = createFilterOptions<AutocompleteOption>();

  // Convert current form value to the appropriate Autocomplete value
  const autocompleteValue = React.useMemo(() => {
    if (value === undefined || value === null) {
      return null;
    }

    if (typeof value === 'string') {
      // If it looks like a UUID, try to find the matching option
      if (
        value.match(
          /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i
        )
      ) {
        const matchingOption = options.find(option => option.id === value);
        if (matchingOption) {
          return matchingOption;
        }
      }
      // Otherwise, return the string as is
      return value;
    }

    // If it's a UUID, find the matching option
    return options.find(option => option.id === value) || null;
  }, [value, options]);

  // Get option label, handling different types of values
  const getOptionLabel = (option: AutocompleteOption | string) => {
    // Value selected with enter, right from the input
    if (typeof option === 'string') {
      // If the string looks like a UUID, try to find the matching option
      if (
        option.match(
          /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i
        )
      ) {
        const matchingOption = options.find(o => o.id === option);
        if (matchingOption) {
          return matchingOption.name;
        }
      }
      return option;
    }
    // Add "xxx" option created dynamically
    if (option.inputValue) {
      return option.inputValue;
    }
    // Regular option
    return option.name;
  };

  const ForwardedPopper = React.forwardRef<HTMLDivElement, CustomPopperProps>(
    (props, ref) => (
      <CustomPopper {...props} ref={ref} popperWidth={popperWidth} />
    )
  );
  ForwardedPopper.displayName = 'ForwardedPopper';

  return (
    <FormControl fullWidth>
      <Autocomplete
        freeSolo
        selectOnFocus
        clearOnBlur
        handleHomeEndKeys
        options={options}
        getOptionLabel={getOptionLabel}
        PopperComponent={ForwardedPopper}
        disabled={disabled}
        filterOptions={(options, params) => {
          // Cast to AutocompleteOption[] - since we know MUI provides valid options internally
          const filtered = filter(options as AutocompleteOption[], params);

          const { inputValue } = params;
          // Suggest the creation of a new value
          const isExisting = options.some(option =>
            typeof option === 'string'
              ? inputValue === option
              : inputValue === option.name
          );
          if (inputValue !== '' && !isExisting) {
            filtered.push({
              inputValue,
              name: `Add "${inputValue}"`,
              id: '' as UUID,
            });
          }

          return filtered;
        }}
        value={autocompleteValue}
        onChange={(event, newValue) => {
          if (typeof newValue === 'string') {
            // User entered a string
            onChange(newValue);
          } else if (newValue && newValue.inputValue) {
            // Create a new value from the input
            onChange(newValue.inputValue);
          } else {
            // Pass the selected option or null
            onChange(newValue);
          }
        }}
        renderOption={(props, option) => {
          const { key: _key, ...otherProps } = props;
          return (
            <li
              {...otherProps}
              key={typeof option === 'string' ? option : option.id}
            >
              {typeof option === 'string' ? option : option.name}
            </li>
          );
        }}
        renderInput={params => (
          <TextField {...params} label={label} required={required} />
        )}
      />
    </FormControl>
  );
}
