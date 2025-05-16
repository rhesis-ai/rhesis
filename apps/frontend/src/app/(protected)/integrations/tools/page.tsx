'use client';

import { Box, Paper, Typography, Button, Grid } from '@mui/material';
import { 
  SiDatadog,
  SiNewrelic,
  SiGrafana,
  SiElasticsearch,
  SiPrometheus,
  SiSplunk,
  SiSentry,
  SiMixpanel
} from "@icons-pack/react-simple-icons";
import BarChartIcon from '@mui/icons-material/BarChart';
import { useState } from "react";

interface ToolService {
  id: string;
  name: string;
  description: string;
  icon: React.ReactNode;
  isConnected: boolean;
  category: string;
}

export default function ToolsPage() {
  const [tools, setTools] = useState<ToolService[]>([
    // Logging & Monitoring
    {
      id: 'datadog',
      name: 'Datadog',
      description: 'Monitor your application performance and logs in real-time.',
      icon: <SiDatadog className="h-8 w-8" />,
      isConnected: false,
      category: 'Monitoring'
    },
    {
      id: 'newrelic',
      name: 'New Relic',
      description: 'Full-stack observability platform for your applications.',
      icon: <SiNewrelic className="h-8 w-8" />,
      isConnected: false,
      category: 'Monitoring'
    },
    {
      id: 'grafana',
      name: 'Grafana',
      description: 'Visualize metrics and logs with customizable dashboards.',
      icon: <SiGrafana className="h-8 w-8" />,
      isConnected: false,
      category: 'Monitoring'
    },
    // Logging
    {
      id: 'elasticsearch',
      name: 'Elasticsearch',
      description: 'Search, analyze, and visualize your log data at scale.',
      icon: <SiElasticsearch className="h-8 w-8" />,
      isConnected: false,
      category: 'Logging'
    },
    {
      id: 'prometheus',
      name: 'Prometheus',
      description: 'Monitor metrics and generate alerts for your systems.',
      icon: <SiPrometheus className="h-8 w-8" />,
      isConnected: false,
      category: 'Monitoring'
    },
    {
      id: 'splunk',
      name: 'Splunk',
      description: 'Analyze and visualize machine-generated data.',
      icon: <SiSplunk className="h-8 w-8" />,
      isConnected: false,
      category: 'Logging'
    },
    // Error Tracking
    {
      id: 'sentry',
      name: 'Sentry',
      description: 'Track and fix errors in real-time.',
      icon: <SiSentry className="h-8 w-8" />,
      isConnected: false,
      category: 'Error Tracking'
    },
    // Analytics
    {
      id: 'mixpanel',
      name: 'Mixpanel',
      description: 'Advanced analytics for user behavior tracking.',
      icon: <SiMixpanel className="h-8 w-8" />,
      isConnected: false,
      category: 'Analytics'
    },
    {
      id: 'segment',
      name: 'Segment',
      description: 'Collect and route your analytics data.',
      icon: <BarChartIcon sx={{ fontSize: 32 }} />,
      isConnected: false,
      category: 'Analytics'
    },
  ]);

  const handleConnect = async (serviceId: string) => {
    // TODO: Implement connection logic
    console.log(`Connecting to ${serviceId}`);
  };

  const handleDisconnect = async (serviceId: string) => {
    // TODO: Implement disconnect logic
    console.log(`Disconnecting from ${serviceId}`);
  };

  return (
    <Box sx={{ p: 3 }}>
      <Box sx={{ mb: 3 }}>
        <Typography variant="h4" sx={{ mb: 1 }}>Development Tools</Typography>
        <Typography color="text.secondary">
          Connect your monitoring, logging, and analytics tools to enhance your development workflow.
        </Typography>
      </Box>

      <Grid container spacing={3}>
        {tools.map((tool) => (
          <Grid item xs={12} md={6} lg={4} key={tool.id}>
            <Paper sx={{ p: 3, height: '100%', display: 'flex', flexDirection: 'column' }}>
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 2, mb: 2 }}>
                {tool.icon}
                <Box>
                  <Typography variant="h6">{tool.name}</Typography>
                  <Typography color="text.secondary" variant="body2">
                    {tool.description}
                  </Typography>
                </Box>
              </Box>
              <Box sx={{ mt: 'auto' }}>
                <Button
                  fullWidth
                  variant="outlined"
                  color={tool.isConnected ? "error" : "primary"}
                  size="small"
                  onClick={() =>
                    tool.isConnected
                      ? handleDisconnect(tool.id)
                      : handleConnect(tool.id)
                  }
                  sx={{ 
                    textTransform: 'none',
                    borderRadius: 1.5
                  }}
                >
                  {tool.isConnected ? "Disconnect" : "Connect"}
                </Button>
              </Box>
            </Paper>
          </Grid>
        ))}
      </Grid>
    </Box>
  );
} 