'use client';

import * as React from 'react';
import Autocomplete from '@mui/material/Autocomplete';
import Box from '@mui/material/Box';
import IconButton from '@mui/material/IconButton';
import MenuItem from '@mui/material/MenuItem';
import TextField from '@mui/material/TextField';
import Typography from '@mui/material/Typography';
import CloseIcon from '@mui/icons-material/Close';
import type { SxProps, Theme } from '@mui/material/styles';
import type {
  ConditionOperatorChoice,
  SpecialFieldChoice,
} from '@/utils/api-client/interfaces/metric';
import {
  type ConditionDraft,
  type FieldOption,
  fieldLabel,
  findOperator,
  operatorLabel,
  SPECIAL_FIELDS_GROUP,
  VALUE_TYPE,
  valueForOperator,
} from '@/utils/metric-target-draft';

interface TargetConditionRowProps {
  /** 1-based, for the row's accessible name. */
  index: number;
  condition: ConditionDraft;
  operators: ConditionOperatorChoice[];
  specialFields: SpecialFieldChoice[];
  fieldOptions: FieldOption[];
  /** Values to suggest for the row's field. */
  suggestions: string[];
  onChange: (condition: ConditionDraft) => void;
  onRemove: () => void;
  /** Mark incomplete parts as errors (after a save attempt). */
  showErrors?: boolean;
}

const codeInputSx: SxProps<Theme> = {
  '& input': { fontFamily: theme => theme.typography.fontFamilyCode },
};

/**
 * One condition: the field (special fields and the catalogue's attribute keys,
 * grouped by kind; any key can be typed), the operator, and a value input that
 * fits the operator, with the field's common values suggested.
 */
export default function TargetConditionRow({
  index,
  condition,
  operators,
  specialFields,
  fieldOptions,
  suggestions,
  onChange,
  onRemove,
  showErrors = false,
}: TargetConditionRowProps) {
  const id = React.useId();
  const operator = findOperator(condition.op, operators);
  const valueType = operator?.value_type ?? VALUE_TYPE.TEXT;
  const isSpecial = specialFields.some(f => f.field === condition.field);
  const selectedField =
    fieldOptions.find(o => o.field === condition.field) ?? null;

  const setValue = (value: string | string[]) =>
    onChange({ ...condition, value });

  const valueInput = () => {
    if (!operator?.takes_value) return null;
    const missing =
      showErrors &&
      (Array.isArray(condition.value)
        ? condition.value.length === 0
        : !condition.value.trim());
    if (valueType === VALUE_TYPE.LIST) {
      return (
        <Autocomplete
          multiple
          freeSolo
          size="small"
          options={suggestions}
          value={Array.isArray(condition.value) ? condition.value : []}
          onChange={(_e, values) => setValue(values.map(String))}
          renderInput={params => (
            <TextField
              {...params}
              label="Values"
              placeholder="Type and press Enter"
              error={missing}
              sx={codeInputSx}
            />
          )}
        />
      );
    }
    if (valueType === VALUE_TYPE.TEXT) {
      return (
        <Autocomplete
          freeSolo
          size="small"
          options={suggestions}
          inputValue={Array.isArray(condition.value) ? '' : condition.value}
          onInputChange={(_e, value) => setValue(value)}
          renderInput={params => (
            <TextField
              {...params}
              label="Value"
              error={missing}
              sx={codeInputSx}
            />
          )}
        />
      );
    }
    const isNumber = valueType === VALUE_TYPE.NUMBER;
    return (
      <TextField
        size="small"
        fullWidth
        label={isNumber ? 'Number' : 'Pattern'}
        value={Array.isArray(condition.value) ? '' : condition.value}
        onChange={e => setValue(e.target.value)}
        error={missing}
        sx={codeInputSx}
        slotProps={{
          htmlInput: isNumber ? { inputMode: 'decimal' } : undefined,
        }}
      />
    );
  };

  return (
    <Box
      role="group"
      aria-label={`Condition ${index}`}
      data-testid="target-condition-row"
      sx={{
        display: 'grid',
        gridTemplateColumns: {
          xs: '1fr auto',
          md: 'minmax(0, 3fr) minmax(0, 2fr) minmax(0, 3fr) auto',
        },
        gap: 1,
        alignItems: 'start',
      }}
    >
      <Box sx={{ gridColumn: { xs: '1 / 2', md: 'auto' } }}>
        <Autocomplete<FieldOption, false, false, true>
          freeSolo
          size="small"
          options={fieldOptions}
          groupBy={option => option.group}
          getOptionKey={option =>
            typeof option === 'string' ? option : option.key
          }
          getOptionLabel={option =>
            typeof option === 'string' ? option : option.label
          }
          isOptionEqualToValue={(option, value) => option.field === value.field}
          value={selectedField}
          inputValue={fieldLabel(condition.field, specialFields)}
          onChange={(_e, option) => {
            const field =
              option === null
                ? ''
                : typeof option === 'string'
                  ? option
                  : option.field;
            onChange({ ...condition, field });
          }}
          onInputChange={(_e, text, reason) => {
            // A pick sets the field in onChange; only typing sets it here.
            if (reason === 'input') onChange({ ...condition, field: text });
          }}
          // Keys are long: the list is wider than the field it opens from.
          slotProps={{
            popper: {
              placement: 'bottom-start',
              sx: { minWidth: theme => theme.spacing(60) },
            },
          }}
          renderOption={(props, option) => {
            const { key, ...rest } = props;
            return (
              <Box
                component="li"
                key={key}
                {...rest}
                sx={{ display: 'flex', gap: 2, alignItems: 'baseline' }}
              >
                <Typography
                  variant="body2"
                  sx={{
                    flex: 1,
                    minWidth: 0,
                    fontFamily: theme =>
                      option.group === SPECIAL_FIELDS_GROUP
                        ? undefined
                        : theme.typography.fontFamilyCode,
                    overflowWrap: 'anywhere',
                  }}
                >
                  {option.label}
                </Typography>
                {option.hint && (
                  <Typography
                    variant="caption"
                    color="text.secondary"
                    sx={{ flexShrink: 0, maxWidth: '45%', textAlign: 'right' }}
                  >
                    {option.hint}
                  </Typography>
                )}
              </Box>
            );
          }}
          renderInput={params => (
            <TextField
              {...params}
              label="Field"
              placeholder="Search attributes"
              error={showErrors && !condition.field.trim()}
              sx={isSpecial ? undefined : codeInputSx}
            />
          )}
        />
      </Box>
      <TextField
        select
        size="small"
        label="Operator"
        id={`${id}-op`}
        value={operator ? condition.op : ''}
        error={showErrors && !operator}
        onChange={e => {
          const next = findOperator(e.target.value, operators);
          onChange({
            ...condition,
            op: e.target.value,
            value: valueForOperator(condition.value, next),
          });
        }}
        sx={{
          gridRow: { xs: 2, md: 'auto' },
          gridColumn: { xs: '1 / 2', md: 'auto' },
        }}
      >
        {operators.map(o => (
          <MenuItem key={o.op} value={o.op}>
            {operatorLabel(o.op)}
          </MenuItem>
        ))}
      </TextField>
      <Box
        sx={{
          gridRow: { xs: 3, md: 'auto' },
          gridColumn: { xs: '1 / 2', md: 'auto' },
        }}
      >
        {valueInput()}
      </Box>
      <IconButton
        aria-label={`Remove condition ${index}`}
        onClick={onRemove}
        size="small"
        sx={{
          mt: 0.5,
          gridRow: { xs: 1, md: 'auto' },
          gridColumn: { xs: '2 / 3', md: 'auto' },
        }}
      >
        <CloseIcon fontSize="small" />
      </IconButton>
    </Box>
  );
}
