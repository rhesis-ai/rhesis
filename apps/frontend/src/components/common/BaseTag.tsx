/**
 * BaseTag component for managing entity tags with customizable behavior
 * Handles tag creation, deletion, and validation with API integration
 */

'use client';

import React, { useState, useRef, KeyboardEvent, ClipboardEvent, ChangeEvent, FocusEvent, useEffect } from 'react';
import styles from '@/styles/BaseTag.module.css';
import {
  Box,
  Chip,
  TextField,
  InputProps,
  StandardTextFieldProps,
  InputLabelProps,
  FormHelperText,
  styled
} from '@mui/material';
import { ApiClientFactory } from '@/utils/api-client/client-factory';
import { TagsClient } from '@/utils/api-client/tags-client';
import { useNotifications } from '@/components/common/NotificationContext';
import { EntityType, TagCreate } from '@/utils/api-client/interfaces/tag';
import { TestTag } from '@/utils/api-client/interfaces/tests';
import { UUID } from 'crypto';

// Styled components for consistent styling
const TagContainer = styled(Box)({
  width: '100%',
  '& .MuiChip-root': {
    margin: '8px 4px 2px 0'
  }
}) as typeof Box;

// Type definitions
interface TaggableEntity {
  id: UUID;
  organization_id?: UUID;
  user_id?: UUID;
  tags?: TestTag[];
}

export interface BaseTagProps extends Omit<StandardTextFieldProps, 'onChange' | 'value'> {
  /** Current tag values */
  value: string[];
  /** Callback when tags change */
  onChange: (value: string[]) => void;
  /** Function to validate tag values */
  validate?: (value: string) => boolean;
  /** Whether to add tag on blur */
  addOnBlur?: boolean;
  /** Color of the tag chips */
  chipColor?: 'primary' | 'secondary' | 'default' | 'error' | 'info' | 'success' | 'warning';
  /** Whether to clear input on blur */
  clearInputOnBlur?: boolean;
  /** Characters that trigger tag addition */
  delimiters?: string[];
  /** Placeholder text */
  placeholder?: string;
  /** Whether to disable tag editing */
  disableEdition?: boolean;
  /** Whether tags must be unique */
  uniqueTags?: boolean;
  /** Maximum number of tags allowed */
  maxTags?: number;
  /** Whether to disable tag deletion on backspace */
  disableDeleteOnBackspace?: boolean;
  /** Session token for API calls */
  sessionToken?: string;
  /** Entity type for tag management */
  entityType?: EntityType;
  /** Entity for tag management */
  entity?: TaggableEntity;
}

// Tag validation utilities
const TagValidation = {
  isValidLength: (value: string) => value.length > 0 && value.length <= 50,
  isValidFormat: (value: string) => /^[a-zA-Z0-9-_\s]+$/.test(value),
  isValidTag: (value: string) => TagValidation.isValidLength(value) && TagValidation.isValidFormat(value)
};

export default function BaseTag({
  value = [],
  onChange,
  validate = TagValidation.isValidTag,
  addOnBlur = false,
  chipColor = 'default',
  clearInputOnBlur = false,
  delimiters = [',', 'Enter'],
  placeholder = '',
  disableEdition = false,
  uniqueTags = true,
  maxTags,
  label,
  disabled = false,
  error = false,
  disableDeleteOnBackspace = false,
  sessionToken,
  entityType,
  entity,
  InputProps: customInputProps,
  InputLabelProps: customInputLabelProps,
  id,
  ...textFieldProps
}: BaseTagProps) {
  const [inputValue, setInputValue] = useState<string>('');
  const [focused, setFocused] = useState<boolean>(false);
  const [isUpdating, setIsUpdating] = useState<boolean>(false);
  const [localTags, setLocalTags] = useState<string[]>(value);
  const inputRef = useRef<HTMLInputElement>(null);
  const notifications = useNotifications();

  // Update local tags when value prop changes
  useEffect(() => {
    setLocalTags(value);
  }, [value]);

  const handleTagsChange = async (newTagNames: string[]) => {
    if (!sessionToken || !entityType || !entity || isUpdating) {
      onChange(newTagNames);
      return;
    }

    setIsUpdating(true);
    const initialTagNames = localTags;

    // Update local state immediately
    setLocalTags(newTagNames);
    onChange(newTagNames);

    try {
      const apiFactory = new ApiClientFactory(sessionToken);
      const tagsClient = new TagsClient(sessionToken);

      // Tags to remove (exist in current but not in new)
      const tagsToRemove = entity.tags?.filter(tag => !newTagNames.includes(tag.name)) || [];

      // Tags to add (exist in new but not in current)
      const tagsToAdd = newTagNames.filter(tagName => !initialTagNames.includes(tagName));

      // Remove tags
      for (const tag of tagsToRemove) {
        await tagsClient.removeTagFromEntity(
          entityType,
          entity.id,
          tag.id
        );
      }

      // Add new tags
      for (const tagName of tagsToAdd) {
        const tagPayload: TagCreate = {
          name: tagName,
          ...(entity.organization_id && { organization_id: entity.organization_id }),
          ...(entity.user_id && { user_id: entity.user_id })
        };

        await tagsClient.assignTagToEntity(
          entityType,
          entity.id,
          tagPayload
        );
      }

      notifications?.show(
        'Tags updated successfully',
        {
          severity: 'success',
          autoHideDuration: 4000
        }
      );
    } catch (error) {
      console.error('Error updating tags:', error);
      notifications?.show(
        error instanceof Error ? error.message : 'Failed to update tags',
        {
          severity: 'error',
          autoHideDuration: 6000
        }
      );
      // Revert local state on error
      setLocalTags(initialTagNames);
      onChange(initialTagNames);
    } finally {
      setIsUpdating(false);
    }
  };

  const handleInputChange = (event: ChangeEvent<HTMLInputElement>) => {
    setInputValue(event.target.value);
  };

  const handleAddTag = (tagValue: string) => {
    if (!tagValue || disabled || isUpdating) return;
    
    const trimmedValue = tagValue.trim();
    if (!trimmedValue || !validate(trimmedValue)) return;

    // Check for max tags limit
    if (maxTags !== undefined && localTags.length >= maxTags) return;
    
    // Check if tag already exists
    if (uniqueTags && localTags.includes(trimmedValue)) return;

    // Add the new tag
    handleTagsChange([...localTags, trimmedValue]);
    setInputValue('');
  };

  const handleInputKeyDown = (event: KeyboardEvent<HTMLDivElement>) => {
    const isDelimiter = delimiters.includes(event.key);
    
    if (isDelimiter && inputValue) {
      event.preventDefault();
      handleAddTag(inputValue);
    } else if (event.key === 'Backspace' && !inputValue && localTags.length > 0 && !disableDeleteOnBackspace) {
      // Remove the last tag on backspace if input is empty
      handleTagsChange(localTags.slice(0, -1));
    }
  };

  const handleDeleteTag = (tagToDelete: string) => {
    if (disabled || isUpdating) return;
    handleTagsChange(localTags.filter((tag) => tag !== tagToDelete));
    // Focus the input after deleting
    inputRef.current?.focus();
  };

  const handlePaste = (event: ClipboardEvent<HTMLDivElement>) => {
    event.preventDefault();
    
    if (disabled || isUpdating) return;
    
    const pastedText = event.clipboardData.getData('text');
    if (!pastedText) return;

    // Split by delimiters
    const delimiter = new RegExp(`[${delimiters.join('')}]`);
    const tags = pastedText.split(delimiter).filter(Boolean);
    
    if (tags.length === 0) return;

    // Process each tag
    const newTags = [...localTags];
    let tagsAdded = 0;
    
    for (const tag of tags) {
      const trimmedTag = tag.trim();
      if (!trimmedTag || !validate(trimmedTag)) continue;
      if (uniqueTags && newTags.includes(trimmedTag)) continue;
      
      // Check max tags limit
      if (maxTags !== undefined && newTags.length >= maxTags) break;
      
      newTags.push(trimmedTag);
      tagsAdded++;
    }
    
    if (tagsAdded > 0) {
      handleTagsChange(newTags);
      setInputValue('');
    }
  };

  const handleBlur = (event: FocusEvent<HTMLInputElement>) => {
    setFocused(false);
    
    if (addOnBlur && inputValue) {
      handleAddTag(inputValue);
    }
    
    if (clearInputOnBlur) {
      setInputValue('');
    }
    
    if (textFieldProps.onBlur) {
      textFieldProps.onBlur(event as any);
    }
  };

  const handleFocus = (event: FocusEvent<HTMLInputElement>) => {
    setFocused(true);
    
    if (textFieldProps.onFocus) {
      textFieldProps.onFocus(event as any);
    }
  };

  // Field is disabled if component is disabled or max tags is reached
  const isTagInputDisabled = disabled || (maxTags !== undefined && localTags.length >= maxTags);

  // Combine default and custom InputLabelProps
  const inputLabelProps: InputLabelProps = {
    ...customInputLabelProps,
    shrink: focused || !!inputValue || localTags.length > 0,
  };

  // Create chips for each tag
  const chipElements = localTags.map((tag) => (
    <Chip
      key={tag}
      label={tag}
      onDelete={!disabled ? () => handleDeleteTag(tag) : undefined}
      color={chipColor}
      className={styles.baseTag}
    />
  ));

  return (
    <TagContainer>
      <TextField
        id={id}
        className="tag-input"
        value={inputValue}
        onChange={handleInputChange}
        onKeyDown={handleInputKeyDown}
        onPaste={handlePaste}
        onBlur={handleBlur}
        onFocus={handleFocus}
        label={label}
        placeholder={localTags.length === 0 ? placeholder : ''}
        disabled={disabled || isUpdating}
        error={error}
        fullWidth
        InputProps={{
          ...customInputProps,
          startAdornment: chipElements.length > 0 ? chipElements : null
        }}
        InputLabelProps={inputLabelProps}
        variant="outlined"
        {...textFieldProps}
      />
    </TagContainer>
  );
} 