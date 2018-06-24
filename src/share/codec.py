import struct
import network_byte


class Encoder(object):
    HEADER_SIZE = 4

    def encode(self, packet):
        size = len(packet)
        pk = network_byte.Pack(self.HEADER_SIZE + size)
        pk.pack_int(self.HEADER_SIZE, size)
        ba = pk.get_buffer()
        # if len+self.HEADER_SIZE!=len(ba):
        # 	raise RuntimeError,'预分配字节数算错了iLen={},ba={}'.format(len,len(ba))
        ba[self.HEADER_SIZE:] = packet
        return ba


# 解码器
class Decoder(object):
    HEADER_SIZE = 4

    def __init__(self, max_input_buffer_size=3 * 1024 * 1024):
        self.packet_len = -1
        self.max_input_buffer_size = max_input_buffer_size

    def reset(self):
        self.packet_len = -1

    def decode(self, buffer):
        readable_bytes = buffer.readable_bytes
        retrieve = buffer.retrieve
        peek_read = buffer.peek_read
        unpack = struct.unpack
        header_size = self.HEADER_SIZE
        max_input_buffer_size = self.max_input_buffer_size

        while True:
            if self.packet_len == -1:
                if readable_bytes() < header_size:  # 连一个头都不够
                    return  # 跳出,需要再读多一点数据

                size = peek_read(header_size)
                self.packet_len, = unpack('!i', size)

                retrieve(header_size)

                if self.packet_len > max_input_buffer_size:  # 防止恶意攻击,恶意的客户端
                    raise RuntimeError('接收到一个包宣称大小是{},超过了{}'.format(self.packet_len, max_input_buffer_size))

            if readable_bytes() < self.packet_len:  # 不够一个逻辑包
                return  # 跳出,需`要再读多一点数据

            packet = peek_read(self.packet_len)
            retrieve(self.packet_len)
            self.packet_len = -1

            yield packet.tobytes()
        # 外部并有可能没有马上使用,这里还在修改(调整,移动),memoryview共用同一份内存,会毁坏数据
        # 况且protobuf的ParseFromString函数只接受str

