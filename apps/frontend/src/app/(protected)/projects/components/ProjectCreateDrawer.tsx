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
  SelectChangeEvent,
} from '@mui/material';
import PersonIcon from '@mui/icons-material/Person';
import BaseDrawer from '@/components/common/BaseDrawer';
import { User } from '@/utils/api-client/interfaces/user';
import { UsersClient } from '@/utils/api-client/users-client';
import { ProjectCreate } from '@/utils/api-client/interfaces/project';

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

const PROJECT_ICONS: {
  name: string;
  component: React.ComponentType;
  label: string;
}[] = [
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

interface ProjectCreateDrawerProps {
  open: boolean;
  onClose: () => void;
  onCreate: (project: ProjectCreate) => Promise<void>;
  sessionToken: string;
}

const EMPTY_FORM = {
  name: '',
  description: '',
  owner_id: '',
  icon: 'SmartToy',
};

export default function ProjectCreateDrawer({
  open,
  onClose,
  onCreate,
  sessionToken,
}: ProjectCreateDrawerProps) {
  const [users, setUsers] = React.useState<User[]>([]);
  const [loading, setLoading] = React.useState(false);
  const [error, setError] = React.useState('');
  const [formData, setFormData] = React.useState(EMPTY_FORM);

  React.useEffect(() => {
    if (!open) return;
    setFormData(EMPTY_FORM);
    setError('');
    const fetchUsers = async () => {
      try {
        const client = new UsersClient(sessionToken);
        const result = await client.getUsers();
        setUsers(result.data);
      } catch (error) {
        console.error(
          'Failed to fetch users for project create drawer:',
          error
        );
      }
    };
    fetchUsers();
  }, [open, sessionToken]);

  const handleText =
    (field: string) =>
    (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) =>
      setFormData(prev => ({ ...prev, [field]: e.target.value }));

  const handleSelect = (field: string) => (e: SelectChangeEvent<string>) =>
    setFormData(prev => ({ ...prev, [field]: e.target.value }));

  const handleSave = async () => {
    if (!formData.name.trim()) {
      setError('Project name is required');
      return;
    }
    setLoading(true);
    setError('');
    try {
      const payload: ProjectCreate = {
        name: formData.name.trim(),
        ...(formData.description && { description: formData.description }),
        ...(formData.owner_id && { owner_id: formData.owner_id }),
        ...(formData.icon && { icon: formData.icon }),
      };
      await onCreate(payload);
      onClose();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to create project');
    } finally {
      setLoading(false);
    }
  };

  return (
    <BaseDrawer
      open={open}
      onClose={onClose}
      title="Create project"
      loading={loading}
      onSave={handleSave}
      saveButtonText="Save"
      error={error}
    >
      {/* 2-column row: Owner | Project Icon */}
      <Box
        sx={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '30px' }}
      >
        <FormControl variant="outlined" fullWidth>
          <InputLabel>Owner</InputLabel>
          <Select
            value={formData.owner_id}
            label="Owner"
            onChange={handleSelect('owner_id')}
            renderValue={selected => {
              const u = users.find(x => x.id === selected);
              return u ? (
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                  <Avatar src={u.picture} sx={{ width: 24, height: 24 }}>
                    <PersonIcon />
                  </Avatar>
                  {u.name || u.email}
                </Box>
              ) : null;
            }}
          >
            <MenuItem value="">
              <em>No owner</em>
            </MenuItem>
            {users.map(u => (
              <MenuItem key={u.id} value={u.id}>
                <ListItemAvatar>
                  <Avatar src={u.picture} sx={{ width: 32, height: 32 }}>
                    <PersonIcon />
                  </Avatar>
                </ListItemAvatar>
                <ListItemText primary={u.name || u.email} secondary={u.email} />
              </MenuItem>
            ))}
          </Select>
        </FormControl>

        <FormControl variant="outlined" fullWidth>
          <InputLabel>Project Icon</InputLabel>
          <Select
            value={formData.icon}
            label="Project Icon"
            onChange={handleSelect('icon')}
            renderValue={selected => {
              const entry = PROJECT_ICONS.find(i => i.name === selected);
              if (!entry) return null;
              const Icon = entry.component as React.ElementType;
              return (
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                  <Icon fontSize="small" />
                  {entry.label}
                </Box>
              );
            }}
          >
            {PROJECT_ICONS.map(({ name, component: Icon, label }) => {
              const IconEl = Icon as React.ElementType;
              return (
                <MenuItem key={name} value={name}>
                  <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                    <IconEl fontSize="small" />
                    {label}
                  </Box>
                </MenuItem>
              );
            })}
          </Select>
        </FormControl>
      </Box>

      {/* Full-width: Project Name */}
      <TextField
        fullWidth
        variant="outlined"
        label="Project Name*"
        value={formData.name}
        onChange={handleText('name')}
        autoFocus
      />

      {/* Full-width: Description */}
      <TextField
        fullWidth
        variant="outlined"
        label="Description*"
        multiline
        rows={4}
        value={formData.description}
        onChange={handleText('description')}
      />
    </BaseDrawer>
  );
}
