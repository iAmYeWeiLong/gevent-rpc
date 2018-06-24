import gevent
import gevent.core
import gevent.event
import gevent.timeout

import util
import end_point

'''
class EndPointWithoutSocket(end_point.EndPointBase):
    spawn = gevent.spawn
    request_queue_cls = gevent.queue.Queue
    RECV_QUEUE_SIZE = None  # 消息包的个数,若是无上限,则赋值为None

    def __init__(self, *args, **kwargs):  # override
        super().__init__(*args, **kwargs)
        self.serialized_ep_id = None
        self.wait_close = gevent.event.Event()
        self.stop_iteration = False
        self.request_queue = self.request_queue_cls(self.RECV_QUEUE_SIZE)  # 防止积累过多的请求
        self.boss_job = None

    def follow_up(self, timeout=3):  # override
        if self.boss_job:
            self.request_queue.put(StopIteration)
            self.boss_job.join(timeout)

    def force_destroy(self):  # override
        super().force_destroy()
        if self.boss_job:
            self.boss_job.kill()

    def start(self):  # implement
        f = util.Functor(self.__boss_proc)
        self.boss_job = self.spawn(f)

    def recv_packet(self, buffer_bytes):  # override
        is_request, request, now = super().recv_packet(buffer_bytes)
        if not is_request:
            return
        # 需要判断recv_queue是否快满了,满了要发信号给网关,断开客户端链接
        if self.request_queue.full():
            text = f'接收队列满了{self} full,队列长度{self.request_queue.qsize()}'
            self.log('info', text)
        self.request_queue.put((now, request))

    def __boss_proc(self):
        for recv_time_stamp, request in self.request_queue:
            self.deal_request(recv_time_stamp, request)

    def send_packet(self, packet):  # override
        if self.stop_iteration and packet != StopIteration:
            return
        ep = self._get_endpoint_to_send()
        if not ep:
            print('not sender')
            return

        if packet == StopIteration:
            ep.rpcShutdownGameClient(self.iEndPointId)  # 向网关发包,有客户端连接要断开
        else:
            if self.serialized_ep_id is None:
                raise RuntimeError('没有设置包前缀')
            ep.send_packet(packet, self.serialized_ep_id)

    def set_target_prefix(self, serialized_ep_id):
        self.serialized_ep_id = serialized_ep_id

    def shutdown(self, timeout=1):  # override 主动关闭,关闭写,半关闭(应该理解成是一个rpc调用)
        if self.stop_iteration:  # not self.sendJob or
            return
        self.stop_iteration = True
        self.send_packet(StopIteration)  # 让已经进了队列的数据发完.
        self.wait_close.wait(timeout)
        self._on_dis_connected()

    def recv_shutdown(self):
        # follow_up

        self.force_destroy()
        if self.stop_iteration:  # 是我方主动调用shutdown关闭的
            self.wait_close.set()
        else:
            self._on_dis_connected()

    def _get_endpoint_to_send(self):
        raise NotImplementedError('请在子类实现')
'''
