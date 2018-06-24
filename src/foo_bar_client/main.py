
# 不再需要,已经在启动脚本操作 PYTHONPATH 环境变量
# sys.path.extend(['utility', 'share', 'rpc', '../pb2'])  # 路径不能以/或\结尾,可以用相对路径

import application_base
import end_point

class Application(application_base.ApplicationBase):
    def run(self):  # override
        super().run()

        import client
        client.test()
        client.ep_maker.connect_until_success()

        # import gevent
        def loop():
            while True:
                ep = client.ep_maker.get_endpoint()
                # ep.rpc_do_something(123, 'bbbb', 1000,56456)
                ep.rpc_do_something(bar1=123, bar2='bbbb', countMax=1000)
                try:
                    xxx = ep.rpc_hello_world(bar1=123, bar2='bbbb', countMax=1000)
                except end_point.RpcTimeout as e:
                    fail_msg, = e.args
                    print(f'etype={type(e)}, reason={fail_msg.reason}, code= {fail_msg.code}')
                except end_point.RpcFail as e:
                    fail_msg, = e.args
                    print(f'etype={type(e)}, reason={fail_msg.reason}, code= {fail_msg.code}')

                print('sended...')
                gevent.sleep(1)

        import gevent
        gevent.spawn(loop)
        gevent.get_hub().join()


if __name__ == '__main__':
    app = Application()
    app.run()
