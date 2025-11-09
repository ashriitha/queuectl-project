QueueCTL - A Python CLI Job Queue System
queuectl is a minimal, production-grade background job queue system built in Python. It uses a SQLite database for persistent storage and a command-line interface (CLI) for enqueuing, managing, and monitoring jobs.

This project was built to satisfy the requirements for a backend developer internship assignment.

Demo
(https://drive.google.com/file/d/1-Y_KSNfoz4m9UYs_Za1vhS8kq776__UB/view?usp=sharing)

Core Features
Persistent Job Queue: Jobs are stored in a local SQLite database.

Background Workers: Start multiple background worker processes to execute jobs in parallel.

Retry with Exponential Backoff: Failed jobs are automatically retried with an increasing delay (base ^ attempts).

Dead Letter Queue (DLQ): Jobs that hit their max_retries are moved to a dead state for manual inspection.

Graceful Shutdown: The worker stop command allows workers to finish their current job before exiting, preventing data corruption.

Cross-Platform: Designed to run on both Windows, macOS, and Linux.

 Setup and Installation
Clone the repository:

Bash

git clone <your-github-repo-url>
cd queuectl_project
Create a virtual environment:

Bash

python -m venv venv
Activate the environment:

On Windows:

PowerShell

.\venv\Scripts\activate
On macOS/Linux:

Bash

source venv/bin/activate
Install the required libraries:

Bash

pip install typer
Initialize the database: Run the db.py script once to create the queue.db file and the jobs table.

Bash

python db.py
 Usage (CLI Commands)
All commands are run through main.py.

Enqueue a Job
Add a new job to the queue. The job must have a unique id and a shell command.

PowerShell

# Enqueue a simple job
python main.py enqueue '{\"id\":\"job1\", \"command\":\"echo Hello World\"}'

# Enqueue a job that fails
python main.py enqueue '{\"id\":\"fail-job-1\", \"command\":\"exit 1\"}'

# Enqueue a long-running job (10 seconds)
python main.py enqueue '{\"id\":\"long-job-1\", \"command\":\"timeout /t 10\"}'
Start Workers
Start one or more workers in the background.

PowerShell

# Start a single worker
python main.py worker start

# Start 3 workers for parallel processing
python main.py worker start --count 3
This will create a workers.pid file to track the running processes.

Check Queue Status
Get a high-level summary of all jobs in the database.

PowerShell

python main.py status
Example Output:

--- Job Status Summary ---
- Pending     : 1
- Processing  : 3
- Completed   : 5
- Failed      : 0
- Dead        : 1
List Jobs
List the details for all jobs, or filter by a specific state.

PowerShell

# List all jobs
python main.py list

# List only the pending jobs
python main.py list --state pending

# List only the dead jobs (see DLQ)
python main.py list --state dead
Stop Workers
Requests a graceful shutdown of all background workers.

PowerShell

python main.py worker stop
This sends a signal to all workers. They will finish their current job before exiting.

Manage the Dead Letter Queue (DLQ)
PowerShell

# List all jobs in the DLQ
python main.py dlq list

# Retry a failed job (moves it from 'dead' to 'pending')
python main.py dlq retry "fail-job-1"
Manage Configuration
Change the retry policy (stored in config.json).

PowerShell

# See the current config
python main.py config show

# Change max_retries to 5
python main.py config set max_retries 5
🏛️ Architecture
This project is split into four main Python files:

main.py (The CLI): The user-facing interface, built with Typer. This is the "manager" who enqueues jobs and checks status. It's also responsible for starting and stopping the worker processes.

worker.py (The "Chef"): A standalone script that runs in the background. It polls the database, fetches a job, runs it, and handles the retry/DLQ logic.

db.py (The Database): The "single source of truth." It uses SQLite to store all jobs. An SQL trigger is used to automatically update the updated_at timestamp.

config.py (The Config): A simple helper to read/write settings from config.json.

Job Lifecycle
A job moves between several states:

pending: The job is enqueued and waiting.

processing: A worker has locked the job and is running its command.

completed: The command finished with Exit Code: 0.

failed: The command finished with a non-zero exit code.

If attempts < max_retries, the job is moved back to pending, and its run_at time is set to the future (exponential backoff).

If attempts >= max_retries, the job is moved to dead.

dead: The job is in the Dead Letter Queue and will not be run again unless manually retried with dlq retry.

Concurrency and Locking
To prevent two workers from grabbing the same job, the fetch_and_lock_job function in worker.py performs an atomic operation. It finds a pending job and immediately runs an UPDATE command to set its state to processing. Because of database locking, only one worker can "win" this race.

Graceful Shutdown
To stop workers safely:

main.py worker stop reads the workers.pid file.

On Windows, it uses the native taskkill command. On Linux/macOS, it uses os.kill with SIGTERM.

The worker.py script "catches" this signal using Python's signal module.

It sets a global SHUTDOWN_REQUESTED flag to True.

The main while loop in the worker exits, but only after the current job is finished.

🧪 How to Test
You can verify all core functionality with this flow:

Start Workers: python main.py worker start --count 3

Enqueue Jobs:

python main.py enqueue '{\"id\":\"good-job\", \"command\":\"echo This will succeed\"}'

python main.py enqueue '{\"id\":\"bad-job\", \"command\":\"exit 1\"}'

Watch the "Bad" Job Fail: Keep running python main.py list --state pending. You will see bad-job appear and disappear as it is retried with a 2-second, then 4-second, etc., delay.

Verify DLQ: After 3 attempts, the job will stop retrying. python main.py dlq list (You will see bad-job here).

Test Graceful Shutdown:

python main.py enqueue '{\"id\":\"long-test\", \"command\":\"timeout /t 10\"}'

Wait ~3 seconds, then check python main.py status (you'll see Processing: 1).

Run python main.py worker stop

Keep running python main.py status. You will see the job remain in processing until its 10 seconds are up, after which it will move to completed. This proves the graceful shutdown worked.

 Assumptions and Trade-offs
Database: SQLite was used for simplicity as it requires no setup. For a multi-server, production environment, this would be replaced with a network database like PostgreSQL or Redis.

Polling: The worker polls the database every 0.1 seconds. This is simple but inefficient. A more advanced system would use a true Pub/Sub message broker like RabbitMQ or Redis Pub/Sub to "push" jobs to workers instantly.

Process Management: Stopping background processes is notoriously difficult, especially on Windows. This solution uses taskkill (Windows) and os.kill (Linux) to provide a robust, cross-platform worker stop command.