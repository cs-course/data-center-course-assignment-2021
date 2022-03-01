import io
import os
import time
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from boto3.session import Session
import botocore
from tqdm import tqdm
from ratelimiter import RateLimiter

# 准备密钥
aws_access_key_id = 'PG3XVLGJ0PI4EWF0SWP3'
aws_secret_access_key = 'QCyuKS2FIq40RpTiRushOh5NblkjmTGxt0hmDoav'

# 本地S3服务地址
local_s3 = 'http://master:8080'

# 建立会话
session = Session(aws_access_key_id=aws_access_key_id, aws_secret_access_key=aws_secret_access_key)

# 连接到服务
s3 = session.resource('s3', endpoint_url=local_s3)

bucket_name = 'loadgen'
if s3.Bucket(bucket_name) not in s3.buckets.all():
    print(f'bucket {bucket_name} not found, creating new one...')
    s3.create_bucket(Bucket=bucket_name)
else:
    print(f'skip bucket {bucket_name}')
    
bucket = s3.Bucket(bucket_name)
for obj in bucket.objects.all():
    print('obj name:%s' % obj.key)

def direct_request(action, res, i, localfile):
    start = time.time()
    action(res, i, localfile)
    end = time.time()
    system_time = end - start
    return system_time * 1000 # 换算为毫秒
    
def hedged_request(action, res, i, localfile):
    start = time.time()
    nThreads = 2
    with ThreadPoolExecutor(max_workers=nThreads) as executor: # 通过 max_workers 设置并发线程数
        futures = [executor.submit(arrival_rate_max, res, i, localfile + str(i)) for i in range(nThreads)]
        for future in as_completed(futures):
            # 只要第一个结果
            end = time.time()
            system_time = end - start
            return system_time * 1000 # 换算为毫秒

timeout = 0
        
def tied_request(action, res, i, localfile):  # 95%分位数时间，超过这个时间就丢弃这个请求，发送新的
    start = time.time()
    with ThreadPoolExecutor(max_workers=1) as executor: # 通过 max_workers 设置并发线程数
        future = executor.submit(arrival_rate_max, res, i, localfile)
        time.sleep(timeout)
        while not future.done():
            future.cancel()
            future = executor.submit(arrival_rate_max)
            time.sleep(timeout)
        end = time.time()
        system_time = end - start
        return system_time * 1000 # 换算为毫秒

    
# 发起请求和计算系统停留时间
def request_timing(s3res, i, file): # 使用独立 session.resource 以保证线程安全
    obj_name = "testObj%08d"%(i,) # 所建对象名
    s3res.Object(bucket_name, obj_name).download_file(file)

# 按照请求到达率限制来执行和跟踪请求
def arrival_rate_max(s3res, i, file): # 不进行限速
    return request_timing(s3res, i, file)

@RateLimiter(0.1, 4)
def arrival_rate_4(s3res, i, file):
    return request_timing(s3res, i, file)

@RateLimiter(0.1, 16)
def arrival_rate_16(s3res, i, file):
    return request_timing(s3res, i, file)

file_size_kb = [4, 256, 1024, 4096]
rate_limits = {
    'max': arrival_rate_max
}
policies = {
#    'direct': direct_request,
#    'hedged': hedged_request
    'tied': tied_request
}
client_count = [1, 16, 64]
_95_percentile = {
    4: 0.02,
    256: 0.05,
    1024: 0.1,
    4096: 0.2
}

def bench(fileBuffer=None, rate_limit=None, policy=None, n_clients=1, nRequests=128):
    assert(fileBuffer is not None)
    assert(rate_limit is not None)
    assert(policy is not None)
    
    _latency = []
    _failed = []

    with tqdm(desc="Accessing S3", total=nRequests) as pbar:      # 进度条设置，合计执行128项上传任务
        with ThreadPoolExecutor(max_workers=n_clients) as executor: # 通过 max_workers 设置并发线程数
            futures = [
                executor.submit(
                    policy,
                    rate_limit,
                    session.resource('s3', endpoint_url=local_s3),
                    i, fileBuffer) for i in range(nRequests) # 为保证线程安全，应给每个任务申请一个新 resource
                ]
            for future in as_completed(futures):
                if future.exception():
                    _failed.append(future)
                else:
                    _latency.append(future.result()) # 正确完成的请求，采集延迟
                pbar.update(1)
        
    return _latency, _failed

for file_size in file_size_kb:
    byte_file = '_test_{0}K.bin'.format(file_size)
    bytez = bytearray([0 for i in range(file_size * 1024)])
    with open(byte_file, 'wb') as f:
        f.write(bytez)
        
    timeout = _95_percentile[file_size]
        
    print('preparing file size {0}K ...'.format(file_size))
    for i in range(128):
        obj_name = "testObj%08d"%(i,) # 所建对象名
        s3.Object(bucket_name, obj_name).upload_file(byte_file)
        
    for limit_name, limit in rate_limits.items():
        for policy_name, policy in policies.items():
            for n_client in client_count:

                print('config: {0}KB-{1}-{2}-{3}clients'.format(file_size, limit_name, policy_name, n_client))
                ltcy, failed = bench(byte_file, limit, policy, n_client)

                if len(failed) > 0:
                    try:
                        failed[0].result()
                    except Exception as e:
                        print(e)

                with open("download-latency-{0}KB-{1}-{2}-{3}clients.csv".format(file_size, limit_name, policy_name, n_client), "w") as tracefile:
                    tracefile.writelines([str(l) + '\n' for l in ltcy])
                    
    bucket.objects.filter().delete()