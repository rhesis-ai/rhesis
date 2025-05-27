'use client';

import { Box, Paper, Button, TextField, Typography, Tooltip, Chip } from '@mui/material';
import PlayArrowIcon from '@mui/icons-material/PlayArrow';
import DownloadIcon from '@mui/icons-material/Download';
import { TestSet } from '@/utils/api-client/interfaces/test-set';
import { useState, useEffect } from 'react';
import { useSession } from 'next-auth/react';
import { ApiClientFactory } from '../../../../../utils/api-client/client-factory';
import TestRunDrawer from '../../components/TestRunDrawer';
import CancelIcon from '@mui/icons-material/Cancel';
import CheckIcon from '@mui/icons-material/Check';
import EditIcon from '@mui/icons-material/Edit';
import TestSetTags from './TestSetTags';

interface TestSetDetailsSectionProps {
  testSet: TestSet;
  sessionToken: string;
}

interface MetadataFieldProps {
  label: string;
  items: string[];
  maxVisible?: number;
}

function MetadataField({ label, items, maxVisible = 20 }: MetadataFieldProps) {
  if (!items || items.length === 0) {
    return (
      <Box sx={{ mb: 3 }}>
        <Typography variant="subtitle1" sx={{ mb: 1, fontWeight: 'medium' }}>
          {label}
        </Typography>
        <Typography variant="body2" color="text.secondary">
          No {label.toLowerCase()} defined
        </Typography>
      </Box>
    );
  }

  const visibleItems = items.slice(0, maxVisible);
  const remainingCount = items.length - maxVisible;

  return (
    <Box sx={{ mb: 3 }}>
      <Typography variant="subtitle1" sx={{ mb: 1, fontWeight: 'medium' }}>
        {label}
      </Typography>
      <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1 }}>
        {visibleItems.map((item, index) => (
          <Chip
            key={index}
            label={item}
            variant="outlined"
            size="small"
            sx={{ 
              backgroundColor: 'rgba(158, 158, 158, 0.08)',
              borderColor: 'rgba(158, 158, 158, 0.3)',
              color: 'rgba(97, 97, 97, 1)',
              '&:hover': {
                backgroundColor: 'rgba(158, 158, 158, 0.12)',
              }
            }}
          />
        ))}
        {remainingCount > 0 && (
          <Chip
            label={`+${remainingCount}`}
            variant="outlined"
            size="small"
            sx={{ 
              backgroundColor: 'rgba(117, 117, 117, 0.08)',
              borderColor: 'rgba(117, 117, 117, 0.3)',
              color: 'rgba(66, 66, 66, 1)',
              fontWeight: 'medium',
              '&:hover': {
                backgroundColor: 'rgba(117, 117, 117, 0.12)',
              }
            }}
          />
        )}
      </Box>
    </Box>
  );
}

export default function TestSetDetailsSection({ testSet, sessionToken }: TestSetDetailsSectionProps) {
  const [testRunDrawerOpen, setTestRunDrawerOpen] = useState(false);
  const [isEditingDescription, setIsEditingDescription] = useState(false);
  const [editedDescription, setEditedDescription] = useState(testSet.description || '');
  const [isUpdating, setIsUpdating] = useState(false);
  const { data: session } = useSession();
  
  if (!session) {
    return null;
  }

  const handleEditDescription = () => {
    setIsEditingDescription(true);
  };

  const handleCancelEdit = () => {
    setIsEditingDescription(false);
    setEditedDescription(testSet.description || '');
  };

  const handleConfirmEdit = async () => {
    if (!sessionToken) return;
    
    setIsUpdating(true);
    try {
      const clientFactory: ApiClientFactory = new ApiClientFactory(sessionToken);
      const testSetsClient = clientFactory.getTestSetsClient();
      
      await testSetsClient.updateTestSet(testSet.id, {
        description: editedDescription
      });
      
      setIsEditingDescription(false);
      // Note: In a real app, you might want to refresh the test set data here
      // or use a state management solution to update the parent component
    } catch (error) {
      console.error('Error updating test set description:', error);
    } finally {
      setIsUpdating(false);
    }
  };

  // Extract metadata from testSet
  const behaviors = testSet.attributes?.metadata?.behaviors || [];
  const categories = testSet.attributes?.metadata?.categories || [];
  const topics = testSet.attributes?.metadata?.topics || [];

  return (
    <Paper sx={{ p: 3, mb: 3 }}>
      {/* Action Buttons */}
      <Box sx={{ display: 'flex', gap: 2, mb: 3 }}>
        <Button
          variant="contained"
          color="primary"
          startIcon={<PlayArrowIcon />}
          onClick={() => setTestRunDrawerOpen(true)}
        >
          Execute Test Set
        </Button>
        <Button
          variant="outlined"
          startIcon={<DownloadIcon />}
        >
          Download Test Set
        </Button>
      </Box>

      {/* Description TextField */}
      <Box sx={{ mb: 3, position: 'relative' }}>
        <Typography variant="h6" sx={{ mb: 2 }}>
          Test Set Details
        </Typography>
        <TextField
          fullWidth
          label="Description"
          multiline
          rows={4}
          value={isEditingDescription ? editedDescription : (testSet.description || '')}
          onChange={(e) => setEditedDescription(e.target.value)}
          sx={{ 
            mb: isEditingDescription ? 1 : 0,
            '& .MuiInputBase-root': {
              paddingRight: !isEditingDescription ? '80px' : '0',
            }
          }}
          InputProps={{
            readOnly: !isEditingDescription,
          }}
        />
        
        {!isEditingDescription ? (
          <Button
            startIcon={<EditIcon />}
            onClick={handleEditDescription}
            sx={{ 
              position: 'absolute', 
              top: 8, 
              right: 8,
              zIndex: 1,
              backgroundColor: 'rgba(255, 255, 255, 0.8)',
              '&:hover': {
                backgroundColor: 'rgba(255, 255, 255, 0.9)',
              }
            }}
          >
            Edit
          </Button>
        ) : (
          <Box sx={{ display: 'flex', justifyContent: 'flex-end', gap: 1 }}>
            <Button
              variant="outlined"
              color="error"
              startIcon={<CancelIcon />}
              onClick={handleCancelEdit}
              disabled={isUpdating}
            >
              Cancel
            </Button>
            <Button
              variant="contained"
              color="primary"
              startIcon={<CheckIcon />}
              onClick={handleConfirmEdit}
              disabled={isUpdating}
            >
              Confirm
            </Button>
          </Box>
        )}
      </Box>

      {/* Metadata Fields */}
      <Box sx={{ mb: 3 }}>
        <MetadataField label="Behaviors" items={behaviors} />
        <MetadataField label="Categories" items={categories} />
        <MetadataField label="Topics" items={topics} />
      </Box>

      {/* Tags Section */}
      <TestSetTags 
        sessionToken={sessionToken} 
        testSet={testSet} 
      />

      <TestRunDrawer
        open={testRunDrawerOpen}
        onClose={() => setTestRunDrawerOpen(false)}
        sessionToken={sessionToken}
        selectedTestSetIds={[testSet.id]}
        onSuccess={() => setTestRunDrawerOpen(false)}
      />
    </Paper>
  );
} 