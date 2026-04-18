import config
from mod.common.mod import Mod

# 换成实际的name和version
@Mod.Binding(name = config.ModName, version = config.ModVersion)
class Shadow:
    @Mod.InitServer()
    def initServer(self):
        # 换成实际的导入路径
        from .architect.comapct import SubsystemManager
        # 换成实际的命名空间和服务器名称
        from .server.shadow_serverSystem import ShadowServerSystem
        SubsystemManager.createServer(config.ModName, config.ServerSystemName)


    @Mod.InitClient()
    def initClient(self):
        # 换成实际的导入路径
        from .architect.comapct import SubsystemManager
        # 换成实际的命名空间和服务器名称
        from .client.shadow_clientSystem import ShadowClientSystem
        SubsystemManager.createClient(config.ModName, config.ClientSystemName)
