import * as React from 'react';
import {
  Box,
  Button,
  Typography,
  Paper,
  List,
  ListItem,
  ListItemText,
  Divider,
  CircularProgress
} from '@mui/material';

interface FormData {
  firstName: string;
  lastName: string;
  organizationName: string;
  website: string;
  invites: { email: string }[];
}

type OnboardingStatus = 'idle' | 'creating_organization' | 'updating_user' | 'loading_initial_data';

interface FinishStepProps {
  formData: FormData;
  onComplete: () => void;
  onBack: () => void;
  isSubmitting?: boolean;
  onboardingStatus: OnboardingStatus;
}

export default function FinishStep({
  formData,
  onComplete,
  onBack,
  isSubmitting = false,
  onboardingStatus
}: FinishStepProps) {
  // Filter out empty email invites
  const validInvites = formData.invites.filter(invite => invite.email.trim() !== '');

  const getButtonText = () => {
    switch (onboardingStatus) {
      case 'creating_organization':
        return 'Creating organization...';
      case 'updating_user':
        return 'Updating user information...';
      case 'loading_initial_data':
        return 'Loading initial data...';
      default:
        return 'Complete';
    }
  };

  return (
    <Box sx={{ mt: 4 }}>
      <Box sx={{ textAlign: 'center', mb: 4 }}>

        <Typography variant="h6" gutterBottom sx={{ mt: 2 }}>
          You&apos;re almost done.
        </Typography>
        <Typography variant="body1" color="text.secondary">
          Please review your information below before completing setup
        </Typography>
      </Box>
      
      <Paper variant="outlined" sx={{ p: 3, mb: 4 }}>
        <Typography variant="subtitle1" gutterBottom fontWeight="bold">
          Your Information
        </Typography>
        
        <List disablePadding>
          <ListItem sx={{ py: 1 }}>
            <ListItemText 
              primary="Organization Name"
              secondary={formData.organizationName}
            />
          </ListItem>
          <Divider component="li" />
          <ListItem sx={{ py: 1 }}>
            <ListItemText 
              primary="Your Name"
              secondary={`${formData.firstName} ${formData.lastName}`}
            />
          </ListItem>
          {formData.website && (
            <>
              <Divider component="li" />
              <ListItem sx={{ py: 1 }}>
                <ListItemText 
                  primary="Website"
                  secondary={formData.website}
                />
              </ListItem>
            </>
          )}
        </List>
        
        {validInvites.length > 0 && (
          <>
            <Typography variant="subtitle1" gutterBottom fontWeight="bold" sx={{ mt: 3 }}>
              Team Members Invited
            </Typography>
            
            <List disablePadding>
              {validInvites.map((invite, index) => (
                <React.Fragment key={index}>
                  {index > 0 && <Divider component="li" />}
                  <ListItem sx={{ py: 1 }}>
                    <ListItemText primary={invite.email} />
                  </ListItem>
                </React.Fragment>
              ))}
            </List>
          </>
        )}
      </Paper>
      
      <Box sx={{ display: 'flex', justifyContent: 'space-between', mt: 4 }}>
        <Button 
          onClick={onBack}
          disabled={isSubmitting}
        >
          Back
        </Button>
        <Button 
          variant="contained"
          color="primary"
          onClick={onComplete}
          disabled={isSubmitting}
          startIcon={isSubmitting ? <CircularProgress size={20} color="inherit" /> : null}
        >
          {isSubmitting ? getButtonText() : 'Complete'}
        </Button>
      </Box>
    </Box>
  );
} 