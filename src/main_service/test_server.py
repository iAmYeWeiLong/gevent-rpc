import gevent.server
import endpoint_with_socket
import terminal_to_server_service
import foo_pb2


def next_end_point_id():
    global end_point_id
    if 'end_point_id' not in globals():
        end_point_id = 0
    end_point_id += 1
    return end_point_id


def after_accept(sock, addr):
    host, port = addr

    protocol = {
        'services': [terminal_to_server_service.Service],
        'stubs': [foo_pb2.TerminalToServer_Stub]
    }
    endpoint_id = next_end_point_id()
    ep = endpoint_with_socket.EndPointWithSocket(protocol, endpoint_id)
    ep.set_host(host).set_port(port).set_socket(sock)
    ep.start()

    ep.join()


def init_server():

    port = 4321
    server = gevent.server.StreamServer(('0.0.0.0', port), after_accept)
    print('Starting server on port {}'.format(port))
    return server
