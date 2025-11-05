import { Typography } from '@mui/material';
import { GridValueGetter, GridRenderCellParams } from '@mui/x-data-grid';
import { TestDetail } from '@/utils/api-client/interfaces/tests';
import { isMultiTurnTest } from '@/constants/test-types';
import { isMultiTurnConfig } from '@/utils/api-client/interfaces/multi-turn-test-config';

/**
 * Value getter for test content column - returns goal for multi-turn, prompt content for single-turn
 */
export const getTestContentValue: GridValueGetter<TestDetail, string> = (
  value,
  row
) => {
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
 * Cell renderer for test content column - displays goal for multi-turn, prompt content for single-turn
 */
export const renderTestContentCell = (
  params: GridRenderCellParams<TestDetail>
) => {
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
