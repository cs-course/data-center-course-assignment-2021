from minio import Minio


def main():
    # 连接服务器
    client = Minio(
        "127.0.0.1:9000",
        access_key="hust",
        secret_key="hust_obs",
        secure=False
    )

    # # create
    # if not client.bucket_exists('yzw'):
    #     client.make_bucket('yzw')
    # # upload objects
    # client.fput_object('yzw', '念奴娇·赤壁怀古.txt', '念奴娇·赤壁怀古.txt')
    # client.fput_object('yzw', '向日葵.jpg', '向日葵.jpg')

    # # read
    # client.fget_object('yzw', '念奴娇·赤壁怀古.txt', 'dl.txt')
    # client.fget_object('yzw', '向日葵.jpg', 'dl.jpg')

    # # update
    # f = open('念奴娇·赤壁怀古.txt', 'a', encoding='utf-8')
    # f.write('\n 滚滚长江东逝水 \n')
    # f.close()
    # client.fput_object('yzw', '念奴娇·赤壁怀古.txt', '念奴娇·赤壁怀古.txt')
    # # client.fget_object('yzw', '念奴娇·赤壁怀古.txt', 'dl.txt')

    # # delete
    # client.remove_object('yzw', '念奴娇·赤壁怀古.txt')
    # client.remove_object('yzw', '向日葵.jpg')
    # client.remove_bucket('yzw')


if __name__ == "__main__":
    main()
