"""
File utility functions for handling uploads and temporary files.
"""
import os
import uuid
import shutil
from pathlib import Path
from typing import Optional
from fastapi import UploadFile

async def save_upload_file_temp(upload_file: UploadFile, temp_dir: Path) -> Path:
    """
    Save an upload file to a temporary location.
    
    Args:
        upload_file: The uploaded file
        temp_dir: Directory to save the file in
        
    Returns:
        Path to the saved temporary file
    """
    # Ensure the temp directory exists
    os.makedirs(temp_dir, exist_ok=True)
    
    # Generate a unique filename
    file_id = str(uuid.uuid4())
    filename = upload_file.filename
    
    # Get file extension
    if filename and "." in filename:
        ext = filename.split(".")[-1]
        temp_filename = f"{file_id}.{ext}"
    else:
        temp_filename = file_id
    
    # Create the full path
    temp_file_path = temp_dir / temp_filename
    
    # Save the file
    with open(temp_file_path, "wb") as buffer:
        # Read file in chunks to handle large files
        chunk_size = 1024 * 1024  # 1MB chunks
        content = await upload_file.read(chunk_size)
        while content:
            buffer.write(content)
            content = await upload_file.read(chunk_size)
    
    return temp_file_path

def get_temp_file_path(filename: str, temp_dir: Path, prefix: Optional[str] = None) -> Path:
    """
    Generate a path for a temporary file.
    
    Args:
        filename: Original filename
        temp_dir: Directory to save the file in
        prefix: Optional prefix for the filename
        
    Returns:
        Path to the temporary file
    """
    # Ensure the temp directory exists
    os.makedirs(temp_dir, exist_ok=True)
    
    # Generate a unique ID
    file_id = str(uuid.uuid4())
    
    # Get file extension
    if filename and "." in filename:
        ext = filename.split(".")[-1]
        if prefix:
            temp_filename = f"{prefix}_{file_id}.{ext}"
        else:
            temp_filename = f"{file_id}.{ext}"
    else:
        if prefix:
            temp_filename = f"{prefix}_{file_id}"
        else:
            temp_filename = file_id
    
    # Create the full path
    return temp_dir / temp_filename

def cleanup_temp_files(temp_dir: Path, max_age_hours: int = 24) -> int:
    """
    Clean up temporary files older than the specified age.
    
    Args:
        temp_dir: Directory containing temporary files
        max_age_hours: Maximum age of files in hours
        
    Returns:
        Number of files removed
    """
    import time
    
    if not temp_dir.exists():
        return 0
    
    current_time = time.time()
    max_age_seconds = max_age_hours * 3600
    removed_count = 0
    
    for file_path in temp_dir.glob("*"):
        if file_path.is_file():
            file_age = current_time - os.path.getmtime(file_path)
            if file_age > max_age_seconds:
                try:
                    os.remove(file_path)
                    removed_count += 1
                except Exception:
                    pass
    
    return removed_count
