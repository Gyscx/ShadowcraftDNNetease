# -*- coding: utf-8 -*-

import mod.server.extraServerApi as serverApi
from mod_log import logger
from .. import config

from ..architect.comapct import ServerSubsystem, SubsystemServer
from ..architect.comapct import EventListener

SS = serverApi.GetServerSystemCls()
SCF = serverApi.GetEngineCompFactory()
levelId = serverApi.GetLevelId()

@SubsystemServer
class ShadowServerSystem(ServerSubsystem):
    def onInit(self):
        print "===== Shadow Server System Init (Dynamic) ====="
        self.system.ListenForEvent(
            serverApi.GetEngineNamespace(),
            serverApi.GetEngineSystemName(),
            'ClientUseShadowEnergyEvent',
            self,
            self.onClientUseShadowEnergyEventaaa
        )
        print 'added ClientUseShadowEnergyEvent'

    def onClientUseShadowEnergyEventaaa(self, args):
        print 'ClientUseShadowEnergyEvent: ', args

    def GetSkillConfig(self, skill_id):
        """获取技能配置"""
        for skill in config.SKILL_CONFIGS:
            if skill["skill_id"] == skill_id:
                return skill
        return None

    @EventListener(config.ServerSkillEvent, isCustomEvent=True)
    def OnSkillEvent(self, args):
        """服务端释放技能事件（使用命令）"""
        print args
        skill_id = args.skill
        player_id = args.playerId
        # 新增：客户端可以传递具体的物品标识符
        item_identifier_used = args.itemIdentifier

        if not player_id:
            player_id = serverApi.GetHostPlayerId()

        skill_cfg = self.GetSkillConfig(skill_id)
        if not skill_cfg:
            logger.error("未知技能ID: %s" % skill_id)
            return

        # 确定要执行的命令列表
        commands_to_execute = []
        if item_identifier_used and "valid_items" in skill_cfg:
            for item_config in skill_cfg["valid_items"]:
                if item_config["item_identifier"] == item_identifier_used:
                    commands_to_execute = item_config.get("server_commands", [])
                    break

        # 如果没匹配到，或者没传item_identifier，则执行第一个物品的命令（或可以定义默认行为）
        if not commands_to_execute and skill_cfg.get("valid_items"):
            commands_to_execute = skill_cfg["valid_items"][0].get("server_commands", [])

        # 执行命令
        cmd_comp = serverApi.GetEngineCompFactory().CreateCommand(levelId)
        for command in commands_to_execute:
            cmd_comp.SetCommand(command, player_id)
        if skill_id == "RW" and item_identifier_used == "minecraft:arrow":
            time_comp = SCF.CreateGame(levelId)
            time_comp.AddTimer(1.0, self.DelayDamage)
        logger.info("玩家 %s 释放了技能: %s (物品: %s)" % (player_id, skill_id, item_identifier_used or "默认"))

    def DelayDamage(self):
        """shadow_blast技能延迟施加伤害"""
        cmd_comp = serverApi.GetEngineCompFactory().CreateCommand(levelId)
        player_id = serverApi.GetHostPlayerId()
        delay_command = "/function shadow_skills"
        cmd_comp.SetCommand(delay_command, player_id)

    def OnHelmetSkillUsed(self, player_id):
        """头盔技能额外效果"""
        # 可以添加头盔特有的逻辑
        pass

    def OnArmorSkillUsed(self, player_id):
        """胸甲技能额外效果"""
        # 可以添加胸甲特有的逻辑
        pass

    def OnWeaponSkillUsed(self, player_id):
        """武器技能额外效果"""
        # 可以添加武器特有的逻辑
        pass

    def OnRangedSkillUsed(self, player_id):
        """远程武器技能额外效果"""
        # 可以添加远程武器特有的逻辑
        pass

    @EventListener(config.ClientUseShadowEnergyEvent, isCustomEvent=True)
    def OnClientUseShadowEnergy(self, args):
        """服务端玩家右键暗影能量物品事件"""
        print "222"
        # print args.dict()
        playerId = args.playerId
        print playerId
        if not playerId:
            return

        item_comp = serverApi.GetEngineCompFactory().CreateItem(playerId)
        selectedSlot = item_comp.GetSelectSlotId()
        # 修复BUG：检查选中的槽位是否有效
        if selectedSlot < 0 or selectedSlot > 8:
            return

        inv_pos = serverApi.GetMinecraftEnum().ItemPosType.INVENTORY

        current_item = item_comp.GetPlayerItem(inv_pos, selectedSlot)
        if not current_item or current_item.get("itemName") != "minecraft:grass":
            return

        count = current_item.get("count", 1)
        new_count = count - 1
        if new_count <= 0:
            item_comp.SetInvItemNum(selectedSlot, 0)
        else:
            item_comp.SetInvItemNum(selectedSlot, new_count)
        self.sendClient(playerId, config.AddShadowEnergyEvent, {"amount": 8})
        print "333"

    @EventListener(config.DamageEvent)
    def OnDamageEvent(self, args):
        """玩家受伤事件"""
        entityId = args.entityId
        player_list = serverApi.GetPlayerList()
        if entityId in player_list:
            print "服务端-玩家已受伤"
            print args.dict()
            print entityId
            self.sendClient(entityId, config.DamageEvent, args.dict())

    @EventListener(config.PlayerAttackEntityEvent)
    def OnPlayerAttackEvent(self, args):
        """玩家攻击事件"""
        playerId = args.playerId
        player_list = serverApi.GetPlayerList()
        print "服务端-玩家已攻击"
        print args.dict()
        print playerId
