import * as React from 'react';
import Box from '@mui/material/Box';
import Paper from '@mui/material/Paper';
import Typography from '@mui/material/Typography';
import Grid from '@mui/material/Grid';
import Chip from '@mui/material/Chip';
import Card from '@mui/material/Card';
import CardContent from '@mui/material/CardContent';
import { PageContainer } from '@toolpad/core/PageContainer';
import { auth } from '@/auth';
import { Metadata } from 'next';
import Button from '@mui/material/Button';
import ButtonGroup from '@mui/material/ButtonGroup';
import Link from 'next/link';
import ArrowBackIcon from '@mui/icons-material/ArrowBack';
import GradingIcon from '@mui/icons-material/Grading';
import ApiIcon from '@mui/icons-material/Api';
import CodeIcon from '@mui/icons-material/Code';
import ChatIcon from '@mui/icons-material/Chat';
import AssessmentIcon from '@mui/icons-material/Assessment';
import ListAltIcon from '@mui/icons-material/ListAlt';
import SmartToyIcon from '@mui/icons-material/SmartToy';
import EditIcon from '@mui/icons-material/Edit';
import ArchiveIcon from '@mui/icons-material/Archive';
import UnarchiveIcon from '@mui/icons-material/Unarchive';
import DeleteIcon from '@mui/icons-material/Delete';
import ClientWorkflowWrapper from './components/ClientWorkflowWrapper';

interface MetricDetail {
  id: string;
  title: string;
  description: string;
  tags: string[];
  evaluationPrompt: string;
  evaluationSteps: string[];
  reasoning: string;
  scoreType: 'binary' | 'numeric';
  minScore?: number;
  maxScore?: number;
  threshold?: number;
  explanation: string;
  llmJudge: {
    id: string;
    name: string;
    description: string;
  };
  createdAt: string;
  updatedAt: string;
  usedInTestSets: number;
  status: 'active' | 'draft' | 'archived';
  type: 'grading' | 'api-call' | 'custom-code' | 'custom-prompt';
}

interface PageProps {
  params: Promise<{ identifier: string }>;
  searchParams: Promise<{ [key: string]: string | string[] | undefined }>;
}

// This would typically come from an API call
const getMetricDetails = (identifier: string): MetricDetail => {
  // For now, return mock data that matches our new structure
  return {
    id: identifier,
    title: 'Response Coherence',
    description: 'Evaluates the logical flow and coherence of AI-generated responses',
    tags: ['coherence', 'quality', 'structure'],
    evaluationPrompt: 'Analyze the response for logical flow, consistency, and clear progression of ideas.',
    evaluationSteps: [
      'Check if the response has a clear introduction and context setting',
      'Evaluate the logical connection between paragraphs and ideas',
      'Assess the conclusion and its relation to the main points'
    ],
    reasoning: 'Focus on how well ideas connect and flow. Look for clear transitions and logical progression. Check if conclusions naturally follow from the presented arguments.',
    scoreType: 'numeric',
    minScore: 0,
    maxScore: 10,
    threshold: 7,
    explanation: 'Scores are based on the presence of clear structure, logical connections, and overall flow of ideas.',
    llmJudge: {
      id: 'claude-3.5',
      name: 'Claude 3.5',
      description: 'Anthropic\'s latest model, optimized for evaluation tasks'
    },
    createdAt: '2024-03-15T10:30:00Z',
    updatedAt: '2024-03-15T10:30:00Z',
    usedInTestSets: 5,
    status: 'active',
    type: 'custom-prompt'
  };
};

// Generate metadata for the page
export async function generateMetadata({ params }: { params: Promise<{ identifier: string }> }): Promise<Metadata> {
  try {
    const resolvedParams = await params;
    const identifier = resolvedParams.identifier;
    const metricDetails = getMetricDetails(identifier);
    
    return {
      title: `Metric | ${metricDetails.title}`,
      description: metricDetails.description,
      openGraph: {
        title: `Metric | ${metricDetails.title}`,
        description: metricDetails.description,
      },
    };
  } catch (error) {
    return {
      title: 'Metric Details',
    };
  }
}

const SectionCard = ({ 
  title, 
  icon, 
  children 
}: { 
  title: string; 
  icon: React.ReactNode; 
  children: React.ReactNode;
}) => (
  <Paper sx={{ p: 3, mb: 3 }}>
    <Box sx={{ display: 'flex', alignItems: 'center', mb: 2 }}>
      <Box sx={{ color: 'primary.main', mr: 1, display: 'flex' }}>
        {icon}
      </Box>
      <Typography variant="h6">{title}</Typography>
    </Box>
    {children}
  </Paper>
);

const InfoRow = ({ label, value }: { label: string; value: React.ReactNode }) => (
  <Box sx={{ mb: 2 }}>
    <Typography variant="subtitle2" color="text.secondary" gutterBottom>
      {label}
    </Typography>
    <Box sx={{ typography: 'body1' }}>
      {value}
    </Box>
  </Box>
);

export default async function MetricDetailPage({ params }: PageProps) {
  try {
    const session = await auth();
    
    if (!session?.session_token) {
      throw new Error('No session token available');
    }
    
    const { identifier } = await params;
    const metricDetails = getMetricDetails(identifier);

    return (
      <PageContainer 
        title={metricDetails.title}
        breadcrumbs={[
          { title: 'Metrics', path: '/metrics' },
          { title: metricDetails.title }
        ]}
      >
        <Box sx={{ maxWidth: '1200px', mx: 'auto', pt: 3 }}>
          {/* Action Buttons */}
          <Box sx={{ mb: 3, display: 'flex', justifyContent: 'flex-end' }}>
            <ButtonGroup variant="contained" aria-label="metric actions">
              <Button
                startIcon={<EditIcon />}
                component={Link}
                href={`/metrics/edit/${metricDetails.id}`}
              >
                Edit
              </Button>
              <Button
                startIcon={metricDetails.status === 'active' ? <ArchiveIcon /> : <UnarchiveIcon />}
                color={metricDetails.status === 'active' ? 'warning' : 'success'}
              >
                {metricDetails.status === 'active' ? 'Archive' : 'Activate'}
              </Button>
              <Button
                startIcon={<DeleteIcon />}
                color="error"
              >
                Delete
              </Button>
            </ButtonGroup>
          </Box>

          <Grid container spacing={3}>
            <Grid item xs={12} md={8}>
              {/* General Information */}
              <SectionCard title="General Information" icon={<AssessmentIcon />}>
                <Grid container spacing={2} sx={{ mb: 3 }}>
                  <Grid item xs={3}>
                    <InfoRow label="Created" value={new Date(metricDetails.createdAt).toLocaleDateString()} />
                  </Grid>
                  <Grid item xs={3}>
                    <InfoRow label="Last Updated" value={new Date(metricDetails.updatedAt).toLocaleDateString()} />
                  </Grid>
                  <Grid item xs={3}>
                    <InfoRow label="Used in Test Sets" value={metricDetails.usedInTestSets} />
                  </Grid>
                  <Grid item xs={3}>
                    <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1 }}>
                      <Chip 
                        label={metricDetails.status.toUpperCase()} 
                        color={metricDetails.status === 'active' ? 'success' : 'default'}
                        size="small"
                      />
                      <Chip 
                        label={metricDetails.type.replace('-', ' ').toUpperCase()}
                        color="primary"
                        size="small"
                      />
                    </Box>
                  </Grid>
                </Grid>
                <InfoRow 
                  label="Description" 
                  value={metricDetails.description}
                />
                <InfoRow 
                  label="Tags" 
                  value={
                    <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1 }}>
                      {metricDetails.tags.map((tag) => (
                        <Chip
                          key={tag}
                          label={tag}
                          size="small"
                          variant="outlined"
                        />
                      ))}
                    </Box>
                  }
                />
              </SectionCard>

              {/* Evaluation Process */}
              <SectionCard title="Evaluation Process" icon={<ListAltIcon />}>
                <InfoRow 
                  label="LLM Judge" 
                  value={
                    <Box>
                      {metricDetails.llmJudge.name}
                      <Box component="span" sx={{ display: 'block', color: 'text.secondary', fontSize: '0.875rem' }}>
                        {metricDetails.llmJudge.description}
                      </Box>
                    </Box>
                  }
                />
                <InfoRow 
                  label="Evaluation Prompt" 
                  value={
                    <Box 
                      sx={{ 
                        fontFamily: 'monospace',
                        fontSize: '0.875rem',
                        bgcolor: 'grey.50', 
                        p: 2, 
                        borderRadius: 1,
                        whiteSpace: 'pre-wrap'
                      }}
                    >
                      {metricDetails.evaluationPrompt}
                    </Box>
                  }
                />
                <InfoRow 
                  label="Evaluation Steps" 
                  value={
                    <Box component="ol" sx={{ pl: 2, m: 0 }}>
                      {metricDetails.evaluationSteps.map((step, index) => (
                        <Box 
                          component="li" 
                          key={index}
                          sx={{ 
                            mb: 1,
                            '&:last-child': { mb: 0 }
                          }}
                        >
                          {step}
                        </Box>
                      ))}
                    </Box>
                  }
                />
                <InfoRow 
                  label="Reasoning Instructions" 
                  value={
                    <Box 
                      sx={{ 
                        fontFamily: 'monospace',
                        fontSize: '0.875rem',
                        bgcolor: 'grey.50', 
                        p: 2, 
                        borderRadius: 1,
                        whiteSpace: 'pre-wrap'
                      }}
                    >
                      {metricDetails.reasoning}
                    </Box>
                  }
                />
              </SectionCard>

              {/* Result Configuration */}
              <SectionCard title="Result Configuration" icon={<SmartToyIcon />}>
                <InfoRow 
                  label="Score Type" 
                  value={metricDetails.scoreType === 'binary' ? 'Binary (Pass/Fail)' : 'Numeric'} 
                />
                {metricDetails.scoreType === 'numeric' && (
                  <>
                    <InfoRow 
                      label="Score Range" 
                      value={`${metricDetails.minScore} - ${metricDetails.maxScore}`} 
                    />
                    <InfoRow 
                      label="Threshold" 
                      value={
                        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                          {metricDetails.threshold}
                          <Box component="span" sx={{ color: 'text.secondary', fontSize: '0.875rem' }}>
                            (minimum score required to pass)
                          </Box>
                        </Box>
                      } 
                    />
                  </>
                )}
                <InfoRow 
                  label="Result Explanation" 
                  value={
                    <Box 
                      sx={{ 
                        fontFamily: 'monospace',
                        fontSize: '0.875rem',
                        bgcolor: 'grey.50', 
                        p: 2, 
                        borderRadius: 1,
                        whiteSpace: 'pre-wrap'
                      }}
                    >
                      {metricDetails.explanation}
                    </Box>
                  }
                />
              </SectionCard>
            </Grid>

            <Grid item xs={12} md={4}>
              <Card>
                <CardContent>
                  <ClientWorkflowWrapper
                    metricId={metricDetails.id}
                    status={metricDetails.status}
                    sessionToken={session.session_token}
                  />
                </CardContent>
              </Card>
            </Grid>
          </Grid>
        </Box>
      </PageContainer>
    );
  } catch (error) {
    const errorMessage = (error as Error).message;
    return (
      <PageContainer title="Metric Details" breadcrumbs={[{ title: 'Metrics', path: '/metrics' }]}>
        <Paper sx={{ p: 3 }}>
          <Typography color="error">
            Error loading metric details: {errorMessage}
          </Typography>
          <Button 
            component={Link} 
            href="/metrics" 
            startIcon={<ArrowBackIcon />}
            sx={{ mt: 2 }}
          >
            Back to Metrics
          </Button>
        </Paper>
      </PageContainer>
    );
  }
} 