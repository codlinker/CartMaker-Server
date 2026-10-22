from django.core.management.base import BaseCommand
from botocore.exceptions import ClientError

from api.cos import storage_manager
from api.models import Company


class Command(BaseCommand):
    help = (
        "Migra todos los objetos sensibles (PRIVATE_STORAGE_PREFIXES) desde el bucket público "
        "(AWS_PUBLIC_BUCKET_NAME) hacia el bucket privado (AWS_PRIVATE_BUCKET_NAME) con cifrado AES256, "
        "y normaliza rutas heredadas en la base de datos."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--delete-from-public",
            action="store_true",
            help="Elimina los archivos privados del bucket público tras confirmar su copia cifrada en el bucket privado.",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Simula la migración mostrando qué objetos se moverían sin modificar S3 ni la base de datos.",
        )

    def handle(self, *args, **options):
        dry_run = bool(options.get("dry_run"))
        delete_from_public = bool(options.get("delete_from_public"))

        # 1. Normalizar URLs heredadas en Company (rif_document_url / mercantil_document_url)
        normalized_companies = 0
        for company in Company.objects.exclude(rif_document_url__isnull=True, mercantil_document_url__isnull=True):
            updated_fields = []
            if company.rif_document_url:
                clean_rif = storage_manager.normalize_path(company.rif_document_url)
                if clean_rif and clean_rif != company.rif_document_url:
                    company.rif_document_url = clean_rif
                    updated_fields.append("rif_document_url")
            if company.mercantil_document_url:
                clean_merc = storage_manager.normalize_path(company.mercantil_document_url)
                if clean_merc and clean_merc != company.mercantil_document_url:
                    company.mercantil_document_url = clean_merc
                    updated_fields.append("mercantil_document_url")
            if updated_fields:
                normalized_companies += 1
                if not dry_run:
                    company.save(update_fields=updated_fields)

        self.stdout.write(
            self.style.SUCCESS(
                f"✔ Compañías con rutas KYB normalizadas a clave relativa: {normalized_companies}"
                + (" (DRY-RUN)" if dry_run else "")
            )
        )

        # 2. Validar configuración de S3 Dual-Bucket
        if storage_manager.storage_type != "aws":
            self.stdout.write(
                self.style.WARNING("⚠️ STORAGE_TYPE no es 'aws'. Solo se ejecutó la normalización de BD.")
            )
            return

        pub_bucket = storage_manager.public_bucket_name
        priv_bucket = storage_manager.private_bucket_name
        if not pub_bucket or not priv_bucket or pub_bucket == priv_bucket:
            self.stdout.write(
                self.style.ERROR(
                    f"❌ AWS_PUBLIC_BUCKET_NAME ('{pub_bucket}') y AWS_PRIVATE_BUCKET_NAME ('{priv_bucket}') "
                    "deben estar configurados y ser distintos en variables.sh antes de migrar objetos S3."
                )
            )
            return

        s3 = storage_manager.s3_client
        copied_count = 0
        deleted_count = 0
        error_count = 0

        self.stdout.write(
            f"🚀 Iniciando migración de prefijos privados desde '{pub_bucket}' -> '{priv_bucket}'..."
        )

        paginator = s3.get_paginator("list_objects_v2")
        for prefix in storage_manager.PRIVATE_STORAGE_PREFIXES:
            for page in paginator.paginate(Bucket=pub_bucket, Prefix=prefix):
                for obj in page.get("Contents", []):
                    key = obj["Key"]
                    if dry_run:
                        self.stdout.write(f"  [DRY-RUN] Copiaría: s3://{pub_bucket}/{key} -> s3://{priv_bucket}/{key}")
                        copied_count += 1
                        continue

                    try:
                        content_type = storage_manager._guess_content_type(key)
                        copy_extra = {
                            "ServerSideEncryption": "AES256",
                            "ContentDisposition": "inline",
                        }
                        if content_type:
                            copy_extra["ContentType"] = content_type
                            copy_extra["MetadataDirective"] = "REPLACE"

                        s3.copy_object(
                            Bucket=priv_bucket,
                            Key=key,
                            CopySource={"Bucket": pub_bucket, "Key": key},
                            **copy_extra,
                        )
                        copied_count += 1

                        if delete_from_public:
                            s3.delete_object(Bucket=pub_bucket, Key=key)
                            deleted_count += 1
                    except ClientError as exc:
                        error_count += 1
                        self.stderr.write(f"  ❌ Error migrando '{key}': {exc}")

        self.stdout.write(
            self.style.SUCCESS(
                f"✅ Migración S3 finalizada: {copied_count} objetos copiados a '{priv_bucket}', "
                f"{deleted_count} eliminados de '{pub_bucket}', {error_count} errores."
            )
        )
