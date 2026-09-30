from django.contrib.postgres.operations import TrigramExtension
from django.db import migrations

class Migration(migrations.Migration):
    dependencies = [('api', '0042_rename_delivery_location_order_client_location')]
    operations = [TrigramExtension()]