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
  SelectChangeEvent,
  Paper,
  ToggleButton,
  ToggleButtonGroup,
} from '@mui/material';
import { Project } from '@/utils/api-client/interfaces/project';
import { User } from '@/utils/api-client/interfaces/user';
import { UsersClient } from '@/utils/api-client/users-client';
import PersonIcon from '@mui/icons-material/Person';
import BaseDrawer from '@/components/common/BaseDrawer';
import styles from '@/styles/ProjectEditDrawer.module.css';

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
    <Box className={styles.iconSelectorContainer}>
      <Typography
        variant="subtitle1"
        gutterBottom
        className={styles.iconSelectorTitle}
      >
        Project Icon
      </Typography>
      <Paper variant="outlined" className={styles.iconSelectorPaper}>
        <ToggleButtonGroup
          value={selectedIcon}
          exclusive
          onChange={(_, newIcon) => {
            if (newIcon) onChange(newIcon);
          }}
          aria-label="project icon"
          className={styles.toggleButtonGroup}
        >
          {PROJECT_ICONS.map(icon => {
            const IconComponent = icon.component;
            return (
              <ToggleButton
                key={icon.name}
                value={icon.name}
                aria-label={icon.label}
                className={styles.toggleButton}
              >
                <IconComponent fontSize="medium" />
                <Typography
                  variant="caption"
                  noWrap
                  className={styles.toggleButtonLabel}
                >
                  {icon.label}
                </Typography>
              </ToggleButton>
            );
          })}
        </ToggleButtonGroup>
      </Paper>
    </Box>
  );
};

interface ProjectEditDrawerProps {
  open: boolean;
  onClose: () => void;
  project: Project;
  onSave: (updatedProject: Partial<Project>) => Promise<void>;
  sessionToken: string;
}

export default function ProjectEditDrawer({
  open,
  onClose,
  project,
  onSave,
  sessionToken,
}: ProjectEditDrawerProps) {
  const [users, setUsers] = React.useState<User[]>([]);
  const [loading, setLoading] = React.useState(false);
  const [formData, setFormData] = React.useState({
    name: project.name,
    description: project.description || '',
    environment: project.environment,
    useCase: project.useCase,
    owner_id: project.owner?.id,
    tags: project.tags || [],
    icon: project.icon || 'SmartToy', // Default icon if not set
  });

  React.useEffect(() => {
    const fetchUsers = async () => {
      try {
        const usersClient = new UsersClient(sessionToken);
        const fetchedUsers = await usersClient.getUsers();
        setUsers(fetchedUsers.data);
      } catch (error) {}
    };

    if (open) {
      fetchUsers();
    }
  }, [open, sessionToken]);

  const handleTextChange =
    (field: string) =>
    (event: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) => {
      setFormData(prev => ({
        ...prev,
        [field]: event.target.value,
      }));
    };

  const handleSelectChange =
    (field: string) => (event: SelectChangeEvent<string>) => {
      setFormData(prev => ({
        ...prev,
        [field]: event.target.value,
      }));
    };

  const handleIconChange = (icon: string) => {
    setFormData(prev => ({
      ...prev,
      icon: icon,
    }));
  };

  const handleSaveWrapper = async () => {
    setLoading(true);
    try {
      // Create a clean update object with only the fields we want to update
      const projectUpdate: Partial<Project> = {};

      if (formData.name) {
        projectUpdate.name = formData.name;
      }

      if (formData.description !== undefined) {
        projectUpdate.description = formData.description;
      }

      // Always include owner_id if it's set (even if empty string to clear owner)
      if (formData.owner_id !== undefined) {
        projectUpdate.owner_id = formData.owner_id;
      }

      if (formData.environment) {
        projectUpdate.environment = formData.environment;
      }

      if (formData.useCase) {
        projectUpdate.useCase = formData.useCase;
      }

      if (formData.icon) {
        projectUpdate.icon = formData.icon;
      }

      if (formData.tags) {
        projectUpdate.tags = formData.tags;
      }

      await onSave(projectUpdate);
      onClose();
    } catch (error) {
    } finally {
      setLoading(false);
    }
  };

  return (
    <BaseDrawer
      open={open}
      onClose={onClose}
      title="Edit Project"
      loading={loading}
      onSave={handleSaveWrapper}
    >
      <FormControl fullWidth>
        <InputLabel>Owner</InputLabel>
        <Select
          value={formData.owner_id}
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
      </FormControl>

      <IconSelector selectedIcon={formData.icon} onChange={handleIconChange} />

      <TextField
        fullWidth
        label="Project Name"
        value={formData.name}
        onChange={handleTextChange('name')}
        required
      />

      <TextField
        fullWidth
        label="Description"
        multiline
        rows={4}
        value={formData.description}
        onChange={handleTextChange('description')}
      />

      <FormControl fullWidth>
        <InputLabel>Environment</InputLabel>
        <Select
          value={formData.environment}
          label="Environment"
          onChange={handleSelectChange('environment')}
        >
          <MenuItem value="development">Development</MenuItem>
          <MenuItem value="staging">Staging</MenuItem>
          <MenuItem value="production">Production</MenuItem>
        </Select>
      </FormControl>

      <FormControl fullWidth>
        <InputLabel>Use Case</InputLabel>
        <Select
          value={formData.useCase}
          label="Use Case"
          onChange={handleSelectChange('useCase')}
        >
          <MenuItem value="chatbot">Chatbot</MenuItem>
          <MenuItem value="assistant">Assistant</MenuItem>
          <MenuItem value="advisor">Advisor</MenuItem>
        </Select>
      </FormControl>

      <TextField
        fullWidth
        label="Tags"
        value={formData.tags.join(', ')}
        onChange={e => {
          const tags = e.target.value
            .split(',')
            .map(tag => tag.trim())
            .filter(Boolean);
          setFormData(prev => ({ ...prev, tags }));
        }}
        helperText="Separate tags with commas"
      />
    </BaseDrawer>
  );
}
