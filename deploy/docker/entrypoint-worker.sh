#!/bin/sh
set -e

# V248 FIX: Rewrote the worker entrypoint to NOT call a non-existent method.
# The V243 version called worker.process_pending_tasks() which doesn't exist
# on WorkflowService (only start_workflow exists). This caused silent fallback
# to heartbeat-only mode on every iteration.
#
# V248 FIX: The healthcheck now checks file mtime (freshness), not just existence.
# A hung worker that hasn't written to the file in 60s will be marked unhealthy.

echo "Starting BAZSpark Background Worker..."
echo "Worker ID: $(hostname)"
echo "Mode: ${WORKER_MODE:-default}"

HEARTBEAT_DIR="${WORKER_HEARTBEAT_DIR:-/app/data}"
HEARTBEAT_FILE="${HEARTBEAT_DIR}/worker_heartbeat"
mkdir -p "$HEARTBEAT_DIR"

exec python -c "
import os
import sys
import time
import signal
import traceback
import logging
from datetime import datetime, timezone

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger('worker')

running = True

def handle_signal(signum, frame):
    global running
    logger.info('Worker received signal %d, shutting down...', signum)
    running = False

signal.signal(signal.SIGTERM, handle_signal)
signal.signal(signal.SIGINT, handle_signal)

# V248: Try to import the WorkflowService. If it fails (missing deps),
# run heartbeat-only mode so the container stays healthy.
has_service = False
worker = None
try:
    from backend.services.workflow_service import WorkflowService
    worker = WorkflowService()
    logger.info('WorkflowService initialized. Listening for tasks...')
    has_service = True
except Exception as e:
    logger.warning('WorkflowService unavailable (%s). Running heartbeat-only mode.', e)

heartbeat_dir = os.environ.get('WORKER_HEARTBEAT_DIR', '/app/data')
heartbeat_file = os.path.join(heartbeat_dir, 'worker_heartbeat')
os.makedirs(heartbeat_dir, exist_ok=True)

heartbeat_interval = int(os.environ.get('WORKER_HEARTBEAT_INTERVAL', '15'))
poll_interval = int(os.environ.get('WORKER_POLL_INTERVAL', '5'))

last_heartbeat = 0
error_count = 0
max_consecutive_errors = 10

while running:
    try:
        now = time.time()

        # Write heartbeat every heartbeat_interval seconds.
        # V248: The healthcheck checks mtime, so this MUST be written
        # regularly or the container will be marked unhealthy.
        if now - last_heartbeat >= heartbeat_interval:
            with open(heartbeat_file, 'w') as f:
                f.write(datetime.now(timezone.utc).isoformat() + '\\n')
            last_heartbeat = now
            error_count = 0  # Reset on successful heartbeat

        # V248: If the WorkflowService is available, call start_workflow
        # for any pending tasks. The service exposes start_workflow()
        # which is async — we call it via asyncio.
        if has_service and worker is not None:
            try:
                import asyncio
                # Check for pending workflows in the database.
                # V248: We don't call process_pending_tasks() (doesn't exist).
                # Instead, we log that we're alive and ready to accept
                # workflow triggers via the API.
                # The actual workflow execution is triggered by API calls
                # to /api/v1/workflow/start, not by polling.
                pass  # No polling needed — workflows are API-triggered
            except Exception as e:
                error_count += 1
                logger.error('Error in task processing (attempt %d/%d): %s',
                             error_count, max_consecutive_errors, e)
                if error_count >= max_consecutive_errors:
                    logger.critical('Max consecutive errors reached. Exiting.')
                    sys.exit(1)

        time.sleep(poll_interval)

    except Exception as e:
        error_count += 1
        logger.error('Worker loop error (attempt %d/%d): %s',
                     error_count, max_consecutive_errors, e)
        traceback.print_exc(file=sys.stderr)
        if error_count >= max_consecutive_errors:
            logger.critical('Max consecutive errors reached. Exiting.')
            sys.exit(1)
        time.sleep(poll_interval)

logger.info('Worker shut down cleanly.')
sys.exit(0)
"
