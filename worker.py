
import sqlite3
import time
import subprocess
import json
import signal  
import sys  
import platform   
from datetime import datetime, timedelta, timezone
from db import get_db_connection
from config import get_config


SHUTDOWN_REQUESTED = False

def signal_handler(sig, frame):
    
    global SHUTDOWN_REQUESTED
    if not SHUTDOWN_REQUESTED:
        print(f"\nSignal {sig} received. Requesting graceful shutdown...")
        print("Will exit after finishing the current job.")
        SHUTDOWN_REQUESTED = True
    else:
        print("Shutdown already requested. Forcing exit.")
        sys.exit(1)


signal.signal(signal.SIGTERM, signal_handler)
signal.signal(signal.SIGINT, signal_handler)

if platform.system() == "Windows":
    signal.signal(signal.SIGBREAK, signal_handler)



def fetch_and_lock_job(conn):
    """
    Atomically fetches a 'pending' job and locks it by setting 'processing'.
    (This function is unchanged)
    """
    cursor = conn.cursor()
    try:
        find_sql = "SELECT id FROM jobs WHERE state = 'pending' AND run_at <= CURRENT_TIMESTAMP LIMIT 1"
        cursor.execute(find_sql)
        job_row = cursor.fetchone()
        
        if job_row is None:
            return None
            
        job_id = job_row['id']
        lock_sql = "UPDATE jobs SET state = 'processing' WHERE id = ? AND state = 'pending'"
        cursor.execute(lock_sql, (job_id,))
        conn.commit()
        
        if cursor.rowcount == 0:
            return None

        get_sql = "SELECT * FROM jobs WHERE id = ?"
        cursor.execute(get_sql, (job_id,))
        return cursor.fetchone()

    except sqlite3.Error as e:
        print(f"Database error during fetch/lock: {e}")
        return None

def run_job(job):
    
    command = job['command']
    job_id = job['id']
    print(f"--- Starting job: {job_id} | Command: {command} ---")
    try:
        result = subprocess.run(
            command, shell=True, capture_output=True, text=True, check=False
        )
        print(f"--- Finished job: {job_id} | Exit Code: {result.returncode} ---")
        return result
    except Exception as e:
        print(f"Error running job {job_id}: {e}")
        return subprocess.CompletedProcess(
            args=command, returncode=1, stdout="", stderr=str(e)
        )

def handle_job_result(conn, job, result, config):
    
    job_id = job['id']
    if result.returncode == 0:
        print(f" Job {job_id} completed successfully.")
        sql = "UPDATE jobs SET state = 'completed', output_log = ?, error_log = ? WHERE id = ?"
        try:
            conn.cursor().execute(sql, (result.stdout, result.stderr, job_id))
            conn.commit()
        except sqlite3.Error as e:
            print(f"Database error completing job {job_id}: {e}")
    else:
        print(f" Job {job_id} failed. Attempt {job['attempts'] + 1}")
        fail_job(conn, job, result, config)

def fail_job(conn, job, result, config):
    
    job_id = job['id']
    max_retries = config.get('max_retries', 3)
    backoff_base = config.get('backoff_base', 2)
    current_attempts = job['attempts'] + 1
    
    if current_attempts >= max_retries:
        print(f" Job {job_id} hit max retries. Moving to DLQ ('dead').")
        sql = "UPDATE jobs SET state = 'dead', attempts = ?, output_log = ?, error_log = ? WHERE id = ?"
        params = (current_attempts, result.stdout, result.stderr, job_id)
    else:
        delay_seconds = backoff_base ** current_attempts
        next_run_time = datetime.now(timezone.utc) + timedelta(seconds=delay_seconds)
        print(f"Job {job_id} will retry in {delay_seconds} seconds (at {next_run_time}).")
        sql = "UPDATE jobs SET state = 'pending', attempts = ?, run_at = ?, output_log = ?, error_log = ? WHERE id = ?"
        params = (current_attempts, next_run_time, result.stdout, result.stderr, job_id)
    
    try:
        conn.cursor().execute(sql, params)
        conn.commit()
    except sqlite3.Error as e:
        print(f"Database error failing job {job_id}: {e}")



def worker_loop():
    
    print(" Smart Worker started. Waiting for jobs... ")
    config = get_config()
    print(f"Config loaded: {config}")
    
    
    while not SHUTDOWN_REQUESTED:
        conn = get_db_connection()
        job = None
        try:
            
            
            job = fetch_and_lock_job(conn)
            
            if job:
                result = run_job(job)
                
                
                if SHUTDOWN_REQUESTED:
                    print(f"Shutdown requested, but job {job['id']} finished. Handling result...")
                
                handle_job_result(conn, job, result, config)
                
            else:
                
                for _ in range(10): 
                    if SHUTDOWN_REQUESTED:
                        break
                    time.sleep(0.1)
                
        except sqlite3.Error as e:
            print(f"Database error in main loop: {e}")
            if not SHUTDOWN_REQUESTED: time.sleep(5)
        except Exception as e:
            print(f"An unexpected error occurred: {e}")
            if job:
                print(f"Trying to fail job {job['id']} due to unexpected error.")
                fake_result = subprocess.CompletedProcess(
                    args=job['command'], returncode=1, stdout="", stderr=str(e)
                )
                handle_job_result(conn, job, fake_result, config)
            if not SHUTDOWN_REQUESTED: time.sleep(5)
        finally:
            conn.close()
            
    
    print("Worker shutting down gracefully. Goodbye.")


if __name__ == "__main__":
    worker_loop()