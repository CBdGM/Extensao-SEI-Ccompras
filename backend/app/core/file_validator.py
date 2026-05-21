import hashlib
import os
from typing import Tuple
from fastapi import UploadFile, HTTPException, status

# PDF magic bytes — %PDF
PDF_MAGIC = b"%PDF"

ALLOWED_EXTENSIONS = {"pdf"}
ALLOWED_MIME_TYPES = {"application/pdf", "application/x-pdf"}


def validate_extension(filename: str) -> str:
    """Return the lowercase extension or raise HTTPException."""
    if not filename or "." not in filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Nome de arquivo inválido: extensão não encontrada",
        )
    ext = filename.rsplit(".", 1)[-1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Tipo de arquivo não permitido. Apenas PDF é aceito.",
        )
    return ext


def validate_magic_bytes(content: bytes, ext: str) -> None:
    """Verify file signature matches declared extension."""
    if ext == "pdf":
        if not content[:4] == PDF_MAGIC:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Arquivo inválido: assinatura do arquivo não corresponde ao tipo PDF.",
            )


def validate_mime_type(mime_type: str) -> None:
    """Reject clearly wrong MIME types."""
    if mime_type and mime_type not in ALLOWED_MIME_TYPES:
        # Some valid PDFs come as application/octet-stream — allow that too
        if mime_type != "application/octet-stream":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Tipo MIME não permitido: {mime_type}",
            )


def validate_file_size(size: int, max_bytes: int) -> None:
    """Reject files exceeding max_bytes."""
    if size > max_bytes:
        max_mb = max_bytes // (1024 * 1024)
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"Arquivo excede o tamanho máximo de {max_mb}MB",
        )


def block_executable(filename: str, content: bytes) -> None:
    """Block common executable signatures."""
    dangerous_extensions = {
        "exe", "bat", "cmd", "sh", "ps1", "js", "vbs", "msi",
        "dll", "com", "scr", "jar", "py", "rb", "php",
    }
    if "." in filename:
        ext = filename.rsplit(".", 1)[-1].lower()
        if ext in dangerous_extensions:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Tipo de arquivo executável não é permitido",
            )
    # MZ header (PE executable)
    if content[:2] == b"MZ":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Arquivo executável detectado e bloqueado",
        )
    # ELF header
    if content[:4] == b"\x7fELF":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Arquivo executável detectado e bloqueado",
        )


def calculate_hashes(content: bytes) -> Tuple[str, str]:
    """Return (sha256_hex, md5_hex) for the given bytes."""
    sha256 = hashlib.sha256(content).hexdigest()
    md5 = hashlib.md5(content).hexdigest()
    return sha256, md5


def safe_filename(original: str) -> str:
    """Sanitize filename to prevent path traversal."""
    name = os.path.basename(original)
    # Keep only safe characters
    safe = "".join(c for c in name if c.isalnum() or c in "._- ")
    safe = safe.strip()
    if not safe:
        safe = "arquivo"
    return safe
