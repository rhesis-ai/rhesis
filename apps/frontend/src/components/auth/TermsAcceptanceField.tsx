'use client';

import { Box, Checkbox, FormControlLabel, Typography } from '@mui/material';

const TERMS_URL = 'https://www.rhesis.ai/terms-conditions';
const PRIVACY_URL = 'https://www.rhesis.ai/privacy-policy';

interface TermsAcceptanceFieldProps {
  checked: boolean;
  onChange: (accepted: boolean) => void;
  showWarning?: boolean;
}

export default function TermsAcceptanceField({
  checked,
  onChange,
  showWarning = false,
}: TermsAcceptanceFieldProps) {
  return (
    <Box>
      <FormControlLabel
        control={
          <Checkbox
            checked={checked}
            onChange={event => onChange(event.target.checked)}
            color="primary"
          />
        }
        label={
          <Typography variant="body2">
            I agree to the{' '}
            <a
              href={TERMS_URL}
              target="_blank"
              rel="noopener noreferrer"
              style={{ color: 'inherit' }}
            >
              Terms
            </a>
            {' & '}
            <a
              href={PRIVACY_URL}
              target="_blank"
              rel="noopener noreferrer"
              style={{ color: 'inherit' }}
            >
              Privacy Policy
            </a>
          </Typography>
        }
      />
      {showWarning && (
        <Typography variant="body2" color="error" sx={{ ml: 4 }}>
          Please accept the Terms and Conditions to continue.
        </Typography>
      )}
    </Box>
  );
}
