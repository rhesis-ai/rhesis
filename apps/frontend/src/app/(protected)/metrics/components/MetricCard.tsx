import React from 'react';
import { Card, CardContent, Typography, Box, Chip } from '@mui/material';
import AssessmentIcon from '@mui/icons-material/Assessment';
import PrecisionManufacturingIcon from '@mui/icons-material/PrecisionManufacturing';
import VerifiedUserIcon from '@mui/icons-material/VerifiedUser';
import SearchIcon from '@mui/icons-material/Search';
import FactCheckIcon from '@mui/icons-material/FactCheck';
import StorageIcon from '@mui/icons-material/Storage';
import CodeIcon from '@mui/icons-material/Code';
import ApiIcon from '@mui/icons-material/Api';
import SmartToyIcon from '@mui/icons-material/SmartToy';
import NumbersIcon from '@mui/icons-material/Numbers';
import CategoryIcon from '@mui/icons-material/Category';
import ToggleOnIcon from '@mui/icons-material/ToggleOn';

interface MetricCardProps {
  title: string;
  description: string;
  backend: string;
  metricType: string;
  scoreType: string;
  type: 'answer_relevancy' | 'faithfulness' | 'contextual_relevancy' | 'contextual_precision' | 'contextual_recall';
  usedIn?: string;
}

const getMetricIcon = (type: string) => {
  switch (type) {
    case 'answer_relevancy':
      return <AssessmentIcon />;
    case 'faithfulness':
      return <VerifiedUserIcon />;
    case 'contextual_relevancy':
      return <SearchIcon />;
    case 'contextual_precision':
      return <PrecisionManufacturingIcon />;
    case 'contextual_recall':
      return <FactCheckIcon />;
    default:
      return <AssessmentIcon />;
  }
};

const getBackendIcon = (backend: string) => {
  switch (backend.toLowerCase()) {
    case 'custom':
      return <StorageIcon fontSize="small" />;
    case 'deepeval':
      return <ApiIcon fontSize="small" />;
    default:
      return <StorageIcon fontSize="small" />;
  }
};

const getMetricTypeDisplay = (metricType: string): string => {
  const mapping: Record<string, string> = {
    'custom-prompt': 'LLM Judge',
    'api-call': 'External API',
    'custom-code': 'Script',
    'grading': 'Grades'
  };
  return mapping[metricType] || metricType;
};

const getMetricTypeIcon = (metricType: string) => {
  switch (metricType.toLowerCase()) {
    case 'custom-prompt':
      return <SmartToyIcon fontSize="small" />;
    case 'api-call':
      return <ApiIcon fontSize="small" />;
    case 'custom-code':
      return <CodeIcon fontSize="small" />;
    case 'grading':
      return <AssessmentIcon fontSize="small" />;
    default:
      return <AssessmentIcon fontSize="small" />;
  }
};

const getScoreTypeIcon = (scoreType: string) => {
  switch (scoreType.toLowerCase()) {
    case 'numeric':
      return <NumbersIcon fontSize="small" />;
    case 'categorical':
      return <CategoryIcon fontSize="small" />;
    case 'binary':
      return <ToggleOnIcon fontSize="small" />;
    default:
      return <NumbersIcon fontSize="small" />;
  }
};

export default function MetricCard({ 
  title, 
  description, 
  backend,
  metricType,
  scoreType,
  type,
  usedIn 
}: MetricCardProps) {
  const capitalizedScoreType = scoreType.charAt(0).toUpperCase() + scoreType.slice(1).toLowerCase();
  const capitalizedBackend = backend.charAt(0).toUpperCase() + backend.slice(1).toLowerCase();

  const chipStyles = {
    '& .MuiChip-icon': {
      color: 'text.secondary',
      marginLeft: '4px'
    }
  };

  return (
    <Card sx={{ 
      height: '100%',
      display: 'flex',
      flexDirection: 'column',
      position: 'relative'
    }}>
      <CardContent sx={{ 
        flexGrow: 1,
        display: 'flex',
        flexDirection: 'column',
        justifyContent: 'space-between',
        pb: 2,
        pt: 3
      }}>
        <Box>
          <Box sx={{ display: 'flex', alignItems: 'center', mb: 1.5 }}>
            <Box sx={{ 
              mr: 1.5,
              color: 'primary.main',
              display: 'flex',
              alignItems: 'center'
            }}>
              {getMetricIcon(type)}
            </Box>
            <Typography 
              variant="subtitle1" 
              component="div" 
              sx={{ 
                fontWeight: 500,
                lineHeight: 1.2
              }}
            >
              {title}
            </Typography>
          </Box>
          
          <Typography 
            variant="body2" 
            color="text.secondary" 
            sx={{ mb: 'auto', minHeight: '2.5em' }}
          >
            {description}
          </Typography>
        </Box>

        <Box sx={{ mt: 2 }}>
          {usedIn && (
            <Typography 
              variant="caption" 
              color="text.secondary" 
              sx={{ 
                display: 'block',
                mb: 1
              }}
            >
              Used in: {usedIn}
            </Typography>
          )}
          <Box sx={{ 
            display: 'flex',
            flexWrap: 'wrap',
            gap: 0.5,
            '& .MuiChip-root': {
              height: '24px',
              fontSize: '0.75rem',
              ...chipStyles
            }
          }}>
            <Chip 
              icon={getBackendIcon(backend)}
              label={capitalizedBackend}
              size="small"
              color="default"
              variant="outlined"
            />
            <Chip 
              icon={getMetricTypeIcon(metricType)}
              label={getMetricTypeDisplay(metricType)}
              size="small"
              color="default"
              variant="outlined"
            />
            <Chip 
              icon={getScoreTypeIcon(scoreType)}
              label={capitalizedScoreType}
              size="small"
              color="default"
              variant="outlined"
            />
          </Box>
        </Box>
      </CardContent>
    </Card>
  );
} 