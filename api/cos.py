import os
import mimetypes
import boto3
from django.conf import settings
from botocore.exceptions import ClientError

class COS:
    """
    Administrador de Cloud Object Storage (COS) con soporte híbrido:
    Local (Carpeta Media) o AWS S3.
    """

    def __init__(self):
        self.storage_type = getattr(settings, 'STORAGE_TYPE', 'local')
        
        if self.storage_type == 'aws':
            self.s3_client = boto3.client(
                's3',
                aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
                aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
                region_name=settings.AWS_S3_REGION_NAME
            )
            self.bucket_name = settings.AWS_STORAGE_BUCKET_NAME

    def save_file(self, file_obj, folder_path, file_name):
        full_path = os.path.join(folder_path, file_name).replace("\\", "/")

        if self.storage_type == 'aws':
            try:
                # Detectamos el MIME type dinámicamente para que el navegador/app lo visualice bien
                content_type, _ = mimetypes.guess_type(file_name)
                extra_args = {}
                if content_type:
                    extra_args['ContentType'] = content_type

                # Reseteamos el puntero del archivo por seguridad
                if hasattr(file_obj, 'seek'):
                    file_obj.seek(0)

                self.s3_client.upload_fileobj(
                    file_obj,
                    self.bucket_name,
                    full_path,
                    ExtraArgs=extra_args
                )
                return full_path
            except ClientError as e:
                print(f"❌ Error subiendo a AWS S3: {e}")
                return None
        else:
            # Lógica Local
            media_path = os.path.join(settings.MEDIA_ROOT, folder_path)
            if not os.path.exists(media_path):
                os.makedirs(media_path, exist_ok=True)
            
            save_path = os.path.join(media_path, file_name)
            
            if hasattr(file_obj, 'seek'):
                file_obj.seek(0)

            with open(save_path, 'wb+') as destination:
                if hasattr(file_obj, 'chunks'):
                    for chunk in file_obj.chunks():
                        destination.write(chunk)
                else:
                    destination.write(file_obj.read())
            
            return full_path

    def get_url(self, relative_path: str, skip_media=False):
        if not relative_path:
            return None

        # Si ya es una URL absoluta, la devolvemos tal cual
        if relative_path.startswith('http://') or relative_path.startswith('https://'):
            return relative_path

        clean_path = relative_path.lstrip('/')

        if self.storage_type == 'aws':
            return f"https://{self.bucket_name}.s3.{settings.AWS_S3_REGION_NAME}.amazonaws.com/{clean_path}"
        else:
            base_url = f"{settings.DOMAIN}{settings.MEDIA_URL}" if not skip_media else settings.DOMAIN
            if not base_url.endswith('/'):
                base_url += "/"
            return f"{base_url}{clean_path}"

    def delete_file(self, relative_path):
        if not relative_path:
            return False

        clean_path = relative_path.lstrip('/')

        if self.storage_type == 'aws':
            try:
                self.s3_client.delete_object(Bucket=self.bucket_name, Key=clean_path)
                return True
            except ClientError as e:
                print(f"❌ Error borrando archivo de S3: {e}")
                return False
        else:
            full_path = os.path.join(settings.MEDIA_ROOT, clean_path)
            if os.path.exists(full_path):
                os.remove(full_path)
                return True
            return False

storage_manager = COS()