import { Typography } from '@mui/material';
import { GridValueGetter, GridRenderCellParams } from '@mui/x-data-grid';
import { TestDetail } from '@/utils/api-client/interfaces/tests';
import { isMultiTurnTest } from '@/constants/test-types';
import { isMultiTurnConfig } from '@/utils/api-client/interfaces/multi-turn-test-config';

/** Goal for multi-turn tests, prompt content for single-turn. */
export function getTestDisplayContent(test: TestDetail): string {
  if (
    isMultiTurnTest(test.test_type?.type_value) &&
    isMultiTurnConfig(test.test_configuration)
  ) {
    return test.test_configuration.goal || '';
  }
  return test.prompt?.content || '';
}

/**
 * Value getter for test content column - returns goal for multi-turn, prompt content for single-turn
 */
export const getTestContentValue: GridValueGetter<TestDetail, string> = (
  _value,
  row
) => getTestDisplayContent(row);

/**
 * Cell renderer for test content column - displays goal for multi-turn, prompt content for single-turn
 */
export const renderTestContentCell = (
  params: GridRenderCellParams<TestDetail>
) => {
  const content = getTestDisplayContent(params.row);

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
