# tu_app/migrations/0002_poblar_datos_iniciales.py
from django.db import migrations
from decimal import Decimal

def poblar_datos(apps, schema_editor):
    # Modelos necesarios para cargar los datos iniciales
    Category = apps.get_model('web', 'Category')
    MerchantPlan = apps.get_model('web', 'MerchantPlan')
    Announcement = apps.get_model('web', 'Announcement')
    # Crear datos iniciales
    Category.objects.bulk_create([
        Category(name='Comida', img_url='img/categories/category_comida.jpg'),
        Category(name='Ropa', img_url='img/categories/category_ropa.jpg'),
        Category(name='Tecnología', img_url='img/categories/category_tecnologia.jpg'),
    ])
    MerchantPlan.objects.bulk_create([
        MerchantPlan(
            name="Plan Emprendo",
            price=Decimal(15.0),
            inventory_capacity=25,
            products_registration_with_ia=True,
            digital_performance_analytics = True,
            short_description_html = "Diseñado para <b>emprendedores</b> que suelen vender de forma informal por redes sociales.",
            large_description_html = "Dile adiós al «vendedor de DM» para convertirte en un comercio con una <b>vitrina digital estructurada</b>. Podrás organizar tus ofertas sin barreras técnicas complicadas.",
            card_bg_color = "#E7E6ED",
            label_bg_color = "#9E8ED9",
            label_border_color = "#6D49F2",
            label_text_color = "#F2F2F2"
        ),
        MerchantPlan(
            name="Plan Comercio",
            price=Decimal(35.0),
            inventory_capacity=60,
            products_registration_with_ia=True,
            profile_histories=True,
            gamification_system=True,
            gamification_analytics=True,
            digital_performance_analytics = True,
            is_popular=True,
            short_description_html = "Diseñado para negocios con <b>clientes recurrentes</b> que necesitan una <b>plataforma robusta</b> para escalar sus ventas.",
            large_description_html = "Convierte tu catálogo en una herramienta de marketing activo mediante <b>historias</b> y <b>gamificación</b> para potenciar la lealtad y el rendimiento de tu marca en el mercado.",
            card_bg_color = "#DCD7EF",
            label_bg_color = "#6D49F2",
            label_border_color = "#F2F2F2",
            label_text_color = "#F2F2F2"
        ),
        MerchantPlan(
            name="Plan Franquicia",
            price=Decimal(165.0),
            inventory_capacity=100,
            products_registration_with_ia=True,
            profile_histories=True,
            gamification_system=True,
            gamification_analytics=True,
            digital_performance_analytics = True,
            clients_behavior_analytics=True,
            operative_management_analytics=True,
            company_branches=True,
            company_employees=True,
            short_description_html = 'Construido para <b>marcas consolidadas</b> que ya no se preocupan solo por "vender", sino por "<b>controlar</b>" lo que venden en <b>diferentes puntos geográficos</b>.',
            large_description_html = "Diseñado para directores de negocio que necesitan una visión de 360 grados de su operación, gestionando la complejidad de <b>múltiples inventarios</b> y logística distribuida desde un solo centro de mando, asegurando que la experiencia de marca sea la misma en cada <b>sucursal</b>. ",
            card_bg_color = "#FFFFF2",
            label_bg_color = "#6D49F2",
            label_border_color = "#F2ED49",
            label_text_color = "#F2ED49",
            requires_business= True
        )
    ])
    Announcement.objects.bulk_create([
        Announcement(
            banner_img='/static/img/third_banner_test.png',
            navigate_to='home',
        ),
        Announcement(
            banner_img='/static/img/2_banner_test.png',
            navigate_to='home',
        ),
        Announcement(
            banner_img='/static/img/first_banner_test.png',
            navigate_to='home',
        )
    ])

def revertir_datos(apps, schema_editor):
    # Obtener los modelos históricos
    Category = apps.get_model('web', 'Category')
    MerchantPlan = apps.get_model('web', 'MerchantPlan')
    # Eliminar las categorías creadas basándonos en el nombre exacto
    Category.objects.filter(name__in=['Comida', 'Ropa', 'Tecnología']).delete()
    # Eliminar los planes creados basándonos en el nombre exacto
    MerchantPlan.objects.filter(name__in=['Plan Emprendo', 'Plan Comercio', 'Plan Franquicia']).delete()

class Migration(migrations.Migration):

    dependencies = [
        ('web', '0014_alter_atlasplusplanpayment_rejection_help_and_more'), # Depende de la migración que creó la tabla
    ]

    operations = [
        migrations.RunPython(poblar_datos, revertir_datos),
    ]