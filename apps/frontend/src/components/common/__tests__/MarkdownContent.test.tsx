import React from 'react';
import { render, screen } from '@testing-library/react';
import '@testing-library/jest-dom';
import MarkdownContent from '../MarkdownContent';

describe('MarkdownContent', () => {
  it('renders plain text content', () => {
    render(<MarkdownContent content="Hello, world!" />);
    expect(screen.getByText('Hello, world!')).toBeInTheDocument();
  });

  it('renders a markdown paragraph', () => {
    render(<MarkdownContent content="This is a paragraph." />);
    expect(screen.getByText('This is a paragraph.')).toBeInTheDocument();
  });

  it('renders markdown headings', () => {
    render(
      <MarkdownContent content={'# Heading 1\n## Heading 2\n### Heading 3'} />
    );
    expect(
      screen.getByRole('heading', { level: 1, name: 'Heading 1' })
    ).toBeInTheDocument();
    expect(
      screen.getByRole('heading', { level: 2, name: 'Heading 2' })
    ).toBeInTheDocument();
    expect(
      screen.getByRole('heading', { level: 3, name: 'Heading 3' })
    ).toBeInTheDocument();
  });

  it('renders a markdown unordered list', () => {
    render(<MarkdownContent content={'- Item A\n- Item B\n- Item C'} />);
    const items = screen.getAllByRole('listitem');
    expect(items).toHaveLength(3);
    expect(screen.getByText('Item A')).toBeInTheDocument();
    expect(screen.getByText('Item B')).toBeInTheDocument();
    expect(screen.getByText('Item C')).toBeInTheDocument();
  });

  it('renders a markdown ordered list', () => {
    render(<MarkdownContent content={'1. First\n2. Second'} />);
    const items = screen.getAllByRole('listitem');
    expect(items).toHaveLength(2);
    expect(screen.getByText('First')).toBeInTheDocument();
  });

  it('renders inline code', () => {
    render(<MarkdownContent content="Use `console.log()` to debug." />);
    expect(screen.getByText('console.log()')).toBeInTheDocument();
  });

  it('renders a fenced code block', () => {
    render(<MarkdownContent content={'```\nconst x = 1;\n```'} />);
    expect(screen.getByText('const x = 1;')).toBeInTheDocument();
  });

  it('renders a link with target="_blank" and rel="noopener noreferrer"', () => {
    render(<MarkdownContent content="[Click here](https://example.com)" />);
    const link = screen.getByRole('link', { name: /click here/i });
    expect(link).toHaveAttribute('href', 'https://example.com');
    expect(link).toHaveAttribute('target', '_blank');
    expect(link).toHaveAttribute('rel', 'noopener noreferrer');
  });

  it('renders a blockquote', () => {
    render(<MarkdownContent content="> This is a quote." />);
    expect(screen.getByText('This is a quote.')).toBeInTheDocument();
    const blockquote = document.querySelector('blockquote');
    expect(blockquote).toBeInTheDocument();
  });

  it('renders non-string content as a JSON code block', () => {
    const obj = { key: 'value', count: 42 };
    render(<MarkdownContent content={obj as never} />);
    // Should contain the JSON representation
    expect(screen.getByText(/"key"/)).toBeInTheDocument();
    expect(screen.getByText(/"value"/)).toBeInTheDocument();
  });

  it('renders a markdown table', () => {
    const tableMarkdown = `| Name | Age |\n| --- | --- |\n| Alice | 30 |\n| Bob | 25 |`;
    render(<MarkdownContent content={tableMarkdown} />);
    expect(screen.getByRole('table')).toBeInTheDocument();
    expect(screen.getByText('Alice')).toBeInTheDocument();
    expect(screen.getByText('Bob')).toBeInTheDocument();
  });

  it('renders bold and italic text', () => {
    render(<MarkdownContent content="**bold text** and *italic text*" />);
    expect(screen.getByText('bold text')).toBeInTheDocument();
    expect(screen.getByText('italic text')).toBeInTheDocument();
  });
});
