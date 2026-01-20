import { Typography, Box } from '@mui/material';
import { GridValueGetter, GridRenderCellParams } from '@mui/x-data-grid';
import { TestDetail } from '@/utils/api-client/interfaces/tests';
import { isMultiTurnTest, isImageTest } from '@/constants/test-types';
import { isMultiTurnConfig } from '@/utils/api-client/interfaces/multi-turn-test-config';
import TestImage from '@/components/common/TestImage';
import ImageIcon from '@mui/icons-material/Image';

/**
 * Value getter for test content column - returns goal for multi-turn, prompt content for single-turn,
 * or generation prompt for image tests
 */
export const getTestContentValue: GridValueGetter<TestDetail, string> = (
  value,
  row
) => {
  // For image tests, show the generation prompt from metadata
  if (isImageTest(row.test_type?.type_value)) {
    return (
      row.test_metadata?.generation_prompt ||
      row.test_metadata?.expected_output ||
      'Image test'
    );
  }
  // For multi-turn tests, show the goal
  if (
    isMultiTurnTest(row.test_type?.type_value) &&
    isMultiTurnConfig(row.test_configuration)
  ) {
    return row.test_configuration.goal || '';
  }
  // For single-turn tests, show the prompt content
  return row.prompt?.content || '';
};

/**
 * Factory function to create a cell renderer with session token for authenticated image loading.
 * Use this when you need to display actual images in the grid.
 *
 * @param sessionToken - Authentication token for API requests
 * @param allImageTestIds - Optional array of all image test IDs for lightbox navigation
 */
export const createTestContentCellRenderer = (
  sessionToken: string,
  allImageTestIds?: string[]
) => {
  return (params: GridRenderCellParams<TestDetail>) => {
    // For image tests, show authenticated thumbnail with the generation prompt
    if (isImageTest(params.row.test_type?.type_value)) {
      const generationPrompt =
        params.row.test_metadata?.generation_prompt ||
        params.row.test_metadata?.expected_output ||
        'Image test';

      return (
        <Box
          sx={{
            display: 'flex',
            alignItems: 'center',
            gap: 1.5,
            width: '100%',
            height: '100%',
            py: 0.5,
          }}
        >
          <TestImage
            testId={params.row.id}
            sessionToken={sessionToken}
            alt={generationPrompt}
            width={48}
            height={48}
            allTestIds={allImageTestIds}
          />
          <Typography
            variant="body2"
            title={generationPrompt}
            sx={{
              overflow: 'hidden',
              textOverflow: 'ellipsis',
              whiteSpace: 'nowrap',
              flex: 1,
            }}
          >
            {generationPrompt}
          </Typography>
        </Box>
      );
    }

    let content = '';

    // For multi-turn tests, show the goal
    if (
      isMultiTurnTest(params.row.test_type?.type_value) &&
      isMultiTurnConfig(params.row.test_configuration)
    ) {
      content = params.row.test_configuration.goal || '';
    } else {
      // For single-turn tests, show the prompt content
      content = params.row.prompt?.content || '';
    }

    if (!content) return null;

    return (
      <Typography
        variant="body2"
        title={content}
        sx={{
          overflow: 'hidden',
          textOverflow: 'ellipsis',
          whiteSpace: 'nowrap',
        }}
      >
        {content}
      </Typography>
    );
  };
};

/**
 * Cell renderer for test content column - displays image icon for image tests (no auth),
 * goal for multi-turn, prompt content for single-turn.
 * Use createTestContentCellRenderer() for authenticated image display.
 */
export const renderTestContentCell = (
  params: GridRenderCellParams<TestDetail>
) => {
  // For image tests, show an image icon with the generation prompt (no auth available)
  if (isImageTest(params.row.test_type?.type_value)) {
    const generationPrompt =
      params.row.test_metadata?.generation_prompt ||
      params.row.test_metadata?.expected_output ||
      'Image test';

    return (
      <Box
        sx={{
          display: 'flex',
          alignItems: 'center',
          gap: 1.5,
          width: '100%',
          height: '100%',
          py: 0.5,
        }}
      >
        <Box
          sx={{
            width: 48,
            height: 48,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            borderRadius: 1,
            flexShrink: 0,
            border: '1px solid',
            borderColor: 'divider',
            bgcolor: 'action.hover',
          }}
        >
          <ImageIcon sx={{ color: 'text.secondary', fontSize: 28 }} />
        </Box>
        <Typography
          variant="body2"
          title={generationPrompt}
          sx={{
            overflow: 'hidden',
            textOverflow: 'ellipsis',
            whiteSpace: 'nowrap',
            flex: 1,
          }}
        >
          {generationPrompt}
        </Typography>
      </Box>
    );
  }

  let content = '';

  // For multi-turn tests, show the goal
  if (
    isMultiTurnTest(params.row.test_type?.type_value) &&
    isMultiTurnConfig(params.row.test_configuration)
  ) {
    content = params.row.test_configuration.goal || '';
  } else {
    // For single-turn tests, show the prompt content
    content = params.row.prompt?.content || '';
  }

  if (!content) return null;

  return (
    <Typography
      variant="body2"
      title={content}
      sx={{
        overflow: 'hidden',
        textOverflow: 'ellipsis',
        whiteSpace: 'nowrap',
      }}
    >
      {content}
    </Typography>
  );
};
