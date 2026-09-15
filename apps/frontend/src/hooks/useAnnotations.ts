import { useCallback, useMemo } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { ApiClientFactory } from '@/utils/api-client/client-factory';
import { useNotifications } from '@/components/common/NotificationContext';
import { annotationKeys, testRunKeys } from '@/constants/query-keys';
import { useIsAuthenticated } from '@/hooks/useIsAuthenticated';
import type {
  Annotation,
  AnnotationEntityType,
  AnnotationTargetInput,
  AnnotationUpdate,
} from '@/utils/api-client/interfaces/annotation';

interface UseEntityAnnotationsOptions {
  /** Server-prefetched rows; seeds the cache so the first render has them. */
  initialData?: Annotation[];
  enabled?: boolean;
}

/** Every annotation on one parent, newest first. */
export function useEntityAnnotations(
  entityType: AnnotationEntityType,
  entityId: string | undefined,
  { initialData, enabled = true }: UseEntityAnnotationsOptions = {}
) {
  const isAuthenticated = useIsAuthenticated();
  const queryKey = useMemo(
    () => annotationKeys.entity(entityType, entityId ?? ''),
    [entityType, entityId]
  );

  const {
    data: annotations = [],
    isLoading,
    error,
    refetch,
  } = useQuery({
    queryKey,
    queryFn: () =>
      new ApiClientFactory()
        .getAnnotationsClient()
        .getByEntity(entityType, entityId ?? ''),
    enabled: enabled && isAuthenticated && !!entityId,
    initialData,
  });

  return {
    annotations,
    isLoading,
    error: error ? 'Failed to load annotations' : null,
    refetch,
  };
}

interface UseAnnotationMutationsOptions {
  /**
   * Refresh the parent after a write. An annotation changes the parent's
   * status and its embedded summary, and the test run detail page holds that
   * parent outside react-query, so it cannot be reached by invalidation.
   */
  parentInvalidate?: () => void;
}

/**
 * Create, update and delete annotations on one parent.
 *
 * Every write invalidates the entity list, the annotation lists behind the
 * hub, and the test run keys, because run-level counts move with it.
 */
export function useAnnotationMutations(
  entityType: AnnotationEntityType,
  entityId: string | undefined,
  { parentInvalidate }: UseAnnotationMutationsOptions = {}
) {
  const queryClient = useQueryClient();
  const notifications = useNotifications();

  // `annotationKeys.all()` is the prefix of every annotation key, so this
  // covers the entity list this panel reads and the hub's own lists.
  const invalidate = useCallback(() => {
    queryClient.invalidateQueries({ queryKey: annotationKeys.all() });
    queryClient.invalidateQueries({ queryKey: testRunKeys.all() });
    parentInvalidate?.();
  }, [queryClient, parentInvalidate]);

  const create = useCallback(
    async (input: {
      statusId: string;
      comments?: string;
      target?: AnnotationTargetInput;
    }) => {
      if (!entityId) throw new Error('No entity to annotate.');
      const annotation = await new ApiClientFactory()
        .getAnnotationsClient()
        .createAnnotation({
          entity_type: entityType,
          entity_id: entityId,
          status_id: input.statusId,
          comments: input.comments,
          target: input.target,
        });
      invalidate();
      notifications.show('Annotation saved.', {
        severity: 'success',
        autoHideDuration: 3000,
      });
      return annotation;
    },
    [entityType, entityId, invalidate, notifications]
  );

  const update = useCallback(
    async (annotationId: string, changes: AnnotationUpdate) => {
      const annotation = await new ApiClientFactory()
        .getAnnotationsClient()
        .updateAnnotation(annotationId, changes);
      invalidate();
      notifications.show('Annotation updated.', {
        severity: 'success',
        autoHideDuration: 3000,
      });
      return annotation;
    },
    [invalidate, notifications]
  );

  const remove = useCallback(
    async (annotationId: string) => {
      const annotation = await new ApiClientFactory()
        .getAnnotationsClient()
        .deleteAnnotation(annotationId);
      invalidate();
      notifications.show('Annotation deleted.', {
        severity: 'success',
        autoHideDuration: 3000,
      });
      return annotation;
    },
    [invalidate, notifications]
  );

  const setResolved = useCallback(
    (annotationId: string, resolved: boolean) =>
      update(annotationId, { resolved }),
    [update]
  );

  return { create, update, remove, setResolved };
}
