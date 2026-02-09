import React from 'react';
import { SvgIcon } from '@mui/material';
import { AutoGraphIcon, PsychologyIcon } from '@/components/icons';
import TurnedInIcon from '@mui/icons-material/TurnedIn';
import ChatBubbleOutlineIcon from '@mui/icons-material/ChatBubbleOutline';
import MessageIcon from '@mui/icons-material/Message';
import HandymanIcon from '@mui/icons-material/Handyman';
import FaceIcon from '@mui/icons-material/Face';
import StorageIcon from '@mui/icons-material/Storage';
import SmartToyIcon from '@mui/icons-material/SmartToy';
import ApiIcon from '@mui/icons-material/Api';
import CodeIcon from '@mui/icons-material/Code';
import AssessmentIcon from '@mui/icons-material/Assessment';
import NumbersIcon from '@mui/icons-material/Numbers';
import CategoryIcon from '@mui/icons-material/Category';
import ToggleOnIcon from '@mui/icons-material/ToggleOn';
import BugReportIcon from '@mui/icons-material/BugReport';
import EntityCard, { type ChipSection } from '@/components/common/EntityCard';

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
      margin: theme => `0 -${theme.spacing(0.5)} 0 ${theme.spacing(0.5)}`,
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

const _getMetricIcon = (_type: string) => {
  // Use the same icon as in the navbar for consistency
  return <AutoGraphIcon />;
};

const getBackendIcon = (backend: string) => {
  switch (backend.toLowerCase()) {
    case 'custom':
      return <FaceIcon fontSize="small" />;
    case 'deepeval':
      return <HandymanIcon fontSize="small" />;
    case 'ragas':
      return <HandymanIcon fontSize="small" />;
    case 'garak':
      return <BugReportIcon fontSize="small" />;
    case 'rhesis ai':
    case 'rhesis':
      return <RhesisAIIcon fontSize="small" />;
    default:
      return <StorageIcon fontSize="small" />;
  }
};

const _getMetricTypeDisplay = (_metricType: string): string => {
  if (!_metricType) return 'Unknown';

  const mapping: Record<string, string> = {
    'custom-prompt': 'LLM Judge',
    'api-call': 'External API',
    'custom-code': 'Script',
    grading: 'Grades',
    framework: 'Framework',
  };

  // If we have a specific mapping, use it; otherwise capitalize the first letter
  return (
    mapping[_metricType] ||
    _metricType.charAt(0).toUpperCase() + _metricType.slice(1).toLowerCase()
  );
};

const _getMetricTypeIcon = (_metricType: string) => {
  switch (_metricType.toLowerCase()) {
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
      return <ChatBubbleOutlineIcon fontSize="small" />;
    case 'Multi-Turn':
      return <MessageIcon fontSize="small" />;
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
  // Safely handle capitalization with fallbacks for empty/undefined values
  const capitalizedScoreType = scoreType
    ? scoreType.charAt(0).toUpperCase() + scoreType.slice(1).toLowerCase()
    : 'Unknown';
  const capitalizedBackend = backend
    ? backend.charAt(0).toUpperCase() + backend.slice(1).toLowerCase()
    : 'Unknown';

  // Prepare chip sections
  const chipSections: ChipSection[] = [];

  // First section: behaviors (if showing usage)
  if (showUsage && usedIn && usedIn.length > 0) {
    chipSections.push({
      chips: [
        ...usedIn.slice(0, 3).map((behaviorName, index) => ({
          key: `behavior-${index}`,
          icon: <PsychologyIcon fontSize="small" />,
          label: behaviorName,
          maxWidth: '150px',
        })),
        ...(usedIn.length > 3
          ? [
              {
                key: 'more-behaviors',
                label: `+${usedIn.length - 3} more`,
              },
            ]
          : []),
      ],
    });
  }

  // Second section: metric properties
  const metricPropertyChips = [];

  if (backend || capitalizedBackend !== 'Unknown') {
    metricPropertyChips.push({
      key: 'backend',
      icon: getBackendIcon(backend || ''),
      label: capitalizedBackend,
    });
  }

  if (scoreType || capitalizedScoreType !== 'Unknown') {
    metricPropertyChips.push({
      key: 'scoreType',
      icon: getScoreTypeIcon(scoreType || ''),
      label: capitalizedScoreType,
    });
  }

  if (metricScope && metricScope.length > 0) {
    metricScope.forEach((scope, index) => {
      metricPropertyChips.push({
        key: `scope-${index}`,
        icon: getMetricScopeIcon(scope),
        label: getMetricScopeDisplay(scope),
      });
    });
  }

  if (metricPropertyChips.length > 0) {
    chipSections.push({
      chips: metricPropertyChips,
    });
  }

  return (
    <EntityCard
      icon={<AutoGraphIcon fontSize="medium" />}
      title={title}
      description={description}
      captionText={
        showUsage && usedIn && usedIn.length > 0
          ? `${usedIn.length} ${usedIn.length === 1 ? 'Behavior' : 'Behaviors'}`
          : undefined
      }
      chipSections={chipSections}
    />
  );
}
