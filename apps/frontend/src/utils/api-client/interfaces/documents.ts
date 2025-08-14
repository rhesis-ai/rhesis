export interface ProcessedDocument {
    id: string;
    name: string;
    description: string;
    path: string;
    content: string;
    originalName: string;
    status: 'uploading' | 'extracting' | 'generating' | 'completed' | 'error';
  }
  
  export interface Document {
    name: string;
    description: string;
    content: string;
  }
  
  // For upload response
  export interface DocumentUploadResponse {
    path: string;
  }
  
  // For metadata generation response
  export interface DocumentMetadata {
    name: string;
    description: string;
  }