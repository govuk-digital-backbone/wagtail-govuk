from django.db import migrations


def convert_root_page_to_homepage(apps, schema_editor):
    Site = apps.get_model("wagtailcore", "Site")
    Page = apps.get_model("wagtailcore", "Page")
    HomePage = apps.get_model("govuk", "HomePage")
    ContentType = apps.get_model("contenttypes", "ContentType")

    db_alias = schema_editor.connection.alias

    default_site = Site.objects.using(db_alias).filter(is_default_site=True).first()
    if not default_site:
        return

    root_page = Page.objects.using(db_alias).filter(pk=default_site.root_page_id).first()
    if not root_page:
        return

    root_content_type = ContentType.objects.using(db_alias).filter(pk=root_page.content_type_id).first()
    if not root_content_type:
        return

    if root_content_type.app_label == "govuk" and root_content_type.model == "homepage":
        return

    # Only auto-convert if the site root is still the generic, non-creatable Wagtail page.
    if root_content_type.app_label != "wagtailcore" or root_content_type.model != "page":
        return

    home_page_content_type, _ = ContentType.objects.using(db_alias).get_or_create(
        app_label="govuk",
        model="homepage",
    )
    child_table = HomePage._meta.db_table
    qn = schema_editor.quote_name

    with schema_editor.connection.cursor() as cursor:
        cursor.execute(
            f"SELECT 1 FROM {qn(child_table)} WHERE {qn('page_ptr_id')} = %s",
            [root_page.id],
        )
        row_exists = cursor.fetchone() is not None
        if not row_exists:
            cursor.execute(
                f"INSERT INTO {qn(child_table)} ({qn('page_ptr_id')}, {qn('body')}) VALUES (%s, %s)",
                [root_page.id, ""],
            )

    root_page.content_type_id = home_page_content_type.id
    root_page.save(update_fields=["content_type"])


class Migration(migrations.Migration):
    replaces = [('home', '0002_convert_root_page_to_homepage')]


    dependencies = [
        ("govuk", "0001_home_initial"),
    ]

    operations = [
        migrations.RunPython(convert_root_page_to_homepage, migrations.RunPython.noop),
    ]
