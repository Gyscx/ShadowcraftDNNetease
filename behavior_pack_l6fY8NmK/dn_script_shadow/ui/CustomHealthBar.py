# -*- coding: UTF-8 -*-
from mod.client.ui.screenNode import ScreenNode
import mod.client.extraClientApi as clientApi
import math


class healthbar(ScreenNode):

    def __init__(self, namespace, name, param):
        ScreenNode.__init__(self, namespace, name, param)
        # 由于使用CreateUi来创建界面，与PushScreen界面不同的是，主路径在最前面需要加一个/
        self.base_screen = "/variables_button_mappings_and_controls/safezone_screen_matrix/inner_matrix/safezone_screen_panel/root_screen_panel"
        self.progress_path = "/health_bar/filled_progress_bar"
        self.health_path = "/health_text"
        self.bind_entity_id = 'sf:man_unique_h'
        self.query_comp = None

    def Create(self):
        self.bind_entity_id = self.GetBindEntityId()
        self.query_comp = clientApi.GetEngineCompFactory().CreateQueryVariable(self.bind_entity_id)

    def Update(self):
        # 当UI完全加载好后，获取到了绑定UI的生物时
        if self.bind_entity_id:
            # 获得生物的当前生命值
            current_health = self.query_comp.GetMolangValue('query.health')
            # 获得生物的最大生命值
            max_health = self.query_comp.GetMolangValue('query.max_health')
            # 设置血量文本格式
            self.SetText(self.base_screen + self.health_path, '{0}/{1}'.format(math.floor(current_health), math.floor(max_health)))
            # 如果血量大于0时，通过计算进行裁切
            if current_health > 0.0:
                self.SetSpriteClipRatio(self.base_screen + self.progress_path, 1.0 - current_health / max_health)
            else:
                # 如果血量小等于0时，则直接裁掉全部的图片
                self.SetSpriteClipRatio(self.base_screen + self.progress_path, 1.0)
