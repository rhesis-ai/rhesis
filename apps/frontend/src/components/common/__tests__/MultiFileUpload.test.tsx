import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import MultiFileUpload from '../MultiFileUpload';

describe('MultiFileUpload', () => {
  const defaultProps = {
    selectedFiles: [] as File[],
    onFilesSelect: jest.fn(),
    onFileRemove: jest.fn(),
  };

  beforeEach(() => {
    jest.clearAllMocks();
  });

  describe('rendering', () => {
    it('renders the drop zone with instructions', () => {
      render(<MultiFileUpload {...defaultProps} />);

      expect(
        screen.getByText('Drag & drop or click to attach files')
      ).toBeInTheDocument();
      expect(
        screen.getByText(/Images, PDFs, or audio/)
      ).toBeInTheDocument();
    });

    it('renders with disabled state', () => {
      render(<MultiFileUpload {...defaultProps} disabled />);

      const dropZone = screen.getByText(
        'Drag & drop or click to attach files'
      ).closest('div[class*="MuiPaper"]');
      expect(dropZone).toBeInTheDocument();
    });

    it('renders staged files list', () => {
      const files = [
        new File(['img'], 'photo.png', { type: 'image/png' }),
        new File(['pdf'], 'document.pdf', { type: 'application/pdf' }),
      ];

      render(<MultiFileUpload {...defaultProps} selectedFiles={files} />);

      expect(screen.getByText('photo.png')).toBeInTheDocument();
      expect(screen.getByText('document.pdf')).toBeInTheDocument();
    });
  });

  describe('file selection', () => {
    it('calls onFilesSelect when valid files are selected via input', async () => {
      const user = userEvent.setup();
      const onFilesSelect = jest.fn();

      render(
        <MultiFileUpload {...defaultProps} onFilesSelect={onFilesSelect} />
      );

      const file = new File(['image data'], 'test.png', {
        type: 'image/png',
      });

      const input = document.querySelector(
        'input[type="file"]'
      ) as HTMLInputElement;
      expect(input).toBeInTheDocument();

      await user.upload(input, file);

      expect(onFilesSelect).toHaveBeenCalledWith([file]);
    });

    it('accepts PDF files', async () => {
      const user = userEvent.setup();
      const onFilesSelect = jest.fn();

      render(
        <MultiFileUpload {...defaultProps} onFilesSelect={onFilesSelect} />
      );

      const file = new File(['pdf data'], 'doc.pdf', {
        type: 'application/pdf',
      });
      const input = document.querySelector(
        'input[type="file"]'
      ) as HTMLInputElement;

      await user.upload(input, file);

      expect(onFilesSelect).toHaveBeenCalledWith([file]);
    });

    it('accepts audio files', async () => {
      const user = userEvent.setup();
      const onFilesSelect = jest.fn();

      render(
        <MultiFileUpload {...defaultProps} onFilesSelect={onFilesSelect} />
      );

      const file = new File(['audio data'], 'recording.mp3', {
        type: 'audio/mpeg',
      });
      const input = document.querySelector(
        'input[type="file"]'
      ) as HTMLInputElement;

      await user.upload(input, file);

      expect(onFilesSelect).toHaveBeenCalledWith([file]);
    });

    it('accepts multiple files at once', async () => {
      const user = userEvent.setup();
      const onFilesSelect = jest.fn();

      render(
        <MultiFileUpload {...defaultProps} onFilesSelect={onFilesSelect} />
      );

      const files = [
        new File(['a'], 'a.png', { type: 'image/png' }),
        new File(['b'], 'b.pdf', { type: 'application/pdf' }),
      ];
      const input = document.querySelector(
        'input[type="file"]'
      ) as HTMLInputElement;

      await user.upload(input, files);

      expect(onFilesSelect).toHaveBeenCalledWith(files);
    });
  });

  describe('validation', () => {
    it('rejects files with unsupported MIME types', () => {
      const onFilesSelect = jest.fn();

      render(
        <MultiFileUpload {...defaultProps} onFilesSelect={onFilesSelect} />
      );

      const file = new File(['video'], 'clip.mp4', { type: 'video/mp4' });
      const input = document.querySelector(
        'input[type="file"]'
      ) as HTMLInputElement;

      // Use fireEvent to bypass browser-level accept attribute filtering
      // so our application-level validation is tested
      fireEvent.change(input, { target: { files: [file] } });

      expect(onFilesSelect).not.toHaveBeenCalled();
      expect(screen.getByText(/unsupported type/i)).toBeInTheDocument();
    });

    it('rejects files that exceed maxFileSize', async () => {
      const user = userEvent.setup();
      const onFilesSelect = jest.fn();
      const smallMaxSize = 100; // 100 bytes

      render(
        <MultiFileUpload
          {...defaultProps}
          onFilesSelect={onFilesSelect}
          maxFileSize={smallMaxSize}
        />
      );

      // Create a file larger than 100 bytes
      const largeContent = 'x'.repeat(200);
      const file = new File([largeContent], 'large.png', {
        type: 'image/png',
      });
      const input = document.querySelector(
        'input[type="file"]'
      ) as HTMLInputElement;

      await user.upload(input, file);

      expect(onFilesSelect).not.toHaveBeenCalled();
      expect(screen.getByText(/exceeds.*limit/i)).toBeInTheDocument();
    });

    it('rejects files that would exceed maxTotalSize', async () => {
      const user = userEvent.setup();
      const onFilesSelect = jest.fn();
      const maxTotalSize = 500;

      render(
        <MultiFileUpload
          {...defaultProps}
          onFilesSelect={onFilesSelect}
          maxTotalSize={maxTotalSize}
          existingFilesSize={400}
        />
      );

      const content = 'x'.repeat(200);
      const file = new File([content], 'extra.png', { type: 'image/png' });
      const input = document.querySelector(
        'input[type="file"]'
      ) as HTMLInputElement;

      await user.upload(input, file);

      expect(onFilesSelect).not.toHaveBeenCalled();
      expect(screen.getByText(/total limit/i)).toBeInTheDocument();
    });

    it('rejects files when max file count is exceeded', async () => {
      const user = userEvent.setup();
      const onFilesSelect = jest.fn();

      // Already have 2 files staged, max is 2
      const existingFiles = [
        new File(['a'], 'a.png', { type: 'image/png' }),
        new File(['b'], 'b.png', { type: 'image/png' }),
      ];

      render(
        <MultiFileUpload
          {...defaultProps}
          selectedFiles={existingFiles}
          onFilesSelect={onFilesSelect}
          maxFiles={2}
        />
      );

      const file = new File(['c'], 'c.png', { type: 'image/png' });
      const input = document.querySelector(
        'input[type="file"]'
      ) as HTMLInputElement;

      await user.upload(input, file);

      expect(onFilesSelect).not.toHaveBeenCalled();
      expect(screen.getByText(/maximum 2 files/i)).toBeInTheDocument();
    });
  });

  describe('file removal', () => {
    it('calls onFileRemove with correct index when remove button is clicked', async () => {
      const user = userEvent.setup();
      const onFileRemove = jest.fn();

      const files = [
        new File(['a'], 'first.png', { type: 'image/png' }),
        new File(['b'], 'second.pdf', { type: 'application/pdf' }),
      ];

      const { container } = render(
        <MultiFileUpload
          {...defaultProps}
          selectedFiles={files}
          onFileRemove={onFileRemove}
        />
      );

      // Target the close icon buttons within list items (not the drop zone)
      const closeButtons = container.querySelectorAll(
        'li button[class*="MuiIconButton"]'
      );
      expect(closeButtons).toHaveLength(2);

      // Remove second file (index 1)
      await user.click(closeButtons[1]);

      expect(onFileRemove).toHaveBeenCalledWith(1);
    });
  });
});
