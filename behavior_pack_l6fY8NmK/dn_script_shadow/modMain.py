# -*- coding: utf-8 -*-
from architect.compact import createServer, createClient

def modInit():
    # 读取 conf.py 中的 MOD_ENGINE_NAME 和 MOD_SYSTEM_NAME 完成初始化
    createServer()
    createClient()