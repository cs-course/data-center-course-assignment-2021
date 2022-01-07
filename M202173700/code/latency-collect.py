import os
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from boto3.session import Session
import botocore
from tqdm import tqdm
import throttle
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.ticker import FuncFormatter

# 准备密钥
aws_access_key_id = 'hust'
aws_secret_access_key = 'hust_obs'

# 本地S3服务地址
local_s3 = 'http://127.0.0.1:9000'

# 建立会话
session = Session(aws_access_key_id=aws_access_key_id, aws_secret_access_key=aws_secret_access_key)

# 连接到服务
s3 = session.resource('s3', endpoint_url=local_s3)

# for bucket in s3.buckets.all():
#     print('bucket name:%s' % bucket.name)

bucket_name = 'testobjs'
if s3.Bucket(bucket_name) not in s3.buckets.all():
    s3.create_bucket(Bucket=bucket_name)

bucket = s3.Bucket(bucket_name)
# for obj in bucket.objects.all():
#     print('obj name:%s' % obj.key)

# 初始化本地数据文件
local_file = "_test_4K.bin"
test_bytes = [0xFF for i in range(1024*4)] # 填充至所需大小

with open(local_file, "wb") as lf:
    lf.write(bytearray(test_bytes))


# 发起请求和计算系统停留时间
def request_timing(s3res, i): # 使用独立 session.resource 以保证线程安全
    obj_name = "testObj%08d"%(i,) # 所建对象名
    # temp_file = '.tempfile'
    service_time = 0 # 系统滞留时间
    start = time.time()
    s3res.Object(bucket_name, obj_name).upload_file(local_file) # 将本地文件上传为对象
    # 或
    # bucket.put_object(Key=obj_name, Body=open(local_file, 'rb'))
    # 下载obj
    # s3res.Object(bucket_name, obj_name).download_file(temp_file)
    end = time.time()
    system_time = end - start
    return system_time * 1000 # 换算为毫秒

# 按照请求到达率限制来执行和跟踪请求
def arrival_rate_max(s3res, i): # 不进行限速
    return request_timing(s3res, i)

@throttle.wrap(0.050, 1) # 100ms 内不超过 2 个请求，下同……
def arrival_rate_2(s3res, i):
    return request_timing(s3res, i)

@throttle.wrap(0.050, 4)
def arrival_rate_4(s3res, i):
    return request_timing(s3res, i)

@throttle.wrap(0.050, 8)
def arrival_rate_8(s3res, i):
    return request_timing(s3res, i)

latency = []
failed_requests = []

atency = []
failed_requests = []
futures = []
with tqdm(desc="Accessing S3", total=100) as pbar:      # 进度条设置，合计执行 100 项上传任务 (见 submit 部分)，进度也设置为 100 步
    with ThreadPoolExecutor(max_workers=1) as executor:  # 通过 max_workers 设置并发线程数
        for i in range(100):
            tmp = executor.submit(
                arrival_rate_max,
                session.resource('s3', endpoint_url=local_s3), i)
            if tmp.result() < 60:
                futures.append(tmp)
            else:
                futures.append(executor.submit(
                arrival_rate_max,
                session.resource('s3', endpoint_url=local_s3), i))

        for future in as_completed(futures):
            if future.exception():
                failed_requests.append(futures[future])
            else:
                latency.append(future.result()) # 正确完成的请求，采集延迟
            pbar.update(1)

try:
    # 删除bucket下所有object
    bucket.objects.filter().delete()

    # 删除bucket下某个object
    # bucket.objects.filter(Prefix=obj_name).delete()

    bucket.delete()
except botocore.exceptions.ClientError as e:
    print('error in bucket removal')


os.remove(local_file)
with open("latency.csv", "w+") as tracefile:
    tracefile.write("latency\n")
    tracefile.writelines([str(l) + '\n' for l in latency])

latency = pd.read_csv('latency.csv').apply(pd.to_numeric).values
plt.subplot(211)
plt.plot(latency)
plt.subplot(212)
plt.plot(sorted(latency, reverse=True))
plt.show()
# 百分比换算
def to_percent(y, position):
    return str(100 * round(y, 2)) + "%"

# 设置纵轴为百分比
fomatter = FuncFormatter(to_percent)
ax = plt.gca()
# ax.xaxis.set_major_locator(MultipleLocator(5))
ax.yaxis.set_major_formatter(fomatter)
# 避免横轴数据起始位置与纵轴重合，调整合适座标范围
x_min = max(min(latency) * 0.8, min(latency) - 5)
x_max = max(latency)
plt.xlim(x_min, x_max)
# 绘制实际百分位延迟
plt.hist(latency, cumulative=True, histtype='step', weights=[1./ len(latency)] * len(latency))

# 排队论模型
# F(t)=1-e^(-1*a*t)
alpha = 0.3
X_qt = np.arange(min(latency), max(latency), 1.)
Y_qt = 1 - np.exp(alpha * (min(latency) - X_qt))
# 绘制排队论模型拟合
plt.plot(X_qt, Y_qt)

plt.grid()
plt.show()