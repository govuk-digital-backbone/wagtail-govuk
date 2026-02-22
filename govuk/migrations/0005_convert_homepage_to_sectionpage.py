from django.db import migrations


def convert_homepages_to_sectionpages(apps, schema_editor):
    ContentType = apps.get_model("contenttypes", "ContentType")
    Page = apps.get_model("wagtailcore", "Page")
    HomePage = apps.get_model("govuk", "HomePage")
    SectionPage = apps.get_model("govuk", "SectionPage")

    db_alias = schema_editor.connection.alias

    homepage_content_type = (
        ContentType.objects.using(db_alias)
        .filter(app_label="govuk", model="homepage")
        .first()
    )
    if homepage_content_type is None:
        return

    sectionpage_content_type, _ = ContentType.objects.using(db_alias).get_or_create(
        app_label="govuk",
        model="sectionpage",
    )

    homepage_ids = list(
        Page.objects.using(db_alias)
        .filter(content_type_id=homepage_content_type.id)
        .values_list("id", flat=True)
    )
    if not homepage_ids:
        return

    homepage_rows = {
        row.page_ptr_id: row
        for row in HomePage.objects.using(db_alias).filter(page_ptr_id__in=homepage_ids)
    }
    existing_section_rows = set(
        SectionPage.objects.using(db_alias)
        .filter(page_ptr_id__in=homepage_ids)
        .values_list("page_ptr_id", flat=True)
    )

    qn = schema_editor.connection.ops.quote_name
    child_table = SectionPage._meta.db_table

    with schema_editor.connection.cursor() as cursor:
        for page_id in homepage_ids:
            if page_id in existing_section_rows:
                continue

            homepage_row = homepage_rows.get(page_id)
            body = getattr(homepage_row, "body", "") or ""
            cursor.execute(
                f"INSERT INTO {qn(child_table)} ({qn('page_ptr_id')}, {qn('hero_title')}, {qn('hero_intro')}, {qn('rows')}, {qn('free_text')}) VALUES (%s, %s, %s, %s, %s)",
                [page_id, "", "", "[]", body],
            )

    Page.objects.using(db_alias).filter(id__in=homepage_ids).update(
        content_type_id=sectionpage_content_type.id
    )


class Migration(migrations.Migration):
    replaces = [('home', '0005_convert_homepage_to_sectionpage')]

    dependencies = [
        ("govuk", "0003_sectionpage"),
    ]

    operations = [
        migrations.RunPython(
            convert_homepages_to_sectionpages, migrations.RunPython.noop
        ),
        migrations.DeleteModel(
            name="HomePage",
        ),
    ]
