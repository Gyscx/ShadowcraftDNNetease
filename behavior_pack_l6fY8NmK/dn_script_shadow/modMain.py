# # -*- coding: utf-8 -*-
# from mod.common.mod import Mod
# import importlib

# # 使用绝对导入以避免相对导入时触发包内其他子模块的顶级导入
# try:
#     user_conf = importlib.import_module('dn_script_shadow.conf')
# except Exception:
#     # 回退到相对导入（极少数运行时环境）
#     from . import conf as user_conf

# @Mod.Binding(name = getattr(user_conf, 'MOD_NAME', 'dn_script_shadow'), version = getattr(user_conf, 'MOD_VERSION', '1.0.0'))
# class ModBase(object):
#     @Mod.InitServer()
#     def initServer(self):
#         from .architect.compact import createServer
#         createServer()

#     @Mod.InitClient()
#     def initClient(self):
#         from .architect.compact import createClient
#         createClient()


# -*- coding: utf-8 -*-
from mod.common.mod import Mod
from .architect.startup import createServer, createClient, conf


@Mod.Binding(name = conf('MOD_NAME'), version = conf('MOD_VERSION'))
class ModBase(object):
    @Mod.InitServer()
    def initServer(self):
        createServer()

    @Mod.InitClient()
    def initClient(self):
        createClient()