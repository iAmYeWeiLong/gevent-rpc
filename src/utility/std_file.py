import sys


# 标准错误.重定向到磁盘,或是Sentry
class StdErr(object):
    def __init__(self):
        self.old_std_err = sys.stderr  # 旧的fd

    def write(self, text):
        print(text)  # , #最后加上逗号,阻止自动加回车
        # self.old_std_err.write(text)

        # 在log线程没起来的情况下，把异常直接写入当前目录下的exception.log文件
        gThread = None
        if gThread:
            gThread.log('exception', text, None)
        else:
            f = open("except.log", "ab+")
            f.write(text)
            f.close()
