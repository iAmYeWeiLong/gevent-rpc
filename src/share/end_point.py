import weakref

import gevent
import gevent.event
import gevent.core
import gevent.timeout
import gevent.queue
import gevent.pool

import google.protobuf.service
import google.protobuf.message

import public_pb2
import util

from google.protobuf.message import Message, DecodeError
from public_pb2 import Fake, Request, Response, Packet, Fail
from public_pb2 import TYPE_REQUEST, TYPE_RESPONSE, TYPE_SUCCESS, TYPE_FAIL

from gevent import getcurrent, GreenletExit
from gevent.core import time

FAKE = public_pb2.Fake()
DUMMY_FAIL_INFO = ()


class RpcInterrupt(GreenletExit):
    pass


class RpcTimeout(RpcInterrupt):
    pass


class RpcFail(RpcInterrupt):
    pass


class EndPointBase(google.protobuf.service.RpcChannel):
    MAX_ID = 1 << 31
    AsyncResult = gevent.event.AsyncResult

    def __init__(self, protocol, endpoint_id=0):
        super().__init__()
        self.ep_id = endpoint_id
        self.dis_connected = util.Event()
        # self.write_complete = util.Event()  # 应用层缓冲区全部数据都写入到了系统缓冲区

        self.host_, self.port_ = 'no set', 0

        self.proxy = weakref.proxy(self)
        self.service_group, self.stub_group = [], []

        for cls in protocol.get('services', []):
            service = cls()
            self.service_group.append(service)

        for cls in protocol.get('stubs', []):
            stub = cls(self.proxy)
            self.stub_group.append(stub)

        self.pending_id, self.pending_rpc_name = {}, {}
        self.worker_job_group = set()  # 正在并发处理的job
        self.pool = self._get_pool()  # 协程池

        self.last_request_id = 0
        self.interface = self._get_interface()
        self.rpc_method_info = {}

    def this(self):
        return self

    # TODO 改成property
    def set_host(self, host):
        self.host_ = host
        return self

    def set_port(self, port):
        self.port_ = port
        return self

    def host(self):
        return self.host_

    def port(self):
        return self.port_

    def start(self):
        raise NotImplementedError('请在子类实现')

    def next_request_id(self):  # 生成request id,肯定不会是0,0用于表示无需回复的请求
        self.last_request_id += 1
        if self.last_request_id >= self.MAX_ID:
            self.last_request_id = 1
        return self.last_request_id

    def send_packet(self, packet_bytes):  # 允许多个生产者往send_queue塞数据
        raise NotImplementedError('请在子类实现')

    def endpoint_id(self):
        return self.ep_id

    def shutdown(self, timeout=1):  # 主动关闭,关闭写,半关闭(应该理解成是一个rpc调用)
        raise NotImplementedError('请在子类实现')

    # noinspection PyMethodMayBeStatic
    def _get_pool(self):
        return gevent.pool.Pool(100)  # 协程池,限制最大并发数

    def deal_request(self, recv_time_stamp, request):
        f = util.Functor(self._process_request)
        job = self.pool.spawn(f, recv_time_stamp, request)
        job.link(util.Functor(self.__remove_worker_job))
        self.worker_job_group.add(job)

    def __remove_worker_job(self, job):
        self.worker_job_group.discard(job)

    def __str__(self):
        return f'{repr(self)},endpoint id={self.ep_id},host={self.host_},port={self.port_}'
        # hex(id(self)), self.__class__.__module__, self.__class__.__name__

    # noinspection PyMethodMayBeStatic
    def log(self, log_type, text):
        print(f'{log_type}:{self}:{text}')

    def recv_packet(self, buffer_bytes):
        packet = Packet()
        try:
            packet.ParseFromString(buffer_bytes)
        except DecodeError:
            text = '收到的逻辑包有误,反序列化出错,收到字节流是"%r"' % buffer_bytes
            self.log('debug', text)
            return

        if packet.type == TYPE_REQUEST:
            if not self.service_group:
                self.log('debug', '收到一个请求,但是endpoint不接受任何请求.')
                return
            request = Request()
            try:
                request.ParseFromString(packet.serialized)
            except DecodeError:
                text = '请求的逻辑包有误,反序列化出错"%r"' % packet.serialized
                self.log('debug', text)
            now = self.interface.get_time_stamp()
            return True, request, now

        elif packet.type == TYPE_RESPONSE:
            self._process_response(packet.serialized)
            return False, None, 0
        else:
            self.log('debug', f'对端恶意:收到未知类型的网络包:{repr(packet)}.')
            return False, None, 0

    def _send_fail_with_field(self, request_id, reason, code=''):
        fail_msg = Fail(reason=reason)
        if code:
            fail_msg.code = code
        self._send_fail_with_msg(request_id, fail_msg)

    def _send_fail_with_msg(self, request_id, fail_msg):
        response = Response(response_id=request_id, sub_type=TYPE_FAIL, serialized=fail_msg.SerializeToString())
        packet = Packet(type=TYPE_RESPONSE, serialized=response.SerializeToString())
        self.send_packet(packet.SerializeToString())

    def get_controller_for_deal_request(self, method_name, request_id):  # 获取ctrl,在处理对端的请求时
        return self

    def _get_controller_for_send_request(self, method_name):  # 获取ctrl,在发送请求到对端时
        return self

    # noinspection PyMethodMayBeStatic
    def _get_interface(self):
        return Interface()

    def is_timeout(self, request, now, recv_time_stamp, method_name):
        if request.timeout <= 0:  # 对端对执行此请求无时间要求
            return False
        if request.time_stamp:
            send_stamp = request.time_stamp
        else:
            send_stamp = recv_time_stamp * 1000  # 对端没有填此域则以收包时间算

        if now * 1000 - send_stamp < request.timeout:
            return False

        text = '收到"{}"请求,还没有调用就发现已经超时.发送时间戳{},当前时间戳{},要求{}毫秒内要处理.'
        text = text.format(method_name, request.time_stamp, now * 1000, request.timeout)
        self.log('debug', text)

        return True

    def get_method_info(self, method_name):
        info = self.rpc_method_info.get(method_name)
        if info:
            return info
        for service in self.service_group:
            # noinspection PyBroadException
            try:  # FindMethodByName当找不到时,C++版本会抛异常,python版本会返回None,行为不一致
                method_descriptor = service.GetDescriptor().FindMethodByName(method_name)
                if method_descriptor:
                    break
            except Exception:
                pass
        else:
            text = f'收到"{method_name}"请求,但是这个rpc没有实现.'
            self.log('debug', text)
            return None, None, None, None

        request_cls = service.GetRequestClass(method_descriptor)
        response_cls = service.GetResponseClass(method_descriptor)
        self.rpc_method_info[method_name] = service, method_descriptor, request_cls, response_cls
        return service, method_descriptor, request_cls, response_cls

    def _process_request(self, recv_time_stamp, request):
        fail_info = None
        request_id = request.request_id
        # noinspection PyBroadException
        try:
            getcurrent().request_id = request_id
            method_name = request.method_name
            now = self.interface.get_time_stamp()

            # 尚未调用方法,已经超时
            if self.is_timeout(request, now, recv_time_stamp, method_name):
                if request_id != 0:
                    fail_info = f'无法在要求的时间内完成处理{method_name}.', ''
                return

            service, method_descriptor, request_cls, response_cls = self.get_method_info(method_name)
            if service is None:
                if request_id != 0:
                    fail_info = f'{method_name}方法不存在.', ''
                return

            if request.serialized:  # request.HasField('serialized') proto3已经去除此方法
                req_msg = request_cls()
                try:
                    req_msg.ParseFromString(request.serialized)
                except DecodeError:
                    text = f'rpc调用{method_name}时,反序列化msg失败,很可能消息定义不一致.'
                    self.log('debug', text)
            else:
                req_msg = None
            controller = self.get_controller_for_deal_request(method_name, request_id)
            if isinstance(controller, str):  # 表示没有通过授权或者其他上下文不存在
                text = controller
                if request_id != 0:
                    fail_info = text, ''
                self.log('debug', text)
                return

            response = service.CallMethod(method_descriptor, self.proxy, req_msg, controller)  # 分发到各rpc处理函数
            # TODO 记录时间消耗
            if response_cls == Fake:  # 无需回复的
                if response is not None:
                    raise RuntimeError(f'调用{method_name}方法无需回复,却返回了{response}')
                return
            if response is None:
                text = f'调用{method_name}方法返回{response},通常有3种原因. 1.没有实现{method_name}方法 2.函数返回值搞错了 3.正常情况,故意终止执行.'
                fail_info = text, ''
                self.log('debug', text)
                return

            elif isinstance(response, Fail):  # 失败
                self._send_fail_with_msg(request_id, response)
                fail_info = DUMMY_FAIL_INFO
                return
            # elif isinstance(response,list):#失败(以后不再支持此特性,因为使用者不易理解)
            # 	if len(response)>=2:
            # 		if response[1]<0:
            # 			raise RuntimeError('错误码必大于等于0.')
            # 	self._send_fail_with_field(request_id,*response)#失败原因
            # 	return
            elif isinstance(response, dict):  # 成功
                resp_msg = response_cls(**response)
            elif isinstance(response, tuple) or not isinstance(response, Message):  # 成功
                response = response if isinstance(response, tuple) else (response,)
                resp_msg = response_cls()
                for i, val in enumerate(response):
                    field_name = response_cls.DESCRIPTOR.fields[i].name
                    # noinspection PyBroadException
                    try:
                        setattr(resp_msg, field_name, val)
                    except Exception:
                        raise util.wrap_except(f'设置{response_cls}消息的字段值时出错.')
            else:  # 成功
                resp_msg = response  # 传过来的就是一个msg对象

            if not isinstance(resp_msg, Message):
                text = f'构造消息用以回复{method_name}的调用.期待一个msg对象,但却是type={type(resp_msg)},value={resp_msg}'
                raise RuntimeError(text)

            # noinspection PyBroadException
            try:
                serialized = resp_msg.SerializeToString()
            except Exception:
                raise util.wrap_except(f'序列化消息出错,用以回复{method_name}的调用')

            # 调用完成后发现超时了,就不发送给对端,省流量,反正对端也提前结束了
            if (request.time_stamp > 0 and request.timeout > 0) and (
                    self.interface.get_time_stamp() * 1000 - request.time_stamp >= request.timeout):
                text = '调用完{method_name}方法后回复响应时,已经超时.'

                fail_info = text, ''
                return
            response = Response(response_id=request_id, sub_type=TYPE_SUCCESS, serialized=serialized)
            packet = Packet(type=TYPE_RESPONSE, serialized=response.SerializeToString())
            self.send_packet(packet.SerializeToString())

            fail_info = DUMMY_FAIL_INFO

        except RpcInterrupt as e:
            fail_msg, = e.args
            fail_info = fail_msg.reason, fail_msg.code
        except BaseException as e:  # 主要是不能漏了GreenletExit
            if request_id != 0:  # 抛异常了,回个包给对端,免得对端死等回复
                fail_info = str(e), type(e).__name__
            raise
        finally:
            if request_id != 0:
                if fail_info is DUMMY_FAIL_INFO:
                    return
                if fail_info is None:
                    raise RuntimeError('必须回复对端')

                if isinstance(fail_info, tuple):
                    reason, code = fail_info
                else:
                    reason, code = fail_info, ''
                self._send_fail_with_field(request_id, reason, code)

    def _process_response(self, serialized):
        response = Response()
        try:
            response.ParseFromString(serialized)
        except DecodeError:
            text = '收到的响应包有误,反序列化出错,字节流是"%r"' % serialized
            self.log('debug', text)
        async_result = self.pending_id.get(response.response_id)
        if not async_result:  # 超时被弹掉或不存在的id
            return
        if response.sub_type == TYPE_SUCCESS:
            async_result.set((True, response.serialized))
        else:
            async_result.set((False, response.serialized))

    def cancel_pending_by_rpc_name(self, rpc_name):  # 不等回复了,某一类的rpc全部不等
        d = self.pending_rpc_name.get(rpc_name)
        if not d:
            return
        for request_id, oAsyncResult in d.items():
            e = gevent.GreenletExit()
            oAsyncResult.set_exception(e)
            self.log('debug', f'中止rpc:{rpc_name},{self}')

    def CallMethod(self, method_descriptor, ctrlr, req_msg, response_cls, done):  # override
        try:
            method_name = method_descriptor.name
            if response_cls == Fake:  # 无需回复的
                request_id, timeout = 0, 0
            else:
                request_id = self.next_request_id()
                assert request_id not in self.pending_id
                async_result = self.AsyncResult()
                self.pending_id[request_id] = async_result
                self.pending_rpc_name.setdefault(method_name, {})[request_id] = async_result

                timeout = getattr(req_msg, 'timeout', None)  # 如果请求消息里本身有这个timeout字段(default值也可以拿到的)
                if timeout is None:
                    timeout = self._get_method_timeout(method_name)

            packet_bytes = self.interface.make_request_packet(method_name, req_msg, request_id, timeout)
            self.send_packet(packet_bytes)

            if response_cls == Fake:  # 无需回复的
                return packet_bytes  # 返回发了什么字节流
            try:
                timeout = None if not timeout else timeout / 1000.0  # 0表示不超时,但AsyncResult应该传None
                # TODO: getcurrent()当前协程放入哪里进行监控
                rpc_ok, resp_buffer = async_result.get(True, timeout)  # 这里timeout是秒为单位的
            # except GreenletExit as e:  # 主动中断
            # 	raise
            except gevent.timeout.Timeout:
                fail_msg = Fail(reason='超时未回复', code='timeout')  # 伪造一个消息,其实不是对端回复的
                raise RpcTimeout(fail_msg)
            else:
                if rpc_ok:
                    resp_msg = response_cls()
                    resp_msg.ParseFromString(resp_buffer)  # 如果反序列化出错,抛异常也很合理
                    return resp_msg
                else:
                    fail_msg = Fail()
                    fail_msg.ParseFromString(resp_buffer)  # 如果反序列化出错,抛异常也很合理
                    raise RpcFail(fail_msg)
        finally:
            self.pending_id.pop(request_id, None)

            async_results = self.pending_rpc_name.get(method_name, None)
            if async_results:
                async_results.pop(request_id, None)

    # noinspection PyMethodMayBeStatic
    def _get_method_timeout(self, method_name):  # 毫秒为单位,返回0表示不超时
        return 1000 * 100  # 100秒,永不超时不好啊!若是对端永远不回,某个协程就永远跳不回去了

    def follow_up(self, timeout=3):
        pass

    def _on_dis_connected(self):
        self.dis_connected(self)

    def force_destroy(self):
        while self.pending_id:
            request_id, async_result = self.pending_id.popitem()
            e = gevent.GreenletExit()
            async_result.set_exception(e)

        for job in tuple(self.worker_job_group):  # RuntimeError: Set changed size during iteration
            # if job!=getcurrent():  # 是否需要避免自己kill自己?
            job.kill()
        self.worker_job_group.clear() 

    def __getattr__(self, attr_name):
        for stub in self.stub_group:
            method = getattr(stub, attr_name, None)
            if method:
                break
        else:
            raise RuntimeError(f'没有{attr_name}方法可调用.')

        method_descriptor = stub.GetDescriptor().FindMethodByName(attr_name)
        if not method_descriptor:
            raise RuntimeError(f'找不到名为{attr_name}的rpc方法')
        request_cls = stub.GetRequestClass(method_descriptor)

        self = weakref.proxy(self)

        def delegate(*args, **kwargs):
            ctrlr = self._get_controller_for_send_request(attr_name)
            if request_cls == Fake:
                req_msg = FAKE
            else:
                if not args and not kwargs:
                    req_msg = request_cls()  # 无参表示msg的全部域都是使用默认值
                elif args:  # 传送一个msg的调用或多个参数
                    if len(args) == 1 and isinstance(args[0], Message):
                        req_msg = args[0]
                    else:
                        req_msg = request_cls()
                        fields = request_cls.DESCRIPTOR.fields
                        for i, val in enumerate(args):
                            # noinspection PyBroadException
                            try:
                                field_name = fields[i].name
                            except IndexError:
                                text = f'rpc调用{attr_name}时,msg的参数给多了吧'
                                raise util.wrap_except(text)
                            # noinspection PyBroadException
                            try:
                                setattr(req_msg, field_name, val)
                            except Exception:
                                text = f'设置{request_cls}消息的字段值时出错,是不是参数顺序搞错了'
                                raise util.wrap_except(text)
                else:
                    req_msg = request_cls(**kwargs)  # 指定参数的调用
            result = method(ctrlr, req_msg, None)  # 调用上面的def CallMethod()
            return result

        self.__dict__[attr_name] = delegate
        return delegate


class Interface(object):
    # noinspection PyMethodMayBeStatic
    def get_time_stamp(self):
        return time()

    def make_request_packet(self, method_name, req_msg, request_id=0, timeout=0):  # request_id==AUTO_REQUEST_ID表示需生成id
        # 值若是为默认值,则不设置,节省流量
        request = Request()
        request.method_name = method_name
        request.serialized = req_msg.SerializeToString()
        # if request_id==AUTO_GEN_REQUEST_ID:#没有这个需求.
        #   request_id=next_request_id()
        if request_id != 0:
            request.request_id = request_id
        if timeout != 0:
            request.timeout = timeout
            request.time_stamp = int(self.get_time_stamp() * 1000)  # 毫秒

        packet = Packet(type=TYPE_REQUEST, serialized=request.SerializeToString())
        return packet.SerializeToString()


class PacketStat(object):
    def __init__(self):
        self.gbPrintRPCname = False
        self.giStatStamp = gevent.core.time()
        self.gdPacketStat = {}
        self.giPacketStatInterval = 10 * 60  # 网络包耗时统计间隔(10分钟)
        self.giNeedLog = 20  # 毫秒

    def test__dfad(self):
        '''
        cost = (self.get_time_stamp() - now) * 1000
        if method_name in gdPacketStat:
            l = gdPacketStat[method_name]
            l[0] += cost
            l[1] += +1
        else:
            gdPacketStat[method_name] = [cost, 1]

        if time() - giStatStamp > giPacketStatInterval:  # 每10分钟统计一下平均每个rpc耗时
            stat_packet()
        if gbPrintRPCname:  # 打印出呼叫的rpc函数名,方便调试
            print('rpc:{},cost:{:.2f}'.format(method_name, cost))

        if cost >= giNeedLog:  # 只记录超过20毫秒的调用
            log.log('packetCost', '{} {:.2f}'.format(method_name, cost))
        '''
        pass

    def stat_packet(self):  # 统计一段时间内的各个rpc总耗时,总调用次数,平均耗时
        global gdPacketStat, giStatStamp
        l = []
        total_cost, total_times = 0, 0

        keys = gdPacketStat.keys()
        keys.sort(util.Functor(packet_cost_comparer, gdPacketStat))
        for rpc_name in keys:
            rpc_cost, rpc_times = gdPacketStat[rpc_name]
            total_cost += rpc_cost
            total_times += rpc_times
            l.append('{}:{:.2f}/{}={:.2f}'.format(rpc_name, rpc_cost, rpc_times, rpc_cost / rpc_times))
        log.log('packetStat', 'total({} request,{:.2f} millisecond)\n{}\n\n'.format(total_times, total_cost, '\n'.join(l)))
        gdPacketStat = {}
        giStatStamp = time()

    def packet_cost_comparer(self, rpc_name1, rpc_name2, gdPacketStat):  # 按照总耗时排序(不是按平均耗时排序)
        iCmdCost1, iCmdTimes1 = gdPacketStat[rpc_name1]
        iCmdCost2, iCmdTimes2 = gdPacketStat[rpc_name2]
        if iCmdCost2 == iCmdCost1:
            return 0
        return 1 if iCmdCost2 > iCmdCost1 else -1

