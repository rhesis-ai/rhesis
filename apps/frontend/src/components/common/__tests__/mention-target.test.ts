import { inferAnnotationTarget } from '../MentionTextInput';
import {
  ANNOTATION_TARGET_TYPES,
  ENTITY_LEVEL_TARGETS,
  ANNOTATION_ENTITY_TYPES,
} from '@/utils/api-client/interfaces/annotation';

describe('inferAnnotationTarget', () => {
  const RESULT_LEVEL =
    ENTITY_LEVEL_TARGETS[ANNOTATION_ENTITY_TYPES.TEST_RESULT];
  const TRACE_LEVEL = ENTITY_LEVEL_TARGETS[ANNOTATION_ENTITY_TYPES.TRACE];

  describe('with no mention', () => {
    // The fallback has to follow the parent. It used to be hardcoded to
    // test_result, which stamped a whole-trace annotation with a target the
    // trace override does not dispatch on -- so the trace's status never
    // flipped and the panel never showed the verdict.
    it('falls back to the entity level of the parent it was given', () => {
      expect(inferAnnotationTarget('Looks wrong to me.', TRACE_LEVEL)).toEqual({
        type: ANNOTATION_TARGET_TYPES.TRACE,
        reference: null,
      });
      expect(inferAnnotationTarget('Looks wrong to me.', RESULT_LEVEL)).toEqual(
        {
          type: ANNOTATION_TARGET_TYPES.TEST_RESULT,
          reference: null,
        }
      );
      expect(
        inferAnnotationTarget(
          'Looks wrong to me.',
          ENTITY_LEVEL_TARGETS[ANNOTATION_ENTITY_TYPES.TEST]
        )
      ).toEqual({ type: ANNOTATION_TARGET_TYPES.TEST, reference: null });
    });

    it('falls back on an empty comment', () => {
      expect(inferAnnotationTarget('', TRACE_LEVEL)).toEqual({
        type: ANNOTATION_TARGET_TYPES.TRACE,
        reference: null,
      });
    });
  });

  describe('with a mention', () => {
    it('reads a metric mention, whatever the parent', () => {
      const comment = '@[Bias Detection](metric:bias-detection) should pass.';
      for (const level of [RESULT_LEVEL, TRACE_LEVEL]) {
        expect(inferAnnotationTarget(comment, level)).toEqual({
          type: ANNOTATION_TARGET_TYPES.METRIC,
          reference: 'Bias Detection',
        });
      }
    });

    it('reads a turn mention', () => {
      expect(
        inferAnnotationTarget('@[Turn 2](turn:2) went off script.', TRACE_LEVEL)
      ).toEqual({
        type: ANNOTATION_TARGET_TYPES.TURN,
        reference: 'Turn 2',
      });
    });

    it('takes the first mention when a comment names several', () => {
      expect(
        inferAnnotationTarget(
          '@[Fluency](metric:fluency) and @[Turn 3](turn:3) both look wrong.',
          RESULT_LEVEL
        )
      ).toEqual({
        type: ANNOTATION_TARGET_TYPES.METRIC,
        reference: 'Fluency',
      });
    });

    it('ignores a plain @name that is not mention markup', () => {
      expect(
        inferAnnotationTarget('@someone please check', TRACE_LEVEL)
      ).toEqual({ type: ANNOTATION_TARGET_TYPES.TRACE, reference: null });
    });
  });
});
