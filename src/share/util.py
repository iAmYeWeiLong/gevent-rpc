import traceback
import sys
import weakref
import types


# 函数对象(仿函数),C++中也有此概念
# 作用有二,1.闭包 2.生成弱引用的函数指针
# 不要研究此版本，此版本较复杂一点点，直接看下面那个已被注释掉的Functor,对使用者来说功能是一模一样的
class Functor(object):
    def __init__(self, func, *args, **kwargs):
        # 被打包的函数处理
        self.func, self.wr = _parse_callable(func)

        if True:
            for obj in args:
                if type(obj) == weakref.ProxyType:
                    raise RuntimeError('你要存储对象的id,不要存对象本身')
            for obj in kwargs.values():
                if type(obj) == weakref.ProxyType:
                    raise RuntimeError('你要存储对象的id,不要存对象本身')
        self.args = args
        self.kwargs = kwargs

    def __call__(self, *args, **kwargs):  # 重载()运算符
        if self.kwargs and kwargs:  # 复制出新的dict,不要修改原来的dict
            temp_kwargs = kwargs.copy()
            temp_kwargs.update(self.kwargs)  # 合并两个个字典
        elif self.kwargs:
            temp_kwargs = self.kwargs
        else:
            temp_kwargs = kwargs
        if not self.wr:
            return self.func(*(args + self.args), **temp_kwargs)
        elif self.wr():
            return self.func(self.wr(), *(args + self.args), **temp_kwargs)

    def is_valid(self):  # 是否还可以调用
        if not self.wr:  # 全局函数或类方法总是有效的
            return True
        return self.wr()  # 实例方法,取决于相关实例是否活着

    def __repr__(self):  # 调试用的
        return self.func_code()

    def inner_func_obj(self):
        return self.get_func_obj(self.func)

    @staticmethod
    def get_func_obj(call_obj):
        while call_obj and isinstance(call_obj, Functor):
            call_obj = call_obj.func

        if isinstance(call_obj, types.MethodType):
            return call_obj.__func__
        return call_obj

    def func_name(self):  # 调试用的
        func = self.inner_func_obj()
        if func:
            return '{}'.format(func.__name__)  # func_name
        return '{}'.format(func)

    def func_code(self):  # 调试用的
        func = self.inner_func_obj()
        if func:
            return '{}'.format(func.__code__)
        return '{}'.format(func)


"""
简化版的函数对象(仿函数)
这个版本不够完美,保存一个函数指针时会增加引用计数,上面那个版本使用弱引用则不会增加引用计数
class Functor(object):
    def __init__(self,func,*args,**kwargs):
        self.func=func
        self.args=args
        self.kwargs=kwargs
    def __call__(self,*args,**kwargs):
        if self.kwargs and kwargs:
            temp_kwargs=kwargs.copy()
            temp_kwargs.update(self.kwargs)
        elif self.kwargs:
            temp_kwargs=self.kwargs
        else:
            temp_kwargs=kwargs
        return self.func(*(args+self.args),**temp_kwargs)
"""


# 事件(观察者模式)
class Event(object):
    def clear_observer(self):  # 清空监听的函数
        self.event_handler_group = []  # 事件响应函数,即是一堆函数指针

    # 返回观察者数量
    def observer_count(self):
        return len(self.event_handler_group)

    def contain(self, handler):  # 是否在观察者列表中
        handler_info = _parse_callable(handler)
        return handler_info in self.event_handler_group

    def clear_dead(self):  # 删掉死亡的观察者
        size = len(self.event_handler_group)
        for i in range(size - 1, -1, -1):  # 从后往前pop,才不会有跳跃行为
            handler, wr = self.event_handler_group[i]
            if wr and not wr():  # 是实例方法,但是观察者已死
                self.event_handler_group.pop(i)

    def __init__(self):
        self.event_handler_group = []

    def __iadd__(self, handler):  # 增加观察者,重载+=运算符
        self.clear_dead()  # 顺便尝试清理死掉的事件响应函数
        handler_info = _parse_callable(handler)
        if handler_info not in self.event_handler_group:
            self.event_handler_group.append(handler_info)
        return self

    def __isub__(self, handler):  # 减少观察者,重载-=运算符
        self.clear_dead()  # 顺便尝试清理死掉的事件响应函数
        handler_info = _parse_callable(handler)
        size = len(self.event_handler_group)
        for i in range(size - 1, -1, -1):  # 从后往前pop,才不会有跳跃行为
            if self.event_handler_group[i] == handler_info:
                self.event_handler_group.pop(i)
        return self

    # 触发事件
    # 重载()运算符
    def __call__(self, *args, **kwargs):
        result = has_dead = False
        dead_indices = []
        # 改为使用切片,因为要复制一份list,防止在遍历过程中某个事件的行为影响到其他的事件
        event_handler_group = self.event_handler_group[:]
        for idx, handler_info in enumerate(event_handler_group):
            handler, wr = handler_info
            # noinspection PyBroadException
            try:
                if not wr:
                    result = handler(*args, **kwargs)
                elif wr():
                    result = handler(wr(), *args, **kwargs)
                else:
                    has_dead = True
                dead_indices.append(idx)  # 已死亡的观察者,记录下来他的索引,要清理掉
                if result:  # 上一个事件处理函数返回True则停止执行剩下的事件响应函数
                    break
            except Exception:
                exception_to_stderr()

        if has_dead:
            self.clear_dead()

        size = len(dead_indices)
        for i in range(size - 1, -1, -1):  # 正式删掉死亡的观察者,从后往前pop,才不会有跳跃行为
            idx = dead_indices[i]
            self.event_handler_group.pop(idx)
        return result


def exception_to_stderr(extra='', skip=0):
    etype, value, tb = sys.exc_info()
    if etype is None or value is None or tb is None:  # 根本没有异常
        return

    # 把之前的调用栈也弄出来
    lines = traceback.format_list(traceback.extract_stack())[skip:-2]
    text1 = ''.join(lines)
    text2 = traceback.format_exc()  # traceback.print_exc()
    if extra:
        text_all = '{}{}\n\n{}{}\n{}'.format(SEPARATOR_1, text1, SEPARATOR_2, text2, extra)  # u.py 
    else:
        text_all = '{}{}\n\n{}{}'.format(SEPARATOR_1, text1, SEPARATOR_2, text2)
    sys.stderr.write(text_all)


def make_weak_func(*funcs):  # 解出带弱引用指针的functor
    if not funcs:
        raise RuntimeError('至少请传一个参数')
    lst = []
    for func in funcs:
        if type(func) not in NEED_WRAP_TYPE:
            func = Functor(func)  # Functor有存储弱引用的功效.
        lst.append(func)  # 即使传None过来也会原样返回None
    return lst


def _parse_callable(func):  # 分解函数,使用弱引用可以不增加引用计数
    if isinstance(func, NEED_WRAP_TYPE):  # 全局函数或是一个子functor
        return func, None
    elif isinstance(func, types.MethodType):  # 实例方法或类方法
        if func.__self__:  # func.im_self
            return func.__func__, weakref.ref(func.__self__)
        else:
            return func.__func__, None  # im_func
    else:
        raise RuntimeError('未知的callable对象')


#  用于重新抛出异常
def wrap_except(text, exception_type=None):  # text  异常提示信息
    etype, value, tb = sys.exc_info()
    message = str(value)
    if exception_type is None:
        return etype(f'{text};{message}', tb)
    else:
        return exception_type(f'{text};{etype.__name__}:{message}', tb)


NEED_WRAP_TYPE = (types.FunctionType, Functor)
SEPARATOR_1 = '==============================================================\n'
SEPARATOR_2 = '--------------------------------------------------------------\n'
