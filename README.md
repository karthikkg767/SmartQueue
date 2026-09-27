# Smart Queue

A Flask-based digital token and queue management app.

## Local development

Python 3.10 or later is recommended.

```powershell
python -m pip install -r requirements.txt
$env:SECRET_KEY = python -c "import secrets; print(secrets.token_urlsafe(48))"
$env:ADMIN_USERNAME = "admin"
$env:ADMIN_PASSWORD = "choose-a-strong-password"
python app.py
```

Without `DATABASE_URL`, the app uses the local `queue.db` SQLite database.
The database schema is initialized automatically when the app starts.

## Deploy to Vercel

Vercel runs this Flask app as a Python Function. Queue data must use a
managed PostgreSQL database because files written by a Vercel Function are
not persistent. Create a PostgreSQL database with a provider such as Neon,
then configure these environment variables in the Vercel project settings for
every environment you will use:

| Variable | Value |
| --- | --- |
| `DATABASE_URL` | PostgreSQL connection string from your database provider. The Vercel Neon integration can also supply this as `DATABASE_POSTGRES_URL`. |
| `SECRET_KEY` | A long random secret, for example output from `python -c "import secrets; print(secrets.token_urlsafe(48))"` |
| `ADMIN_USERNAME` | Admin login username |
| `ADMIN_PASSWORD` | A strong admin login password |

The app creates or upgrades its `tokens` table at startup. `queue.db` is
excluded from the Vercel deployment and existing SQLite records are not
automatically copied to PostgreSQL.

After connecting the GitHub repository to Vercel, deploy from the project
root with the Vercel CLI:

```powershell
npx vercel
npx vercel --prod
```

Keep connection strings and secrets in Vercel environment settings; do not
commit them to the repository.
