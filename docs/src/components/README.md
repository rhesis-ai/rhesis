# CodeBlock Component

A terminal-style code block component that mimics the styling from the Rhesis website. Supports both code files and terminal output with syntax highlighting.

## Features

- **Terminal-style design** with macOS-style window controls (red, yellow, blue dots)
- **Syntax highlighting** for Python and Bash/Shell languages
- **Dark theme** matching the Rhesis brand colors
- **Responsive design** with horizontal scrolling for long lines
- **Terminal output mode** for displaying command results

## Usage

The CodeBlock component is globally available in all MDX files. No import needed.

### Basic Code Block

```mdx
<CodeBlock filename="app.py" language="python">
{`import os
from rhesis.sdk import RhesisClient

client = RhesisClient(api_key="your-key")`}

</CodeBlock>
```

### Terminal/Shell Commands

```mdx
<CodeBlock filename="terminal" language="bash">
  {`pip install rhesis-sdk
cd my-project
python app.py`}
</CodeBlock>
```

### Terminal Output

```mdx
<CodeBlock filename="Terminal Output" isTerminal={true}>
  {`✓ Tests generated successfully
✓ 100 test cases created
✓ Ready for execution`}
</CodeBlock>
```

## Props

| Prop         | Type      | Default      | Description                                                                      |
| ------------ | --------- | ------------ | -------------------------------------------------------------------------------- |
| `filename`   | `string`  | `"code.txt"` | The filename to display in the header                                            |
| `language`   | `string`  | `"text"`     | Programming language for syntax highlighting (`python`, `bash`, `shell`, `text`) |
| `isTerminal` | `boolean` | `false`      | Whether this is terminal output (disables syntax highlighting)                   |
| `children`   | `string`  | -            | The code content to display                                                      |

## Supported Languages

- **Python**: Keywords, strings, numbers, and comments are highlighted
- **Bash/Shell**: Commands, strings, and comments are highlighted
- **Text**: No highlighting (default)

## Styling

The component uses the following color scheme to match the Rhesis brand:

**Code Syntax Highlighting:**

- Background: `#161B22` (dark gray)
- Header: `#1F242B` (darker gray)
- Text: `#E6EDF3` (light gray)
- Keywords: `#3BC4F2` (blue)
- Strings: `#FCD34D` (yellow)
- Numbers: `#86EFAC` (green)
- Comments: `#A9B1BB` (muted gray)

**Terminal Output:**

- Separators (dashes): `#6B7280` (muted gray with opacity)
- Labels (Prompt:, Behavior:, etc.): `#60A5FA` (blue, semi-bold)
- Values: `#E5E7EB` (light gray)

All styles are defined in `styles/globals.css` under the `.rhesis-codeblock` namespace.

## Examples

See the main documentation index page for live examples of the CodeBlock component in action.
