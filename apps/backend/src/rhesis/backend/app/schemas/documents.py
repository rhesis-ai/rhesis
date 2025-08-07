import os
from pydantic import BaseModel, model_validator
from typing import Optional


class Document(BaseModel):
    name: str
    description: str
    path: Optional[str] = None
    content: Optional[str] = None

    @model_validator(mode='after')
    def validate_document(self):
        # Check that either path or content is provided
        if not self.path and not self.content:
            raise ValueError('Either path or content must be provided')
        
        # If path is provided, check that file exists
        if self.path and not os.path.exists(self.path):
            raise ValueError(f"Document not found at path: {self.path}. Note: Documents are automatically cleaned up after processing, you may need to re-upload.")
            
        return self
