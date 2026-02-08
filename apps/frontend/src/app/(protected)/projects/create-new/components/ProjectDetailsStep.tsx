import * as React from 'react';
import {
  Box,
  TextField,
  Button,
  Typography,
  Grid,
  CircularProgress,
  Avatar,
  Paper,
  ToggleButton,
  ToggleButtonGroup,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  ListItemAvatar,
  ListItemText,
  SelectChangeEvent,
} from '@mui/material';
import { useState, useEffect } from 'react';
import Link from 'next/link';
import { User } from '@/utils/api-client/interfaces/user';
import { UsersClient } from '@/utils/api-client/users-client';
import PersonIcon from '@mui/icons-material/Person';
import styles from '@/styles/ProjectDetailsStep.module.css';

// Import icons for selection
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

// Standardized error messages
const ERROR_MESSAGES = {
  required: (field: string) => `${field} is required`,
};

// Standardized spacing values for consistent UI
const SPACING = {
  sectionTop: 3,
  betweenSections: 4,
  betweenFields: 2,
  buttonGap: 2,
};

// Type for form errors to ensure type safety
type FormErrors = Record<string, boolean>;

interface FormData {
  projectName: string;
  description: string;
  icon: string;
  owner_id?: string;
}

interface ProjectDetailsStepProps {
  formData: FormData;
  updateFormData: (data: Partial<FormData>) => void;
  onNext: () => void;
  userName: string;
  userImage: string;
  sessionToken: string;
  userId: string;
}

// Define available icons for selection
const PROJECT_ICONS = [
  { name: 'SmartToy', component: SmartToyIcon, label: 'AI Assistant' },
  { name: 'Psychology', component: PsychologyIcon, label: 'AI Brain' },
  { name: 'Chat', component: ChatIcon, label: 'Chatbot' },
  { name: 'Web', component: WebIcon, label: 'Web App' },
  { name: 'Devices', component: DevicesIcon, label: 'Multi-platform' },
  { name: 'Code', component: CodeIcon, label: 'Development' },
  { name: 'Terminal', component: TerminalIcon, label: 'CLI Tool' },
  { name: 'Storage', component: StorageIcon, label: 'Database' },
  { name: 'DataObject', component: DataObjectIcon, label: 'Data Model' },
  { name: 'Cloud', component: CloudIcon, label: 'Cloud Service' },
  { name: 'Analytics', component: AnalyticsIcon, label: 'Analytics' },
  { name: 'Dashboard', component: DashboardIcon, label: 'Dashboard' },
  { name: 'ShoppingCart', component: ShoppingCartIcon, label: 'E-commerce' },
  { name: 'VideogameAsset', component: VideogameAssetIcon, label: 'Game' },
  { name: 'Search', component: SearchIcon, label: 'Search Tool' },
  { name: 'AutoFixHigh', component: AutoFixHighIcon, label: 'Automation' },
  { name: 'PhoneIphone', component: PhoneIphoneIcon, label: 'Mobile App' },
  { name: 'School', component: SchoolIcon, label: 'Education' },
  { name: 'Science', component: ScienceIcon, label: 'Research' },
  { name: 'AccountTree', component: AccountTreeIcon, label: 'Workflow' },
];

// IconSelector component
const IconSelector = ({
  selectedIcon,
  onChange,
}: {
  selectedIcon: string;
  onChange: (icon: string) => void;
}) => {
  return (
    <FormControl fullWidth className={styles.iconSelector}>
      <InputLabel>Project Icon</InputLabel>
      <Select
        value={selectedIcon || 'SmartToy'}
        label="Project Icon"
        onChange={e => onChange(e.target.value)}
      >
        {PROJECT_ICONS.map(icon => {
          const IconComponent = icon.component;
          return (
            <MenuItem key={icon.name} value={icon.name}>
              <Box className={styles.iconOption}>
                <IconComponent fontSize="small" />
                <Typography>{icon.label}</Typography>
              </Box>
            </MenuItem>
          );
        })}
      </Select>
    </FormControl>
  );
};

export default function ProjectDetailsStep({
  formData,
  updateFormData,
  onNext,
  userName,
  userImage,
  sessionToken,
  userId,
}: ProjectDetailsStepProps) {
  const [loading, setLoading] = useState(false);
  const [users, setUsers] = useState<User[]>([]);
  const [loadingUsers, setLoadingUsers] = useState(false);
  const [errors, setErrors] = useState<FormErrors>({
    projectName: false,
    description: false,
    owner_id: false,
  });
  const [attemptedSubmit, setAttemptedSubmit] = useState(false);

  // Initialize formData.owner_id if not set
  useEffect(() => {
    if (!formData.owner_id) {
      updateFormData({ owner_id: userId });
    }
  }, [formData.owner_id, userId, updateFormData]);

  // Fetch users for the owner dropdown
  useEffect(() => {
    const fetchUsers = async () => {
      setLoadingUsers(true);
      try {
        const usersClient = new UsersClient(sessionToken);
        const fetchedUsers = await usersClient.getUsers();
        setUsers(fetchedUsers.data);
      } catch (_error) {
      } finally {
        setLoadingUsers(false);
      }
    };

    fetchUsers();
  }, [sessionToken]);

  const validateForm = () => {
    const newErrors: FormErrors = {
      projectName: !formData.projectName,
      description: !formData.description,
      owner_id: !formData.owner_id,
    };

    setErrors(newErrors);
    return !Object.values(newErrors).some(Boolean);
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setAttemptedSubmit(true);

    if (validateForm()) {
      try {
        setLoading(true);
        // Proceed to next step
        onNext();
      } catch (_error) {
      } finally {
        setLoading(false);
      }
    }
  };

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const { name, value } = e.target;
    updateFormData({ [name]: value });

    // Only clear errors after attempted submit
    if (attemptedSubmit && errors[name]) {
      setErrors(prev => ({ ...prev, [name]: false }));
    }
  };

  const handleSelectChange = (event: SelectChangeEvent<string>) => {
    updateFormData({ owner_id: event.target.value });

    // Clear error when user selects
    if (attemptedSubmit && errors.owner_id) {
      setErrors(prev => ({ ...prev, owner_id: false }));
    }
  };

  const handleIconChange = (icon: string) => {
    updateFormData({ icon: icon });
  };

  if (loading) {
    return (
      <Box
        sx={{
          display: 'flex',
          justifyContent: 'center',
          alignItems: 'center',
          minHeight: '200px',
        }}
      >
        <CircularProgress />
      </Box>
    );
  }

  return (
    <Box
      component="form"
      onSubmit={handleSubmit}
      sx={{ mt: SPACING.sectionTop, width: '100%' }}
    >
      <Typography variant="h6" gutterBottom align="center">
        Enter Project Details
      </Typography>
      <Typography
        variant="body1"
        color="text.secondary"
        align="center"
        sx={{ mb: SPACING.betweenFields * 2 }}
      >
        Please provide basic information about this project
      </Typography>
      <Grid container spacing={SPACING.betweenFields} sx={{ width: '100%' }}>
        {/* Owner Dropdown */}
        <Grid size={12}>
          <FormControl fullWidth error={errors.owner_id && attemptedSubmit}>
            <InputLabel>Owner</InputLabel>
            <Select
              value={formData.owner_id || ''}
              label="Owner"
              onChange={handleSelectChange}
              disabled={loadingUsers}
              renderValue={selected => {
                const selectedUser = users.find(u => u.id === selected);
                return selectedUser ? (
                  <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                    <Avatar
                      src={selectedUser.picture}
                      alt={selectedUser.name || selectedUser.email}
                      sx={{ width: 24, height: 24 }}
                    >
                      <PersonIcon />
                    </Avatar>
                    <Typography>
                      {selectedUser.name || selectedUser.email}
                    </Typography>
                  </Box>
                ) : loadingUsers ? (
                  <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                    <CircularProgress size={20} />
                    <Typography>Loading users...</Typography>
                  </Box>
                ) : null;
              }}
            >
              {users.map(user => (
                <MenuItem key={user.id} value={user.id}>
                  <ListItemAvatar>
                    <Avatar
                      src={user.picture}
                      alt={user.name || user.email}
                      sx={{ width: 32, height: 32 }}
                    >
                      <PersonIcon />
                    </Avatar>
                  </ListItemAvatar>
                  <ListItemText
                    primary={user.name || user.email}
                    secondary={user.email}
                  />
                </MenuItem>
              ))}
            </Select>
            {errors.owner_id && attemptedSubmit && (
              <Typography color="error" variant="caption">
                {ERROR_MESSAGES.required('Owner')}
              </Typography>
            )}
          </FormControl>
        </Grid>

        {/* Icon Selector */}
        <Grid size={12}>
          <IconSelector
            selectedIcon={formData.icon}
            onChange={handleIconChange}
          />
        </Grid>

        <Grid size={12}>
          <TextField
            fullWidth
            label="Project Name"
            name="projectName"
            value={formData.projectName}
            onChange={handleChange}
            required
            error={attemptedSubmit && errors.projectName}
            helperText={
              attemptedSubmit && errors.projectName
                ? ERROR_MESSAGES.required('Project name')
                : ''
            }
          />
        </Grid>

        <Grid size={12}>
          <TextField
            fullWidth
            label="Description"
            name="description"
            value={formData.description}
            onChange={handleChange}
            required
            multiline
            rows={4}
            error={attemptedSubmit && errors.description}
            helperText={
              attemptedSubmit && errors.description
                ? ERROR_MESSAGES.required('Description')
                : ''
            }
          />
        </Grid>
      </Grid>
      <Box
        sx={{
          display: 'flex',
          justifyContent: 'space-between',
          mt: SPACING.betweenSections,
          width: '100%',
        }}
      >
        <Button
          variant="outlined"
          color="inherit"
          component={Link}
          href="/projects"
        >
          Cancel
        </Button>
        <Button
          type="submit"
          variant="contained"
          color="primary"
          disabled={loading || loadingUsers}
        >
          Continue
        </Button>
      </Box>
    </Box>
  );
}
