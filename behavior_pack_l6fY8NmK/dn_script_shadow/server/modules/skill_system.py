# -*- coding: utf-8 -*-

import mod.server.extraServerApi as serverApi
from mod_log import logger
from dn_script_shadow import config

SCF = serverApi.GetEngineCompFactory()
levelId = serverApi.GetLevelId()


class SkillSystem:
    """技能系统 - 负责技能配置、升级、等级管理"""
    
    def __init__(self, subsystem):
        self.subsystem = subsystem
    
    def GetSkillConfig(self, skill_id):
        """获取技能配置"""
        for skill in config.SKILL_CONFIGS:
            if skill["skill_id"] == skill_id:
                return skill
        return None

    def GetSkillLevel(self, player_id, skill_id):
        """获取玩家技能等级"""
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

        self.subsystem.sendClient(player_id, config.SyncSkillLevelsEvent, {
            "skill_levels": skill_levels
        })
        logger.info("向玩家 %s 同步技能等级: %s" % (player_id, skill_levels))

    def getUpgradeInfo(self, skill_id, current_level):
        """获取升级信息"""
        next_level = current_level + 1

        skill_upgrade_config = config.SKILL_UPGRADE_CONFIG["upgrade_effects"].get(skill_id)
        if skill_upgrade_config and len(skill_upgrade_config) >= next_level:
            return skill_upgrade_config[next_level - 1]

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
                        item_comp.SetInvItemNum(slot, 0)
                    else:
                        item_comp.SetInvItemNum(slot, new_count)

                    remaining -= consume

        return remaining == 0

    def ProcessSkillUpgrade(self, player_id, skill_id, fragment_cost, current_level):
        """统一的技能升级处理方法"""
        if fragment_cost > 0:
            if not self.consumeFragments(player_id, fragment_cost):
                self.subsystem.sendClient(player_id, config.UpgradeSkillResultEvent, {
                    "skill_id": skill_id,
                    "new_level": current_level,
                    "success": False,
                    "reason": "碎片不足"
                })
                logger.info("玩家 %s 升级技能 %s 失败：碎片不足" % (player_id, skill_id))
                return False

        next_level = current_level + 1
        self.SetSkillLevel(player_id, skill_id, next_level)

        upgrade_info = self.getUpgradeInfo(skill_id, current_level)

        damage_multiplier = 1.0
        cooldown_multiplier = 1.0
        if upgrade_info:
            damage_multiplier = upgrade_info.get("damage_multiplier", 1.0)
            cooldown_multiplier = upgrade_info.get("cooldown_multiplier", 1.0)

        self.subsystem.sendClient(player_id, config.UpgradeSkillResultEvent, {
            "skill_id": skill_id,
            "new_level": next_level,
            "success": True,
            "damage_multiplier": damage_multiplier,
            "cooldown_multiplier": cooldown_multiplier
        })

        logger.info("玩家 %s 升级了技能 %s 到 %s级，消耗碎片: %s" % (player_id, skill_id, next_level, fragment_cost))
        return True