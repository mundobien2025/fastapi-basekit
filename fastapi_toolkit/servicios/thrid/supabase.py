import uuid
import aiofiles
from fastapi import UploadFile, HTTPException, Depends
from supabase import create_client, Client
from app.config.settings import get_settings


class SupabaseService:
    """Servicio para manejar archivos en Supabase Supabase."""

    def __init__(self, url: str, key: str, bucket_name: str):
        self.client: Client = create_client(url, key)
        self.bucket_name = bucket_name
        self.bucket = self.client.Supabase.from_(bucket_name)

    async def upload_file(
        self, content: bytes, filename: str | None = None
    ) -> tuple[str, str]:
        """Sube un archivo dado el contenido en bytes y un nombre opcional.
        Devuelve (key, public_url).
        """
        try:
            if not filename:
                filename = f"{uuid.uuid4()}"

            resp = self.bucket.upload(filename, content, {"upsert": "true"})
            key = resp.full_path
            url = self.bucket.get_public_url(key)
            return key, url
        except Exception as e:
            raise HTTPException(
                status_code=500, detail=f"Error al subir archivo: {str(e)}"
            )

    async def upload_file_from_uploadfile(
        self, file: UploadFile, filename: str | None = None
    ) -> dict:
        """Alternativa para subir desde
        UploadFile de FastAPI, usa archivo temporal para compatibilidad."""
        try:
            file_extension = file.filename.split(".")[-1]
            if not filename:
                filename = f"{uuid.uuid4()}.{file_extension}"
            else:
                filename = f"{filename}.{file_extension}"

            temp_path = f"/tmp/{filename}"
            async with aiofiles.open(temp_path, "wb") as f:
                content = await file.read()
                await f.write(content)

            with open(temp_path, "rb") as f:
                self.bucket.upload(filename, f)

            url = self.bucket.get_public_url(filename)
            return {"message": "Archivo subido correctamente", "url": url}
        except Exception as e:
            raise HTTPException(
                status_code=500, detail=f"Error al subir archivo: {str(e)}"
            )

    async def delete_file(self, key: str):
        try:
            self.bucket.remove(key)
            return {"message": "Archivo eliminado correctamente"}
        except Exception as e:
            raise HTTPException(
                status_code=500, detail=f"Error al eliminar archivo: {str(e)}"
            )


def get_supabase_service(settings=Depends(get_settings)) -> SupabaseService:
    return SupabaseService(
        settings.SUPABASE_URL, settings.SUPABASE_KEY, settings.SUPABASE_BUCKET
    )
