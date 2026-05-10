import os
import boto3
from django.conf import settings
from botocore.exceptions import NoCredentialsError, ClientError

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
        """
        Guarda un archivo en el almacenamiento configurado.
        
        :param file_obj: El objeto del archivo (ej. request.FILES['archivo'])
        :param folder_path: Carpeta relativa (ej. 'profiles/avatars')
        :param file_name: Nombre final del archivo
        :return: La ruta relativa guardada
        """
        full_path = os.path.join(folder_path, file_name)

        if self.storage_type == 'aws':
            try:
                self.s3_client.upload_fileobj(
                    file_obj,
                    self.bucket_name,
                    full_path,
                    ExtraArgs={'ACL': 'public-read'} # Opcional: ajustar según política
                )
                return full_path
            except ClientError as e:
                print(f"Error subiendo a AWS: {e}")
                return None
        else:
            # Lógica Local
            media_path = os.path.join(settings.MEDIA_ROOT, folder_path)
            
            # Crear la carpeta si no existe
            if not os.path.exists(media_path):
                os.makedirs(media_path, exist_ok=True)
            
            save_path = os.path.join(media_path, file_name)
            
            with open(save_path, 'wb+') as destination:
                for chunk in file_obj.chunks():
                    destination.write(chunk)
            
            return full_path

    def get_url(self, relative_path:str, skip_media=False):
        """
        Devuelve la URL absoluta para acceder al recurso.
        """
        if not relative_path:
            return None

        if self.storage_type == 'aws':
            return f"https://{self.bucket_name}.s3.{settings.AWS_S3_REGION_NAME}.amazonaws.com/{relative_path}"
        else:
            # Asegura que MEDIA_URL termine en /
            base_url = f"{settings.DOMAIN}{settings.MEDIA_URL}" if not skip_media else settings.DOMAIN
            print("BASE URL:  ", base_url)
            if not base_url.endswith('/') and not relative_path.startswith('/'):
                base_url += "/"
            return f"{base_url}{relative_path}"

    def delete_file(self, relative_path):
        """
        Elimina un archivo del almacenamiento.
        """
        if self.storage_type == 'aws':
            try:
                self.s3_client.delete_object(Bucket=self.bucket_name, Key=relative_path)
                return True
            except ClientError:
                return False
        else:
            full_path = os.path.join(settings.MEDIA_ROOT, relative_path)
            full_path = full_path.replace(f"{settings.DOMAIN}{settings.MEDIA_URL}", "")
            if os.path.exists(full_path):
                print("Si existe")
                os.remove(full_path)
                return True
            else:
                print("No existe")
            return False

# Instancia global para importar en los ViewSets o Serializers
storage_manager = COS()