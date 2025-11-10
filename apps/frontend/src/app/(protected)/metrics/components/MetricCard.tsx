import React from 'react';
import { useTheme } from '@mui/material/styles';
import {
  Card,
  CardContent,
  Typography,
  Box,
  Chip,
  SvgIcon,
} from '@mui/material';
import {
  AssessmentIcon,
  PrecisionManufacturingIcon,
  VerifiedUserIcon,
  SearchIcon,
  FactCheckIcon,
  StorageIcon,
  CodeIcon,
  ApiIcon,
  SmartToyIcon,
  NumbersIcon,
  CategoryIcon,
  ToggleOnIcon,
} from '@/components/icons';
import TurnedInIcon from '@mui/icons-material/TurnedIn';
import LooksOneIcon from '@mui/icons-material/LooksOne';
import RepeatIcon from '@mui/icons-material/Repeat';

// Custom Rhesis AI icon component using inline SVG
const RhesisAIIcon = ({
  fontSize = 'small',
}: {
  fontSize?: 'small' | 'medium' | 'large';
}) => (
  <SvgIcon
    fontSize={fontSize}
    viewBox="0 0 390 371"
    sx={{
      margin: '0 -4px 0 4px',
    }}
  >
    <path
      d="M17.6419 272.939C72.0706 284.122 119.805 321.963 182.044 358.896C203.958 371.859 229.133 373.691 251.291 366.398C273.398 359.106 292.557 342.671 302.495 319.206C330.616 252.492 346.55 193.663 383.685 152.315C394.79 140.121 388.322 120.476 372.178 117.318C330.598 109.153 300.054 73.5806 298.171 31.2211C297.404 14.7518 278.976 5.48786 265.291 14.6646C258.213 19.4623 250.611 23.0911 242.819 25.6732C211.873 35.8618 177.127 29.0054 152.11 6.18571C146.06 0.655251 138.075 -0.513647 131.294 1.71947C124.512 3.95259 118.776 9.64007 117.172 17.7002C110.652 50.9004 86.7151 77.1221 55.7699 87.3108C47.9595 89.8928 39.6958 91.4804 31.1532 91.8293C14.6956 92.597 5.36845 110.985 14.591 124.681C38.1617 159.887 34.7097 206.678 6.11811 237.959C-5.00474 250.084 1.46325 269.746 17.6245 272.956L17.6419 272.939Z"
      fill="currentColor"
    />
  </SvgIcon>
);

interface MetricCardProps {
  type?: 'custom-prompt' | 'api-call' | 'custom-code' | 'grading';
  title: string;
  description: string;
  backend?: string;
  metricType?: string;
  scoreType?: string;
  metricScope?: string[];
  usedIn?: string[];
  showUsage?: boolean;
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
    case 'rhesis ai':
    case 'rhesis':
      return <RhesisAIIcon fontSize="small" />;
    default:
      return <StorageIcon fontSize="small" />;
  }
};

const getMetricTypeDisplay = (metricType: string): string => {
  if (!metricType) return 'Unknown';

  const mapping: Record<string, string> = {
    'custom-prompt': 'LLM Judge',
    'api-call': 'External API',
    'custom-code': 'Script',
    grading: 'Grades',
    framework: 'Framework',
  };

  // If we have a specific mapping, use it; otherwise capitalize the first letter
  return (
    mapping[metricType] ||
    metricType.charAt(0).toUpperCase() + metricType.slice(1).toLowerCase()
  );
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
    case 'rhesis ai':
    case 'rhesis':
      return <RhesisAIIcon fontSize="small" />;
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
    case 'rhesis ai':
    case 'rhesis':
      return <RhesisAIIcon fontSize="small" />;
    default:
      return <NumbersIcon fontSize="small" />;
  }
};

const getMetricScopeDisplay = (scope: string): string => {
  return scope;
};

const getMetricScopeIcon = (scope: string) => {
  switch (scope) {
    case 'Single-Turn':
      return <LooksOneIcon fontSize="small" />;
    case 'Multi-Turn':
      return <RepeatIcon fontSize="small" />;
    default:
      return <TurnedInIcon fontSize="small" />;
  }
};

export default function MetricCard({
  title,
  description,
  backend,
  metricType,
  scoreType,
  metricScope,
  type,
  usedIn,
  showUsage = false,
}: MetricCardProps) {
  const theme = useTheme();

  // Safely handle capitalization with fallbacks for empty/undefined values
  const capitalizedScoreType = scoreType
    ? scoreType.charAt(0).toUpperCase() + scoreType.slice(1).toLowerCase()
    : 'Unknown';
  const capitalizedBackend = backend
    ? backend.charAt(0).toUpperCase() + backend.slice(1).toLowerCase()
    : 'Unknown';

  const chipStyles = {
    '& .MuiChip-icon': {
      color: 'text.secondary',
      marginLeft: '4px',
    },
  };

  return (
    <Card
      sx={{
        height: '100%',
        display: 'flex',
        flexDirection: 'column',
        position: 'relative',
      }}
    >
      <CardContent
        sx={{
          flexGrow: 1,
          display: 'flex',
          flexDirection: 'column',
          justifyContent: 'space-between',
          pb: 2,
          pt: 3,
        }}
      >
        <Box>
          <Box sx={{ display: 'flex', alignItems: 'center', mb: 1.5 }}>
            <Box
              sx={{
                mr: 1.5,
                color: 'primary.main',
                display: 'flex',
                alignItems: 'center',
              }}
            >
              {getMetricIcon(type || '')}
            </Box>
            <Typography
              variant="subtitle1"
              component="div"
              sx={{
                fontWeight: 500,
                lineHeight: 1.2,
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
          <Typography
            variant="caption"
            color="text.secondary"
            sx={{
              display: 'block',
              mb: 1,
              minHeight: '1.5em',
            }}
          >
            {showUsage && usedIn && usedIn.length > 0
              ? `Used in: ${usedIn.join(', ')}`
              : ''}
          </Typography>
          <Box
            sx={{
              display: 'flex',
              flexWrap: 'wrap',
              gap: 0.5,
              '& .MuiChip-root': {
                height: '24px',
                fontSize: theme?.typography?.chartLabel?.fontSize || '0.75rem',
                ...chipStyles,
              },
            }}
          >
            {(backend || capitalizedBackend !== 'Unknown') && (
              <Chip
                icon={getBackendIcon(backend || '')}
                label={capitalizedBackend}
                size="small"
                variant="outlined"
              />
            )}
            {(metricType ||
              getMetricTypeDisplay(metricType || '') !== 'Unknown') && (
              <Chip
                icon={getMetricTypeIcon(metricType || '')}
                label={getMetricTypeDisplay(metricType || '')}
                size="small"
                variant="outlined"
              />
            )}
            {(scoreType || capitalizedScoreType !== 'Unknown') && (
              <Chip
                icon={getScoreTypeIcon(scoreType || '')}
                label={capitalizedScoreType}
                size="small"
                variant="outlined"
              />
            )}
            {metricScope &&
              metricScope.length > 0 &&
              metricScope.map((scope, index) => (
                <Chip
                  key={`scope-${index}`}
                  icon={getMetricScopeIcon(scope)}
                  label={getMetricScopeDisplay(scope)}
                  size="small"
                  variant="outlined"
                  color="primary"
                />
              ))}
          </Box>
        </Box>
      </CardContent>
    </Card>
  );
}
