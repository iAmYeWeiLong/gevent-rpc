import gevent
import gevent.socket
import gevent.lock

import util

# import myGreenlet

# import log
# import misc
# import config

import foo_pb2
import endpoint_with_socket
import server_to_terminal_service


class _DummyEndpoint(object):
    def __getattr__(self, attr_name):
        raise RuntimeError('无效的endpoint,使用endpoint前要先判断其有效性')

    def __bool__(self):  # 用if obj判断时,返回结果为假
        return False


_dummy_endpoint = _DummyEndpoint()
del _DummyEndpoint


class EndpointMaker(object):
    lock_cls = gevent.lock.RLock
    MIN_DELAY, MAX_DELAY = 0.01, 3
    endpoint_cls = endpoint_with_socket.EndPointWithSocket
    spawn = gevent.spawn

    def __init__(self, host, port, services, stubs):
        self.host = host
        self.port = port
        self.endpoint = None
        self.create_lock = self.lock_cls()
        self.get_lock = self.lock_cls()
        self.protocol = {'services': services, 'stubs': stubs}

    def connect_until_success(self):  # 尝试连接,直到成功
        delay = self.MIN_DELAY
        self.log('info', '尝试重连到服务器,直到成功')
        while True:
            ep = self.get_endpoint()  # 获取时会自动连
            if ep:  # 连接成功
                return ep
            delay = min(self.MAX_DELAY, delay * 2)
            gevent.sleep(delay)

    def _connect_once(self):
        with self.create_lock:  # 要加锁,因为创建连接是异步过程
            if self.endpoint is not None:  # 已建立了连接了
                return
            host, port = self.host, self.port
            self.log('info', f'尝试连接到{host}:{port}')
            # noinspection PyBroadException
            try:
                sock = gevent.socket.create_connection((host, port))
            except Exception as e:  # ConnectionRefusedError
                text = f'连接{host}:{port}失败.{e}'
                self.log('info', text)
                return
            text = f'连接{host}:{port}成功'
            self.log('info', text)

            self.endpoint = self.endpoint_cls(self.protocol)
            self.endpoint.dis_connected += self.endpoint_dis_connect
            self.endpoint.set_host(self.host).set_port(self.port).set_socket(sock)
            self.endpoint.start()

    def endpoint_dis_connect(self, ep):
        self.log('info', f'{ep}断线了')
        self.endpoint = None

        # 断线了,要尝试重连.启动一个协程里不断地尝试
        f = util.Functor(self.connect_until_success)
        self.spawn(f)

    def get_endpoint(self):  # 取得ep,没有则连接服务器后再返回ep
        if self.endpoint:  # 大多数是走这里进去了,如果仅有下面的代码每次都加锁,不好
            return self.endpoint

        with self.get_lock:
            if self.endpoint is None:
                self._connect_once()
            if self.endpoint is None:
                return _dummy_endpoint
            return self.endpoint

    # noinspection PyMethodMayBeStatic
    def log(self, log_type, text):
        print(f'{log_type}:{self}:{text}')

    def __str__(self):
        return f'{repr(self)}'
