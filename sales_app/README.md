# Sales Query Application

This Streamlit app provides sales staff with an easy interface to search the latest
pricing information. The app fetches the master dataset directly from GitHub on
startup so that users always work with the most up to date data.

Run locally with:

```bash
python run_sales_app.py
```

Set the `MASTER_DATA_URL` environment variable to override the default master
dataset location.
