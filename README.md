# gevent-rpc
用 python 的协程网络框架 gevent 与 google protobuf 实现的 rpc

适应于 IO 密集型任务,不适合 CPU 密集型任务


## 优点:
* 得益于协程,与对端通讯就像调用本地函数一样,无需回调.(因为上下文切换导致的状态不一样的问题仍然存在,这个是本质,无法改变)
* 得益于libev 的 one loop per thread 实现,可以用一个线程实现高并发
* 设计上抽象出 endpoint 概念,可以基于服务端代码快速地写机器人,做压力测试,非常爽

## 缺点:
* protobuf 的 python 版 比较慢, 用上了 C++ 的 backend 还是慢
* IO 与 计算都在同一个线程.因为 Python GIL ,分开也解决不了多核利用的问题
* 容易踩坑,这是 gevent 的问题.代码必须非阻塞,包括选用的第 3 方库,比如 mysql mongoDB 驱动(用线程池或 monkey patch 可解决).

   写磁盘 log 一定得另开线程


## 特性:
* 双向调用 - 服务端也可以调用客户端
* 无序调用 - 不是 http 那种 requset 和 response 必须有严格时序的模型,可以任意时序互相调用
* 无序启动 - 客户端可以先于服务端启动
* 断线重连 - 服务端重启之后,客户端不用重启,会定时重连
* request 并发数量控制
* 过载保护,request 超时丢弃处理




