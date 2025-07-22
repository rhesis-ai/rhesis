import * as React from 'react';
import {
  Box,
  TextField,
  Button,
  Typography,
  CircularProgress,
  Snackbar,
  Alert,
  Stack
} from '@mui/material';
import { useSession } from 'next-auth/react';
import { useEffect, useState } from 'react';

interface FormData {
  firstName: string;
  lastName: string;
  organizationName: string;
  website: string;
}

// Define our Auth0-specific user properties that might be available
interface ExtendedUser {
  given_name?: string;
  family_name?: string;
  name?: string | null;
  email?: string | null;
}

interface OrganizationDetailsStepProps {
  formData: FormData;
  updateFormData: (data: Partial<FormData>) => void;
  onNext: () => void;
}

export default function OrganizationDetailsStep({
  formData,
  updateFormData,
  onNext
}: OrganizationDetailsStepProps) {
  const { data: session, status: sessionStatus } = useSession();
  const [loading, setLoading] = useState(true);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);
  const [errors, setErrors] = useState({
    firstName: false,
    lastName: false,
    organizationName: false
  });

  // Prefill form with user data from session
  useEffect(() => {
    if (sessionStatus === 'loading') return;
    
    // Only attempt to prefill if the user session exists
    if (session?.user) {
      try {
        // Only prefill if form fields are empty (avoid overwriting user edits)
        if (!formData.firstName || !formData.lastName) {
          const data: Partial<FormData> = {};
          
          // Log the user object to check what fields are actually available
          console.log('Session user data:', session.user);
          
          // Access potential Auth0 properties
          const extendedUser = session.user as unknown as ExtendedUser;
          
          // First try to use given_name for firstName if available
          if (extendedUser.given_name && !formData.firstName) {
            data.firstName = extendedUser.given_name;
            console.log('Using given_name for firstName:', data.firstName);
          } 
          // Fall back to name parsing if given_name is not available
          else if (session.user.name && !formData.firstName) {
            const nameParts = session.user.name.split(' ');
            if (nameParts.length > 0) {
              data.firstName = nameParts[0];
              console.log('Using split name for firstName:', data.firstName);
            }
          }
          
          // First try to use family_name for lastName if available
          if (extendedUser.family_name && !formData.lastName) {
            data.lastName = extendedUser.family_name;
            console.log('Using family_name for lastName:', data.lastName);
          } 
          // Fall back to name parsing if family_name is not available
          else if (session.user.name && !formData.lastName) {
            const nameParts = session.user.name.split(' ');
            if (nameParts.length > 1) {
              data.lastName = nameParts.slice(1).join(' ');
              console.log('Using split name for lastName:', data.lastName);
            }
          }
          
          // Update form data with the user info
          if (Object.keys(data).length > 0) {
            updateFormData(data);
          }
        }
      } catch (error) {
        console.error('Error processing user session data:', error);
      }
    }
    
    // Always set loading to false when done
    setLoading(false);
  }, [session, sessionStatus, formData.firstName, formData.lastName, updateFormData]);

  const validateForm = () => {
    const newErrors = {
      firstName: !formData.firstName.trim(),
      lastName: !formData.lastName.trim(),
      organizationName: !formData.organizationName.trim()
    };
    
    setErrors(newErrors);
    return !Object.values(newErrors).some(Boolean);
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    
    if (!validateForm()) {
      return;
    }

    try {
      setIsSubmitting(true);
      
      // Store form data in sessionStorage without updating user profile
      // This allows other components to access the user's name information
      try {
        const userData = {
          firstName: formData.firstName,
          lastName: formData.lastName,
          fullName: `${formData.firstName} ${formData.lastName}`,
          organizationName: formData.organizationName,
          website: formData.website || ''
        };
        sessionStorage.setItem('onboardingUserData', JSON.stringify(userData));
      } catch (storageError) {
        console.error('Error storing user data in session storage:', storageError);
      }
      
      // Proceed to next step without updating user profile
      onNext();
    } catch (error) {
      console.error('Error during form submission:', error);
      setErrorMessage('Failed to submit form. Please try again.');
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const { name, value } = e.target;
    updateFormData({ [name]: value });
    
    // Clear error once the user types
    if (errors[name as keyof typeof errors]) {
      setErrors(prev => ({ ...prev, [name]: false }));
    }
  };

  const handleCloseSnackbar = () => {
    setErrorMessage(null);
    setSuccessMessage(null);
  };

  if (loading) {
    return (
      <Box display="flex" justifyContent="center" alignItems="center" minHeight="400px">
        <CircularProgress />
      </Box>
    );
  }

  return (
    <Box component="form" onSubmit={handleSubmit}>
      {/* Header Section */}
      <Box textAlign="center" mb={4}>
        <Typography variant="h5" component="h2" gutterBottom>
          Help us get to know you and your organization
        </Typography>
        <Typography variant="body1" color="text.secondary">
          We need these details to set up your workspace and personalize your experience.
        </Typography>
      </Box>

      {/* Form Fields */}
      <Stack spacing={3}>
        <TextField
          fullWidth
          label="First Name"
          name="firstName"
          value={formData.firstName}
          onChange={handleChange}
          required
          error={errors.firstName}
          helperText={errors.firstName ? 'First name is required' : ''}
          variant="outlined"
        />
        
        <TextField
          fullWidth
          label="Last Name"
          name="lastName"
          value={formData.lastName}
          onChange={handleChange}
          required
          error={errors.lastName}
          helperText={errors.lastName ? 'Last name is required' : ''}
          variant="outlined"
        />
        
        <TextField
          fullWidth
          label="Organization Name"
          name="organizationName"
          value={formData.organizationName}
          onChange={handleChange}
          required
          error={errors.organizationName}
          helperText={errors.organizationName ? 'Organization name is required' : ''}
          variant="outlined"
        />
        
        <TextField
          fullWidth
          label="Website URL (Optional)"
          name="website"
          value={formData.website}
          onChange={handleChange}
          placeholder="https://example.com"
          variant="outlined"
        />
      </Stack>

      {/* Action Buttons */}
      <Box display="flex" justifyContent="flex-end" mt={4}>
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