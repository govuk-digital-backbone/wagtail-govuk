# wagtail-govuk

## Local Setup

1. Create and activate a virtual environment

```bash
python -m venv .venv
source .venv/bin/activate
# For Windows
# .venv\Scripts\activate
```

2. Install the project via `pyproject.toml`

```bash
python -m pip install --upgrade pip
pip install -e .
```

3. Run the development server

By default the project uses `govuk/settings/local.py` for local development which is configured to use SQLite. You can override this by setting the `DJANGO_SETTINGS_MODULE` environment variable to point to a different settings file.

```bash
# Run checks, apply migrations, and start the server
python manage.py check
python manage.py migrate
python manage.py runserver
```

## Environment Variables

- `DJANGO_SETTINGS_MODULE`: The settings module to use for the project. Defaults to `govuk.settings.local`.

When using `govuk.settings.dev`, the following variables are required:

- `SECRET_KEY`: A secret key for the Django project. Required for production.
- `DATABASE_NAME`: PostgreSQL database name.
- `DATABASE_USER`: PostgreSQL user.
- `DATABASE_PASSWORD`: PostgreSQL password.
- `DATABASE_HOST`: PostgreSQL host.
- `DATABASE_PORT`: PostgreSQL port (defaults to `5432`).
- `DOMAIN`: Hostname for `ALLOWED_HOSTS` (in addition to `*`).
- `BASE_URL`: Full base URL used for CSRF, CORS, and Wagtail admin URLs (for example `https://example.com`).
- `OIDC_CLIENT_ID`: Internal Access client ID.
- `OIDC_CLIENT_SECRET`: Internal Access client secret.
