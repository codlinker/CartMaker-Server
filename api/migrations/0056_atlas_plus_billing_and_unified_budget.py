# Generated for Atlas Plus Dynamic SENIAT Billing, Digital Invoices & Unified Daily Budget

from datetime import timedelta
import decimal
import secrets
import uuid
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models
from django.utils import timezone


def seed_atreyus_fiscal_config_and_backfill_invoices(apps, schema_editor):
    SystemConfig = apps.get_model("api", "SystemConfig")
    CartMakerBankAccount = apps.get_model("api", "CartMakerBankAccount")
    AtlasPlusPlanPayment = apps.get_model("api", "AtlasPlusPlanPayment")
    AtlasPlusInvoice = apps.get_model("api", "AtlasPlusInvoice")
    Company = apps.get_model("api", "Company")
    ClientLocation = apps.get_model("api", "ClientLocation")
    CompanyStore = apps.get_model("api", "CompanyStore")

    # 1. Asegurar configuración fiscal inicial con el RIF y Cédula de Atreyus y tarifas 3.99 / 30 / 7 / 3
    config = SystemConfig.objects.order_by("-creation").first()
    if config:
        if not config.billing_issuer_rif:
            config.billing_issuer_rif = "V-30222103-7"
        if not config.billing_issuer_cedula:
            config.billing_issuer_cedula = "V-30.222.103"
        if not config.billing_issuer_name:
            config.billing_issuer_name = "ATREYUS DE JESUS REYES ALVAREZ"
        config.save()

    # 2. Actualizar cuentas bancarias receptoras por defecto si tenían datos placeholder
    CartMakerBankAccount.objects.filter(
        document_number__in=["00000000", "12345678", ""]
    ).update(
        document_type=0,  # BankDocumentType.CEDULA (V)
        document_number="30222103",
    )
    CartMakerBankAccount.objects.filter(
        beneficiary_name__in=["CartMaker C.A.", "CartMaker", ""]
    ).update(
        beneficiary_name="ATREYUS DE JESUS REYES ALVAREZ",
    )

    # 3. Emitir facturas retrospectivas para pagos de Atlas Plus que ya estaban APROBADOS (status=1)
    approved_payments = (
        AtlasPlusPlanPayment.objects.filter(status=1)
        .select_related("plan__user")
        .order_by("creation", "id")
    )
    correlative = max(1, int(getattr(config, "billing_next_correlative", 1) or 1))
    existing_max = (
        AtlasPlusInvoice.objects.aggregate(models.Max("correlative_number")).get(
            "correlative_number__max"
        )
        or 0
    )
    if correlative <= existing_max:
        correlative = existing_max + 1

    for payment in approved_payments:
        if AtlasPlusInvoice.objects.filter(payment_id=payment.id).exists():
            continue

        user = payment.plan.user
        company = Company.objects.filter(owner_id=user.id).first()
        buyer_is_company = False
        if company and getattr(company, "rif", None) and getattr(company, "name", None):
            buyer_name = company.name.strip().upper()
            buyer_document = company.rif.strip().upper()
            buyer_is_company = True
        else:
            full_name = f"{user.first_name or ''} {user.last_name or ''}".strip()
            buyer_name = (full_name or user.email.split("@")[0]).upper()
            if getattr(user, "cedula_number", None):
                clean_ced = str(user.cedula_number).strip().upper()
                if clean_ced and clean_ced[0] in ("V", "E", "J", "G", "P"):
                    buyer_document = clean_ced
                else:
                    buyer_document = f"V-{clean_ced}"
            else:
                buyer_document = "V-00000000 (Consumidor Final)"

        buyer_address = "República Bolivariana de Venezuela"
        first_loc = ClientLocation.objects.filter(user_id=user.id).first()
        if first_loc and getattr(first_loc, "name", None):
            buyer_address = first_loc.name
        elif company:
            main_store = (
                CompanyStore.objects.filter(company_id=company.id)
                .select_related("location")
                .first()
            )
            if main_store and getattr(main_store, "location", None) and main_store.location.name:
                buyer_address = main_store.location.name

        bcv_rate = decimal.Decimal(str(payment.bcv_taxes_to_day or "42.5000"))
        if bcv_rate <= decimal.Decimal("0"):
            bcv_rate = decimal.Decimal("42.5000")

        total_usd = decimal.Decimal(
            str(getattr(config, "atlas_plus_price_usd", "3.99") if config else "3.99")
        ).quantize(decimal.Decimal("0.01"))
        total_bs = (total_usd * bcv_rate).quantize(decimal.Decimal("0.01"))

        raw_paid_bs = decimal.Decimal(str(payment.amount or "0.00")).quantize(
            decimal.Decimal("0.01")
        )
        if raw_paid_bs > decimal.Decimal("0.00"):
            amount_paid_bs = raw_paid_bs
            amount_paid_usd = (raw_paid_bs / bcv_rate).quantize(decimal.Decimal("0.01"))
            payment_method = "Pago Móvil / Transferencia Bancaria"
        else:
            amount_paid_bs = total_bs
            amount_paid_usd = total_usd
            payment_method = "Saldo en Billetera Digital CartMaker (UserWallet)"

        surplus_usd = max(
            decimal.Decimal("0.00"),
            (amount_paid_usd - total_usd).quantize(decimal.Decimal("0.01")),
        )
        surplus_bs = (surplus_usd * bcv_rate).quantize(decimal.Decimal("0.01"))

        series = (getattr(config, "billing_series_prefix", "A") if config else "A") or "A"
        ctrl_prefix = (getattr(config, "billing_control_prefix", "00") if config else "00") or "00"
        invoice_number = f"{series}-{correlative:08d}"
        control_number = f"{ctrl_prefix}-{correlative:08d}"
        issued_dt = payment.verified_at or payment.creation or timezone.now()
        verification_code = f"CMK-{issued_dt.strftime('%Y%m%d')}-{secrets.token_hex(4).upper()}"

        AtlasPlusInvoice.objects.create(
            id=uuid.uuid4(),
            payment=payment,
            user=user,
            correlative_number=correlative,
            invoice_number=invoice_number,
            control_number=control_number,
            verification_code=verification_code,
            issued_at=issued_dt,
            period_start=issued_dt,
            period_end=payment.plan.valid_until or (issued_dt + timedelta(days=30)),
            issuer_type=getattr(config, "billing_issuer_type", "PERSONAL") if config else "PERSONAL",
            issuer_name=(
                getattr(config, "billing_issuer_name", "ATREYUS DE JESUS REYES ALVAREZ")
                if config
                else "ATREYUS DE JESUS REYES ALVAREZ"
            ),
            issuer_trade_name=(
                getattr(config, "billing_trade_name", "CartMaker") if config else "CartMaker"
            ),
            issuer_rif=(
                getattr(config, "billing_issuer_rif", "V-30222103-7")
                if config
                else "V-30222103-7"
            ),
            issuer_cedula=(
                getattr(config, "billing_issuer_cedula", "V-30.222.103")
                if config
                else "V-30.222.103"
            ),
            issuer_fiscal_address=(
                getattr(
                    config,
                    "billing_fiscal_address",
                    "CTRA NACIONAL GUATIRE-GUARENAS CASA TOWN HOUSE NRO C-11 CONJUNTO RESIDENCIAL EL REFUGIO GUATIRE MIRANDA ZONA POSTAL 1221",
                )
                if config
                else "CTRA NACIONAL GUATIRE-GUARENAS CASA TOWN HOUSE NRO C-11 CONJUNTO RESIDENCIAL EL REFUGIO GUATIRE MIRANDA ZONA POSTAL 1221"
            ),
            issuer_seniat_region=(
                getattr(
                    config,
                    "billing_seniat_region",
                    "GERENCIA REGIONAL DE TRIBUTOS INTERNOS REGIÓN CAPITAL / SECTOR GUARENAS / GUATIRE",
                )
                if config
                else "GERENCIA REGIONAL DE TRIBUTOS INTERNOS REGIÓN CAPITAL / SECTOR GUARENAS / GUATIRE"
            ),
            issuer_rif_certificate=(
                getattr(config, "billing_rif_certificate_number", "202401P0000063963955")
                if config
                else "202401P0000063963955"
            ),
            tax_regime=(
                getattr(config, "billing_tax_regime", "EXENTO_NO_SUJETO")
                if config
                else "EXENTO_NO_SUJETO"
            ),
            buyer_name=buyer_name,
            buyer_document=buyer_document,
            buyer_email=user.email or "",
            buyer_address=buyer_address,
            buyer_is_company=buyer_is_company,
            payment_method=payment_method,
            payment_reference=payment.reference_number or "",
            concept_description=(
                getattr(
                    config,
                    "billing_service_concept",
                    "Servicios de Programación, Procesamiento de Datos y Suscripción Mensual al Asistente de Inteligencia Artificial Atlas Plus (CartMaker)",
                )
                if config
                else "Servicios de Programación, Procesamiento de Datos y Suscripción Mensual al Asistente de Inteligencia Artificial Atlas Plus (CartMaker)"
            ),
            bcv_rate=bcv_rate,
            subtotal_usd=total_usd,
            subtotal_bs=total_bs,
            exempt_amount_usd=total_usd,
            exempt_amount_bs=total_bs,
            taxable_base_usd=decimal.Decimal("0.00"),
            taxable_base_bs=decimal.Decimal("0.00"),
            iva_percentage=decimal.Decimal("0.00"),
            iva_amount_usd=decimal.Decimal("0.00"),
            iva_amount_bs=decimal.Decimal("0.00"),
            total_usd=total_usd,
            total_bs=total_bs,
            amount_paid_bs=amount_paid_bs,
            amount_paid_usd=amount_paid_usd,
            wallet_surplus_usd=surplus_usd,
            wallet_surplus_bs=surplus_bs,
            legal_note=(
                getattr(config, "billing_legal_note", "")
                if config
                else "Montos expresados en Bolívares (Bs.) como moneda de curso legal y su equivalencia en Dólares (USD) según tasa oficial del Banco Central de Venezuela (BCV)."
            ),
        )
        correlative += 1

    if config and correlative > int(getattr(config, "billing_next_correlative", 1) or 1):
        config.billing_next_correlative = correlative
        config.save(update_fields=["billing_next_correlative"])


class Migration(migrations.Migration):

    dependencies = [
        ("api", "0055_performance_indexes"),
    ]

    operations = [
        migrations.AddField(
            model_name="atlasplusplan",
            name="daily_usage_date",
            field=models.DateField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="atlasplusplan",
            name="daily_usage_count",
            field=models.IntegerField(default=0),
        ),
        migrations.AlterField(
            model_name="cartmakerbankaccount",
            name="document_number",
            field=models.CharField(default="30222103"),
        ),
        migrations.AlterField(
            model_name="cartmakerbankaccount",
            name="beneficiary_name",
            field=models.CharField(default="ATREYUS DE JESUS REYES ALVAREZ"),
        ),
        migrations.AlterField(
            model_name="systemconfig",
            name="atlas_plus_price_usd",
            field=models.DecimalField(
                decimal_places=2, default=decimal.Decimal("3.99"), max_digits=12
            ),
        ),
        migrations.AlterField(
            model_name="systemconfig",
            name="atlas_plus_daily_limit",
            field=models.IntegerField(default=30),
        ),
        migrations.AlterField(
            model_name="systemconfig",
            name="atlas_free_daily_limit",
            field=models.IntegerField(default=7),
        ),
        migrations.AddField(
            model_name="systemconfig",
            name="billing_issuer_type",
            field=models.CharField(
                choices=[
                    ("PERSONAL", "Persona Natural / Servicios Profesionales (RIF V-)"),
                    ("COMPANY", "Persona Jurídica / Empresa Registrada (RIF J-)"),
                ],
                default="PERSONAL",
                help_text="Define si las facturas de Atlas Plus se emiten a tu nombre personal (RIF V-) o a nombre de tu empresa registrada (RIF J-).",
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name="systemconfig",
            name="billing_issuer_name",
            field=models.CharField(
                default="ATREYUS DE JESUS REYES ALVAREZ",
                help_text="Nombre completo (Persona Natural) o Razón Social (Empresa) tal como aparece en el RIF del SENIAT.",
                max_length=255,
            ),
        ),
        migrations.AddField(
            model_name="systemconfig",
            name="billing_trade_name",
            field=models.CharField(
                default="CartMaker",
                help_text="Nombre comercial o marca mostrada en el encabezado de la factura.",
                max_length=255,
            ),
        ),
        migrations.AddField(
            model_name="systemconfig",
            name="billing_issuer_rif",
            field=models.CharField(
                default="V-30222103-7",
                help_text="RIF fiscal activo ante el SENIAT (ej. V-30222103-7 o J-XXXXXXXX-X cuando registres la empresa).",
                max_length=30,
            ),
        ),
        migrations.AddField(
            model_name="systemconfig",
            name="billing_issuer_cedula",
            field=models.CharField(
                blank=True,
                default="V-30.222.103",
                help_text="Cédula de Identidad del emisor o representante legal (ej. V-30.222.103).",
                max_length=30,
            ),
        ),
        migrations.AddField(
            model_name="systemconfig",
            name="billing_fiscal_address",
            field=models.TextField(
                default="CTRA NACIONAL GUATIRE-GUARENAS CASA TOWN HOUSE NRO C-11 CONJUNTO RESIDENCIAL EL REFUGIO GUATIRE MIRANDA ZONA POSTAL 1221",
                help_text="Domicilio Fiscal exacto registrado en el comprobante RIF del SENIAT.",
            ),
        ),
        migrations.AddField(
            model_name="systemconfig",
            name="billing_seniat_region",
            field=models.CharField(
                blank=True,
                default="GERENCIA REGIONAL DE TRIBUTOS INTERNOS REGIÓN CAPITAL / SECTOR GUARENAS / GUATIRE",
                help_text="Gerencia Regional de Tributos Internos del SENIAT.",
                max_length=255,
            ),
        ),
        migrations.AddField(
            model_name="systemconfig",
            name="billing_rif_certificate_number",
            field=models.CharField(
                blank=True,
                default="202401P0000063963955",
                help_text="N° de Comprobante del Registro Único de Información Fiscal (SENIAT).",
                max_length=60,
            ),
        ),
        migrations.AddField(
            model_name="systemconfig",
            name="billing_tax_regime",
            field=models.CharField(
                choices=[
                    (
                        "EXENTO_NO_SUJETO",
                        "Exento / No Sujeto de IVA (Persona Natural / Exonerado)",
                    ),
                    ("CONTRIBUYENTE_ORDINARIO", "Contribuyente Ordinario de IVA (16%)"),
                    ("CONTRIBUYENTE_ESPECIAL", "Contribuyente Especial SENIAT"),
                ],
                default="EXENTO_NO_SUJETO",
                help_text="Condición frente al IVA. Usa 'Exento / No Sujeto' como Persona Natural inicial, o 'Contribuyente Ordinario (16%)' al facturar con IVA.",
                max_length=30,
            ),
        ),
        migrations.AddField(
            model_name="systemconfig",
            name="billing_iva_percentage",
            field=models.DecimalField(
                decimal_places=2,
                default=decimal.Decimal("0.00"),
                help_text="Porcentaje de IVA aplicable (0.00 para Persona Natural Exento/No Sujeto; 16.00 para Contribuyente Ordinario).",
                max_digits=5,
            ),
        ),
        migrations.AddField(
            model_name="systemconfig",
            name="billing_series_prefix",
            field=models.CharField(
                blank=True,
                default="A",
                help_text="Prefijo de serie para la numeración de facturas digitales (ej. A -> A-00000001).",
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name="systemconfig",
            name="billing_control_prefix",
            field=models.CharField(
                blank=True,
                default="00",
                help_text="Prefijo de Número de Control (ej. 00 -> 00-00000001).",
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name="systemconfig",
            name="billing_next_correlative",
            field=models.PositiveIntegerField(
                default=1,
                help_text="Siguiente número correlativo de factura a emitir (se incrementa automáticamente con cada pago aprobado).",
            ),
        ),
        migrations.AddField(
            model_name="systemconfig",
            name="billing_service_concept",
            field=models.CharField(
                default="Servicios de Programación, Procesamiento de Datos y Suscripción Mensual al Asistente de Inteligencia Artificial Atlas Plus (CartMaker)",
                help_text="Descripción del servicio tecnológico que aparece en el renglón principal de la factura.",
                max_length=500,
            ),
        ),
        migrations.AddField(
            model_name="systemconfig",
            name="billing_legal_note",
            field=models.TextField(
                blank=True,
                default="La condición de este contribuyente requiere la retención del 100% del impuesto causado, salvo que esté exento, no sujeto o demuestre ante el Agente de Retención del IVA que es un contribuyente exonerado (SENIAT). Montos expresados en Bolívares (Bs.) como moneda de curso legal y su equivalencia en Dólares (USD) según tasa oficial del Banco Central de Venezuela (BCV) vigente a la fecha de la operación.",
            ),
        ),
        migrations.CreateModel(
            name="AtlasPlusInvoice",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                ("correlative_number", models.PositiveIntegerField(db_index=True, unique=True)),
                ("invoice_number", models.CharField(db_index=True, max_length=40, unique=True)),
                ("control_number", models.CharField(db_index=True, max_length=40, unique=True)),
                ("verification_code", models.CharField(db_index=True, max_length=64, unique=True)),
                (
                    "issued_at",
                    models.DateTimeField(db_index=True, default=django.utils.timezone.now),
                ),
                ("period_start", models.DateTimeField(blank=True, null=True)),
                ("period_end", models.DateTimeField(blank=True, null=True)),
                (
                    "issuer_type",
                    models.CharField(
                        choices=[
                            (
                                "PERSONAL",
                                "Persona Natural / Servicios Profesionales (RIF V-)",
                            ),
                            (
                                "COMPANY",
                                "Persona Jurídica / Empresa Registrada (RIF J-)",
                            ),
                        ],
                        default="PERSONAL",
                        max_length=20,
                    ),
                ),
                ("issuer_name", models.CharField(max_length=255)),
                ("issuer_trade_name", models.CharField(default="CartMaker", max_length=255)),
                ("issuer_rif", models.CharField(max_length=30)),
                ("issuer_cedula", models.CharField(blank=True, default="", max_length=30)),
                ("issuer_fiscal_address", models.TextField()),
                ("issuer_seniat_region", models.CharField(blank=True, default="", max_length=255)),
                ("issuer_rif_certificate", models.CharField(blank=True, default="", max_length=60)),
                (
                    "tax_regime",
                    models.CharField(
                        choices=[
                            (
                                "EXENTO_NO_SUJETO",
                                "Exento / No Sujeto de IVA (Persona Natural / Exonerado)",
                            ),
                            (
                                "CONTRIBUYENTE_ORDINARIO",
                                "Contribuyente Ordinario de IVA (16%)",
                            ),
                            ("CONTRIBUYENTE_ESPECIAL", "Contribuyente Especial SENIAT"),
                        ],
                        default="EXENTO_NO_SUJETO",
                        max_length=30,
                    ),
                ),
                ("buyer_name", models.CharField(max_length=255)),
                ("buyer_document", models.CharField(default="Consumidor Final", max_length=60)),
                ("buyer_email", models.CharField(blank=True, default="", max_length=255)),
                (
                    "buyer_address",
                    models.TextField(blank=True, default="República Bolivariana de Venezuela"),
                ),
                ("buyer_is_company", models.BooleanField(default=False)),
                (
                    "payment_method",
                    models.CharField(
                        default="Pago Móvil / Transferencia Bancaria", max_length=80
                    ),
                ),
                ("payment_reference", models.CharField(max_length=100)),
                ("concept_description", models.CharField(max_length=500)),
                ("bcv_rate", models.DecimalField(decimal_places=4, max_digits=12)),
                ("subtotal_usd", models.DecimalField(decimal_places=2, max_digits=12)),
                ("subtotal_bs", models.DecimalField(decimal_places=2, max_digits=14)),
                (
                    "exempt_amount_usd",
                    models.DecimalField(
                        decimal_places=2, default=decimal.Decimal("0.00"), max_digits=12
                    ),
                ),
                (
                    "exempt_amount_bs",
                    models.DecimalField(
                        decimal_places=2, default=decimal.Decimal("0.00"), max_digits=14
                    ),
                ),
                (
                    "taxable_base_usd",
                    models.DecimalField(
                        decimal_places=2, default=decimal.Decimal("0.00"), max_digits=12
                    ),
                ),
                (
                    "taxable_base_bs",
                    models.DecimalField(
                        decimal_places=2, default=decimal.Decimal("0.00"), max_digits=14
                    ),
                ),
                (
                    "iva_percentage",
                    models.DecimalField(
                        decimal_places=2, default=decimal.Decimal("0.00"), max_digits=5
                    ),
                ),
                (
                    "iva_amount_usd",
                    models.DecimalField(
                        decimal_places=2, default=decimal.Decimal("0.00"), max_digits=12
                    ),
                ),
                (
                    "iva_amount_bs",
                    models.DecimalField(
                        decimal_places=2, default=decimal.Decimal("0.00"), max_digits=14
                    ),
                ),
                ("total_usd", models.DecimalField(decimal_places=2, max_digits=12)),
                ("total_bs", models.DecimalField(decimal_places=2, max_digits=14)),
                (
                    "amount_paid_bs",
                    models.DecimalField(
                        decimal_places=2, default=decimal.Decimal("0.00"), max_digits=14
                    ),
                ),
                (
                    "amount_paid_usd",
                    models.DecimalField(
                        decimal_places=2, default=decimal.Decimal("0.00"), max_digits=12
                    ),
                ),
                (
                    "wallet_surplus_usd",
                    models.DecimalField(
                        decimal_places=2, default=decimal.Decimal("0.00"), max_digits=12
                    ),
                ),
                (
                    "wallet_surplus_bs",
                    models.DecimalField(
                        decimal_places=2, default=decimal.Decimal("0.00"), max_digits=14
                    ),
                ),
                ("legal_note", models.TextField(blank=True, default="")),
                (
                    "payment",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="invoice",
                        to="api.atlasplusplanpayment",
                    ),
                ),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="atlas_invoices",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "ordering": ["-issued_at", "-correlative_number"],
                "indexes": [
                    models.Index(
                        fields=["user", "-issued_at"], name="atlas_inv_user_issued_idx"
                    ),
                ],
            },
        ),
        migrations.RunPython(
            seed_atreyus_fiscal_config_and_backfill_invoices,
            reverse_code=migrations.RunPython.noop,
        ),
    ]
