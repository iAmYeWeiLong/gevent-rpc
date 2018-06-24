# packet相关操作
import struct


def _get_int_format(size, signed):
    if size == 1:
        return '!b' if signed else '!B'
    elif size == 2:
        return '!h' if signed else '!H'
    elif size == 4:
        return '!i' if signed else '!I'
    elif size == 8:
        return '!q' if signed else '!Q'
    else:
        raise RuntimeError('pack_int或unpack_int字节数只能传1,2,4,8')


class Pack(object):
    def __init__(self, pre_size=0):  # iPreSize只能少或刚刚好,绝对不能多
        self.buffer = bytearray(pre_size)
        self.write_idx = 0

    def clear(self, pre_size=0):
        self.buffer = bytearray(pre_size)
        self.write_idx = 0

    def get_buffer(self):  # 取得全部打包好的buff
        return self.buffer

    def pack_int(self, size, value, signed=True):
        fm = _get_int_format(size, signed)
        string = struct.pack(fm, value)
        self.buffer[self.write_idx:self.write_idx + size] = string  # 空间不够会自动扩展的
        self.write_idx += size
        return self  # 可以链式调用

    def pack_str(self, text):
        size = len(text)
        self.pack_int(size, 4)

        content = struct.pack('!{}s'.format(size), text)  # str也要调用pack??
        if size != len(content):  # 我不敢确认
            raise RuntimeError('为什么会不相等呢?有空要查一下文档')

        self.buffer[self.write_idx:self.write_idx + size] = content  # 空间不够会自动扩展的
        self.write_idx += size
        return self  # 可以链式调用


class Unpack(object):
    def __init__(self, buffer):
        self.buffer = buffer

    def get_buffer(self):  # 取得剩下未解完的buffer
        return self.buffer

    def reset_buffer(self, buffer):
        self.buffer = buffer

    def unpack_str(self):
        size = self.unpack_int(4)  # 先解出字符串长度
        if not self.buffer:
            raise RuntimeError('buffer已经被解完了')
        text, = struct.unpack('!{}s'.format(size), self.buffer[:size])
        self.buffer = self.buffer[size:]
        return text

    def unpack_int(self, size, signed=True):
        if not self.buffer:
            raise RuntimeError('buffer已经被解完了')
        fm = _get_int_format(size, signed)
        # struct.unpack第二个参数可以接受 bytearray,memoryview,buffer 三种类型
        value, = struct.unpack(fm, self.buffer[:size])
        self.buffer = self.buffer[size:]
        return value



