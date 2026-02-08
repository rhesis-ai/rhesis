'use client';

import * as React from 'react';
import {
  TextField,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  Avatar,
  ListItemAvatar,
  ListItemText,
  Box,
  Typography,
  Stack,
  SelectChangeEvent,
  FormHelperText,
  FormControlLabel,
  Switch,
  ToggleButton,
  ToggleButtonGroup,
  Paper,
} from '@mui/material';
import { Project } from '@/utils/api-client/interfaces/project';
import { User } from '@/utils/api-client/interfaces/user';
import { UsersClient } from '@/utils/api-client/users-client';
import PersonIcon from '@mui/icons-material/Person';
import BaseDrawer from '@/components/common/BaseDrawer';

// Import all the available project icons
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

// IconSelector component for drawer
const IconSelector = ({
  selectedIcon,
  onChange,
  error,
}: {
  selectedIcon: string;
  onChange: (icon: string) => void;
  error?: string;
}) => {
  return (
    <FormControl fullWidth sx={{ mt: 2, mb: 2 }} error={!!error}>
      <InputLabel id="project-icon-label">Project Icon</InputLabel>
      <Select
        labelId="project-icon-label"
        value={selectedIcon || 'SmartToy'}
        label="Project Icon"
        onChange={e => onChange(e.target.value)}
        aria-describedby={error ? 'project-icon-error' : undefined}
      >
        {PROJECT_ICONS.map(icon => {
          const IconComponent = icon.component;
          return (
            <MenuItem key={icon.name} value={icon.name}>
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                <IconComponent fontSize="small" aria-hidden="true" />
                <Typography>{icon.label}</Typography>
              </Box>
            </MenuItem>
          );
        })}
      </Select>
      {error && (
        <FormHelperText id="project-icon-error">{error}</FormHelperText>
      )}
    </FormControl>
  );
};

interface EditDrawerProps {
  open: boolean;
  onClose: () => void;
  project: Project;
  onSave: (updatedProject: Partial<Project>) => Promise<void>;
  sessionToken: string;
}

interface FormErrors {
  name?: string;
  description?: string;
  owner_id?: string;
  is_active?: string;
  icon?: string;
  form?: string;
}

export default function EditDrawer({
  open,
  onClose,
  project,
  onSave,
  sessionToken,
}: EditDrawerProps) {
  const [users, setUsers] = React.useState<User[]>([]);
  const [loading, setLoading] = React.useState(false);
  const [errors, setErrors] = React.useState<FormErrors>({});
  const [formData, setFormData] = React.useState({
    name: project.name,
    description: project.description || '',
    owner_id: project.owner?.id || project.owner_id, // Fallback to owner_id field
    is_active: project.is_active,
    icon: project.icon || 'SmartToy',
  });

  // Reset form data when project changes
  React.useEffect(() => {
    if (open) {
      setFormData({
        name: project.name,
        description: project.description || '',
        owner_id: project.owner?.id || project.owner_id, // Fallback to owner_id field
        is_active: project.is_active,
        icon: project.icon || 'SmartToy',
      });
      setErrors({});
    }
  }, [project, open]);

  // Fetch users only when drawer opens
  React.useEffect(() => {
    let isMounted = true;

    const fetchUsers = async () => {
      try {
        const usersClient = new UsersClient(sessionToken);
        const fetchedUsers = await usersClient.getUsers();
        if (isMounted) {
          setUsers(fetchedUsers.data);
        }
      } catch (_error) {}
    };

    if (open) {
      fetchUsers();
    }

    return () => {
      isMounted = false;
    };
  }, [open, sessionToken]);

  // Memoize event handlers
  const handleTextChange = React.useCallback(
    (field: string) =>
      (event: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) => {
        setFormData(prev => ({
          ...prev,
          [field]: event.target.value,
        }));
        // Clear error when user types
        if (errors[field as keyof FormErrors]) {
          setErrors(prev => ({
            ...prev,
            [field]: undefined,
          }));
        }
      },
    [errors]
  );

  const handleSelectChange = React.useCallback(
    (field: string) => (event: SelectChangeEvent<string>) => {
      setFormData(prev => ({
        ...prev,
        [field]: event.target.value,
      }));
      // Clear error when user selects
      if (errors[field as keyof FormErrors]) {
        setErrors(prev => ({
          ...prev,
          [field]: undefined,
        }));
      }
    },
    [errors]
  );

  const handleToggleChange = React.useCallback(
    (event: React.ChangeEvent<HTMLInputElement>) => {
      setFormData(prev => ({
        ...prev,
        is_active: event.target.checked,
      }));
      // Clear error when user selects
      if (errors.is_active) {
        setErrors(prev => ({
          ...prev,
          is_active: undefined,
        }));
      }
    },
    [errors]
  );

  const handleIconChange = React.useCallback((icon: string) => {
    setFormData(prev => ({
      ...prev,
      icon: icon,
    }));
  }, []);

  // Validate form before submission
  const validateForm = React.useCallback(() => {
    const newErrors: FormErrors = {};

    if (!formData.name?.trim()) {
      newErrors.name = 'Project name is required';
    } else if (formData.name.length > 100) {
      newErrors.name = 'Project name must be less than 100 characters';
    }

    if (formData.description && formData.description.length > 500) {
      newErrors.description = 'Description must be less than 500 characters';
    }

    if (!formData.owner_id || formData.owner_id.trim() === '') {
      newErrors.owner_id = 'Owner is required';
    }

    if (!formData.icon) {
      newErrors.icon = 'Project icon is required';
    }

    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  }, [formData]);

  const handleSaveWrapper = React.useCallback(async () => {
    if (!validateForm()) {
      return;
    }

    setLoading(true);
    try {
      // Create a clean update object with only explicitly set fields
      const projectUpdate: Partial<Project> = {};

      if (formData.name) {
        projectUpdate.name = formData.name;
      }

      if (formData.description !== undefined) {
        projectUpdate.description = formData.description;
      }

      if (formData.owner_id !== undefined) {
        projectUpdate.owner_id = formData.owner_id;
      }

      if (formData.is_active !== undefined) {
        projectUpdate.is_active = formData.is_active;
      }

      if (formData.icon) {
        projectUpdate.icon = formData.icon;
      }

      await onSave(projectUpdate);
      onClose();
    } catch (error) {
      // Show generic error if backend doesn't provide specific ones
      setErrors(prev => ({
        ...prev,
        form: 'Failed to save. Please try again.',
      }));
    } finally {
      setLoading(false);
    }
  }, [formData, validateForm, onSave, onClose]);

  // Memoize select rendering for performance
  const renderUserSelect = React.useMemo(
    () => (
      <FormControl fullWidth error={!!errors.owner_id}>
        <InputLabel>Owner</InputLabel>
        <Select
          value={formData.owner_id || ''}
          label="Owner"
          onChange={handleSelectChange('owner_id')}
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
        {errors.owner_id && <FormHelperText>{errors.owner_id}</FormHelperText>}
      </FormControl>
    ),
    [users, formData.owner_id, errors.owner_id, handleSelectChange]
  );

  return (
    <BaseDrawer
      open={open}
      onClose={onClose}
      title="Edit Project"
      loading={loading}
      onSave={handleSaveWrapper}
      error={errors.form}
    >
      <Stack spacing={3}>
        {renderUserSelect}

        <IconSelector
          selectedIcon={formData.icon}
          onChange={handleIconChange}
          error={errors.icon}
        />

        <TextField
          label="Project Name"
          value={formData.name}
          onChange={handleTextChange('name')}
          error={!!errors.name}
          helperText={errors.name}
          fullWidth
          required
        />

        <TextField
          label="Description"
          value={formData.description}
          onChange={handleTextChange('description')}
          error={!!errors.description}
          helperText={errors.description}
          fullWidth
          multiline
          rows={4}
        />

        <FormControlLabel
          control={
            <Switch
              checked={!!formData.is_active}
              onChange={handleToggleChange}
              color="primary"
            />
          }
          label="Active Project"
        />
      </Stack>
    </BaseDrawer>
  );
}
