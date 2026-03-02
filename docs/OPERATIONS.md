# Amazon Replens Automation System - Operations Manual

This document provides instructions for operating and maintaining the Amazon Replens Automation System.

## 1. Daily Operations

### 1.1. Checking System Status

- **Review Logs:** Check the log file (`logs/replens_automation.log`) for any errors or warnings.
- **Monitor Dashboard:** Open the Streamlit dashboard (`http://localhost:8501`) to get a real-time view of KPIs and system status.

### 1.2. Reviewing New Opportunities

1. Navigate to the "Opportunities" tab in the dashboard.
2. Review the list of new products identified by the discovery engine.
3. For each product, you can:
    - **Approve:** The product will be moved to the sourcing phase.
    - **Reject:** The product will be archived and not considered again.
    - **Archive:** The product will be temporarily archived.

## 2. Maintenance

### 2.1. Backups

- **Database:** Perform regular backups of the PostgreSQL database.
  ```bash
  pg_dump -U <user> -d <database> > backup.sql
  ```
- **Configuration:** Keep a secure backup of your `.env` file.

### 2.2. Updating the System

1. Pull the latest code from the Git repository.
2. Install any new dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Apply any database migrations (if applicable).
4. Restart the Docker containers:
   ```bash
   docker-compose down && docker-compose up -d
   ```

## 3. Troubleshooting

- **API Errors:** Check the API credentials in `.env` and ensure the APIs are not down.
- **Database Errors:** Verify the database connection string and ensure the database server is running.
- **Scheduler Not Running:** Check the logs for the `scheduler` service to identify any issues.
