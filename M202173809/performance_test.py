#!/usr/bin/python
# -*- encoding: utf-8 -*-
'''
@File  : performance_test.py
@Author: Penistrong
@Email : chen18296276027@gmail.com
@Date  : 2021-12-31 周五 16:02:26
@Desc  : 对s3对象存储服务器进行性能测试，并保存相关结果
'''
import os
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

import botocore
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import throttle
from boto3 import Session
from matplotlib.ticker import FuncFormatter
from tqdm import tqdm
import asyncio

default_access_id = 'admin'
default_access_key = 'chenliwei'
default_s3_endpoint = 'http://127.0.0.1:9090'

class PerformanceTester(object):
    """
    测试s3对象存储服务器的性能

    指标:
    - 吞吐率 Throughput
    - 延迟 Latency
    
    环境参数
    - 对象大小 Object size
    - 服务器数量
    - 并发性
    """
    def __init__(self, access_id=None, access_key=None, s3_endpoint=None):
        super().__init__()
        self.__access_id = access_id if access_id is not None else default_access_id
        self.__access__key = access_key if access_key is not None else default_access_key
        self.s3_endpoint = s3_endpoint if s3_endpoint is not None else default_s3_endpoint

        self.session = Session(aws_access_key_id=self.__access_id,
                               aws_secret_access_key=self.__access__key)
        self.s3 = self.session.resource('s3', endpoint_url=self.s3_endpoint)
        print("[Init] s3 server at {}".format(self.s3_endpoint))
        # 列出当前服务器中所有bucket
        for i, bucket in enumerate(self.s3.buckets.all()):
            print("[%d] Bucket Name: %s" % (i, bucket.name))
        

    def request_timing(self, s3_res, i, suffix=''):
        """
        发起对象存储请求并计算系统的停留时间

        Params
        ------
        s3_res : 独立的session.resource, 保证线程安全
        i : 对象编号
        suffix : 对象名后缀，用以区分不同大小的对象等 
        """
        obj_name = "testObj%08d%s" % (i, suffix, )
        start = time.time()
        s3_res.Object(self.test_bucket_name, obj_name).upload_file(self.test_file)
        end = time.time()
        system_time = end - start

        return system_time * 1000

    # 按照请求到达率限制，执行并跟踪请求

    # 请求发送无限制
    def arrival_rate_max(self, s3_res, i, suffix=''):
        return self.request_timing(s3_res, i, suffix)
    
    # 0.1s(100ms)内不超过2个请求
    @throttle.wrap(0.1, 2)
    def arrival_rate_2(self, s3_res, i, suffix=''):
        return self.request_timing(s3_res, i, suffix)
    
    @throttle.wrap(0.1, 4)
    def arrival_rate_4(self, s3_res, i, suffix=''):
        return self.request_timing(s3_res, i, suffix)

    @throttle.wrap(0.1, 8)
    def arrival_rate_8(self, s3_res, i, suffix=''):
        return self.request_timing(s3_res, i, suffix)

    async def hedged_request(self, s3_res, i, suffix=''):
        '''
        模拟对冲请求，使用asyncio

        发送的请求如果在限定延迟后还未到达，立即发送第二个请求
        接收到任意一个请求的返回值后，取消其他请求

        Return
        ------
        latency (float) : 小于给定阈值的延迟，单位ms
        '''
        obj_name = "testObj%08d%s" % (i, suffix, )
        latency = 0

        async def write_object():
            start = time.time()
            s3_res.Object(self.test_bucket_name, obj_name).upload_file(self.test_file)
            end = time.time()
            return (end - start) * 1000

        # 如果超时则再发一次请求，直到某次请求的延迟小于timeout即可
        while latency == 0:
            try:
                # 超时时间设置为200ms，超时后自动取消
                latency = await asyncio.wait_for(write_object(), timeout=0.2)
            except asyncio.TimeoutError as timeout:
                print("[INFO] Time out!Submitting a new hedged request...")
                continue

        return latency
            
    def wrapper_coroutine_run(self, coroutine):
        return asyncio.run(coroutine)

    @staticmethod
    def get_quantile_num(latency, percentile):
        '''
        根据给定的latency数组获取指定分位数并返回
        '''
        df = pd.DataFrame(latency, columns=['latency'])
        return df.quantile(percentile).iloc[0]

    def latency_collect(self, object_num=100, object_size=4, workers=1, request_func=None):
        '''
        收集延迟

        Params
        ------
        object_num (int) : 写入对象个数
        object_size (int) : 每个对象的尺寸
        workers (int) : 并发数
        request_func (function object) : 采用的请求函数，默认为arrival_rate_max，不对请求作限制
        '''
        # 打印参数
        print("********************************************\n[INFO] Begin a new round of performance test")
        print("[Test Params]\n对象个数: {}\n对象尺寸: {}\n并发数: {}".format(object_num, object_size, workers))
        
        # 绑定要使用的写请求函数，如果默认使用arrival_rate_max会因其未绑定实际对象而不能执行
        # 注意，传入的request_func如果不是None, 通常都是用instance.func作为已绑定类实例的函数对象传入
        if request_func is None:
            request_func = self.arrival_rate_max
        print("[Using Request Function] %s" % (request_func.__name__))

        # 初始化测试用数据文件
        self.test_file = "_test_%dK.bin" % object_size
        # 填充数据文件至对应大小
        test_bytes = [0xFF for i in range(1024 * object_size)]

        with open(self.test_file, "wb") as lf:
            lf.write(bytearray(test_bytes))

        suffix = "per%dkb" % (object_size,)

        # 新建测试用Bucket
        self.test_bucket_name = 'test%dobjs' % (object_num,)
        if self.s3.Bucket(self.test_bucket_name) not in self.s3.buckets.all():
            self.s3.create_bucket(Bucket=self.test_bucket_name)
        
        test_bucket = self.s3.Bucket(self.test_bucket_name)

        latency = []
        failed_requests = []

        with tqdm(desc="Accessing S3 at %s" % self.s3_endpoint, total=object_num) as pbar:
            with ThreadPoolExecutor(max_workers=workers) as executor:   # 设置并发线程数
                if request_func != self.hedged_request:
                    futures = [
                        executor.submit(
                            request_func,
                            self.session.resource('s3', endpoint_url=self.s3_endpoint),
                            i,
                            suffix
                        ) for i in range(object_num)
                    ]
                    for future in as_completed(futures):
                        if future.exception():
                            failed_requests.append(future)
                        else:   # 正常执行的请求，采集其延迟
                            latency.append(future.result())
                        pbar.update(1)
                else:
                    # 模拟对冲请求，由于被async修饰的hedged_request()函数只是个尚未执行的协程，使用wrapper包装一个asyncio.run()函数
                    # 交付ThreadPoolExecutor使用map执行每一个协程
                    coros = [request_func(self.session.resource('s3', endpoint_url=self.s3_endpoint),
                            i,
                            suffix) for i in range(object_num)]
                    for r_latency in executor.map(self.wrapper_coroutine_run, coros):
                        latency.append(r_latency)
                        pbar.update(1)

        try:
            test_bucket.objects.filter().delete()   # 删除测试桶内所有对象
            test_bucket.delete()                    # 删除测试桶
        except botocore.exceptions.ClientError as e:
            print('[Error] Cannot remove test bucket')

        # 移除本地测试用的数据文件
        os.remove(self.test_file)

        latency_file = "latency_%dobjs_per%dk_%dworkers.csv" % (object_num, object_size, workers)

        with open(latency_file, "w+") as tracefile:
            tracefile.write("latency\n")
            tracefile.writelines([str(l) + '\n' for l in latency])

        # 计算总吞吐率
        total_transferred = (object_num * object_size ) / 1024  # 计算总的数据交换大小
        total_duration = sum(latency) / 1000                    # 总延迟耗时
        throughput = total_transferred / total_duration

        print('[Result Analysis]\nTotal Transferred : %.3f MB\nTotal Duration : %.3f s\nThroughput : %.2f MB/s'
              % (total_transferred, total_duration, throughput))

        # 测试时绘图用
        # self.latency_plot(latency_file)
        # 获取99%分位数
        quantile_at_99 = self.get_quantile_num(latency, 0.99)

        return latency_file, throughput, quantile_at_99
        
    def latency_plot(self, latency_file : str):
        """
        绘制延迟参数图

        Params
        ------
        latency_file (str) : 收集的延迟参数文件名，格式latency_xx_xx.csv
        """
        latency = pd.read_csv(latency_file).apply(pd.to_numeric).values
        plt.subplot(211)
        plt.plot(latency)
        plt.subplot(212)
        plt.plot(sorted(latency, reverse=True))
        plt.show()

        def to_percent(y, position):
            return str(100 * round(y, 2)) + '%'

        formatter = FuncFormatter(to_percent)
        # 得到当前活动子图(Axes对象)
        ax = plt.gca()
        ax.set_title(latency_file.split('.')[0])
        ax.set_xlabel('Latency/ms')
        ax.set_ylabel('Percentile')
        # 纵轴转换为百分比显示
        ax.yaxis.set_major_formatter(formatter)
        # 横轴调节坐标范围，防止数据起始位置与纵轴重合影响观感
        x_min = max(min(latency) * 0.8, min(latency) - 5)
        x_max = max(latency)
        plt.xlim(x_min, x_max)
        # 绘制实际百分位延迟，以阶跃式直方图呈现
        cdf, bins, patches = plt.hist(latency, cumulative=True, histtype='step', weights=[1./len(latency)]*len(latency), label='Cumulative Histogram')

        # 使用排队论模型绘制曲线
        # F(t) = 1 - e^{-1 * alpha * t}
        # 注意这里的相对延迟t, 用测试数据中的最小延迟去减所有延迟，得到的就是-1 * (各延迟数据 - 最小延迟)
        alpha = 0.3
        X_qt = np.arange(min(latency), max(latency), 1.)
        Y_qt = 1 - np.exp(alpha * (min(latency) - X_qt))

        # 绘制排队论模型，与百分位延迟共享同一张子图
        plt.plot(X_qt, Y_qt, label='Queuing Theory Model')
        # 在99%百分位处绘制虚线
        y_99 = 0.99
        x_99 = self.get_quantile_num(latency, y_99)
        # x_99 = min(latency) - round(1 / alpha * np.log(1 - y_99))

        plt.axhline(y=y_99, linestyle=':', alpha=0.7, color='red', lw=2)
        plt.text(x=X_qt[len(X_qt)//2], y=y_99+0.005, s=formatter(y_99), multialignment='center')

        plt.axvline(x=x_99, linestyle=':', alpha=0.7, color='red', lw=2, label='99% Qutantile')
        plt.text(x=x_99+2, y=0.5, s="%.3f ms" % x_99, rotation=90, multialignment='center')

        plt.grid(alpha=0.5)
        plt.legend(loc='lower right')
        plt.show()
        
    def latency_compare(self, init_size=1, step=2, rounds=10, object_num=100, workers=1):
        '''
        根据给定倍增系数step改变object的大小，然后采集延迟，并绘制对比图

        Params
        ------
        init_size (int) : 对象初始尺寸 default 1
        step (int) : 尺寸倍增倍数 default 2
        rounds (int) : 倍增次数 default 10
        object_num (int) : 对象个数 default 100
        workers (int) : 并发数 default 1
        '''
        # 字典，存储不同对象尺寸的性能测试结果
        diff_size_latencies = {
            'object_sizes': [init_size * (step ** i) for i in range(rounds + 1)],
            'throughput': [],
            'quantile': [],
        }
        for i in range(rounds + 1):
            cur_size = init_size * (step ** i)
            # 第一个返回值为采集延迟后保存的文件，这里不需要用到
            _, throughput, quantile_at_99 = self.latency_collect(object_num=object_num, object_size=cur_size, workers=workers)
            diff_size_latencies['throughput'].append(throughput)
            diff_size_latencies['quantile'].append(quantile_at_99)

        # 绘制比较图
        x_axis = [str(size)+'KB' for size in diff_size_latencies['object_sizes']]
        ax = plt.gca()
        ax.set_title("Different Object Size Comparation")
        ax.set_xlabel('Object Sizes | KB')
        ax.set_ylabel('Quantile at 99% | ms')
        line1 = ax.plot(x_axis, diff_size_latencies['quantile'], color='red', label='Quantile at 99%')
        ax2 = ax.twinx()
        line2 = ax2.plot(x_axis, diff_size_latencies['throughput'], color='green', label='Throughput')
        ax2.set_ylabel('Throughput | MB/s')
        lines = line1 + line2
        ax.legend(lines, [l.get_label() for l in lines], loc='upper left')
        ax.grid()
        plt.show()

if __name__ == "__main__":
    tester = PerformanceTester()
    # 测试256个32KB对象，使用8个线程写入对象存储服务器
    latency_file, _, _ = tester.latency_collect(object_num=256, object_size=32, workers=8)
    # 相当于tester.latency_plot('latency_256objs_per32k_8workers.csv')
    tester.latency_plot(latency_file)

    # 测试对象尺寸对延迟的影响
    # tester.latency_compare(init_size=1, step=2, rounds=10, object_num=256, workers=8)

    # 模拟对冲请求
    hedged_latency_file, _, _ = tester.latency_collect(object_num=256,
                                                object_size=32,
                                                workers=8,
                                                request_func=tester.hedged_request)
    tester.latency_plot(hedged_latency_file)