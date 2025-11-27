import os
import tempfile
from fastapi import UploadFile

def save_temp_file(upload_file: UploadFile) -> str:
  suffix = os.path.splitext(upload_file.filename or "")[1] or ".webm"
  fd, path = tempfile.mkstemp(suffix=suffix)
  with os.fdopen(fd, "wb") as f:
    f.write(upload_file.file.read())
  return path
