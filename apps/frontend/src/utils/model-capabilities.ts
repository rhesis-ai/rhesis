import type { Model } from '@/utils/api-client/interfaces/model';
import { MODEL_TYPES } from '@/constants/model-types';
import { SCORE_TYPES } from '@/constants/score-types';
import { isDecisionProvider } from '@/config/model-providers';

export function isEmbeddingModel(model: Model): boolean {
  return model.model_type === MODEL_TYPES.EMBEDDING;
}

export function isDecisionModel(model: Model): boolean {
  return (
    model.model_type === MODEL_TYPES.DECISION ||
    isDecisionProvider(model.provider_type?.type_value)
  );
}

/** True for models that can generate text (test generation, execution, free-form judging). */
export function generatesText(model: Model): boolean {
  return !isEmbeddingModel(model) && !isDecisionModel(model);
}

/** Whether a model can judge a metric of the given score type. */
export function canJudgeScoreType(
  model: Model,
  scoreType: string | undefined
): boolean {
  if (isEmbeddingModel(model)) return false;
  return !isDecisionModel(model) || scoreType === SCORE_TYPES.CATEGORICAL;
}
