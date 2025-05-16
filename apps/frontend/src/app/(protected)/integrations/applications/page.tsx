'use client';

import { Box, Paper, Typography, Button, Grid } from '@mui/material';
import { 
  SiGithub, 
  SiGitlab, 
  SiBitbucket, 
  SiConfluence, 
  SiJira,
  SiSlack,
  SiDiscord,
  SiLinear,
  SiNotion 
} from "@icons-pack/react-simple-icons";
import TeamsIcon from '@mui/icons-material/Groups';
import { useState } from "react";

interface IntegrationService {
  id: string;
  name: string;
  description: string;
  icon: React.ReactNode;
  isConnected: boolean;
}

export default function IntegrationsPage() {
  const [integrations, setIntegrations] = useState<IntegrationService[]>([
    // Version Control
    {
      id: 'github',
      name: 'GitHub',
      description: 'Connect your GitHub repositories to sync issues and pull requests.',
      icon: <SiGithub className="h-8 w-8" />,
      isConnected: false,
    },
    {
      id: 'gitlab',
      name: 'GitLab',
      description: 'Integrate with GitLab for seamless project management.',
      icon: <SiGitlab className="h-8 w-8" />,
      isConnected: false,
    },
    {
      id: 'bitbucket',
      name: 'Bitbucket',
      description: 'Connect your Bitbucket repositories and track your projects.',
      icon: <SiBitbucket className="h-8 w-8" />,
      isConnected: false,
    },
    // Project Management
    {
      id: 'jira',
      name: 'Jira',
      description: 'Integrate with Jira for issue tracking and project management.',
      icon: <SiJira className="h-8 w-8" />,
      isConnected: false,
    },
    {
      id: 'linear',
      name: 'Linear',
      description: 'Connect with Linear for streamlined issue tracking and roadmap planning.',
      icon: <SiLinear className="h-8 w-8" />,
      isConnected: false,
    },
    // Documentation
    {
      id: 'confluence',
      name: 'Confluence',
      description: 'Connect to Confluence to sync documentation and knowledge base.',
      icon: <SiConfluence className="h-8 w-8" />,
      isConnected: false,
    },
    {
      id: 'notion',
      name: 'Notion',
      description: 'Integrate with Notion for documentation and knowledge management.',
      icon: <SiNotion className="h-8 w-8" />,
      isConnected: false,
    },
    // Communication
    {
      id: 'slack',
      name: 'Slack',
      description: 'Get notifications and test results directly in your Slack channels.',
      icon: <SiSlack className="h-8 w-8" />,
      isConnected: false,
    },
    {
      id: 'teams',
      name: 'Microsoft Teams',
      description: 'Receive updates and alerts in Microsoft Teams channels.',
      icon: <TeamsIcon sx={{ fontSize: 32 }} />,
      isConnected: false,
    },
    {
      id: 'discord',
      name: 'Discord',
      description: 'Get real-time notifications in your Discord servers.',
      icon: <SiDiscord className="h-8 w-8" />,
      isConnected: false,
    },
  ]);

  const handleConnect = async (serviceId: string) => {
    // TODO: Implement OAuth flow or API connection logic
    console.log(`Connecting to ${serviceId}`);
  };

  const handleDisconnect = async (serviceId: string) => {
    // TODO: Implement disconnect logic
    console.log(`Disconnecting from ${serviceId}`);
  };

  return (
    <Box sx={{ p: 3 }}>
      <Box sx={{ mb: 3 }}>
        <Typography variant="h4" sx={{ mb: 1 }}>Connect Your Tools</Typography>
        <Typography color="text.secondary">
          Enhance your workflow by integrating with your favorite services.
        </Typography>
      </Box>

      <Grid container spacing={3}>
        {integrations.map((integration) => (
          <Grid item xs={12} md={6} lg={4} key={integration.id}>
            <Paper sx={{ p: 3, height: '100%', display: 'flex', flexDirection: 'column' }}>
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 2, mb: 2 }}>
                {integration.icon}
                <Box>
                  <Typography variant="h6">{integration.name}</Typography>
                  <Typography color="text.secondary" variant="body2">
                    {integration.description}
                  </Typography>
                </Box>
              </Box>
              <Box sx={{ mt: 'auto' }}>
                <Button
                  fullWidth
                  variant="outlined"
                  color={integration.isConnected ? "error" : "primary"}
                  size="small"
                  onClick={() =>
                    integration.isConnected
                      ? handleDisconnect(integration.id)
                      : handleConnect(integration.id)
                  }
                  sx={{ 
                    textTransform: 'none',
                    borderRadius: 1.5
                  }}
                >
                  {integration.isConnected ? "Disconnect" : "Connect"}
                </Button>
              </Box>
            </Paper>
          </Grid>
        ))}
      </Grid>
    </Box>
  );
}
