import rpc_client
import foo_pb2
import server_to_terminal_service

ep_maker = None


def test():
    global ep_maker
    services = [server_to_terminal_service.Service]
    stubs = [foo_pb2.TerminalToServer_Stub]
    ep_maker = rpc_client.EndpointMaker('localhost', 4321, services, stubs)
