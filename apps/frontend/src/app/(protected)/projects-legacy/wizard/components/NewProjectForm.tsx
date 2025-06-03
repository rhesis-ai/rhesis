'use client';

import * as React from 'react';
import { Box, Stepper, Step, StepLabel, Paper, Typography, Breadcrumbs } from '@mui/material';
import Link from 'next/link';
import GitHubStep from './GitHubStep';
import RequirementsStep from './RequirementsStep';
import ScenariosStep from './ScenariosStep';
import PersonasStep from './PersonasStep';
import SuccessStep from './SuccessStep';
import { Project } from '@/utils/api-client/interfaces/project';

const steps = [
  'Repository',
  'Requirements',
  'Scenarios',
  'Personas',
  'Complete'
];

interface NewProjectFormProps {
  sessionToken: string;
}

export default function NewProjectForm({ sessionToken }: NewProjectFormProps) {
  const [activeStep, setActiveStep] = React.useState(0);
  const [projectData, setProjectData] = React.useState<Partial<Project>>({ id: '1' });

  const handleNext = () => {
    setActiveStep((prevStep) => prevStep + 1);
  };

  const handleBack = () => {
    setActiveStep((prevStep) => prevStep - 1);
  };

  const handleGitHubData = async (data: any) => {
    setProjectData({ ...data, id: '1' });
    handleNext();
  };

  const renderStep = () => {
    switch (activeStep) {
      case 0:
        return <GitHubStep onNext={handleGitHubData} sessionToken={sessionToken} />;
      case 1:
        return <RequirementsStep data={projectData?.requirements} onNext={handleNext} onBack={handleBack} />;
      case 2:
        return <ScenariosStep data={projectData?.scenarios} onNext={handleNext} onBack={handleBack} />;
      case 3:
        return <PersonasStep data={projectData?.personas} onNext={handleNext} onBack={handleBack} />;
      case 4:
        return <SuccessStep projectId={projectData.id} />;
      default:
        return null;
    }
  };

  return (
    <Box>
      <Box sx={{ mb: 4 }}>
        <Breadcrumbs sx={{ mb: 2 }}>
          <Link href="/projects-legacy" style={{ textDecoration: 'none', color: 'inherit' }}>
            Projects
          </Link>
          <Typography color="text.primary">New Project</Typography>
        </Breadcrumbs>
        <Typography variant="h4" gutterBottom>
          New Project Wizard
        </Typography>
        <Typography variant="body1" color="text.secondary" sx={{ mb: 3 }}>
          This wizard will analyze your GitHub repository to automatically extract key information about your multi-agent system. 
          It identifies system architecture, discovers agents and their responsibilities, and extracts requirements, scenarios, and personas. 
          This analysis forms the foundation for comprehensive testing of your agent interactions.
        </Typography>
      </Box>

      <Box sx={{ p: 3 }}>
        <Paper sx={{ p: 3, mb: 3 }}>
          <Stepper activeStep={activeStep} alternativeLabel>
            {steps.map((label) => (
              <Step key={label}>
                <StepLabel>{label}</StepLabel>
              </Step>
            ))}
          </Stepper>
        </Paper>
        {renderStep()}
      </Box>
    </Box>
  );
} 