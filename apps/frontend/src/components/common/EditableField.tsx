'use client';

import React from 'react';
import { TextField, type TextFieldProps } from '@mui/material';
import {
  editableOutlinedFieldSx,
  readOnlyOutlinedFieldSx,
} from '@/components/common/drawerFormFieldSx';

export type EditableFieldProps = Omit<TextFieldProps, 'slotProps'> & {
  editing: boolean;
  slotProps?: TextFieldProps['slotProps'];
};

export default function EditableField({
  editing,
  sx,
  slotProps,
  ...rest
}: EditableFieldProps) {
  return (
    <TextField
      {...rest}
      slotProps={{
        ...slotProps,
        input: {
          ...slotProps?.input,
          readOnly: !editing,
        },
      }}
      sx={[
        ...(Array.isArray(sx) ? sx : sx ? [sx] : []),
        ...(!editing ? [readOnlyOutlinedFieldSx] : [editableOutlinedFieldSx]),
      ]}
    />
  );
}
