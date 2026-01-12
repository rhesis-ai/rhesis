"""
Custom Pygments style for Rhesis documentation.
Uses Rhesis brand colors for syntax highlighting.
"""

from pygments.style import Style
from pygments.token import (
    Comment,
    Error,
    Generic,
    Keyword,
    Literal,
    Name,
    Number,
    Operator,
    Punctuation,
    String,
    Text,
    Whitespace,
)


class RhesisStyle(Style):
    """
    Rhesis brand color scheme for code syntax highlighting.
    """

    # Background color for highlighted code
    background_color = "#161B22"
    default_style = "#E6EDF3"  # Primary text color

    styles = {
        # Comments - secondary text color (subdued but clear)
        Comment:                        '#A9B1BB',
        Comment.Multiline:              '#A9B1BB',
        Comment.Preproc:                '#A9B1BB',
        Comment.Single:                 '#A9B1BB',
        Comment.Special:                '#A9B1BB',

        # Keywords - primary light blue (bright but not harsh)
        Keyword:                        '#3BC4F2',
        Keyword.Constant:               '#3BC4F2',
        Keyword.Declaration:            '#3BC4F2',
        Keyword.Namespace:              '#3BC4F2',
        Keyword.Pseudo:                 '#3BC4F2',
        Keyword.Reserved:               '#3BC4F2',
        Keyword.Type:                   '#3BC4F2',

        # Operators - secondary text (subtle, like comments)
        Operator:                       '#A9B1BB',
        Operator.Word:                  '#A9B1BB',

        # Punctuation
        Punctuation:                    '#E6EDF3',

        # Names/Variables - primary text color (clean default)
        Name:                           '#E6EDF3',
        Name.Attribute:                 '#E6EDF3',
        Name.Variable:                  '#E6EDF3',
        Name.Variable.Class:            '#E6EDF3',
        Name.Variable.Global:           '#E6EDF3',
        Name.Variable.Instance:         '#E6EDF3',

        # Built-ins - soft purple (distinct from keywords, professional)
        Name.Builtin:                   '#C084FC',
        Name.Builtin.Pseudo:            '#C084FC',

        # Function names - secondary CTA orange (stands out nicely)
        Name.Function:                  '#FD6E12',
        Name.Function.Magic:            '#FD6E12',

        # Class names - primary light blue
        Name.Class:                     '#3BC4F2',

        # Package/Module names - warning yellow (matches numbers, stands out)
        Name.Namespace:                 '#FCD34D',

        # Decorators
        Name.Decorator:                 '#FD6E12',

        # Strings - warm terracotta/brown (classic terminal, distinct from blues)
        String:                         '#CE9178',
        String.Backtick:                '#CE9178',
        String.Char:                    '#CE9178',
        String.Doc:                     '#CE9178',
        String.Double:                  '#CE9178',
        String.Escape:                  '#CE9178',
        String.Heredoc:                 '#CE9178',
        String.Interpol:                '#CE9178',
        String.Other:                   '#CE9178',
        String.Regex:                   '#CE9178',
        String.Single:                  '#CE9178',
        String.Symbol:                  '#CE9178',

        # Numbers - warning yellow (subtle highlight)
        Number:                         '#FCD34D',
        Number.Bin:                     '#FCD34D',
        Number.Float:                   '#FCD34D',
        Number.Hex:                     '#FCD34D',
        Number.Integer:                 '#FCD34D',
        Number.Integer.Long:            '#FCD34D',
        Number.Oct:                     '#FCD34D',

        # Literals
        Literal:                        '#E6EDF3',
        Literal.Date:                   '#86EFAC',

        # Generic
        Generic:                        '#E6EDF3',
        Generic.Deleted:                '#FD6E12',
        Generic.Emph:                   'italic #E6EDF3',
        Generic.Error:                  '#FD6E12',
        Generic.Heading:                'bold #3BC4F2',
        Generic.Inserted:               '#86EFAC',
        Generic.Output:                 '#E6EDF3',
        Generic.Prompt:                 '#2AA1CE',
        Generic.Strong:                 'bold #E6EDF3',
        Generic.Subheading:             'bold #3BC4F2',
        Generic.Traceback:              '#FD6E12',

        # Errors
        Error:                          '#FD6E12',

        # Whitespace
        Text:                           '#E6EDF3',
        Whitespace:                     '#E6EDF3',
    }
