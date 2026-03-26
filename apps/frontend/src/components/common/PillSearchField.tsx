'use client';

import React from 'react';
import {
  InputBase,
  Box,
  IconButton,
  InputAdornment,
  BoxProps,
} from '@mui/material';
import SearchIcon from '@mui/icons-material/Search';
import ClearIcon from '@mui/icons-material/Clear';

interface PillSearchFieldControlledProps {
  value: string;
  onChange: (value: string) => void;
  inputRef?: never;
  defaultValue?: never;
  onInputChange?: never;
  onClear?: never;
  showClear?: never;
}

interface PillSearchFieldUncontrolledProps {
  value?: never;
  onChange?: never;
  inputRef: React.Ref<HTMLInputElement>;
  defaultValue?: string;
  onInputChange: (e: React.ChangeEvent<HTMLInputElement>) => void;
  onClear?: () => void;
  showClear?: boolean;
}

type PillSearchFieldProps = (
  | PillSearchFieldControlledProps
  | PillSearchFieldUncontrolledProps
) & {
  placeholder?: string;
  onSearch?: () => void;
  width?: number | string;
  height?: number;
  sx?: BoxProps['sx'];
};

export default function PillSearchField(props: PillSearchFieldProps) {
  const {
    placeholder = 'Search...',
    onSearch,
    width = 288,
    height = 38,
    sx,
  } = props;

  const isControlled = 'value' in props && props.value !== undefined;

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && onSearch) {
      onSearch();
    }
  };

  return (
    <Box
      sx={{
        display: 'flex',
        alignItems: 'center',
        bgcolor: 'grey.100',
        borderRadius: (theme: any) => `${theme.customRadius.full}px`,
        height,
        width,
        pl: 2,
        pr: 0.5,
        ...sx,
      }}
    >
      <InputBase
        {...(isControlled
          ? {
              value: (props as PillSearchFieldControlledProps).value,
              onChange: (e: React.ChangeEvent<HTMLInputElement>) =>
                (props as PillSearchFieldControlledProps).onChange(
                  e.target.value
                ),
            }
          : {
              inputRef: (props as PillSearchFieldUncontrolledProps).inputRef,
              defaultValue:
                (props as PillSearchFieldUncontrolledProps).defaultValue ?? '',
              onChange: (props as PillSearchFieldUncontrolledProps)
                .onInputChange,
            })}
        onKeyDown={handleKeyDown}
        placeholder={placeholder}
        sx={{
          flex: 1,
          fontSize: 14,
          '& .MuiInputBase-input': {
            py: 0.5,
            '&::placeholder': { color: 'grey.400', opacity: 1 },
          },
        }}
        endAdornment={
          !isControlled &&
          (props as PillSearchFieldUncontrolledProps).showClear ? (
            <InputAdornment position="end">
              <IconButton
                size="small"
                onClick={(props as PillSearchFieldUncontrolledProps).onClear}
                aria-label="Clear search"
              >
                <ClearIcon sx={{ fontSize: 16 }} />
              </IconButton>
            </InputAdornment>
          ) : null
        }
      />
      <Box
        sx={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          bgcolor: 'primary.main',
          borderRadius: (theme: any) => theme.shape.circular,
          width: 30,
          height: 30,
          flexShrink: 0,
          cursor: 'pointer',
        }}
        onClick={onSearch}
      >
        <SearchIcon sx={{ fontSize: 18, color: '#fff' }} />
      </Box>
    </Box>
  );
}
