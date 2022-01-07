#!/bin/sh
# locate s3bench

s3bench=~/go/bin/s3bench

if [ -n "$GOPATH" ]; then
    s3bench=$GOPATH/bin/s3bench
fi

$s3bench \
	-endpoint=http://192.168.123.125:9000 \
	-accessKey=cqh -accessSecret=hust_cqh \
	-bucket=loadgen -objectNamePrefix=loadgen \
	-objectSize=$((128*1024)) -numClients=2 -numSamples=10240
