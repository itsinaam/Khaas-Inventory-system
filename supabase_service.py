from supabase import create_client
import os
from dotenv import load_dotenv
import uuid
from pathlib import Path

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

BUCKET_NAME = "products-images"


def upload_product_image(file_content: bytes, filename: str, content_type: str = "image/jpeg") -> str:
    """
    Upload an image to Supabase storage and return the public URL.
    
    Args:
        file_content: The binary content of the image file
        filename: Original filename (will be made unique)
        content_type: MIME type of the image (default: image/jpeg)
    
    Returns:
        Public URL of the uploaded image
    
    Raises:
        Exception: If upload fails
    """
    try:
        # Generate a unique filename to avoid collisions
        file_extension = Path(filename).suffix
        unique_filename = f"{uuid.uuid4()}{file_extension}"
        
        # Upload to Supabase storage
        supabase.storage.from_(BUCKET_NAME).upload(
            path=unique_filename,
            file=file_content,
            file_options={
                "content-type": content_type
            }
        )
        
        # Get public URL
        public_url = supabase.storage.from_(BUCKET_NAME).get_public_url(unique_filename)
        return public_url
        
    except Exception as e:
        raise Exception(f"Failed to upload image: {str(e)}")


def delete_product_image(image_url: str) -> bool:
    """
    Delete an image from Supabase storage.
    
    Args:
        image_url: The public URL of the image to delete
    
    Returns:
        True if deletion was successful, False otherwise
    """
    try:
        # Extract filename from URL
        # URL format: https://{project}.supabase.co/storage/v1/object/public/{bucket}/{filename}
        filename = image_url.split(f"{BUCKET_NAME}/")[-1]
        
        # Delete from storage
        supabase.storage.from_(BUCKET_NAME).remove([filename])
        return True
        
    except Exception as e:
        print(f"Failed to delete image: {str(e)}")
        return False


def get_content_type(filename: str) -> str:
    """
    Determine content type based on file extension.
    
    Args:
        filename: Name of the file
    
    Returns:
        MIME type string
    """
    extension = Path(filename).suffix.lower()
    content_types = {
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png": "image/png",
        ".gif": "image/gif",
        ".webp": "image/webp",
        ".svg": "image/svg+xml",
    }
    return content_types.get(extension, "image/jpeg")
