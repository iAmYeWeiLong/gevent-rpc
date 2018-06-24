import sys
import os


# 不再需要,已经在启动脚本操作 PYTHONPATH 环境变量
# sys.path.extend(['utility', 'share', 'rpc', '../pb2'])  # 路径不能以/或\结尾,可以用相对路径

import application_base


class Application(application_base.ApplicationBase):
    def run(self):  # override
        super().run()

        import test_server
        server = test_server.init_server()
        server.serve_forever()


if __name__ == '__main__':
    app = Application()
    app.run()
