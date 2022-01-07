#!/bin/sh

# Locate s3bench

s3bench=~/go/bin/s3-benchmark

if [ -n "$GOPATH" ]; then
    s3bench=$GOPATH/bin/s3-benchmark
fi

# Usage of myflag:
#   -a string
#         Access key
#   -b string
#         Bucket for testing (default "loadgen")
#   -d int
#         Duration of each test in seconds (default 60)
#   -l int
#         Number of times to repeat test (default 1)
#   -r string
#         Region for testing (default "us-east-1")
#   -s string
#         Secret key
#   -t int
#         Number of threads to run (default 1)
#   -u string
#         URL for host with method prefix
#   -z string
#        Size of objects in bytes with postfix K, M, and G (default "1M")

$s3bench \
	-a cqh \
	-s hust_cqh \
	-u http://192.168.123.125:9000 \
	-b s3bench-test-cqh \
	-d 60 \
	-t 2 \
	-z 1K
