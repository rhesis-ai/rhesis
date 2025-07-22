import * as React from 'react';
import {
  Box,
  TextField,
  Button,
  Typography,
  IconButton,
  CircularProgress,
  Snackbar,
  Alert,
  Stack
} from '@mui/material';
import AddIcon from '@mui/icons-material/Add';
import DeleteIcon from '@mui/icons-material/Delete';
import { useState } from 'react';

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
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);
  const [errors, setErrors] = useState<{ [key: number]: boolean }>({});

  // Email validation regex
  const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

  const validateForm = () => {
    const newErrors: { [key: number]: boolean } = {};
    let hasError = false;
    
    // Only validate non-empty emails
    formData.invites.forEach((invite, index) => {
      if (invite.email.trim() && !emailRegex.test(invite.email.trim())) {
        newErrors[index] = true;
        hasError = true;
      }
    });
    
    setErrors(newErrors);
    return !hasError;
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    
    if (!validateForm()) {
      return;
    }

    try {
      setIsSubmitting(true);
      
      // Proceed to next step
      onNext();
    } catch (error) {
      console.error('Error during form submission:', error);
      setErrorMessage('Failed to submit form. Please try again.');
    } finally {
      setIsSubmitting(false);
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

  const handleCloseSnackbar = () => {
    setErrorMessage(null);
    setSuccessMessage(null);
  };

  return (
    <Box component="form" onSubmit={handleSubmit}>
      {/* Header Section */}
      <Box textAlign="center" mb={4}>
        <Typography variant="h5" component="h2" gutterBottom>
          Invite Team Members
        </Typography>
        <Typography variant="body1" color="text.secondary">
          Invite colleagues to join your organization. You can skip this step and add team members later.
        </Typography>
      </Box>

      {/* Form Fields */}
      <Stack spacing={3}>
        {formData.invites.map((invite, index) => (
          <Box key={index} display="flex" alignItems="flex-start" gap={2}>
            <TextField
              fullWidth
              label="Email Address"
              value={invite.email}
              onChange={(e) => handleEmailChange(index, e.target.value)}
              error={Boolean(errors[index])}
              helperText={errors[index] ? 'Please enter a valid email address' : ''}
              placeholder="colleague@company.com"
              variant="outlined"
            />
            {formData.invites.length > 1 && (
              <IconButton 
                onClick={() => removeEmailField(index)}
                color="error"
                size="large"
              >
                <DeleteIcon />
              </IconButton>
            )}
          </Box>
        ))}
        
        <Box display="flex" justifyContent="flex-start">
          <Button
            startIcon={<AddIcon />}
            onClick={addEmailField}
            variant="outlined"
            size="medium"
          >
            Add Another Email
          </Button>
        </Box>
      </Stack>

      {/* Action Buttons */}
      <Box display="flex" justifyContent="space-between" mt={4}>
        <Button 
          onClick={onBack}
          disabled={isSubmitting}
          size="large"
        >
          Back
        </Button>
        <Button 
          type="submit"
          variant="contained"
          color="primary"
          disabled={isSubmitting}
          startIcon={isSubmitting ? <CircularProgress size={20} color="inherit" /> : null}
          size="large"
        >
          {isSubmitting ? 'Saving...' : 'Next'}
        </Button>
      </Box>

      {/* Notifications */}
      <Snackbar 
        open={!!errorMessage} 
        autoHideDuration={6000} 
        onClose={handleCloseSnackbar}
        anchorOrigin={{ vertical: 'bottom', horizontal: 'center' }}
      >
        <Alert onClose={handleCloseSnackbar} severity="error">
          {errorMessage}
        </Alert>
      </Snackbar>

      <Snackbar 
        open={!!successMessage} 
        autoHideDuration={4000} 
        onClose={handleCloseSnackbar}
        anchorOrigin={{ vertical: 'bottom', horizontal: 'center' }}
      >
        <Alert onClose={handleCloseSnackbar} severity="success">
          {successMessage}
        </Alert>
      </Snackbar>
    </Box>
  );
} 