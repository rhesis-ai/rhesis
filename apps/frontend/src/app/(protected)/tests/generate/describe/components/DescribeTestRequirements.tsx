'use client';

import React, { useState, useCallback } from 'react';
import { useRouter } from 'next/navigation';
import {
  Box,
  Container,
  Typography,
  TextField,
  Button,
  Chip,
  Paper,
  IconButton,
  LinearProgress,
} from '@mui/material';
import ArrowBackIcon from '@mui/icons-material/ArrowBack';
import CloudUploadIcon from '@mui/icons-material/CloudUpload';
import SettingsIcon from '@mui/icons-material/Settings';
import { useNotifications } from '@/components/common/NotificationContext';
import { ApiClientFactory } from '@/utils/api-client/client-factory';
import {
  ProcessedDocument,
  DocumentUploadResponse,
} from '@/utils/api-client/interfaces/documents';

interface DescribeTestRequirementsProps {
  sessionToken: string;
  onNext?: () => void;
  onBack?: () => void;
}

const suggestions = [
  'Evaluate our support chatbot',
  'Test the compliance of our financial advisor',
  'Review integrity of our AI therapy application',
  'Evaluate our Gen AI application for any biases',
];

export default function DescribeTestRequirements({
  sessionToken,
  onNext,
  onBack,
}: DescribeTestRequirementsProps) {
  const router = useRouter();
  const { show } = useNotifications();

  const [description, setDescription] = useState('');
  const [documents, setDocuments] = useState<ProcessedDocument[]>([]);
  const [isUploading, setIsUploading] = useState(false);
  const [isGenerating, setIsGenerating] = useState(false);

  const handleSuggestionClick = (suggestion: string) => {
    setDescription(suggestion);
  };

  const handleFileUpload = useCallback(
    async (files: FileList | null) => {
      if (!files || files.length === 0) return;

      setIsUploading(true);
      try {
        const apiFactory = new ApiClientFactory(sessionToken);
        const servicesClient = apiFactory.getServicesClient();

        const uploadPromises = Array.from(files).map(async file => {
          const response = await servicesClient.uploadDocument(file);
          return response;
        });

        const uploadedDocs = await Promise.all(uploadPromises);

        // Transform DocumentUploadResponse to ProcessedDocument format
        const processedDocs: ProcessedDocument[] = uploadedDocs.map(
          (uploadedDoc, index) => ({
            id: `doc-${Date.now()}-${index}`,
            name: uploadedDoc.path.split('/').pop() || 'Document',
            description: '',
            path: uploadedDoc.path,
            content: '',
            originalName: uploadedDoc.path.split('/').pop() || 'Document',
            status: 'completed' as const,
          })
        );

        setDocuments(prev => [...prev, ...processedDocs]);

        show('Documents uploaded successfully', { severity: 'success' });
      } catch (error) {
        console.error('Failed to upload documents:', error);
        show('Failed to upload documents', { severity: 'error' });
      } finally {
        setIsUploading(false);
      }
    },
    [sessionToken, show]
  );

  const handleRemoveDocument = (docId: string) => {
    setDocuments(prev => prev.filter(doc => doc.id !== docId));
  };

  const handleContinue = async () => {
    if (!description.trim()) {
      show('Please describe your testing requirements', { severity: 'error' });
      return;
    }

    setIsGenerating(true);
    try {
      // Generate configuration from description
      const apiFactory = new ApiClientFactory(sessionToken);
      const servicesClient = apiFactory.getServicesClient();

      const configResponse =
        await servicesClient.generateTestConfig(description);

      // Store the description, documents, and generated configuration in session storage
      sessionStorage.setItem('testGenerationDescription', description);
      sessionStorage.setItem(
        'testGenerationDocuments',
        JSON.stringify(documents)
      );
      sessionStorage.setItem(
        'testGenerationConfig',
        JSON.stringify(configResponse)
      );

      // Navigate to configuration page or call onNext
      if (onNext) {
        onNext();
      } else {
        router.push('/tests/generate/configure');
      }
    } catch (error) {
      console.error('Failed to proceed:', error);
      show('Failed to generate configuration. Please try again.', {
        severity: 'error',
      });
    } finally {
      setIsGenerating(false);
    }
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    handleFileUpload(e.dataTransfer.files);
  };

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
  };

  const handleBack = () => {
    if (onBack) {
      onBack();
    } else {
      router.push('/tests/generate');
    }
  };

  return (
    <Container maxWidth="md" sx={{ py: 4 }}>
      {/* Back Button */}
      <Box sx={{ mb: 4 }}>
        <IconButton onClick={handleBack} sx={{ mb: 2 }}>
          <ArrowBackIcon />
        </IconButton>
      </Box>

      {/* Main Content */}
      <Box sx={{ maxWidth: 800, mx: 'auto' }}>
        {/* Description Input */}
        <Box sx={{ mb: 4 }}>
          <Typography variant="body1" sx={{ mb: 2 }}>
            Describe your testing requirements in detail. For example: &apos;I
            want to test my e-commerce API for security vulnerabilities and
            performance under high load...&apos;
          </Typography>

          <TextField
            multiline
            rows={6}
            fullWidth
            value={description}
            onChange={e => setDescription(e.target.value)}
            placeholder="Enter your testing requirements here..."
            variant="outlined"
            sx={{
              '& .MuiOutlinedInput-root': {
                backgroundColor: 'grey.50',
              },
            }}
          />

          <Box sx={{ display: 'flex', justifyContent: 'flex-end', mt: 1 }}>
            <Typography variant="body2" color="text.secondary">
              {description.length} characters
            </Typography>
          </Box>
        </Box>

        {/* Suggestions */}
        <Box sx={{ mb: 4 }}>
          <Typography variant="h6" gutterBottom>
            Or try one of these suggestions:
          </Typography>
          <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1 }}>
            {suggestions.map((suggestion, index) => (
              <Chip
                key={index}
                label={suggestion}
                onClick={() => handleSuggestionClick(suggestion)}
                variant="outlined"
                sx={{ cursor: 'pointer' }}
              />
            ))}
          </Box>
        </Box>

        {/* Document Upload */}
        <Box sx={{ mb: 4 }}>
          <Typography variant="h6" gutterBottom>
            Upload relevant documents (optional)
          </Typography>

          <Paper
            variant="outlined"
            sx={{
              p: 4,
              textAlign: 'center',
              border: '2px dashed',
              borderColor: 'grey.300',
              cursor: 'pointer',
              transition: 'border-color 0.2s',
              '&:hover': {
                borderColor: 'primary.main',
              },
            }}
            onDrop={handleDrop}
            onDragOver={handleDragOver}
            onClick={() => document.getElementById('file-upload')?.click()}
          >
            <CloudUploadIcon sx={{ fontSize: 48, color: 'grey.400', mb: 2 }} />
            <Typography variant="body1" gutterBottom>
              Click to upload or drag and drop files here
            </Typography>
            <Typography variant="body2" color="text.secondary">
              PDF, DOC, DOCX, TXT files supported
            </Typography>

            <input
              id="file-upload"
              type="file"
              multiple
              accept=".pdf,.doc,.docx,.txt"
              style={{ display: 'none' }}
              onChange={e => handleFileUpload(e.target.files)}
            />
          </Paper>

          {isUploading && (
            <Box sx={{ mt: 2 }}>
              <LinearProgress />
              <Typography variant="body2" color="text.secondary" sx={{ mt: 1 }}>
                Uploading documents...
              </Typography>
            </Box>
          )}

          {/* Uploaded Documents */}
          {documents.length > 0 && (
            <Box sx={{ mt: 2 }}>
              <Typography variant="subtitle2" gutterBottom>
                Uploaded Documents:
              </Typography>
              {documents.map(doc => (
                <Box
                  key={doc.id}
                  sx={{
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'space-between',
                    p: 1,
                    border: 1,
                    borderColor: 'grey.200',
                    sx: theme => ({ borderRadius: theme.shape.borderRadius }),
                    mb: 1,
                  }}
                >
                  <Typography variant="body2">{doc.name}</Typography>
                  <IconButton
                    size="small"
                    onClick={() => handleRemoveDocument(doc.id)}
                  >
                    ×
                  </IconButton>
                </Box>
              ))}
            </Box>
          )}
        </Box>

        {/* Continue Button */}
        <Box sx={{ textAlign: 'center' }}>
          <Button
            variant="contained"
            size="large"
            startIcon={<SettingsIcon />}
            onClick={handleContinue}
            disabled={!description.trim() || isGenerating}
            sx={{ px: 4, py: 1.5 }}
          >
            {isGenerating ? 'Processing...' : 'Continue with AI Generation'}
          </Button>
        </Box>
      </Box>
    </Container>
  );
}
