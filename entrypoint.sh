#!/bin/sh
set -eu

if [ "$#" -gt 0 ]; then
	exec /bin/ciadpi "$@"
fi

port="${BYEDPI_PORT:-3080}"
options="${BYEDPI_OPTIONS:-}"

if [ -n "$options" ]; then
	# Re-parse the options string so quoted host lists stay intact.
	eval "set -- --port \"$port\" $options"
	exec /bin/ciadpi "$@"
fi

exec /bin/ciadpi --port "$port"
