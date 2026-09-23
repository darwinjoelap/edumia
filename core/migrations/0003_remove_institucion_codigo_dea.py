from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0002_perfilusuario'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='institucion',
            name='codigo_dea',
        ),
    ]
