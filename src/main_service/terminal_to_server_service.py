import foo_pb2
import end_point


class Service(foo_pb2.TerminalToServer):
    def rpc_do_something(self, ep, req_msg, ctx):
        print('rpc_do_something', req_msg)

    def rpc_hello_world(self, ep, req_msg, ctx):
        print('rpc_hello_world', req_msg)
        import public_pb2
        return public_pb2.Fail(reason='我提reason', code='i am code')
        return {'field1': 'jjjj', 'field2': True, 'field3': 656}

