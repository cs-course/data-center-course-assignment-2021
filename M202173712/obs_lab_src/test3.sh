#!/bin/sh

# Locate s3bench

s3bench=~/goProject/bin/s3bench
testresult=~/goProject/bin/testresult

if [ -n "$GOPATH" ]; then
    s3bench=$GOPATH/bin/s3bench
fi

if [ ! -d $testresult ]; then
	mkdir  $testresult
fi

# -accessKey        Access Key
# -accessSecret     Secret Key
# -bucket=loadgen   Bucket for holding all test objects.
# -endpoint=http://127.0.0.1:9000 Endpoint URL of object storage service being tested.
# -numClients=8     Simulate 8 clients running concurrently.
# -numSamples=256   Test with 256 objects.
# -objectNamePrefix=loadgen Name prefix of test objects.
# -objectSize=1024          Size of test objects.
# -verbose          Print latency for every request.

# set numClients as 1 2 4 8 12 16 24 32 40 48 64 80 96 112 128
testArr=(1 2 4 8 12 16 24 32 40 48 64 80 96 112 128)

for i in ${testArr[*]} 
do
	$s3bench \
    	-accessKey=hust \
   	-accessSecret=hust_obs \
    	-bucket=loadgen \
    	-endpoint=http://127.0.0.1:9000 \
    	-numClients=$i \
    	-numSamples=256 \
    	-objectNamePrefix=loadgen \
    	-objectSize=$(( 1024*32 )) >> $testresult/result3
done

# build your own test script with designated '-numClients', '-numSamples' and '-objectSize'
# 1. Use loop structure to generate test batch (E.g.: to re-evaluate multiple s3 servers under the same configuration, or to gather data from a range of parameters);
# 2. Use redirection (the '>' operator) for storing program output to text files;
# 3. Observe and analyse the underlying relation between configuration parameters and performance metrics.

