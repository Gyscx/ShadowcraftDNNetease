if 1 > 2:
    from .subsystem import SubsystemManager, Subsystem

from .conf import PLUGINS, PLUGIN_NAME
from .basic import isServer, clientApi, serverApi
from .annotation import AnnotationHelper

class _ModuleLocator(object):
    pass


__modname__ = _ModuleLocator.__module__[:_ModuleLocator.__module__.find('.')]
__filename__ = _ModuleLocator.__module__[:_ModuleLocator.__module__.rfind('.')]
__dirname__ = __filename__[:__filename__.rfind('.')]


class PluginBase(object):

    def onAttach(self, manager):
        # type: (SubsystemManager) -> None
        pass

    def onDetach(self, manager):
        # type: (SubsystemManager) -> None
        pass

    def onRegisterComponent(self, manager, compCls):
        # type: (SubsystemManager, type) -> None
        pass

    def onAddSubsystem(self, manager, subsystem):
        # type: (SubsystemManager, Subsystem) -> None
        pass

    def onRemoveSubsystem(self, manager, subsystem):
        # type: (SubsystemManager, Subsystem) -> None
        pass


def Plugin(name):
    def _decorator(cls):
        # type: (type) -> type
        AnnotationHelper.addAnnotation(cls, PLUGIN_NAME, name)
        return cls
    return _decorator


VendorPlugins = __dirname__ + '.plugins.'
UserPlugins = __modname__ + '.plugins.'


def pluginPath(name):
    # type: (str) -> str
    return name.replace('$vendor', VendorPlugins).replace('$user', UserPlugins)


_LOADED_PLUGINS = {}

def _scanPlugins():
    for _name in PLUGINS:
        absPath = pluginPath(_name)
        if isServer():
            serverApi.ImportModule(absPath)
        else:
            clientApi.ImportModule(absPath)


def _loadPlugins(ctor):
    pass