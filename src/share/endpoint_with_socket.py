import socket

import gevent
import gevent.queue
import gevent.timeout

import buf
import end_point
import util
import codec

GRACEFULLY = object()


class EndPointWithSocket(end_point.EndPointBase):
    spawn = gevent.spawn
    SEND_QUEUE_SIZE = None  # 消息包的个数,若是无上限,则赋值为None
    send_queue_cls = gevent.queue.Queue

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.recv_job = self.send_job = None
        self.socket = None
        self.send_queue = self.send_queue_cls()
        self.decoder, self.encoder = self._get_decoder(), self._get_encoder()
        self.stop_iteration = False

    def set_socket(self, sock):
        self.socket = sock
        sock.setsockopt(socket.SOL_TCP, socket.TCP_NODELAY, 1)
        return self

    def start(self):  # implement
        f = util.Functor(self.__recv_proc)
        self.recv_job = self.spawn(f)

        f = util.Functor(self.__after_recv_job_exit)
        self.recv_job.link(f)

        f = util.Functor(self.__send_proc)
        self.send_job = self.spawn(f)

        f = util.Functor(self.__after_send_job_exit)
        self.send_job.link(f)

    def join(self, timeout=None):
        self.recv_job.join(timeout)
        self.send_job.join(timeout)

    def force_destroy(self):  # override
        super().force_destroy()
        if self.send_job:
            self.send_job.kill()
        if self.recv_job:
            self.recv_job.kill()

    # noinspection PyMethodMayBeStatic
    def _get_decoder(self):
        return codec.Decoder(1 * 1024 * 1024)  # 最大能接收的逻辑包大小,1兆

    # noinspection PyMethodMayBeStatic
    def _get_encoder(self):
        return codec.Encoder()

    def follow_up(self, timeout=3):  # override
        if self.send_job:
            if not self.stop_iteration:  # 收到fin但不是我方主动shutdown引起的
                self.send_packet(StopIteration)  # 让发送队列中的发送完毕
            self.send_job.join(timeout)  # 如果我方已经放了StopIteration,也可能正发送中就收到fin
        super().follow_up(timeout)

    def __after_recv_job_exit(self, recv_job):
        if recv_job.value is GRACEFULLY:  # 没有异常,包括被kill的GreenletExit
            self.follow_up()
        else:
            self.force_destroy()

        self.decoder.reset()
        self.socket.close()  # 真正地全关闭
        self._on_dis_connected()

    def __after_send_job_exit(self, send_job):
        if send_job.value is GRACEFULLY:  # 优雅退出
            pass
        else:  # 抛异常退出(包括被kill抛GreenletExit退出)
            self.force_destroy()

    def __send_proc(self):
        pack_head_and_send = self.pack_head_and_send

        for packet in self.send_queue:
            pack_head_and_send(packet)
            # self.write_complete()
        self.socket.shutdown(socket.SHUT_WR)
        return GRACEFULLY
        # socket.error

    # noinspection PyMethodMayBeStatic
    def get_buffer_obj(self):
        return buf.Buffer()

    def __recv_proc(self):
        buffer = self.get_buffer_obj()

        recv_into = self.socket.recv_into
        peek_write = buffer.peek_write
        has_written = buffer.has_written
        decode = self.decoder.decode
        recv_packet = self.recv_packet
        intercept_and_deal = self.intercept_and_deal

        while True:
            mv = peek_write()
            size = recv_into(mv)
            if size == 0:  # 收到了Fin分节
                return GRACEFULLY
            has_written(size)

            for packet in decode(buffer):
                intercept, new_packet = intercept_and_deal(packet)
                if intercept:
                    continue
                is_request, request, now = recv_packet(new_packet)
                if is_request:
                    self.deal_request(now, request)

    # noinspection PyMethodMayBeStatic
    def intercept_and_deal(self, packet):  # 是否拦截并处理
        return False, packet

    def send_packet(self, packet):  # override
        if not self.send_job or self.stop_iteration:
            return
        if self.SEND_QUEUE_SIZE and self.send_queue.qsize() >= self.SEND_QUEUE_SIZE:  # 对待接收缓慢者,严格的手段,断开连接(服务器之间的连接不能这么做)
            text = '发送队列满了,包数量 {},即将关闭socket,{} '.format(self.send_queue.qsize(), self.selfDescription())
            self.log('info', text)
            print(text)
            self.socket.close()
            self.recv_job.kill()
            return
        self.send_queue.put(packet)

    def pack_head_and_send(self, packet):
        self.socket.sendall(self.encoder.encode(packet))

    def shutdown(self, timeout=1):  # override 相当于是一个rpc调用
        if self.stop_iteration or not self.send_job:
            return
        self.stop_iteration = True
        self.send_queue.put(StopIteration)  # 让已经进了队列的数据发完.
        try:
            self.recv_job.get(True, timeout)  # n秒内要收到客户端的fin,因为客户端可能收fin后但是就不愿意shutdown(恶意的客户端)
        except gevent.timeout.Timeout:
            self.recv_job.kill()

