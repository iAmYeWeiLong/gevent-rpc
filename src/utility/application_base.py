class ApplicationBase:
    def __init__(self):
        pass

    def run(self):
        import sys
        import os

        print('模块搜索路径: ')
        for s in sys.path:
            print('\t{}'.format(s))
        print('\n')
        print('工作目录: {}'.format(os.getcwd()))

        import tools
        tools.set_g('set_g', tools.set_g)

        # import std_file
        # sys.stderr = std_file.StdErr()  # 重定向标准错误.把错误内容输到log中去.(默认的标准错误是输出到屏幕的)

        import gevent.monkey
        gevent.monkey.patch_socket()
        gevent.monkey.patch_time()
        gevent.monkey.patch_ssl()

        # import gc
        # if config.IS_INNER_SERVER:
        #     gc.set_debug(gc.DEBUG_LEAK)  # 这个设定的作用是:在collect后,会把循环引用对象移到gc.garbage,方便分析

        # def collect():
        #   print
        #   gc.collect()

        #   goTimerMng=timer.TimerManager()
        #   guTimerId=goTimerMng.run(lambda:gc.collect(),300,300)#每10秒一次gc
