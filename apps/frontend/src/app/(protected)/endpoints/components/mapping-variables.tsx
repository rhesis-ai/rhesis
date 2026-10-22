import React from 'react';

export interface RequestVariableGroup {
  groupLabel: string;
  /** Single chip — use this OR chips, not both */
  name?: string;
  /** Multiple chips sharing one description */
  chips?: string[];
  description: React.ReactNode;
  docsUrl?: string;
}

/** Not a template variable: a reserved body key whose value is the prompt text. */
export const SYSTEM_PROMPT_KEY = 'system_prompt';
export const SYSTEM_PROMPT_CHIP = '"system_prompt"';

export const REQUEST_VARIABLES: RequestVariableGroup[] = [
  {
    groupLabel: 'Input',
    name: '{{ input }}',
    description: 'Required. The test prompt sent to your endpoint.',
  },
  {
    groupLabel: 'Multi-turn',
    chips: ['{{ messages }}', '{{ conversation_id }}'],
    description: (
      <>
        <strong>messages</strong>: full conversation history for stateless
        endpoints. <strong>conversation_id</strong>: tracking ID for both
        stateful and stateless endpoints.
      </>
    ),
    docsUrl:
      'https://docs.rhesis.ai/docs/endpoints/request-mapping#multi-turn-conversations',
  },
  {
    groupLabel: 'System prompt',
    name: SYSTEM_PROMPT_CHIP,
    description:
      'A reserved key holding the prompt text itself. Rhesis adds it to messages as the system message, and removes it from the body of stateless endpoints.',
  },
  {
    groupLabel: 'Files',
    name: '{{ files }}',
    description:
      'File attachments (images, PDFs). Use provider filters: to_openai, to_anthropic, to_gemini.',
    docsUrl:
      'https://docs.rhesis.ai/docs/endpoints/request-mapping#file-format-filters',
  },
  {
    groupLabel: 'Experiments',
    name: '{{ experiment_parameters }}',
    description:
      'Required if you run experiments. Access individual values with dot notation: {{ experiment_parameters.model }}, {{ experiment_parameters.temperature }}.',
    docsUrl:
      'https://docs.rhesis.ai/docs/endpoints#using-experiment-parameters',
  },
  {
    groupLabel: 'Execution context',
    chips: [
      '{{ test_id }}',
      '{{ test_run_id }}',
      '{{ test_configuration_id }}',
    ],
    description:
      'Auto-filled on every test run — useful if your API logs or traces which test triggered the request.',
    docsUrl:
      'https://docs.rhesis.ai/docs/endpoints/mapping-examples#test-execution-context',
  },
];

export interface RequestField {
  name: string;
  required?: boolean;
  description: string;
  /** Filter appended when easy input writes this variable into the template. */
  defaultFilter: string;
}

/** One row per variable in the Mapping step's easy input, in display order. */
export const REQUEST_FIELDS: RequestField[] = [
  {
    name: 'input',
    required: true,
    description: 'The test prompt sent to your endpoint.',
    defaultFilter: '',
  },
  {
    name: 'messages',
    description: 'Full conversation history, for stateless endpoints.',
    defaultFilter: ' | tojson',
  },
  {
    name: 'conversation_id',
    description: 'Tracking ID for stateful and stateless multi-turn endpoints.',
    defaultFilter: '',
  },
  {
    name: 'files',
    description: 'File attachments (images, PDFs), in OpenAI format.',
    defaultFilter: ' | to_openai | tojson',
  },
];

/** The create wizard leaves out the execution-context IDs; they matter only to APIs that log them. */
export const CREATE_REQUEST_VARIABLES = REQUEST_VARIABLES.filter(
  v => v.groupLabel !== 'Execution context'
);

/** Variables Rhesis fills in itself, so the Test step doesn't ask for them. */
export const AUTO_FILLED_VARS = new Set([
  'test_id',
  'test_run_id',
  'test_configuration_id',
]);
