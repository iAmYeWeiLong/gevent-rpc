class Buffer(object):
    def __init__(self, init_len=1024):
        if init_len <= 0:
            raise RuntimeError('滚,长度至少为1')
        self.buffer = memoryview(bytearray(init_len))
        self.read_idx, self.write_idx = 0, 0  # [前闭,后开)

    def readable_bytes(self):
        return self.write_idx - self.read_idx

    def make_space(self, need_size):  # 挪动或扩充,得到一个连续的need_size可写空间.(只会扩充得比需要的多,不会少)
        readable = self.write_idx - self.read_idx
        length = len(self.buffer)

        while length - readable < need_size or length - readable < length / 3.0:  # 可写空间不够needSize或不足1/3,要搞大他
            length *= 2

        if length != len(self.buffer):
            new_buffer = memoryview(bytearray(length))  # 扩充空间只能另搞一个对象,因为bytearray被memoryview包装过后无法扩大容量
            new_buffer[0:readable] = self.buffer[self.read_idx:self.read_idx + readable]
            self.buffer = new_buffer
        else:
            self.buffer[0:readable] = self.buffer[self.read_idx:self.read_idx + readable]
        self.read_idx, self.write_idx = 0, readable

    def has_written(self, length):
        if length > len(self.buffer) - self.write_idx:
            raise RuntimeError('都没有这么多字节数')
        self.write_idx += length

    def retrieve(self, length):
        if length > self.write_idx - self.read_idx:
            raise RuntimeError('没有这么多字节数')
        if length < self.write_idx - self.read_idx:
            self.read_idx += length
        else:
            self.read_idx = self.write_idx = 0

    def peek_write(self, size=0):  # 0表示拿全部
        if size == 0:
            if self.write_idx == len(self.buffer):  # 没有空间了
                self.make_space(1024)
            return self.buffer[self.write_idx:]
        else:  #
            if self.write_idx + size > len(self.buffer):  # 空间不足
                self.make_space(size)
            return self.buffer[self.write_idx:self.write_idx + size]

    def peek_read(self, size):
        return self.buffer[self.read_idx:self.read_idx + size]
