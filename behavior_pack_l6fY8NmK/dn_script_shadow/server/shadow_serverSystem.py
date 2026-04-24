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

    def GetSkillConfig(self, skill_id):
        """获取技能配置"""
        for skill in config.SKILL_CONFIGS:
            if skill["skill_id"] == skill_id:
                return skill
        return None

    def DelayDamage(self):
        """shadow_blast技能延迟施加伤害"""
        cmd_comp = serverApi.GetEngineCompFactory().CreateCommand(levelId)
        player_id = serverApi.GetHostPlayerId()
        delay_command = "/function shadow_skills"
        cmd_comp.SetCommand(delay_command, player_id)

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
        if not current_item or current_item.get("itemName") != "sf:shadow_energy":
            return

        count = current_item.get("count", 1)
        new_count = count - 1
        if new_count <= 0:
            item_comp.SetInvItemNum(selectedSlot, 0)
        else:
            item_comp.SetInvItemNum(selectedSlot, new_count)
        self.sendClient(playerId, config.AddShadowEnergyEvent, {"amount": 8})
        print "333"

    def ProcessSkillUpgrade(self, player_id, skill_id, fragment_cost, current_level):
        """统一的技能升级处理方法"""
        # 1. 检查并消耗暗影碎片
        if fragment_cost > 0:
            if not self.consumeFragments(player_id, fragment_cost):
                # 碎片不足，升级失败
                self.sendClient(player_id, config.UpgradeSkillResultEvent, {
                    "skill_id": skill_id,
                    "new_level": current_level,
                    "success": False,
                    "reason": "碎片不足"
                })
                logger.info("玩家 %s 升级技能 %s 失败：碎片不足" % (player_id, skill_id))
                return False

        # 2. 升级技能
        next_level = current_level + 1
        self.SetSkillLevel(player_id, skill_id, next_level)

        # 3. 获取升级效果信息
        upgrade_info = self.getUpgradeInfo(skill_id, current_level)

        # 确保始终发送 damage_multiplier 和 cooldown_multiplier
        damage_multiplier = 1.0
        cooldown_multiplier = 1.0
        if upgrade_info:
            damage_multiplier = upgrade_info.get("damage_multiplier", 1.0)
            cooldown_multiplier = upgrade_info.get("cooldown_multiplier", 1.0)

        # 发送升级结果给客户端
        self.sendClient(player_id, config.UpgradeSkillResultEvent, {
            "skill_id": skill_id,
            "new_level": next_level,
            "success": True,
            "damage_multiplier": damage_multiplier,
            "cooldown_multiplier": cooldown_multiplier
        })

        logger.info("玩家 %s 升级了技能 %s 到 %s级，消耗碎片: %s" % (player_id, skill_id, next_level, fragment_cost))
        return True

    def GetSkillLevel(self, player_id, skill_id):
        """获取玩家技能等级"""
        # 这里可以从服务端存储中获取
        # 可以使用serverApi的Config组件
        comp = SCF.CreateExtraData(player_id)
        data = comp.GetExtraData("skill_levels") or {}
        return data.get(skill_id, 1)

    def SetSkillLevel(self, player_id, skill_id, level):
        """设置玩家技能等级"""
        comp = SCF.CreateExtraData(player_id)
        data = comp.GetExtraData("skill_levels") or {}
        data[skill_id] = level
        comp.SetExtraData("skill_levels", data)

    def SyncSkillLevelsToPlayer(self, player_id):
        """向指定玩家同步技能等级"""
        skill_levels = {}
        for skill in config.SKILL_CONFIGS:
            skill_id = skill["skill_id"]
            level = self.GetSkillLevel(player_id, skill_id)
            skill_levels[skill_id] = level

        self.sendClient(player_id, config.SyncSkillLevelsEvent, {
            "skill_levels": skill_levels
        })
        logger.info("向玩家 %s 同步技能等级: %s" % (player_id, skill_levels))

    def getUpgradeInfo(self, skill_id, current_level):
        """获取升级信息"""
        # 这里需要从config中读取升级配置
        # 注意：服务端也需要导入config模块
        from .. import config

        # 获取下一级
        next_level = current_level + 1

        # 优先使用技能特定的升级配置
        skill_upgrade_config = config.SKILL_UPGRADE_CONFIG["upgrade_effects"].get(skill_id)
        if skill_upgrade_config and len(skill_upgrade_config) >= next_level:
            return skill_upgrade_config[next_level - 1]  # 列表索引从0开始

        # 使用通用升级配置
        common_config = config.SKILL_UPGRADE_CONFIG["common_upgrade_effects"]
        if len(common_config) >= next_level:
            return common_config[next_level - 1]

        return None

    def consumeFragments(self, player_id, count):
        """服务端消耗暗影碎片"""
        if count <= 0:
            return True

        item_comp = serverApi.GetEngineCompFactory().CreateItem(player_id)
        inv_pos = serverApi.GetMinecraftEnum().ItemPosType.INVENTORY

        remaining = count
        for slot in range(9):
            if remaining <= 0:
                break

            item_dict = item_comp.GetPlayerItem(inv_pos, slot)
            if item_dict and item_dict.get('itemName') == config.SKILL_UPGRADE_CONFIG["fragment_item_id"]:
                current_count = item_dict.get('count', 0)
                if current_count > 0:
                    consume = min(current_count, remaining)
                    new_count = current_count - consume

                    if new_count <= 0:
                        # 清空槽位
                        item_comp.SetInvItemNum(slot, 0)
                    else:
                        # 更新数量
                        item_comp.SetInvItemNum(slot, new_count)

                    remaining -= consume

        return remaining == 0

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

    @EventListener(config.ClientUpgradeSkillEvent, isCustomEvent=True)
    def OnClientUpgradeSkill(self, args):
        """服务端处理客户端升级请求（转发到统一处理方法）"""
        skill_id = args.skill_id
        player_id = args.playerId

        if not skill_id or not player_id:
            return

        # 获取当前等级
        current_level = self.GetSkillLevel(player_id, skill_id)
        if current_level >= 5:  # 最高5级
            return

        # 计算下一级
        next_level = current_level + 1

        # 获取升级所需碎片数量
        upgrade_info = self.getUpgradeInfo(skill_id, current_level)
        if not upgrade_info:
            return

        fragment_cost = upgrade_info.get("fragment_cost", 0)

        # 调用统一的升级处理方法
        self.ProcessSkillUpgrade(player_id, skill_id, fragment_cost, current_level)

    @EventListener(config.ServerUpgradeSkillEvent, isCustomEvent=True)
    def OnServerUpgradeSkill(self, args):
        """服务端处理技能升级请求"""
        skill_id = args.skill_id
        player_id = args.playerId
        fragment_cost = args.fragment_cost

        if not skill_id or not player_id:
            return

        # 获取当前等级
        current_level = self.GetSkillLevel(player_id, skill_id)
        if current_level >= 5:  # 最高5级
            return

        # 调用统一的升级处理方法
        self.ProcessSkillUpgrade(player_id, skill_id, fragment_cost, current_level)

    @EventListener(config.RequestSkillLevelsEvent, isCustomEvent=True)
    def OnRequestSkillLevels(self, args):
        """处理客户端请求技能等级同步"""
        player_id = args.playerId
        if not player_id:
            return

        # 获取所有技能等级
        skill_levels = {}
        for skill in config.SKILL_CONFIGS:
            skill_id = skill["skill_id"]
            level = self.GetSkillLevel(player_id, skill_id)
            skill_levels[skill_id] = level

        # 发送给客户端
        self.sendClient(player_id, config.SyncSkillLevelsEvent, {
            "skill_levels": skill_levels
        })

    @EventListener("ServerPlayerTryJoinEvent")
    def OnPlayerJoin(self, args):
        """玩家加入游戏时，自动同步技能等级"""
        print "玩家已加入游戏"
        player_id = args.playerId
        if player_id:
            # 延迟一段时间，确保客户端已准备好
            time_comp = SCF.CreateGame(levelId)
            time_comp.AddTimer(1.0, lambda: self.SyncSkillLevelsToPlayer(player_id))

    @EventListener(config.ServerSkillEvent, isCustomEvent=True)
    def OnSkillEvent(self, args):
        """服务端释放技能事件（使用命令）"""
        skill_id = args.skill
        player_id = args.playerId
        item_identifier_used = args.itemIdentifier
        damage_multiplier = args.damageMultiplier  # 获取伤害乘数

        def DelayCommand():
            command_list = [
                "execute as @s at @s positioned ^ ^ ^8 run damage @e[r=3,type=!player] {} entity_attack entity @s",
                "execute as @s at @s positioned ^ ^ ^7.5 run damage @e[r=3,type=!player] {} entity_attack entity @s",
                "execute as @s at @s positioned ^ ^ ^7 run damage @e[r=3,type=!player] {} entity_attack entity @s",
                "execute as @s at @s positioned ^ ^ ^6.5 run damage @e[r=3,type=!player] {} entity_attack entity @s",
                "execute as @s at @s positioned ^ ^ ^6 run damage @e[r=3,type=!player] {} entity_attack entity @s",
                "execute as @s at @s positioned ^ ^ ^5.5 run damage @e[r=3,type=!player] {} entity_attack entity @s",
                "execute as @s at @s positioned ^ ^ ^5 run damage @e[r=3,type=!player] {} entity_attack entity @s",
                "execute as @s at @s positioned ^ ^ ^4.5 run damage @e[r=3,type=!player] {} entity_attack entity @s",
                "execute as @s at @s positioned ^ ^ ^4 run damage @e[r=3,type=!player] {} entity_attack entity @s",
                "execute as @s at @s positioned ^ ^ ^3.5 run damage @e[r=3,type=!player] {} entity_attack entity @s",
                "execute as @s at @s positioned ^ ^ ^3 run damage @e[r=3,type=!player] {} entity_attack entity @s",
                "execute as @s at @s positioned ^ ^ ^2.5 run damage @e[r=3,type=!player] {} entity_attack entity @s",
                "execute as @s at @s positioned ^ ^ ^2 run damage @e[r=3,type=!player] {} entity_attack entity @s",
                "execute as @s at @s positioned ^ ^ ^1.5 run damage @e[r=3,type=!player] {} entity_attack entity @s",
                "execute as @s at @s positioned ^ ^ ^1 run damage @e[r=3,type=!player] {} entity_attack entity @s",
                "execute as @s at @s positioned ^ ^ ^0.5 run damage @e[r=3,type=!player] {} entity_attack entity @s"
            ]
            for delay_command in command_list:
                cmd_comp.SetCommand(delay_command.format(int(30 * damage_multiplier)), player_id)

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
            time_comp.AddTimer(1.0, DelayCommand)
            if skill_id == "armor" and item_identifier_used == "sf:burden_of_loneliness":
                cmd_comp.SetCommand(
                    "/damage @e[r=3,type=!player] {} entity_attack entity @s".format(int(30 * damage_multiplier)),
                    player_id)
                print "12345"

            logger.info("玩家 %s 释放了技能: %s (物品: %s)" % (player_id, skill_id, item_identifier_used or "默认"))

    @EventListener("ServerSpawnMobEvent")
    def OnServerSpawnMob(self, args):
        """服务端生成生物事件"""
        print "服务端生成生物事件"
        print args.dict()

        try:
            # 获取生成的生物信息
            entity_id = args.entityId
            identifier = args.identifier

            print "生成的生物ID: %s, 类型: %s" % (entity_id, identifier)

            # 检查是否为需要绑定UI的生物类型
            # 这里可以根据需要修改条件
            if identifier.find("minecraft") != -1:
                print "为生物 %s (%s) 发送UI绑定通知" % (entity_id, identifier)
                self.NotifyClientToBindUI(entity_id)

        except Exception as e:
            logger.error("OnServerSpawnMob error: %s" % str(e))
            print "OnServerSpawnMob error: %s" % str(e)

    def NotifyClientToBindUI(self, entity_id):
        """
        通知客户端为实体绑定UI
        """
        try:
            # 检查实体ID是否有效
            # if entity_id <= 0:
            #     logger.warning("尝试为无效的实体ID %s 发送UI绑定通知，操作已取消。" % entity_id)
            #     return

            # 获取所有玩家ID列表
            player_list = serverApi.GetPlayerList()

            event_data = {
                "entityId": entity_id,  # 传递整数类型的entityId
                "uiName": config.shadowEntityUIName
            }

            # 关键修改：延迟发送事件，确保客户端已加载该实体
            for player_id in player_list:
                # 为每个玩家创建一个延迟任务
                time_comp = SCF.CreateGame(levelId)
                # 延迟0.5秒发送，可根据实际情况调整
                time_comp.AddTimer(0.5,
                                   lambda pid=player_id, eid=entity_id, ed=event_data: self._delayedBindNotify(pid, eid,
                                                                                                               ed))

            logger.info("已调度实体 %s 的UI绑定通知，将在0.5秒后发送给客户端。" % entity_id)

        except Exception as e:
            logger.error("NotifyClientToBindUI error: %s" % str(e))

    def _delayedBindNotify(self, player_id, entity_id, event_data):
        """
        延迟发送绑定通知的内部方法
        """
        # 延迟后再次检查实体是否仍然存在（可选，但更安全）
        try:
            comp = serverApi.GetEngineCompFactory().CreatePos(entity_id)
            if comp is None:
                logger.error("延迟检查：实体 %s 已不存在，取消UI绑定通知。" % entity_id)
                return
        except:
            logger.error("延迟检查：实体 %s 无效，取消UI绑定通知。" % entity_id)
            return

        # 发送事件
        self.sendClient(player_id, config.BindEntityUIEvent, event_data)
        logger.info("已向玩家 %s 发送实体 %s 的UI绑定事件。" % (player_id, entity_id))

    @EventListener("DamageEvent")
    def OnEntityHurtEvent(self, args):
        """
        实体受伤事件 - 实体被玩家攻击
        """
        try:
            # 从事件参数中获取数据
            hurt_entity_id = args.entityId
            attacker_id = args.srcId  # DamageEvent中攻击者参数是srcId

            if not hurt_entity_id or not attacker_id:
                return

            # 检查攻击者是否是玩家
            player_list = serverApi.GetPlayerList()
            if attacker_id in player_list:
                # 检查受伤实体是否是玩家（避免玩家攻击玩家也触发）
                if hurt_entity_id not in player_list:
                    # 实体被玩家攻击，为该实体增加10点暗影能量
                    logger.info("实体 %s 被玩家 %s 攻击，增加暗影能量" % (hurt_entity_id, attacker_id))
                    self.SendShadowEnergyToEntity(hurt_entity_id, 10)

        except Exception as e:
            logger.error("DamageEvent error: %s" % str(e))

    @EventListener("PlayerHurtEvent")
    def OnPlayerHurtEvent(self, args):
        """
        玩家受伤事件 - 玩家被实体攻击
        """
        try:
            # 从事件参数中获取数据
            hurt_player_id = args.id  # PlayerHurtEvent中受伤玩家参数是id
            attacker_id = args.attacker  # PlayerHurtEvent中攻击者参数是attacker

            if not hurt_player_id or not attacker_id:
                return

            # 检查攻击者是否是实体（非玩家）
            player_list = serverApi.GetPlayerList()
            if attacker_id not in player_list:
                # 玩家被实体攻击，为该攻击实体增加5点暗影能量
                logger.info("玩家 %s 被实体 %s 攻击，为实体增加暗影能量" % (hurt_player_id, attacker_id))
                self.SendShadowEnergyToEntity(attacker_id, 5)

        except Exception as e:
            logger.error("PlayerHurtEvent error: %s" % str(e))

    def SendShadowEnergyToEntity(self, entity_id, amount):
        """
        为指定实体发送暗影能量增加事件
        注意：需要将事件发送给所有玩家，因为任何玩家都可能看到这个实体的UI
        """
        try:
            # 获取所有在线玩家
            player_list = serverApi.GetPlayerList()

            for player_id in player_list:
                # 向每个玩家发送事件，让他们的客户端更新该实体的暗影能量
                self.sendClient(player_id, config.AddShadowEnergyEvent, {
                    "amount": amount,
                    "entityId": entity_id
                })

            logger.info("为实体 %s 发送 %s 点暗影能量给所有玩家" % (entity_id, amount))

        except Exception as e:
            logger.error("SendShadowEnergyToEntity error: %s" % str(e))