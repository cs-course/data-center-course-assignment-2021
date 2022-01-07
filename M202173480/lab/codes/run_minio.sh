#!/bin/bash
export MINIO_ROOT_USER=cqh
export MINIO_ROOT_PASSWORD=hust_cqh

# Export metrics
export MINIO_PROMETHEUS_AUTH_TYPE="public"

# Use "-C" flag to store configuration file in local directory "./".
# Use server command to start object storage server with "./root" as root directory, in which holds all buckets and objects.
./minio -C ./ server ./root --console-address ":9090"

