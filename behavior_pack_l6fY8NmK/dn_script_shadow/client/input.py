# 用于注册客户端子系统
from ..architect.comapct import ClientSubsystem, SubsystemClient
# 用于注册事件监听器
from ..architect.comapct import EventListener
# 非常基础的组件，比如clientApi, serverApi
from ..architect.comapct import clientApi

from .. import config

@SubsystemClient
class InputSubsystem(ClientSubsystem):

    # 事件建议直接用字符串，到时候方便定位
    @EventListener('OnKeyPressInGame')
    def OnKeyPressInGame(self, args):
        """处理按键按下事件"""
        if args.isDown != "1":
            return
        key = int(args.key)
        ui_node = clientApi.GetUI(config.ModName, config.shadowUIName)
        if not ui_node:
            return
        # 确保UI控件已初始化
        if not hasattr(ui_node, 'mShadowAbility'):
            return
        ability_ctrl = ui_node.GetBaseUIControl(ui_node.mShadowAbility)
        if not ability_ctrl or not ability_ctrl.GetVisible():
            return
        # 获取按键映射组件
        levelId = clientApi.GetLevelId()
        playerViewComp = clientApi.GetEngineCompFactory().CreatePlayerView(levelId)
        # 遍历所有技能配置，检查按键匹配
        for skill_cfg in config.SKILL_CONFIGS:
            mapped_key = playerViewComp.GetKeyMappings(skill_cfg["key_mapping_name"])
            if key == mapped_key and self.CheckItemForSkill(skill_cfg):
                # 触发技能
                if self.TriggerSkillAbility(skill_cfg["skill_id"]):
                    ui_node.StartCooldown(skill_cfg["skill_id"])
                break