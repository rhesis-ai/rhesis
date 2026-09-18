'use client';

import React from 'react';
import { MenuItem, TextField } from '@mui/material';
import { CURRENCIES, formatMoney, type Currency } from '@/utils/money';

/** A sample cost, so each option shows what it will actually look like. */
const SAMPLE_USD = 12.3456;

export const FOLLOW_ORGANIZATION = '';

interface CurrencySelectProps {
  label: string;
  helperText?: React.ReactNode;
  /** `FOLLOW_ORGANIZATION` when this picker offers a defer-to-default option. */
  value: Currency | typeof FOLLOW_ORGANIZATION;
  onChange: (value: Currency | typeof FOLLOW_ORGANIZATION) => void;
  /** Rates, so each option can preview a real converted figure. */
  rates?: Partial<Record<Currency, number>>;
  /** Label for the defer option. Omitted where there is nothing to defer to. */
  inheritLabel?: string;
  disabled?: boolean;
}

/**
 * Picks the currency costs are shown in.
 *
 * Each option previews the same sample cost in that currency, because a
 * three-letter code says less about what you are choosing than the figure
 * does -- and it shows immediately when a currency has no rate available, by
 * previewing in the stored currency instead.
 */
export default function CurrencySelect({
  label,
  helperText,
  value,
  onChange,
  rates = {},
  inheritLabel,
  disabled = false,
}: CurrencySelectProps) {
  return (
    <TextField
      select
      size="small"
      label={label}
      value={value}
      disabled={disabled}
      helperText={helperText}
      onChange={event =>
        onChange(event.target.value as Currency | typeof FOLLOW_ORGANIZATION)
      }
      sx={{ minWidth: 280 }}
    >
      {inheritLabel && (
        <MenuItem value={FOLLOW_ORGANIZATION}>{inheritLabel}</MenuItem>
      )}
      {CURRENCIES.map(currency => (
        <MenuItem key={currency} value={currency}>
          {currency} &nbsp;·&nbsp; {formatMoney(SAMPLE_USD, currency, rates)}
        </MenuItem>
      ))}
    </TextField>
  );
}
