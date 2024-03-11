# filename = f"modules-backup-{datetime.now().strftime('%Y-%m-%d-%H-%M-%S')}.db"

import boto3
from apscheduler.schedulers.background import BackgroundScheduler
from datetime import datetime
import os
import subprocess
import shutil

def print_orange(text):
    """
    Prints the given text in an orange-like color to the terminal.
    """
    # ANSI escape code for a bright yellow, which is a close approximation to orange
    orange_escape_code = '\033[93m'
    # Reset code to return text color back to default
    reset_code = '\033[0m'
    print(f"{orange_escape_code}{text}{reset_code}")

def backup_database(app):
    app.logger.debug("Starting database backup...")
    backup_dir = "/app/backup-tmp"
    filename = "modules-backup-latest.db"
    backup_path = os.path.join(backup_dir, filename)
    
    # Ensure the backup directory exists
    os.makedirs(backup_dir, exist_ok=True)

    # SQLite DB path is /app/modules.db
    subprocess.run(["cp", "/app/modules.db", backup_path])
    app.logger.debug(f"backup_path: {backup_path} | filename: {filename}")
    
    # Upload the backup to S3
    s3 = boto3.client('s3')
    data_directory = os.getenv('DATA_DIRECTORY').replace('s3://', '', 1).split('/', 1)
    bucket_name = data_directory[0]
    object_name = data_directory[1] + filename if len(data_directory) > 1 else filename
    app.logger.debug(f"bucket_name: {bucket_name} | object_name: {object_name}")
    with open(backup_path, "rb") as f:
        s3.upload_fileobj(f, bucket_name, object_name)
    app.logger.debug("Backup uploaded successfully.")
    
    # Cleanup the local backup file
    if os.path.exists(backup_path):
        os.remove(backup_path)

def restore_database():
    print_orange("Checking for existing backup in S3...")
    s3 = boto3.client('s3')
    bucket_name, prefix = os.getenv('DATA_DIRECTORY').replace('s3://', '', 1).split('/', 1)
    
    # List objects in the S3 bucket with the specified prefix
    response = s3.list_objects_v2(Bucket=bucket_name, Prefix=prefix)
    backups = [obj['Key'] for obj in response.get('Contents', []) if 'modules-backup' in obj['Key']]
    
    if backups:
        latest_backup = sorted(backups)[-1]
        print_orange(f"Found backup: {latest_backup}. Restoring database...")
        
        # Download the backup
        with open("/app/modules.db", "wb") as f:
            s3.download_fileobj(bucket_name, latest_backup, f)
        print_orange("Database restored successfully.")
    else:
        print_orange("No backup found to restore.")

def start_scheduler(app):
    restore_database()
    
    scheduler = BackgroundScheduler()
    # scheduler.add_job(lambda: backup_database(app), 'cron', minute='*')  # Once every minute
    # scheduler.add_job(lambda: backup_database(app), 'cron', minute=0) # every hour
    scheduler.add_job(lambda: backup_database(app), 'cron', minute='*/5') # every 5 minutes
    # scheduler.add_job(lambda: restore_database(), 'cron', day_of_week='*', hour=0, minute=0)  # Daily at midnight, adjust as needed
    
    # Start the scheduler
    scheduler.start()
    print_orange("Scheduler started...")