from django.db import migrations
from staging_runtime.audit_guard import install_guard


class Migration(migrations.Migration):
    dependencies = [("service", "0004_securityevent_loginsession_authenticated_role_and_more")]
    operations = [migrations.RunPython(install_guard, reverse_code=migrations.RunPython.noop)]
