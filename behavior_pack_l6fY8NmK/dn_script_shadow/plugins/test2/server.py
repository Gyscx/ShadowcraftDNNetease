from ...architect.comapct import Plugin, PluginBase, getPlugin

@Plugin(
    'SFDN_Plugin2',
    '1.0.0'
)
class TestServer(PluginBase):
    def onReady(self, manager):
        print("插件2")
        plugin = getPlugin('SFDN_Plugin')
        print('plugin loaded: ', plugin.getCustomData())