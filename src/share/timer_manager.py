import gevent
import gevent.core
import util


# 定时器优先级
HIGHTEST = 2  # 最高
HIGHT = 1  # 高
NORMAL = None  # 普通
LOW = -1  # 低
LOWEST = -2  # 最低

NOT_DELAY = 0  # 不延迟,马上执行
NOT_REPEAT = 0  # 只执行一次,不重复

NO_NAME = ''


# 定时器管理器

# 最重要的作用是对各种传进来的函数指针作弱引用处理.避免循环引用

class TimerManager(object):
    spawn = gevent.spawn

    def __init__(self):
        self.timer_dict = {}
        self.id = 0  # 如果注册定时器时没有提供标识,则自动生成标识

    # 在n秒后运行
    # delay负数表示立即执行
    # interval不能小于0,等于0表示不重复
    def run(self, callback_func, delay, interval=NOT_REPEAT, timer_id=NO_NAME, priority=NORMAL):
        if isinstance(timer_id, int):
            raise RuntimeError('定时器名字不能是数值型')  # 目的是防止与自动生成的id重复
        if priority is not None and not LOWEST <= priority < HIGHTEST:
            raise RuntimeError('优先级必须是[-2,2]或者是None,None代表0.')
        if timer_id:  # 停掉原来的同id定时器
            self.cancel(timer_id)
        if delay > 30 * 24 * 3600:  # 基本上不可能30天服务器没有重启
            return 0
        helper_func, callback_func = util.make_weak_func(self._call_helper, callback_func)

        if timer_id != NO_NAME:
            timer_id = timer_id
        else:
            self.id += 1
            timer_id = self.id

        self.timer_dict[timer_id] = tm = gevent.get_hub().loop.timer(delay, interval, True, priority)
        once = False if interval > 0 else True
        tm.start(helper_func, timer_id, callback_func, once)
        return timer_id

    def _call_helper(self, timer_id, callback_func, once):
        # 这里一定是hub协程
        if once:
            self.cancel(timer_id)
        self.spawn(callback_func)

    def cancel(self, timer_id):  # 停止某个定时器
        timer = self.timer_dict.pop(timer_id, None)
        if timer:
            timer.stop()

    def cancel_all(self):  # 停止全部定时器
        for timer_id, timer in self.timer_dict.items():
            timer.stop()
        self.timer_dict = {}

    def has_timer_id(self, timer_id):
        return timer_id in self.timer_dict

    def has_timer(self):
        return self.timer_dict
