import foo_pb2
import end_point


class Service(foo_pb2.ServerToTerminal):
    def rpc_do_something(self, ep, req_msg, ctx):
        print('rpc_do_something', req_msg)



