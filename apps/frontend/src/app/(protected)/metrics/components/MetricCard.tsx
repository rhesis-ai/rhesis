import React from 'react';
import type { Theme } from '@mui/material/styles';
import { SvgIcon } from '@mui/material';
import { AutoGraphIcon, PsychologyIcon } from '@/components/icons';
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
import { getMetricScopeIcon } from '@/constants/metric-scopes';

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
  onClick?: () => void;
}

const getBackendIcon = (backend: string) => {
  switch (backend.toLowerCase()) {
    case 'custom':
      return <FaceIcon fontSize="small" />;
    case 'deepeval':
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

const _getMetricTypeIcon = (metricType: string) => {
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

export default function MetricCard({
  title,
  description,
  backend,
  scoreType,
  metricScope,
  usedIn,
  showUsage = false,
  onClick,
}: MetricCardProps) {
  const capitalizedScoreType = scoreType
    ? scoreType.charAt(0).toUpperCase() + scoreType.slice(1).toLowerCase()
    : 'Unknown';
  const capitalizedBackend = backend
    ? backend.charAt(0).toUpperCase() + backend.slice(1).toLowerCase()
    : 'Unknown';

  const chipSections: ChipSection[] = [];

  if (showUsage && usedIn && usedIn.length > 0) {
    chipSections.push({
      label: 'Behaviors',
      chips: [
        ...usedIn.slice(0, 3).map((behaviorName, index) => ({
          key: `behavior-${index}`,
          icon: <PsychologyIcon fontSize="small" />,
          label: behaviorName,
          maxWidth: (theme: Theme) => theme.spacing(19),
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
        label: scope,
      });
    });
  }

  if (metricPropertyChips.length > 0) {
    chipSections.push({
      label: 'Properties',
      chips: metricPropertyChips,
    });
  }

  return (
    <EntityCard
      icon={<AutoGraphIcon fontSize="medium" />}
      title={title}
      description={description}
      chipSections={chipSections}
      onClick={onClick}
    />
  );
}
