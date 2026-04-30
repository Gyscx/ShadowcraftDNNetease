from ...architect.compact import Plugin, PluginBase

@Plugin(
    'SFDN_Plugin',
    '1.0.0'
)
class TestServer(PluginBase):
    def onReady(self, manager):
        print('插件1')

    def getCustomData(self):
        return 'this is custom data'