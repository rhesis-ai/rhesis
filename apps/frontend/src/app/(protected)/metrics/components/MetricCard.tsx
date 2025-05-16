import React from 'react';
import { Card, CardContent, Typography, Box, Chip } from '@mui/material';
import AssessmentIcon from '@mui/icons-material/Assessment';
import PrecisionManufacturingIcon from '@mui/icons-material/PrecisionManufacturing';
import VerifiedUserIcon from '@mui/icons-material/VerifiedUser';
import SearchIcon from '@mui/icons-material/Search';
import FactCheckIcon from '@mui/icons-material/FactCheck';

interface MetricCardProps {
  title: string;
  description: string;
  backend: string;
  requiresGroundTruth: boolean;
  defaultThreshold: number;
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

export default function MetricCard({ 
  title, 
  description, 
  backend, 
  requiresGroundTruth, 
  defaultThreshold, 
  type,
  usedIn 
}: MetricCardProps) {
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
        pt: 3 // Add padding top to account for absolute positioned icons
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
              fontSize: '0.75rem'
            }
          }}>
            <Chip 
              label={`Backend: ${backend}`}
              size="small"
              color="primary"
              variant="outlined"
            />
            <Chip 
              label={`Threshold: ${defaultThreshold}`}
              size="small"
              color="secondary"
              variant="outlined"
            />
            <Chip 
              label={requiresGroundTruth ? "Requires Ground Truth" : "No Ground Truth"}
              size="small"
              color={requiresGroundTruth ? "warning" : "success"}
              variant="outlined"
            />
          </Box>
        </Box>
      </CardContent>
    </Card>
  );
} 