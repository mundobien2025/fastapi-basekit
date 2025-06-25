import uuid
import aiofiles
from app.config.supabase import supabase
from app.config.settings import get_settings
from fastapi import UploadFile, HTTPException

settings = get_settings()


class StorageService:
    """Controlador para manejar la subida de archivos a Supabase Storage."""

    @staticmethod
    async def upload_file(file: UploadFile, filename: str = None) -> dict:
        """Sube un archivo a Supabase Storage.

        Args:
            file (UploadFile): Archivo recibido en la petición.
            filename (str, opcional): Nombre personalizado del archivo.
                                      Si no se especifica, se genera un UUID.

        Returns:
            dict: Mensaje y URL del archivo subido.
        """
        try:
            # Obtener la extensión del archivo
            file_extension = file.filename.split(".")[-1]

            # Si no se proporciona filename, generar uno único
            if not filename:
                filename = f"{uuid.uuid4()}.{file_extension}"
            else:
                filename = f"{filename}.{file_extension}"

            # Guardar temporalmente el archivo
            temp_path = f"/tmp/{filename}"
            async with aiofiles.open(temp_path, "wb") as buffer:
                content = await file.read()
                await buffer.write(content)

            # Subir el archivo a Supabase Storage
            with open(temp_path, "rb") as f:
                try:
                    supabase.storage.from_(settings.SUPABASE_BUCKET).upload(
                        filename, f
                    )
                except Exception as e:
                    error_message = str(e)
                    if "The resource already exists" in error_message:
                        raise HTTPException(
                            status_code=409,
                            detail="El recurso ya existe.",
                        )
                    raise

            # Obtener la URL pública
            file_url = supabase.storage.from_(
                settings.SUPABASE_BUCKET
            ).get_public_url(filename)

            return {"message": "Archivo subido correctamente", "url": file_url}

        except HTTPException as e:
            raise e  # Re-lanzar HTTPException si ya fue capturada
        except Exception as e:
            raise HTTPException(
                status_code=500, detail=f"Error al subir el archivo: {str(e)}"
            )

    @staticmethod
    async def delete_file(file_path: str):
        """Elimina un archivo de Supabase Storage."""
        try:
            # Extraer el nombre del archivo desde la URL completa
            file_name = file_path.split("/")[-1]
            supabase.storage.from_(settings.SUPABASE_BUCKET).remove(file_name)
            return {"message": "Archivo eliminado correctamente"}
        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=f"Error al eliminar el archivo: {str(e)}",
            )
