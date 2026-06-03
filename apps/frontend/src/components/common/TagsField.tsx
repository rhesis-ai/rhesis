'use client';

import * as React from 'react';
import { Box, Typography } from '@mui/material';
import type { SxProps, Theme } from '@mui/material/styles';
import BaseTag, { type BaseTagProps } from '@/components/common/BaseTag';
import Tag from '@/components/common/Tag';

const readOnlyBoxSx: SxProps<Theme> = {
  border: (theme: Theme) => `1px solid ${theme.palette.greyscale.border}`,
  borderRadius: '4px',
  pl: '16px',
  pr: '12px',
  py: '16px',
  display: 'flex',
  gap: '10px',
  flexWrap: 'wrap',
  alignItems: 'center',
  minHeight: 56,
};

export interface TagsFieldProps {
  tagNames: string[];
  isEditing: boolean;
  onChange: (tagNames: string[]) => void;
  label?: string;
  placeholder?: string;
  helperText?: string;
  emptyLabel?: string;
  baseTagProps?: Partial<BaseTagProps>;
}

/**
 * Tags in edit mode: removable MUI chips (rectangular tag).
 * Tags in view mode: read-only Tag (same rectangular shape, no ×).
 */
export function TagsField({
  tagNames,
  isEditing,
  onChange,
  label = 'Tags',
  placeholder = 'Add tags (press Enter or comma to add)',
  helperText,
  emptyLabel = 'Tags',
  baseTagProps,
}: TagsFieldProps) {
  if (isEditing) {
    return (
      <BaseTag
        value={tagNames}
        onChange={onChange}
        label={label}
        placeholder={placeholder}
        helperText={helperText}
        chipColor="default"
        addOnBlur
        delimiters={[',', 'Enter']}
        size="medium"
        fullWidth
        {...baseTagProps}
      />
    );
  }

  return (
    <Box>
      <Box sx={readOnlyBoxSx}>
        {tagNames.length > 0 ? (
          tagNames.map(tag => <Tag key={tag} label={tag} />)
        ) : (
          <Typography
            sx={{
              fontSize: '1rem',
              lineHeight: '24px',
              color: theme => theme.palette.greyscale.label,
            }}
          >
            {emptyLabel}
          </Typography>
        )}
      </Box>
      {helperText ? (
        <Typography
          sx={{
            fontSize: 12,
            lineHeight: '18px',
            color: 'text.secondary',
            px: '14px',
            pt: '3px',
          }}
        >
          {helperText}
        </Typography>
      ) : null}
    </Box>
  );
}

export default TagsField;
