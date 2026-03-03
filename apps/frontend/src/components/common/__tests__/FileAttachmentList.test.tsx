import React from 'react';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import FileAttachmentList from '../FileAttachmentList';
import { FileResponse } from '@/utils/api-client/interfaces/file';
import { createMockFileResponse } from '@/__mocks__/test-utils';

// Mock the ApiClientFactory for AuthImage blob fetching
jest.mock('@/utils/api-client/client-factory', () => ({
  ApiClientFactory: jest.fn().mockImplementation(() => ({
    getFilesClient: () => ({
      getFileContent: jest.fn().mockResolvedValue(new Blob(['fake'])),
    }),
  })),
}));

// Mock URL.createObjectURL and revokeObjectURL
const mockCreateObjectURL = jest.fn(() => 'blob:mock-url');
const mockRevokeObjectURL = jest.fn();
global.URL.createObjectURL = mockCreateObjectURL;
global.URL.revokeObjectURL = mockRevokeObjectURL;

describe('FileAttachmentList', () => {
  const defaultProps = {
    files: [] as FileResponse[],
    sessionToken: 'mock-token',
  };

  beforeEach(() => {
    jest.clearAllMocks();
  });

  describe('rendering', () => {
    it('returns null when no files are provided', () => {
      const { container } = render(
        <FileAttachmentList {...defaultProps} />
      );
      expect(container.firstChild).toBeNull();
    });

    it('shows loading skeleton when isLoading is true', () => {
      const { container } = render(
        <FileAttachmentList {...defaultProps} isLoading />
      );
      // Skeleton renders as span elements with MuiSkeleton class
      const skeletons = container.querySelectorAll(
        'span[class*="MuiSkeleton"]'
      );
      expect(skeletons.length).toBeGreaterThan(0);
    });

    it('renders a list of files with filenames', () => {
      const files: FileResponse[] = [
        createMockFileResponse({
          id: 'file-1',
          filename: 'screenshot.png',
          content_type: 'image/png',
          size_bytes: 2048,
        }) as FileResponse,
        createMockFileResponse({
          id: 'file-2',
          filename: 'report.pdf',
          content_type: 'application/pdf',
          size_bytes: 10240,
        }) as FileResponse,
      ];

      render(<FileAttachmentList {...defaultProps} files={files} />);

      expect(screen.getByText('screenshot.png')).toBeInTheDocument();
      expect(screen.getByText('report.pdf')).toBeInTheDocument();
    });

    it('displays file sizes', () => {
      const files: FileResponse[] = [
        createMockFileResponse({
          id: 'file-1',
          filename: 'small.png',
          size_bytes: 1024,
        }) as FileResponse,
      ];

      render(<FileAttachmentList {...defaultProps} files={files} />);

      expect(screen.getByText('1 KB')).toBeInTheDocument();
    });
  });

  describe('file type icons', () => {
    it('renders image thumbnail for image files', async () => {
      const files: FileResponse[] = [
        createMockFileResponse({
          id: 'file-img',
          filename: 'photo.jpg',
          content_type: 'image/jpeg',
        }) as FileResponse,
      ];

      render(<FileAttachmentList {...defaultProps} files={files} />);

      // AuthImage initially shows a skeleton, then fetches
      expect(screen.getByText('photo.jpg')).toBeInTheDocument();
    });

    it('renders PDF icon for PDF files', () => {
      const files: FileResponse[] = [
        createMockFileResponse({
          id: 'file-pdf',
          filename: 'document.pdf',
          content_type: 'application/pdf',
        }) as FileResponse,
      ];

      const { container } = render(
        <FileAttachmentList {...defaultProps} files={files} />
      );

      // PictureAsPdfIcon renders an SVG
      const svgIcon = container.querySelector(
        'svg[data-testid="PictureAsPdfIcon"]'
      );
      expect(svgIcon).toBeInTheDocument();
    });

    it('renders audio icon for audio files', () => {
      const files: FileResponse[] = [
        createMockFileResponse({
          id: 'file-audio',
          filename: 'recording.mp3',
          content_type: 'audio/mpeg',
        }) as FileResponse,
      ];

      const { container } = render(
        <FileAttachmentList {...defaultProps} files={files} />
      );

      const svgIcon = container.querySelector(
        'svg[data-testid="AudioFileIcon"]'
      );
      expect(svgIcon).toBeInTheDocument();
    });
  });

  describe('delete functionality', () => {
    it('renders delete button when onDelete is provided', () => {
      const files: FileResponse[] = [
        createMockFileResponse({
          id: 'file-1',
          filename: 'test.png',
        }) as FileResponse,
      ];

      render(
        <FileAttachmentList
          {...defaultProps}
          files={files}
          onDelete={jest.fn()}
        />
      );

      expect(
        screen.getByRole('button', { name: /delete file/i })
      ).toBeInTheDocument();
    });

    it('does not render delete button when onDelete is not provided', () => {
      const files: FileResponse[] = [
        createMockFileResponse({
          id: 'file-1',
          filename: 'test.png',
        }) as FileResponse,
      ];

      render(<FileAttachmentList {...defaultProps} files={files} />);

      expect(
        screen.queryByRole('button', { name: /delete file/i })
      ).not.toBeInTheDocument();
    });

    it('calls onDelete with file id when delete button is clicked', async () => {
      const user = userEvent.setup();
      const onDelete = jest.fn();

      const files: FileResponse[] = [
        createMockFileResponse({
          id: 'file-to-delete',
          filename: 'remove-me.png',
        }) as FileResponse,
      ];

      render(
        <FileAttachmentList
          {...defaultProps}
          files={files}
          onDelete={onDelete}
        />
      );

      await user.click(
        screen.getByRole('button', { name: /delete file/i })
      );

      expect(onDelete).toHaveBeenCalledWith('file-to-delete');
    });
  });

  describe('multiple files', () => {
    it('renders all files in the list', () => {
      const files: FileResponse[] = [
        createMockFileResponse({
          id: 'f1',
          filename: 'image1.png',
          content_type: 'image/png',
        }) as FileResponse,
        createMockFileResponse({
          id: 'f2',
          filename: 'doc.pdf',
          content_type: 'application/pdf',
        }) as FileResponse,
        createMockFileResponse({
          id: 'f3',
          filename: 'audio.wav',
          content_type: 'audio/wav',
        }) as FileResponse,
      ];

      render(<FileAttachmentList {...defaultProps} files={files} />);

      expect(screen.getByText('image1.png')).toBeInTheDocument();
      expect(screen.getByText('doc.pdf')).toBeInTheDocument();
      expect(screen.getByText('audio.wav')).toBeInTheDocument();
    });
  });
});
