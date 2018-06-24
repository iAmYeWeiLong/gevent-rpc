# import types
# import sys

# 真正的全局变量,无需import,想用随时用
def set_g(k, v):
    # 程序启动时不带-m参数时__builtins__是module,带了-m参数时__builtins__ 是dict
    if isinstance(__builtins__, dict):
        __builtins__[k] = v
    else:
        setattr(__builtins__, k, v)







