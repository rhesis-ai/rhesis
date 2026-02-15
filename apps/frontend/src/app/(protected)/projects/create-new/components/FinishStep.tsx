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
  Avatar,
  ListItemIcon,
} from '@mui/material';
import { User } from '@/utils/api-client/interfaces/user';
import { useState, useEffect } from 'react';
import { UsersClient } from '@/utils/api-client/users-client';
import PersonIcon from '@mui/icons-material/Person';

// Import all MUI icons for dynamic rendering
import SmartToyIcon from '@mui/icons-material/SmartToy';
import DevicesIcon from '@mui/icons-material/Devices';
import WebIcon from '@mui/icons-material/Web';
import StorageIcon from '@mui/icons-material/Storage';
import CodeIcon from '@mui/icons-material/Code';
import DataObjectIcon from '@mui/icons-material/DataObject';
import CloudIcon from '@mui/icons-material/Cloud';
import AnalyticsIcon from '@mui/icons-material/Analytics';
import ShoppingCartIcon from '@mui/icons-material/ShoppingCart';
import TerminalIcon from '@mui/icons-material/Terminal';
import VideogameAssetIcon from '@mui/icons-material/VideogameAsset';
import ChatIcon from '@mui/icons-material/Chat';
import PsychologyIcon from '@mui/icons-material/Psychology';
import DashboardIcon from '@mui/icons-material/Dashboard';
import SearchIcon from '@mui/icons-material/Search';
import AutoFixHighIcon from '@mui/icons-material/AutoFixHigh';
import PhoneIphoneIcon from '@mui/icons-material/PhoneIphone';
import SchoolIcon from '@mui/icons-material/School';
import ScienceIcon from '@mui/icons-material/Science';
import AccountTreeIcon from '@mui/icons-material/AccountTree';

// Define available icons for selection
const PROJECT_ICONS = {
  SmartToy: SmartToyIcon,
  Psychology: PsychologyIcon,
  Chat: ChatIcon,
  Web: WebIcon,
  Devices: DevicesIcon,
  Code: CodeIcon,
  Terminal: TerminalIcon,
  Storage: StorageIcon,
  DataObject: DataObjectIcon,
  Cloud: CloudIcon,
  Analytics: AnalyticsIcon,
  Dashboard: DashboardIcon,
  ShoppingCart: ShoppingCartIcon,
  VideogameAsset: VideogameAssetIcon,
  Search: SearchIcon,
  AutoFixHigh: AutoFixHighIcon,
  PhoneIphone: PhoneIphoneIcon,
  School: SchoolIcon,
  Science: ScienceIcon,
  AccountTree: AccountTreeIcon,
};

// Map of icon names to labels
const _ICON_LABELS = {
  SmartToy: 'AI Assistant',
  Psychology: 'AI Brain',
  Chat: 'Chatbot',
  Web: 'Web App',
  Devices: 'Multi-platform',
  Code: 'Development',
  Terminal: 'CLI Tool',
  Storage: 'Database',
  DataObject: 'Data Model',
  Cloud: 'Cloud Service',
  Analytics: 'Analytics',
  Dashboard: 'Dashboard',
  ShoppingCart: 'E-commerce',
  VideogameAsset: 'Game',
  Search: 'Search Tool',
  AutoFixHigh: 'Automation',
  PhoneIphone: 'Mobile App',
  School: 'Education',
  Science: 'Research',
  AccountTree: 'Workflow',
};

interface FormData {
  projectName: string;
  description: string;
  icon: string;
  owner_id?: string;
}

interface FinishStepProps {
  formData: FormData;
  onComplete: () => void;
  onBack: () => void;
  isSubmitting?: boolean;
  sessionToken: string;
}

export default function FinishStep({
  formData,
  onComplete,
  onBack,
  isSubmitting = false,
  sessionToken,
}: FinishStepProps) {
  const [owner, setOwner] = useState<User | null>(null);
  const [loadingOwner, setLoadingOwner] = useState(false);

  // Fetch owner details if we have an owner_id
  useEffect(() => {
    if (!formData.owner_id || !sessionToken) return;

    const fetchOwner = async () => {
      setLoadingOwner(true);
      try {
        const usersClient = new UsersClient(sessionToken);
        if (formData.owner_id) {
          const ownerData = await usersClient.getUser(formData.owner_id);
          setOwner(ownerData);
        }
      } catch (_error) {
        // Fall back to a placeholder if the API call fails
        if (formData.owner_id) {
          setOwner({
            id: formData.owner_id as `${string}-${string}-${string}-${string}-${string}`,
            name: 'Unknown User',
            email: 'unknown@example.com',
            picture: '',
          });
        }
      } finally {
        setLoadingOwner(false);
      }
    };

    fetchOwner();
  }, [formData.owner_id, sessionToken]);

  // Get the icon component with better error handling
  const getIconComponent = () => {
    // Make sure the icon name exists in our icons mapping
    if (
      formData.icon &&
      PROJECT_ICONS[formData.icon as keyof typeof PROJECT_ICONS]
    ) {
      return PROJECT_ICONS[formData.icon as keyof typeof PROJECT_ICONS];
    }
    // Fallback to default icon if the selected one doesn't exist
    return SmartToyIcon;
  };

  const IconComponent = getIconComponent();

  return (
    <Box sx={{ mt: 3 }}>
      <Box sx={{ textAlign: 'center', mb: 4 }}>
        <Typography variant="h6" gutterBottom>
          Almost done!
        </Typography>
        <Typography variant="body1" color="text.secondary">
          Please review your project information before completing
        </Typography>
      </Box>

      <Paper variant="outlined" sx={{ p: 3, mb: 4 }}>
        <Typography variant="subtitle1" gutterBottom fontWeight="bold">
          Project Information
        </Typography>

        <List disablePadding>
          <ListItem sx={{ py: 1 }}>
            {loadingOwner ? (
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                <CircularProgress size={20} />
                <Typography>Loading owner details...</Typography>
              </Box>
            ) : owner ? (
              <>
                <ListItemIcon>
                  <Avatar
                    src={owner.picture}
                    alt={owner.name || owner.email}
                    sx={{ width: 32, height: 32 }}
                  >
                    <PersonIcon />
                  </Avatar>
                </ListItemIcon>
                <ListItemText
                  primary="Owner"
                  secondary={owner.name || owner.email}
                />
              </>
            ) : (
              <ListItemText primary="Owner" secondary="Not specified" />
            )}
          </ListItem>
          <Divider component="li" />

          <ListItem sx={{ py: 1 }}>
            <ListItemIcon>
              <IconComponent aria-hidden="true" />
            </ListItemIcon>
            <ListItemText primary="Project Icon" />
          </ListItem>
          <Divider component="li" />

          <ListItem sx={{ py: 1 }}>
            <ListItemText
              primary="Project Name"
              secondary={formData.projectName}
            />
          </ListItem>
          <Divider component="li" />

          <ListItem sx={{ py: 1 }}>
            <ListItemText
              primary="Description"
              secondary={formData.description}
            />
          </ListItem>
        </List>
      </Paper>

      <Box sx={{ display: 'flex', justifyContent: 'space-between', mt: 4 }}>
        <Button onClick={onBack} disabled={isSubmitting} variant="outlined">
          Back
        </Button>
        <Button
          variant="contained"
          color="primary"
          onClick={onComplete}
          disabled={isSubmitting}
          startIcon={
            isSubmitting ? <CircularProgress size={20} color="inherit" /> : null
          }
        >
          {isSubmitting ? 'Creating Project...' : 'Create Project'}
        </Button>
      </Box>
    </Box>
  );
}
