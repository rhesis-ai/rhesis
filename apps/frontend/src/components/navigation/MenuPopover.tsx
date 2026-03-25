'use client';

import React, { ReactNode } from 'react';
import { Popover, List, PopoverProps } from '@mui/material';

interface MenuPopoverProps extends Omit<
  PopoverProps,
  'children' | 'slotProps'
> {
  children: ReactNode;
  borderRadius?: number;
}

export default function MenuPopover({
  children,
  borderRadius = 2,
  ...props
}: MenuPopoverProps) {
  return (
    <Popover
      slotProps={{
        paper: {
          sx: {
            bgcolor: 'grey.200',
            borderRadius,
            boxShadow:
              '0px 2px 8px rgba(0, 0, 0, 0.08), 0px 0px 1px rgba(0, 0, 0, 0.3)',
            mt: props.anchorOrigin?.vertical === 'bottom' ? 0.5 : 0,
            mb: props.anchorOrigin?.vertical === 'top' ? 0.5 : 0,
            minWidth: 200,
          },
        },
      }}
      {...props}
    >
      <List disablePadding sx={{ py: 0.5 }}>
        {children}
      </List>
    </Popover>
  );
}
