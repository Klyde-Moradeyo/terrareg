# filename = f"modules-backup-{datetime.now().strftime('%Y-%m-%d-%H-%M-%S')}.db"

import boto3
from apscheduler.schedulers.background import BackgroundScheduler
from datetime import datetime
import os
import subprocess

def backup_database(app):
    app.logger.info("Starting database backup...")
    filename = "modules-backup-latest.db"
    backup_path = os.path.join("/tmp", filename)
    
    # Assuming your SQLite DB path is /app/modules.db
    subprocess.run(["cp", "/app/modules.db", backup_path])
    
    # Upload the backup to S3
    s3 = boto3.client('s3')
    data_directory = os.getenv('DATA_DIRECTORY').replace('s3://', '', 1).split('/', 1)
    bucket_name = data_directory[0]
    object_name = data_directory[1] + filename if len(data_directory) > 1 else filename
    with open(backup_path, "rb") as f:
        s3.upload_fileobj(f, bucket_name, object_name)
    app.logger.info("Backup uploaded successfully.")
    
    # Cleanup the local backup file
    os.remove(backup_path)

def restore_database(app):
    app.logger.info("Checking for existing backup in S3...")
    s3 = boto3.client('s3')
    bucket_name, prefix = os.getenv('DATA_DIRECTORY').replace('s3://', '', 1).split('/', 1)
    
    # List objects in the S3 bucket with the specified prefix
    response = s3.list_objects_v2(Bucket=bucket_name, Prefix=prefix)
    backups = [obj['Key'] for obj in response.get('Contents', []) if 'modules-backup' in obj['Key']]
    
    if backups:
        latest_backup = sorted(backups)[-1]
        app.logger.info(f"Found backup: {latest_backup}. Restoring database...")
        
        # Download the backup
        with open("/app/modules.db", "wb") as f:
            s3.download_fileobj(bucket_name, latest_backup, f)
        app.logger.info("Database restored successfully.")
    else:
        app.logger.info("No backup found to restore.")

def start_scheduler(app):
    scheduler = BackgroundScheduler()
    scheduler.add_job(lambda: backup_database(app), 'cron', minute='*')  # Once every minute
    scheduler.add_job(lambda: restore_database(app), 'cron', day_of_week='*', hour=0, minute=0)  # Daily at midnight, adjust as needed
    
    # Start the scheduler
    scheduler.start()
    app.logger.info("Scheduler started...")
