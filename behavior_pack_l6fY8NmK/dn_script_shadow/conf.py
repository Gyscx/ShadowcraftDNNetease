class _ModuleLocator: pass
__modname__ = _ModuleLocator.__module__[:_ModuleLocator.__module__.find('.')]
"""
这里是引擎配置, 不建议直接修改.
MOD_* 和 PLUGINS 遵循覆盖原则, 用户可以在脚本根目录下创建 conf.py 覆盖默认配置.
如果你不知道有哪些配置可以修改, 请将引擎配置中 “推荐修改的配置” 和 “插件列表” 复制到你的 conf.py 中
"""



# 推荐修改的配置
MOD_NAME = __modname__
MOD_VERSION = '1.0.0'
MOD_ENGINE_NAME = MOD_NAME
MOD_SYSTEM_NAME = 'ModSubsystem'
MOD_SERVER_MODULES = [
    'server',
]
MOD_CLIENT_MODULES = [
    'client',
]

# 插件列表
"""
$vendor为系统插件, $user为用户插件
系统插件在{modname}/architect/plugins目录下
用户插件在{modname}/plugins目录下
"""
PLUGINS = [
    '$vendor.event',        # 事件系统
]