// jsx-a11y only checks DOM elements, so MUI controls that render without a
// name (icon-only buttons, unlinked selects, bare progress bars) pass lint
// while screen readers announce "button", "combobox" or "progressbar".

function elementName(openingElement) {
  return openingElement?.name?.type === 'JSXIdentifier'
    ? openingElement.name.name
    : undefined;
}

function hasAttribute(node, names) {
  return node.attributes.some(
    attr =>
      // A spread may carry the name; we can't tell statically.
      attr.type === 'JSXSpreadAttribute' || names.has(attr.name?.name)
  );
}

function insideTooltip(node) {
  const parent = node.parent?.parent;
  return (
    parent?.type === 'JSXElement' &&
    elementName(parent.openingElement) === 'Tooltip'
  );
}

function nameRule({ components, attributes, allowTooltip, message }) {
  const names = new Set(attributes);
  return {
    meta: {
      type: 'problem',
      docs: { description: message },
      messages: { missing: message },
      schema: [],
    },
    create(context) {
      return {
        JSXOpeningElement(node) {
          if (!components.has(elementName(node))) return;
          if (hasAttribute(node, names)) return;
          // MUI Tooltip applies a string title as the child's aria-label.
          if (allowTooltip && insideTooltip(node)) return;
          context.report({ node, messageId: 'missing' });
        },
      };
    },
  };
}

export const iconButtonName = nameRule({
  components: new Set(['IconButton']),
  attributes: ['aria-label', 'aria-labelledby', 'title'],
  allowTooltip: true,
  message:
    'IconButton needs an accessible name: add aria-label, or wrap it in a <Tooltip title="...">.',
});

export const selectLabel = nameRule({
  components: new Set(['Select']),
  // `inputProps['aria-label']` also works, but only via the spread-free form
  // `inputProps={{ 'aria-label': ... }}`, which this check accepts too.
  attributes: [
    'labelId',
    'aria-label',
    'aria-labelledby',
    'inputProps',
    'native',
  ],
  allowTooltip: false,
  message:
    'Select needs a linked label: give the InputLabel an id and pass it as labelId.',
});

export const progressName = nameRule({
  // CircularProgress gets 'Loading' from the theme's defaultProps.
  components: new Set(['LinearProgress']),
  attributes: ['aria-label', 'aria-labelledby', 'aria-hidden'],
  allowTooltip: false,
  message:
    'Progress indicators need a name (aria-label), or aria-hidden when a visible text says the same.',
});

export default iconButtonName;
