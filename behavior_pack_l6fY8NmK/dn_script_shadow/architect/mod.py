# -*- coding: utf-8 -*-
from mod.common.mod import Mod
from .conf import __modname__, MOD_VERSION, MOD_NAME, MOD_SERVER_MODULES, MOD_CLIENT_MODULES


@Mod.Binding(name = 'mod_' + MOD_NAME, version = MOD_VERSION)
class ModBase(object):
    @Mod.InitServer()
    def initServer(self):
        from .core.subsystem import SubsystemManager
        from .core.loader import modConf
        getConf = modConf()
        SubsystemManager.createServer(
            getConf('MOD_ENGINE_NAME'),
            getConf('MOD_SYSTEM_NAME')
        )

    @Mod.InitClient()
    def initClient(self):
        from .core.subsystem import SubsystemManager
        from .core.loader import modConf
        getConf = modConf()
        SubsystemManager.createClient(
            getConf('MOD_ENGINE_NAME'),
            getConf('MOD_SYSTEM_NAME')
        )


def server(*userModuleNames):
    MOD_SERVER_MODULES.extend(userModuleNames)


def client(*userModuleNames):
    MOD_CLIENT_MODULES.extend(userModuleNames)