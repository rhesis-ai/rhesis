/**
 * BaseTag component for managing entity tags with customizable behavior
 * Handles tag creation, deletion, and validation with API integration
 */

'use client';

import React, {
  useState,
  useRef,
  KeyboardEvent,
  ClipboardEvent,
  ChangeEvent,
  FocusEvent,
  useEffect,
} from 'react';
import styles from '@/styles/BaseTag.module.css';
import {
  Box,
  Chip,
  TextField,
  Autocomplete,
  InputProps,
  StandardTextFieldProps,
  InputLabelProps,
  FormHelperText,
} from '@mui/material';
import { ApiClientFactory } from '@/utils/api-client/client-factory';
import { TagsClient } from '@/utils/api-client/tags-client';
import { useNotifications } from '@/components/common/NotificationContext';
import { EntityType, Tag, TagCreate } from '@/utils/api-client/interfaces/tag';
import { UUID } from 'crypto';

// Type definitions
interface TaggableEntity {
  id: UUID;
  organization_id?: UUID;
  user_id?: UUID;
  tags?: Tag[];
}

export interface BaseTagProps extends Omit<
  StandardTextFieldProps,
  'onChange' | 'value'
> {
  /** Current tag values */
  value: string[];
  /** Callback when tags change */
  onChange: (value: string[]) => void;
  /** Function to validate tag values */
  validate?: (value: string) => boolean;
  /** Whether to add tag on blur */
  addOnBlur?: boolean;
  /** Color of the tag chips */
  chipColor?:
    | 'primary'
    | 'secondary'
    | 'default'
    | 'error'
    | 'info'
    | 'success'
    | 'warning';
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
  /** Custom className for chip styling */
  chipClassName?: string;
}

// Tag validation utilities
const TagValidation = {
  isValidLength: (value: string) => value.length > 0 && value.length <= 50,
  isValidFormat: (value: string) =>
    /^[a-zA-Z0-9\-_\s\u00C0-\u017F\u0180-\u024F.,!?()]+$/.test(value),
  isValidTag: (value: string) =>
    TagValidation.isValidLength(value) && TagValidation.isValidFormat(value),
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
  chipClassName,
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
  const isProcessingKeyboardInput = useRef<boolean>(false);
  const notifications = useNotifications();

  // Keep track of current tag objects (name -> tag mapping)
  const [tagObjectsMap, setTagObjectsMap] = useState<Map<string, Tag>>(
    new Map()
  );

  // Update local tags when value prop changes
  useEffect(() => {
    setLocalTags(value);
  }, [value]);

  // Update tag objects map when entity tags change
  useEffect(() => {
    if (entity?.tags) {
      const newMap = new Map<string, Tag>();
      entity.tags.forEach(tag => {
        newMap.set(tag.name, tag);
      });
      setTagObjectsMap(newMap);
    }
  }, [entity?.tags]);

  const handleTagsChange = async (newTagNames: string[]) => {
    if (!sessionToken || !entityType || !entity || isUpdating) {
      onChange(newTagNames);
      return;
    }

    setIsUpdating(true);
    const initialTagNames = localTags;
    const initialTagObjectsMap = new Map(tagObjectsMap);

    // Update local state immediately
    setLocalTags(newTagNames);
    onChange(newTagNames);

    try {
      const apiFactory = new ApiClientFactory(sessionToken);
      const tagsClient = new TagsClient(sessionToken);

      // Tags to remove (exist in current but not in new) - use the current tagObjectsMap
      const tagsToRemove = initialTagNames
        .filter(tagName => !newTagNames.includes(tagName))
        .map(tagName => tagObjectsMap.get(tagName))
        .filter((tag): tag is Tag => tag !== undefined);

      // Tags to add (exist in new but not in current)
      const tagsToAdd = newTagNames.filter(
        tagName => !initialTagNames.includes(tagName)
      );

      // Remove tags
      for (const tag of tagsToRemove) {
        await tagsClient.removeTagFromEntity(entityType, entity.id, tag.id);
        // Update the map by removing the deleted tag
        const newMap = new Map(tagObjectsMap);
        newMap.delete(tag.name);
        setTagObjectsMap(newMap);
      }

      // Add new tags
      for (const tagName of tagsToAdd) {
        const tagPayload: TagCreate = {
          name: tagName,
          ...(entity.organization_id && {
            organization_id: entity.organization_id,
          }),
          ...(entity.user_id && { user_id: entity.user_id }),
        };

        const newTag = await tagsClient.assignTagToEntity(
          entityType,
          entity.id,
          tagPayload
        );
        // Update the map by adding the new tag
        const newMap = new Map(tagObjectsMap);
        newMap.set(newTag.name, newTag);
        setTagObjectsMap(newMap);
      }

      notifications?.show('Tags updated successfully', {
        severity: 'success',
        autoHideDuration: 4000,
      });
    } catch (error) {
      notifications?.show(
        error instanceof Error ? error.message : 'Failed to update tags',
        {
          severity: 'error',
          autoHideDuration: 6000,
        }
      );
      // Revert local state on error
      setLocalTags(initialTagNames);
      onChange(initialTagNames);
      setTagObjectsMap(initialTagObjectsMap);
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
    if (uniqueTags && localTags.includes(trimmedValue)) {
      notifications?.show(`Tag "${trimmedValue}" already exists`, {
        severity: 'info',
        autoHideDuration: 3000,
      });
      setInputValue('');
      return;
    }

    // Add the new tag
    handleTagsChange([...localTags, trimmedValue]);
    setInputValue('');
  };

  const handleInputKeyDown = (event: KeyboardEvent<HTMLDivElement>) => {
    const isDelimiter = delimiters.includes(event.key);

    if (isDelimiter && inputValue) {
      event.preventDefault();
      event.stopPropagation();
      isProcessingKeyboardInput.current = true;
      handleAddTag(inputValue);
      // Reset the flag after a short delay to allow Autocomplete's onChange to complete
      setTimeout(() => {
        isProcessingKeyboardInput.current = false;
      }, 0);
    } else if (
      event.key === 'Backspace' &&
      !inputValue &&
      localTags.length > 0 &&
      !disableDeleteOnBackspace
    ) {
      // Remove the last tag on backspace if input is empty
      event.preventDefault();
      handleTagsChange(localTags.slice(0, -1));
    }
  };

  const handleDeleteTag = (tagToDelete: string) => {
    if (disabled || isUpdating) return;
    handleTagsChange(localTags.filter(tag => tag !== tagToDelete));
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
    const duplicates: string[] = [];

    for (const tag of tags) {
      const trimmedTag = tag.trim();
      if (!trimmedTag || !validate(trimmedTag)) continue;

      if (uniqueTags && newTags.includes(trimmedTag)) {
        duplicates.push(trimmedTag);
        continue;
      }

      // Check max tags limit
      if (maxTags !== undefined && newTags.length >= maxTags) break;

      newTags.push(trimmedTag);
      tagsAdded++;
    }

    if (tagsAdded > 0) {
      handleTagsChange(newTags);
      setInputValue('');
    }

    // Notify about duplicates
    if (duplicates.length > 0) {
      const message =
        duplicates.length === 1
          ? `Tag "${duplicates[0]}" already exists`
          : `${duplicates.length} duplicate tags skipped`;
      notifications?.show(message, {
        severity: 'info',
        autoHideDuration: 3000,
      });
    }
  };

  const handleBlur = (event: FocusEvent<HTMLInputElement>) => {
    setFocused(false);

    if (addOnBlur && inputValue) {
      isProcessingKeyboardInput.current = true;
      handleAddTag(inputValue);
      // Reset the flag after a short delay to allow Autocomplete's onChange to complete
      setTimeout(() => {
        isProcessingKeyboardInput.current = false;
      }, 0);
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
  const isTagInputDisabled =
    disabled || (maxTags !== undefined && localTags.length >= maxTags);

  // Combine default and custom InputLabelProps
  const inputLabelProps: InputLabelProps = {
    ...customInputLabelProps,
    shrink: focused || !!inputValue || localTags.length > 0,
  };

  return (
    <Box className={styles.tagContainer}>
      <Autocomplete
        multiple
        freeSolo
        clearIcon={false}
        options={[]}
        value={localTags}
        inputValue={inputValue}
        onChange={(event, newValue: string[]) => {
          // Skip if we're already processing keyboard input to prevent duplicate API calls
          if (isProcessingKeyboardInput.current) {
            return;
          }
          // Handle tag changes when chips are removed or values change
          handleTagsChange(newValue);
        }}
        onInputChange={(event, newInputValue: string, reason) => {
          if (reason === 'input') {
            setInputValue(newInputValue);
          } else if (reason === 'clear') {
            setInputValue('');
          }
        }}
        onKeyDown={handleInputKeyDown}
        disabled={disabled || disableEdition}
        renderTags={(value: string[], getTagProps) =>
          value.map((option: string, index: number) => (
            <Chip
              {...getTagProps({ index })}
              key={option}
              label={option}
              color={chipColor}
              variant="outlined"
              disabled={disabled}
              className={chipClassName || styles.baseTag}
              onDelete={
                !disabled && !disableEdition
                  ? () => handleDeleteTag(option)
                  : undefined
              }
            />
          ))
        }
        renderInput={params => (
          <TextField
            {...params}
            {...textFieldProps}
            label={label}
            placeholder={localTags.length === 0 ? placeholder : ''}
            error={error}
            inputRef={inputRef}
            onBlur={handleBlur}
            onFocus={handleFocus}
            onPaste={handlePaste}
            InputLabelProps={inputLabelProps}
            InputProps={{
              ...params.InputProps,
              ...customInputProps,
              readOnly: disableEdition,
            }}
            fullWidth
          />
        )}
      />
    </Box>
  );
}
