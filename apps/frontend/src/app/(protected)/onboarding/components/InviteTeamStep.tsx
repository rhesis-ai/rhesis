import * as React from 'react';
import {
  Box,
  TextField,
  Button,
  Typography,
  Grid,
  IconButton
} from '@mui/material';
import AddIcon from '@mui/icons-material/Add';
import DeleteIcon from '@mui/icons-material/Delete';

interface FormData {
  invites: { email: string }[];
}

interface InviteTeamStepProps {
  formData: FormData;
  updateFormData: (data: Partial<FormData>) => void;
  onNext: () => void;
  onBack: () => void;
}

export default function InviteTeamStep({
  formData,
  updateFormData,
  onNext,
  onBack
}: InviteTeamStepProps) {
  const [errors, setErrors] = React.useState<{ [key: number]: boolean }>({});

  // Email validation regex
  const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

  const validateForm = () => {
    const newErrors: { [key: number]: boolean } = {};
    let hasError = false;
    
    // Only validate non-empty emails
    formData.invites.forEach((invite, index) => {
      if (invite.email && !emailRegex.test(invite.email)) {
        newErrors[index] = true;
        hasError = true;
      }
    });
    
    setErrors(newErrors);
    return !hasError;
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    
    if (validateForm()) {
      onNext();
    }
  };

  const handleEmailChange = (index: number, value: string) => {
    const updatedInvites = [...formData.invites];
    updatedInvites[index] = { email: value };
    updateFormData({ invites: updatedInvites });
    
    // Clear error when user types
    if (errors[index]) {
      const newErrors = { ...errors };
      delete newErrors[index];
      setErrors(newErrors);
    }
  };

  const addEmailField = () => {
    updateFormData({
      invites: [...formData.invites, { email: '' }]
    });
  };

  const removeEmailField = (index: number) => {
    const updatedInvites = [...formData.invites];
    updatedInvites.splice(index, 1);
    updateFormData({ invites: updatedInvites });
    
    // Remove error for this field if it exists
    if (errors[index]) {
      const newErrors = { ...errors };
      delete newErrors[index];
      setErrors(newErrors);
    }
  };

  return (
    <Box component="form" onSubmit={handleSubmit} sx={{ mt: 4 }}>
      <Typography variant="h6" gutterBottom align="center">
        Invite Team Members
      </Typography>
      
      <Typography variant="body1" color="text.secondary" align="center" sx={{ mb: 3 }}>
        Invite colleagues to join your organization
      </Typography>
      
      {formData.invites.map((invite, index) => (
        <Grid container spacing={2} key={index} alignItems="center" sx={{ mb: 2 }}>
          <Grid item xs>
            <TextField
              fullWidth
              label="Email Address"
              value={invite.email}
              onChange={(e) => handleEmailChange(index, e.target.value)}
              error={Boolean(errors[index])}
              helperText={errors[index] ? 'Please enter a valid email address' : ''}
              placeholder="colleague@company.com"
            />
          </Grid>
          {formData.invites.length > 1 && (
            <Grid item>
              <IconButton 
                onClick={() => removeEmailField(index)}
                color="error"
                size="small"
              >
                <DeleteIcon />
              </IconButton>
            </Grid>
          )}
        </Grid>
      ))}
      
      <Button
        startIcon={<AddIcon />}
        onClick={addEmailField}
        sx={{ mt: 1, mb: 4 }}
      >
        Add Another
      </Button>
      
      <Box sx={{ display: 'flex', justifyContent: 'space-between', mt: 2 }}>
        <Button onClick={onBack}>
          Back
        </Button>
        <Button 
          type="submit"
          variant="contained"
          color="primary"
        >
          Next
        </Button>
      </Box>
    </Box>
  );
} 