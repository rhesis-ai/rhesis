import * as React from 'react';
import { Box, Paper, TextField, Button, Typography, Tabs, Tab } from '@mui/material';
import EditableTable from './EditableTable';

interface SystemStepProps {
  data: {
    name: string;
    description: string;
    primary_goals: string[];
    key_capabilities: string[];
  };
  onNext: () => void;
  onBack: () => void;
}

interface TabPanelProps {
  children?: React.ReactNode;
  index: number;
  value: number;
}

function TabPanel(props: TabPanelProps) {
  const { children, value, index, ...other } = props;
  return (
    <div
      role="tabpanel"
      hidden={value !== index}
      {...other}
    >
      {value === index && (
        <Box sx={{ pt: 3 }}>
          {children}
        </Box>
      )}
    </div>
  );
}

export default function SystemStep({ data, onNext, onBack }: SystemStepProps) {
  const [systemData, setSystemData] = React.useState({
    name: data?.name || '',
    description: data?.description || '',
  });

  const [goals, setGoals] = React.useState(
    data?.primary_goals.map((goal, index) => ({
      id: `goal-${index}`,
      description: goal,
    })) || []
  );

  const [capabilities, setCapabilities] = React.useState(
    data?.key_capabilities.map((capability, index) => ({
      id: `capability-${index}`,
      description: capability,
    })) || []
  );

  const [tabValue, setTabValue] = React.useState(0);

  const handleTabChange = (event: React.SyntheticEvent, newValue: number) => {
    setTabValue(newValue);
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    onNext();
  };

  return (
    <Box component="form" onSubmit={handleSubmit}>
      <Paper sx={{ p: 3, mb: 3 }}>
        <Tabs value={tabValue} onChange={handleTabChange}>
          <Tab label="Basic Information" />
          <Tab label="Goals & Capabilities" />
        </Tabs>

        <TabPanel value={tabValue} index={0}>
          <Typography variant="h6" gutterBottom>
            Basic Information
          </Typography>
          <TextField
            fullWidth
            label="System Name"
            value={systemData.name}
            onChange={(e) => setSystemData({ ...systemData, name: e.target.value })}
            margin="normal"
            required
          />
          <TextField
            fullWidth
            label="Description"
            value={systemData.description}
            onChange={(e) => setSystemData({ ...systemData, description: e.target.value })}
            margin="normal"
            multiline
            rows={4}
            required
          />
        </TabPanel>

        <TabPanel value={tabValue} index={1}>
          <Typography variant="h6" gutterBottom>
            Primary Goals
          </Typography>
          <EditableTable
            data={goals}
            columns={[{ id: 'description', label: 'Goal' }]}
            onUpdate={setGoals}
          />
          
          <Box sx={{ mt: 4 }}>
            <Typography variant="h6" gutterBottom>
              Key Capabilities
            </Typography>
            <EditableTable
              data={capabilities}
              columns={[{ id: 'description', label: 'Capability' }]}
              onUpdate={setCapabilities}
            />
          </Box>
        </TabPanel>
      </Paper>

      <Box sx={{ display: 'flex', justifyContent: 'space-between', mt: 2 }}>
        <Button onClick={onBack}>Back</Button>
        <Button type="submit" variant="contained">
          Next
        </Button>
      </Box>
    </Box>
  );
} 