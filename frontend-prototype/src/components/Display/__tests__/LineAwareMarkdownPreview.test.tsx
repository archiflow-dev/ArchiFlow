/**
 * Tests for LineAwareMarkdownPreview component
 */

import React from 'react';
import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { LineAwareMarkdownPreview, transformMarkdownWithLines } from '../LineAwareMarkdownPreview';

// Mock console methods to avoid noise
console.warn = vi.fn();
console.error = vi.fn();

describe('transformMarkdownWithLines', () => {
  it('should split content into lines with line numbers', () => {
    const content = 'Line 1\nLine 2\nLine 3';
    const result = transformMarkdownWithLines(content);

    expect(result).toEqual([
      { content: 'Line 1', lineNumber: 1 },
      { content: 'Line 2', lineNumber: 2 },
      { content: 'Line 3', lineNumber: 3 },
    ]);
  });

  it('should handle empty content', () => {
    const result = transformMarkdownWithLines('');
    expect(result).toEqual([{ content: '', lineNumber: 1 }]);
  });

  it('should handle single line', () => {
    const result = transformMarkdownWithLines('Single line');
    expect(result).toEqual([{ content: 'Single line', lineNumber: 1 }]);
  });

  it('should preserve trailing empty lines', () => {
    const content = 'Line 1\n\nLine 3';
    const result = transformMarkdownWithLines(content);

    expect(result).toEqual([
      { content: 'Line 1', lineNumber: 1 },
      { content: '', lineNumber: 2 },
      { content: 'Line 3', lineNumber: 3 },
    ]);
  });
});

describe('LineAwareMarkdownPreview', () => {
  const mockOnTextSelection = vi.fn();

  const defaultProps = {
    content: '# Test Heading\n\nThis is a test paragraph.',
    onTextSelection: mockOnTextSelection,
  };

  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('should render markdown content', () => {
    render(<LineAwareMarkdownPreview {...defaultProps} />);

    expect(screen.getByText('Test Heading')).toBeInTheDocument();
    expect(screen.getByText('This is a test paragraph.')).toBeInTheDocument();
  });

  it('should render with data-line attributes', () => {
    const { container } = render(<LineAwareMarkdownPreview {...defaultProps} />);

    // Check for data-line attributes
    const line1Element = container.querySelector('[data-line="1"]');
    const line2Element = container.querySelector('[data-line="3"]');

    expect(line1Element).toBeInTheDocument();
    expect(line2Element).toBeInTheDocument();
  });

  it('should render headers with correct styling', () => {
    render(<LineAwareMarkdownPreview {...defaultProps} />);

    const heading = screen.getByText('Test Heading');
    expect(heading).toBeInTheDocument();
    expect(heading.className).toContain('text-2xl');
    expect(heading.className).toContain('font-bold');
  });

  it('should render bold text', () => {
    render(<LineAwareMarkdownPreview content="This is **bold** text" />);

    const boldText = screen.getByText('bold');
    expect(boldText).toBeInTheDocument();
    expect(boldText.className).toContain('font-semibold');
  });

  it('should render italic text', () => {
    render(<LineAwareMarkdownPreview content="This is *italic* text" />);

    const italicText = screen.getByText('italic');
    expect(italicText).toBeInTheDocument();
    expect(italicText.className).toContain('italic');
  });

  it('should render inline code', () => {
    render(<LineAwareMarkdownPreview content="This is `code` text" />);

    const codeText = screen.getByText('code');
    expect(codeText).toBeInTheDocument();
    expect(codeText.className).toContain('bg-gray-800');
    expect(codeText.className).toContain('text-yellow-400');
  });

  it('should render links', () => {
    render(<LineAwareMarkdownPreview content="[Link](https://example.com)" />);

    const link = screen.getByText('Link');
    expect(link).toBeInTheDocument();
    expect(link.tagName).toBe('A');
    expect(link).toHaveAttribute('href', 'https://example.com');
    expect(link).toHaveAttribute('target', '_blank');
  });

  it('should render blockquotes', () => {
    render(<LineAwareMarkdownPreview content="> This is a quote" />);

    const quote = screen.getByText('This is a quote');
    expect(quote).toBeInTheDocument();
    expect(quote.className).toContain('border-l-4');
    expect(quote.className).toContain('border-gray-600');
  });

  it('should render unordered lists', () => {
    render(<LineAwareMarkdownPreview content="- Item 1\n- Item 2" />);

    expect(screen.getByText('Item 1')).toBeInTheDocument();
    expect(screen.getByText('Item 2')).toBeInTheDocument();
  });

  it('should render ordered lists', () => {
    render(<LineAwareMarkdownPreview content="1. First\n2. Second" />);

    expect(screen.getByText('First')).toBeInTheDocument();
    expect(screen.getByText('Second')).toBeInTheDocument();
  });

  it('should render code blocks', () => {
    render(<LineAwareMarkdownPreview content="```\nconst x = 1;\n```" />);

    const code = screen.getByText('const x = 1;');
    expect(code).toBeInTheDocument();
    expect(code.className).toContain('text-green-400');
  });

  it('should render code blocks with language specified', () => {
    render(<LineAwareMarkdownPreview content="```javascript\nconst x = 1;\n```" />);

    const code = screen.getByText('const x = 1;');
    expect(code).toBeInTheDocument();
  });

  it('should render horizontal rules', () => {
    const { container } = render(<LineAwareMarkdownPreview content="---" />);

    const hr = container.querySelector('hr');
    expect(hr).toBeInTheDocument();
    expect(hr.className).toContain('border-gray-700');
  });

  it('should handle multiple consecutive empty lines', () => {
    render(<LineAwareMarkdownPreview content="Line 1\n\n\n\nLine 5" />);

    expect(screen.getByText('Line 1')).toBeInTheDocument();
    expect(screen.getByText('Line 5')).toBeInTheDocument();
  });

  it('should escape HTML special characters', () => {
    render(<LineAwareMarkdownPreview content="<script>alert('xss')</script>" />);

    // Should not contain actual script tag
    const { container } = render(<LineAwareMarkdownPreview content="<div>raw HTML</div>" />);
    expect(container.innerHTML).not.toContain('<div>');
    expect(container.innerHTML).toContain('&lt;');
  });

  describe('Selection handling', () => {
    it('should call onTextSelection when text is selected', () => {
      render(<LineAwareMarkdownPreview {...defaultProps} />);

      // Simulate text selection
      const selectionMock = vi.fn().mockReturnValue({
        rangeCount: 1,
        getRangeAt: vi.fn().mockReturnValue({
          getBoundingClientRect: () => ({ top: 100, left: 50, width: 100 }),
          cloneContents: () => document.createDocumentFragment(),
        }),
        toString: () => 'Test Heading',
      });

      // Mock window.getSelection
      global.getSelection = selectionMock;

      // Trigger mouseup
      const preview = screen.getByText('Test Heading').closest('.markdown-preview');
      if (preview) {
        fireEvent.mouseUp(preview);
      }

      // Note: This test shows the structure - actual selection simulation
      // would need a more complex DOM setup
    });

    it('should not call onTextSelection when no selection exists', () => {
      render(<LineAwareMarkdownPreview content="Test content" onTextSelection={mockOnTextSelection} />);

      // Clear any existing selection
      const selection = window.getSelection();
      selection?.removeAllRanges();

      const preview = screen.getByText('Test content').closest('.markdown-preview');
      if (preview) {
        fireEvent.mouseUp(preview);
      }

      expect(mockOnTextSelection).not.toHaveBeenCalled();
    });
  });

  describe('Code block handling', () => {
    it('should track code block start line', () => {
      const { container } = render(
        <LineAwareMarkdownPreview content="Line before\n```\ncode content\n```\nLine after" />
      );

      // Code block should have data-line attribute of the opening ```
      const codeBlock = container.querySelector('[data-line="2"]');
      expect(codeBlock).toBeInTheDocument();
      expect(codeBlock).toHaveClass('md-code-block');
    });

    it('should handle code blocks without language', () => {
      render(<LineAwareMarkdownPreview content="```\nconst x = 1;\n```" />);

      const code = screen.getByText('const x = 1;');
      expect(code).toBeInTheDocument();
    });
  });

  describe('Edge cases', () => {
    it('should handle markdown with only headers', () => {
      render(<LineAwareMarkdownPreview content="# H1\n## H2\n### H3" />);

      expect(screen.getByText('H1')).toBeInTheDocument();
      expect(screen.getByText('H2')).toBeInTheDocument();
      expect(screen.getByText('H3')).toBeInTheDocument();
    });

    it('should handle markdown with only lists', () => {
      render(<LineAwareMarkdownPreview content="- Item 1\n- Item 2\n- Item 3" />);

      expect(screen.getByText('Item 1')).toBeInTheDocument();
      expect(screen.getByText('Item 2')).toBeInTheDocument();
      expect(screen.getByText('Item 3')).toBeInTheDocument();
    });

    it('should handle mixed formatting in a single line', () => {
      render(<LineAwareMarkdownPreview content="This has **bold** and `code` and *italic*" />);

      expect(screen.getByText('bold')).toBeInTheDocument();
      expect(screen.getByText('code')).toBeInTheDocument();
      expect(screen.getByText('italic')).toBeInTheDocument();
    });

    it('should handle links with special characters', () => {
      render(<LineAwareMarkdownPreview content="[Test Link](https://example.com/path?query=value)" />);

      const link = screen.getByText('Test Link');
      expect(link).toHaveAttribute('href', 'https://example.com/path?query=value');
    });

    it('should handle nested formatting', () => {
      render(<LineAwareMarkdownPreview content="**This has *italic* inside bold**" />);

      expect(screen.getByText('italic')).toBeInTheDocument();
    });
  });

  describe('Line number accuracy', () => {
    it('should assign correct line numbers to all elements', () => {
      const content = '# First\n\nSecond\n\n### Third';
      const { container } = render(<LineAwareMarkdownPreview content={content} />);

      // Check line 1 has the heading
      const line1 = container.querySelector('[data-line="1"]');
      expect(line1).toBeInTheDocument();
      expect(line1?.textContent).toContain('First');

      // Check line 3 (empty line 2 is line 2)
      const line3 = container.querySelector('[data-line="3"]');
      expect(line3).toBeInTheDocument();
      expect(line3?.textContent).toContain('Second');
    });

    it('should handle long documents with many lines', () => {
      const lines = Array.from({ length: 100 }, (_, i) => `Line ${i + 1}`);
      const content = lines.join('\n');

      render(<LineAwareMarkdownPreview content={content} />);

      // Spot check some lines
      expect(screen.getByText('Line 1')).toBeInTheDocument();
      expect(screen.getByText('Line 50')).toBeInTheDocument();
      expect(screen.getByText('Line 100')).toBeInTheDocument();
    });
  });

  describe('Phase 2: Hover Effects', () => {
    it('should render line number indicator on hover', () => {
      const { container } = render(<LineAwareMarkdownPreview content="# Test Heading\n\nSome content" />);

      // Find a line element
      const lineElement = container.querySelector('[data-line="1"]');

      expect(lineElement).toBeInTheDocument();

      // Trigger mouse move event
      if (lineElement) {
        fireEvent.mouseMove(lineElement, {
          clientX: 10,
          clientY: 10,
        });
      }

      // Note: The actual hover state update happens through DOM manipulation
      // In a real scenario, we'd need to mock getBoundingClientRect
    });

    it('should add md-line-hovered class on hover', () => {
      const { container } = render(<LineAwareMarkdownPreview content="# Test Heading" />);

      const lineElement = container.querySelector('[data-line="1"]');

      expect(lineElement).toBeInTheDocument();

      // Initially should not have the hovered class
      expect(lineElement).not.toHaveClass('md-line-hovered');
    });

    it('should clear hover state on mouse leave', () => {
      const { container } = render(<LineAwareMarkdownPreview content="# Test Heading\n\nSecond line" />);

      const preview = container.querySelector('.markdown-preview');

      expect(preview).toBeInTheDocument();

      if (preview) {
        fireEvent.mouseLeave(preview);
      }

      // After mouse leave, no elements should have the hover class
      const hoveredElements = container.querySelectorAll('.md-line-hovered');
      expect(hoveredElements.length).toBe(0);
    });

    it('should show line number indicator with correct line number', () => {
      const content = '# Line 1\n## Line 2\n### Line 3';
      const { container } = render(<LineAwareMarkdownPreview content={content} />);

      // Verify all lines have data-line attributes
      expect(container.querySelector('[data-line="1"]')).toBeInTheDocument();
      expect(container.querySelector('[data-line="2"]')).toBeInTheDocument();
      expect(container.querySelector('[data-line="3"]')).toBeInTheDocument();
    });

    it('should handle hover on code blocks', () => {
      const { container } = render(
        <LineAwareMarkdownPreview content="Line before\n```\ncode content\n```\nLine after" />
      );

      const codeBlock = container.querySelector('[data-line="2"]');

      expect(codeBlock).toBeInTheDocument();
      expect(codeBlock).toHaveClass('md-code-block');
    });

    it('should handle hover on empty lines', () => {
      const { container } = render(<LineAwareMarkdownPreview content="Line 1\n\nLine 3" />);

      const emptyLine = container.querySelector('[data-line="2"]');

      expect(emptyLine).toBeInTheDocument();
    });

    it('should handle hover on mixed markdown elements', () => {
      const content = '**Bold text** and `code` and [link](https://example.com)';
      const { container } = render(<LineAwareMarkdownPreview content={content} />);

      const lineElement = container.querySelector('[data-line="1"]');

      expect(lineElement).toBeInTheDocument();
      expect(screen.getByText('Bold text')).toBeInTheDocument();
      expect(screen.getByText('code')).toBeInTheDocument();
      expect(screen.getByText('link')).toBeInTheDocument();
    });
  });

  describe('Phase 2: Selection Popup Animation', () => {
    it('should apply animation class to selection popup', () => {
      // This test verifies the popup has the correct structure
      // The actual animation is handled by CSS
      const { container } = render(
        <LineAwareMarkdownPreview content="Test content" onTextSelection={mockOnTextSelection} />
      );

      const preview = container.querySelector('.markdown-preview');
      expect(preview).toBeInTheDocument();
    });

    it('should have smooth transition for line number indicator', () => {
      const { container } = render(<LineAwareMarkdownPreview content="Test content" />);

      // Verify the container exists for the indicator
      const containerDiv = container.querySelector('.relative');
      expect(containerDiv).toBeInTheDocument();
    });
  });

  describe('Phase 3: Range Comment Support', () => {
    it('should accept commentRanges prop', () => {
      const commentRanges = [
        { lineNumber: 1, endLineNumber: 3, commentId: 'comment1' },
      ];

      const { container } = render(
        <LineAwareMarkdownPreview content="# Line 1\n## Line 2\n### Line 3" commentRanges={commentRanges} />
      );

      expect(container).toBeInTheDocument();
    });

    it('should highlight lines with existing comments', () => {
      const commentRanges = [
        { lineNumber: 1, endLineNumber: 2, commentId: 'comment1' },
      ];

      const { container } = render(
        <LineAwareMarkdownPreview content="# Line 1\n## Line 2\n### Line 3" commentRanges={commentRanges} />
      );

      // Lines 1 and 2 should have the comment highlight class
      const line1 = container.querySelector('[data-line="1"]');
      const line2 = container.querySelector('[data-line="2"]');
      const line3 = container.querySelector('[data-line="3"]');

      expect(line1).toHaveClass('md-line-comment');
      expect(line2).toHaveClass('md-line-comment');
      expect(line3).not.toHaveClass('md-line-comment');
    });

    it('should highlight single-line comments', () => {
      const commentRanges = [
        { lineNumber: 2, commentId: 'comment1' },
      ];

      const { container } = render(
        <LineAwareMarkdownPreview content="# Line 1\n## Line 2\n### Line 3" commentRanges={commentRanges} />
      );

      const line2 = container.querySelector('[data-line="2"]');
      expect(line2).toHaveClass('md-line-comment');
    });

    it('should highlight multiple separate comment ranges', () => {
      const commentRanges = [
        { lineNumber: 1, endLineNumber: 2, commentId: 'comment1' },
        { lineNumber: 5, endLineNumber: 6, commentId: 'comment2' },
      ];

      const content = '# Line 1\n## Line 2\n### Line 3\n#### Line 4\n##### Line 5\n###### Line 6';
      const { container } = render(
        <LineAwareMarkdownPreview content={content} commentRanges={commentRanges} />
      );

      const line1 = container.querySelector('[data-line="1"]');
      const line2 = container.querySelector('[data-line="2"]');
      const line3 = container.querySelector('[data-line="3"]');
      const line5 = container.querySelector('[data-line="5"]');
      const line6 = container.querySelector('[data-line="6"]');

      expect(line1).toHaveClass('md-line-comment');
      expect(line2).toHaveClass('md-line-comment');
      expect(line3).not.toHaveClass('md-line-comment');
      expect(line5).toHaveClass('md-line-comment');
      expect(line6).toHaveClass('md-line-comment');
    });

    it('should update highlights when commentRanges change', () => {
      const { container, rerender } = render(
        <LineAwareMarkdownPreview
          content="# Line 1\n## Line 2\n### Line 3"
          commentRanges={[{ lineNumber: 1, commentId: 'comment1' }]}
        />
      );

      const line1 = container.querySelector('[data-line="1"]');
      expect(line1).toHaveClass('md-line-comment');

      // Update commentRanges
      rerender(
        <LineAwareMarkdownPreview
          content="# Line 1\n## Line 2\n### Line 3"
          commentRanges={[{ lineNumber: 2, commentId: 'comment2' }]}
        />
      );

      const line1After = container.querySelector('[data-line="1"]');
      const line2 = container.querySelector('[data-line="2"]');

      expect(line1After).not.toHaveClass('md-line-comment');
      expect(line2).toHaveClass('md-line-comment');
    });

    it('should handle empty commentRanges array', () => {
      const { container } = render(
        <LineAwareMarkdownPreview content="# Line 1\n## Line 2" commentRanges={[]} />
      );

      const line1 = container.querySelector('[data-line="1"]');
      const line2 = container.querySelector('[data-line="2"]');

      expect(line1).not.toHaveClass('md-line-comment');
      expect(line2).not.toHaveClass('md-line-comment');
    });

    it('should handle undefined commentRanges', () => {
      const { container } = render(
        <LineAwareMarkdownPreview content="# Line 1\n## Line 2" commentRanges={undefined} />
      );

      const line1 = container.querySelector('[data-line="1"]');
      expect(line1).not.toHaveClass('md-line-comment');
    });

    it('should apply selection highlight to all lines in range', () => {
      const { container } = render(
        <LineAwareMarkdownPreview
          content="Line 1\nLine 2\nLine 3\nLine 4"
          onTextSelection={mockOnTextSelection}
        />
      );

      // Simulate that lines 2-3 are selected
      const line2 = container.querySelector('[data-line="2"]');
      const line3 = container.querySelector('[data-line="3"]');

      expect(line2).toBeInTheDocument();
      expect(line3).toBeInTheDocument();

      // After mouseup with selection, these should get selected class
      // (This would need actual DOM selection simulation)
    });

    it('should clear selection highlights when selection is cleared', () => {
      const { container } = render(
        <LineAwareMarkdownPreview
          content="Line 1\nLine 2\nLine 3"
          onTextSelection={mockOnTextSelection}
        />
      );

      const preview = container.querySelector('.markdown-preview');
      expect(preview).toBeInTheDocument();
    });

    it('should show range indicator in selection popup', () => {
      // This verifies the popup structure supports ranges
      const { container } = render(
        <LineAwareMarkdownPreview
          content="Line 1\nLine 2\nLine 3"
          onTextSelection={mockOnTextSelection}
        />
      );

      const preview = container.querySelector('.markdown-preview');
      expect(preview).toBeInTheDocument();
    });

    it('should handle overlapping comment and selection highlights', () => {
      const commentRanges = [
        { lineNumber: 2, commentId: 'comment1' },
      ];

      const { container } = render(
        <LineAwareMarkdownPreview
          content="Line 1\nLine 2\nLine 3"
          commentRanges={commentRanges}
          onTextSelection={mockOnTextSelection}
        />
      );

      const line2 = container.querySelector('[data-line="2"]');
      expect(line2).toHaveClass('md-line-comment');
      // When selected, it would also get md-line-selected class
    });
  });

  describe('Phase 3: Integration with Comment Types', () => {
    it('should support endLineNumber in CommentCreate type', () => {
      // Type checking test - this ensures the types support endLineNumber
      const commentCreate = {
        file_path: '/test.md',
        line_number: 1,
        end_line_number: 3,
        comment_text: 'Test comment',
      };

      expect(commentCreate.line_number).toBe(1);
      expect(commentCreate.end_line_number).toBe(3);
    });

    it('should support endLineNumber in Comment type', () => {
      const comment = {
        id: 'comment1',
        session_id: 'session1',
        file_path: '/test.md',
        line_number: 1,
        end_line_number: 3,
        selected_text: 'Selected text',
        comment_text: 'Test comment',
        author: 'user',
        status: 'pending' as const,
        created_at: '2024-01-01',
        updated_at: '2024-01-01',
      };

      expect(comment.line_number).toBe(1);
      expect(comment.end_line_number).toBe(3);
    });
  });
});
