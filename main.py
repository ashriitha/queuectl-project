
import typer
import json
import sqlite3
import os
import sys
import signal
import subprocess
import platform  
from db import get_db_connection
from config import get_config, CONFIG_FILE
from typing_extensions import Annotated
from typing import Optional

PID_FILE = "workers.pid"

app = typer.Typer(help="A CLI-based background job queue system.")
dlq_app = typer.Typer(help="Manage the Dead Letter Queue (DLQ).")
config_app = typer.Typer(help="Manage configuration.")
worker_app = typer.Typer(help="Manage worker processes.")

app.add_typer(dlq_app, name="dlq")
app.add_typer(config_app, name="config")
app.add_typer(worker_app, name="worker")



@app.command()
def enqueue(
    job_json_str: Annotated[str, typer.Argument(
        help="The job data as a JSON string. e.g. '{\"id\":\"job1\", \"command\":\"sleep 2\"}'"
    )]
):
    try:
        job_data = json.loads(job_json_str)
        job_id = job_data.get('id')
        command = job_data.get('command')
        if not job_id or not command:
            typer.echo("Error: JSON must include 'id' and 'command' keys.")
            raise typer.Exit(code=1)
        conn = get_db_connection()
        sql = "INSERT INTO jobs (id, command) VALUES (?, ?)"
        try:
            conn.cursor().execute(sql, (job_id, command))
            conn.commit()
            typer.echo(f"✅ Job '{job_id}' enqueued successfully.")
        except sqlite3.IntegrityError:
            typer.echo(f"Error: Job with ID '{job_id}' already exists.")
            raise typer.Exit(code=1)
        except sqlite3.Error as e:
            typer.echo(f"Database error: {e}")
            raise typer.Exit(code=1)
        finally:
            conn.close()
    except json.JSONDecodeError:
        typer.echo("Error: Invalid JSON string provided.")
        raise typer.Exit(code=1)

@app.command()
def status():
    conn = get_db_connection()
    try:
        sql = "SELECT state, COUNT(*) as count FROM jobs GROUP BY state"
        cursor = conn.cursor()
        cursor.execute(sql)
        results = cursor.fetchall()
        typer.echo("--- Job Status Summary ---")
        if not results:
            typer.echo("No jobs found.")
            return
        state_map = {row['state']: row['count'] for row in results}
        states = ['pending', 'processing', 'completed', 'failed', 'dead']
        for state in states:
            count = state_map.get(state, 0)
            typer.echo(f"- {state.capitalize():<12}: {count}")
    except sqlite3.Error as e:
        typer.echo(f"Database error: {e}")
    finally:
        conn.close()

@app.command()
def list(
    state: Annotated[Optional[str], typer.Option(
        help="Filter jobs by state (e.g., 'pending', 'dead')"
    )] = None
):
    conn = get_db_connection()
    try:
        sql = "SELECT id, state, command, attempts, run_at FROM jobs"
        params = []
        if state:
            sql += " WHERE state = ?"
            params.append(state)
        sql += " ORDER BY created_at DESC"
        cursor = conn.cursor()
        cursor.execute(sql, params)
        jobs = cursor.fetchall()
        if not jobs:
            typer.echo(f"No jobs found" + (f" with state '{state}'." if state else "."))
            return
        typer.echo(f"--- Showing {len(jobs)} Jobs ---")
        for job in jobs:
            typer.echo(f"Job ID: {job['id']}")
            typer.echo(f"  State:    {job['state']}")
            typer.echo(f"  Command:  {job['command']}")
            typer.echo(f"  Attempts: {job['attempts']}")
            typer.echo(f"  Run At:   {job['run_at']}")
            typer.echo("-" * 20)
    except sqlite3.Error as e:
        typer.echo(f"Database error: {e}")
    finally:
        conn.close()

@dlq_app.command("list")
def dlq_list():
    typer.echo("--- Dead Letter Queue (DLQ) ---")
    list(state='dead')

@dlq_app.command("retry")
def dlq_retry(
    job_id: Annotated[str, typer.Argument(help="The ID of the job to retry.")]
):
    conn = get_db_connection()
    try:
        sql = "UPDATE jobs SET state = 'pending', attempts = 0, run_at = CURRENT_TIMESTAMP WHERE id = ? AND state = 'dead'"
        cursor = conn.cursor()
        cursor.execute(sql, (job_id,))
        if cursor.rowcount == 0:
            typer.echo(f"Error: Job '{job_id}' not found in DLQ ('dead').")
        else:
            conn.commit()
            typer.echo(f" Job '{job_id}' moved to 'pending' for retry.")
    except sqlite3.Error as e:
        typer.echo(f"Database error: {e}")
    finally:
        conn.close()

@config_app.command("set")
def config_set(
    key: Annotated[str, typer.Argument(help="Config key (e.g., 'max_retries')")],
    value: Annotated[str, typer.Argument(help="Config value")]
):
    config = get_config()
    try: value = int(value)
    except ValueError: pass
    config[key] = value
    try:
        with open(CONFIG_FILE, 'w') as f: json.dump(config, f, indent=4)
        typer.echo(f"Config updated: {key} = {value}")
    except Exception as e:
        typer.echo(f"Error writing config file: {e}")

@config_app.command("show")
def config_show():
    typer.echo(f"--- Current Configuration ({CONFIG_FILE}) ---")
    config = get_config()
    typer.echo(json.dumps(config, indent=4))

@worker_app.command("start")
def worker_start(
    count: Annotated[int, typer.Option(
        help="Number of worker processes to start."
    )] = 1
):
    
    
    
    
    pids = []
    typer.echo(f"Starting {count} worker(s)...")
    
    creation_flags = 0
    if platform.system() == "Windows":
        creation_flags = subprocess.CREATE_NEW_PROCESS_GROUP

    for _ in range(count):
        process = subprocess.Popen(
            [sys.executable, "worker.py"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            creationflags=creation_flags
        )
        typer.echo(f"Started worker with PID: {process.pid}")
        pids.append(str(process.pid))
    
    try:
        with open(PID_FILE, "w") as f:
            f.write("\n".join(pids))
        typer.echo(f"PIDs written to {PID_FILE}")
    except Exception as e:
        typer.echo(f"Error writing PID file: {e}")

@worker_app.command("stop")
def worker_stop():
    
    
    
    
    if not os.path.exists(PID_FILE):
        typer.echo("No workers running (PID file not found).")
        return
        
    typer.echo("Sending graceful shutdown signal to workers...")
    
    try:
        with open(PID_FILE, "r") as f:
            pids = [int(pid) for pid in f.read().splitlines()]
            
        for pid in pids:
            try:
            
                if platform.system() == "Windows":
                    
                    
                    cmd = ["taskkill", "/PID", str(pid)]
                    subprocess.run(
                        cmd, 
                        stdout=subprocess.PIPE, 
                        stderr=subprocess.PIPE,
                        check=False 
                    )
                    typer.echo(f"Sent signal to PID: {pid} (using taskkill)")
                else:
                    
                    os.kill(pid, signal.SIGTERM)
                    typer.echo(f"Sent signal to PID: {pid}")
                
                    
            except ProcessLookupError:
                typer.echo(f"Worker PID {pid} not found (already stopped).")
            except Exception as e:
                typer.echo(f"Error stopping PID {pid}: {e}")
                
        os.remove(PID_FILE)
        typer.echo(f"Cleaned up {PID_FILE}.")
        
    except Exception as e:
        typer.echo(f"Error reading PID file: {e}")

if __name__ == "__main__":
    app()