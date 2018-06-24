#!/bin/sh
protoc --version
protoc --python_out=../pb2 *.proto

echo 按任意键结束
read -n 1


# call ..\protoc.exe  --python_out=..\..\pb2\universal  *.proto 
# pause
# goto end
# 	---------------------------------------------------------------
# 	如果全部*.proto文件(包括被import的*.proto文件)都在当前目录下时
# 	不需要-I=来指示proto文件所在
# 	如 protoc.exe --python_out=../pb2  *.proto
# 	---------------------------------------------------------------
# 	如果被import的proto文件不在当时目录时,需要用-I=来指示"头文件"所在
# 	同时要求当前目录下的proto也需要用-I=来指定目录
# 	即变得需要两个-I=分别指定头文件与主proto文件
# 	如 protoc.exe  -I=../rpc -I=./ --python_out=../pb2  *.proto
# 	---------------------------------------------------------------
# 	如果在*.proto上写有import "abu/rpc/void.proto";时
# 	执行protoc.exe生成*_pb2.py时,会检查abu/rpc/void.proto是否存在
# 	检查"abu/rpc/void.proto"是否存在是从-I=指定的路径下查找
# 	最后目标*_pb2.py文件中也会生成import abu.rpc.void_pb2语句
# 	在*.proto上可以直接使用void.proto里面的msg,而不用像void.xxx这样加前缀
# 	---------------------------------------------------------------
# :end
