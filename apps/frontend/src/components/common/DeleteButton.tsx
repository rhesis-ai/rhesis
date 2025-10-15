import React from 'react';
import { Button, ButtonProps } from '@mui/material';
import DeleteIcon from '@mui/icons-material/Delete';

interface DeleteButtonProps
  extends Omit<ButtonProps, 'variant' | 'color' | 'startIcon'> {
  /**
   * The text to display on the button
   * @default "Delete"
   */
  label?: string;
  /**
   * Whether to show the delete icon
   * @default true
   */
  showIcon?: boolean;
}

/**
 * Standardized delete button component for consistent styling across the platform
 * Uses outlined variant with error color and delete icon
 */
export const DeleteButton: React.FC<DeleteButtonProps> = ({
  label = 'Delete',
  showIcon = true,
  children,
  ...props
}) => {
  return (
    <Button
      variant="outlined"
      color="error"
      startIcon={showIcon ? <DeleteIcon /> : undefined}
      {...props}
    >
      {children || label}
    </Button>
  );
};

export default DeleteButton;
