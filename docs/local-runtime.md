# Local runtime

Double-click `启动网站.cmd` to start both services in the background. Double-click `停止网站.cmd` to stop the supervisor and its owned services. No Windows login task is installed; run the starter after a reboot.

`scripts/watch_local.ps1` holds a per-project mutex, prevents duplicate supervisors, checks services every 10 seconds, and restarts an exited process. Six consecutive failed health checks trigger a restart. Startup retries back off to 60 seconds. HTTP checks have four-second timeouts. Process handles and explicitly adopted process IDs prevent terminating unrelated programs occupying these ports.

Logs: `outputs/local-runtime/supervisor.log` plus timestamped frontend/backend stdout and stderr. Existing processes adopted during rollout keep their original log files until restarted. This makes future exits observable; the earlier Vite exit cause was not recorded and remains unknown.

This is a development-machine reliability measure, not a production hosting solution. It cannot serve while Windows is shut down, asleep, or the supervisor itself is terminated. It does not install a login startup task. `start_user_test.ps1` is the repository's existing Docker deployment path and uses a separate database; do not switch a live user's database without migration/backups. Production deployment requires a persistent server, built frontend, process/container restart policy, readiness checks and backups.

Health recovery restarts a hung service; in-flight requests may need a retry. A successful health check confirms service availability, not every business operation.
