/**
 * Annotation wording, in one place so the test-result, trace and explorer
 * surfaces cannot drift apart.
 */
export const ANNOTATION_COPY = {
  sectionTitle: 'Annotations',
  humanVerdictLabel: 'Human Annotation:',
  noneChip: 'Not Annotated',

  conflictTitle: 'Status Conflict Detected:',
  conflictBody:
    'The human annotation differs from the automated result. This indicates the annotator disagreed with the automation.',

  emptyNone: 'No annotations yet',
  emptyMine: 'You have not annotated this yet',
  emptyBody:
    'Annotate this to record your assessment of the automated findings.',
  createButton: 'Add annotation',
  showOthers: (count: number) => `Show annotations from other users (${count})`,

  drawerTitle: 'Add Annotation',
  editTitle: 'Edit Annotation',
  resolvedLabel: 'Resolved',
  verdictLabel: 'Verdict',
  verdictRequired: 'Please choose a verdict for this annotation.',
  commentPlaceholder:
    'Explain your verdict... Type @ to mention a metric or turn',
  commentHelp: 'Add a comment to support your verdict',
  commentTooShort: (min: number) =>
    `Comment must be at least ${min} characters long.`,
  commentCounter: (length: number, min: number) =>
    `Minimum ${min} characters required (${length}/${min})`,
  saveFailed: 'Failed to save the annotation. Please try again.',

  indicatorNone: 'Not yet annotated',
  indicatorAnnotated: 'Annotated',
  indicatorBy: (name: string) => `Annotated by ${name}`,

  deleteTitle: 'Delete Annotation',
  deleteTooltip: 'Delete annotation',
  deleteMessage:
    'Are you sure you want to delete this annotation? This action cannot be undone.',
} as const;
