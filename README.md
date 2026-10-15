# Farm Management App

A local-first farm operations application built with Python, Flask, and SQLite. The Windows launcher starts the app locally in a browser.

## Features

- Track partner records and payments
- Record staff salaries and advances
- Track medicine and feed expenses
- Record production and revenue
- Review operating totals and profit/loss reports
- Export workbook reports and create local database backups
- Run locally with a Windows batch launcher

## Run

1. Use a Windows environment with Python 3 installed.
2. Open `farm_app` and run `START_FARM_APP.bat`.
3. The application starts a local Flask server and opens the interface in a browser.

The application initializes its SQLite database locally. Do not commit `.db` or `.sqlite` files, exported workbooks, or real business records. The previously tracked database has been removed from the current branch.

## Project structure

- `farm_app/app.py` - Flask routes, SQLite initialization, reporting and backup endpoints
- `farm_app/templates/` - application interface
- `farm_app/START_FARM_APP.bat` - Windows launcher

## Privacy

This project was developed for a client. Client data and operational records must remain private. The repository history may still contain the removed database, so history cleanup is pending.

## Technology

Python, Flask, SQLite, HTML, JavaScript
