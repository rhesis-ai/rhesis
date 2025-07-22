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
  CircularProgress,
  Stack
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
    <Box>
      {/* Header Section */}
      <Box textAlign="center" mb={4}>
        <Typography variant="h5" component="h2" gutterBottom>
          You&apos;re almost done!
        </Typography>
        <Typography variant="body1" color="text.secondary">
          Please review your information below before completing setup
        </Typography>
      </Box>
      
      {/* Review Section */}
      <Stack spacing={3} mb={4}>
        <Paper variant="outlined" elevation={0}>
          <Box p={3}>
            <Typography variant="h6" gutterBottom color="primary">
              Your Information
            </Typography>
            
            <List disablePadding>
              <ListItem>
                <ListItemText 
                  primary={
                    <Typography variant="subtitle2">
                      Organization Name
                    </Typography>
                  }
                  secondary={
                    <Typography variant="body1" color="text.primary">
                      {formData.organizationName}
                    </Typography>
                  }
                />
              </ListItem>
              
              <Divider component="li" />
              
              <ListItem>
                <ListItemText 
                  primary={
                    <Typography variant="subtitle2">
                      Your Name
                    </Typography>
                  }
                  secondary={
                    <Typography variant="body1" color="text.primary">
                      {`${formData.firstName} ${formData.lastName}`}
                    </Typography>
                  }
                />
              </ListItem>
              
              {formData.website && (
                <>
                  <Divider component="li" />
                  <ListItem>
                    <ListItemText 
                      primary={
                        <Typography variant="subtitle2">
                          Website
                        </Typography>
                      }
                      secondary={
                        <Typography variant="body1" color="text.primary">
                          {formData.website}
                        </Typography>
                      }
                    />
                  </ListItem>
                </>
              )}
            </List>
          </Box>
        </Paper>
        
        {validInvites.length > 0 && (
          <Paper variant="outlined" elevation={0}>
            <Box p={3}>
              <Typography variant="h6" gutterBottom color="primary">
                Team Members Invited ({validInvites.length})
              </Typography>
              
              <List disablePadding>
                {validInvites.map((invite, index) => (
                  <React.Fragment key={index}>
                    {index > 0 && <Divider component="li" />}
                    <ListItem>
                      <ListItemText 
                        primary={
                          <Typography variant="body1" color="text.primary">
                            {invite.email}
                          </Typography>
                        }
                      />
                    </ListItem>
                  </React.Fragment>
                ))}
              </List>
            </Box>
          </Paper>
        )}
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
          variant="contained"
          color="primary"
          onClick={onComplete}
          disabled={isSubmitting}
          startIcon={isSubmitting ? <CircularProgress size={20} color="inherit" /> : null}
          size="large"
        >
          {isSubmitting ? getButtonText() : 'Complete Setup'}
        </Button>
      </Box>
    </Box>
  );
} 