# Sales Query Application

This Streamlit app provides sales staff with an easy interface to search the latest
pricing information. The app fetches the master dataset directly from GitHub on
startup so that users always work with the most up to date data. The dataset is
stored in a SQLite database (`master.db`).

Run locally with:

```bash
python run_sales_app.py
```

Set the `MASTER_DB_URL` environment variable to override the default database
location. The images displayed for each record are downloaded from GitHub as
well. Use `IMAGE_BASE_URL` to customise the base URL for these images.
