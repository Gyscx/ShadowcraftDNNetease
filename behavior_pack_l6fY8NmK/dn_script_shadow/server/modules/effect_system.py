# -*- coding: utf-8 -*-

import mod.server.extraServerApi as serverApi
from mod_log import logger
from dn_script_shadow import config

SCF = serverApi.GetEngineCompFactory()
levelId = serverApi.GetLevelId()


class EffectSystem:
    """效果管理系统 - 负责实体和玩家的效果管理（抑制、充能、暗影形态）"""
    
    def __init__(self, subsystem):
        self.subsystem = subsystem
    
    def applyShadowSuppression(self, entity_id):
        """应用暗影抑制效果：能量条始终为空（clip_ratio=1）"""
        entity_id_str = str(entity_id)
        self.subsystem.entity_shadow_effects[entity_id_str] = {"effect": "suppression"}
        self.subsystem.broadcastEntityShadowUpdate(entity_id_str, {
            "shadow_data": 0,
            "clip_ratio": 1.0,
            "is_full": False,
            "effect": "suppression"
        })
        logger.info("实体 %s 应用暗影抑制效果，能量条为空" % entity_id_str)

    def applyShadowCharging(self, entity_id):
        """应用暗影充能效果：能量条始终为满（clip_ratio=0）"""
        entity_id_str = str(entity_id)
        self.subsystem.entity_shadow_effects[entity_id_str] = {"effect": "charging"}
        self.subsystem.broadcastEntityShadowUpdate(entity_id_str, {
            "shadow_data": 100,
            "clip_ratio": 0.0,
            "is_full": True,
            "effect": "charging"
        })
        logger.info("实体 %s 应用暗影充能效果，能量条为满" % entity_id_str)

    def removeShadowEffect(self, entity_id):
        """移除特殊效果，恢复正常状态"""
        entity_id_str = str(entity_id)
        if entity_id_str in self.subsystem.entity_shadow_effects:
            del self.subsystem.entity_shadow_effects[entity_id_str]
        normal_data = self.subsystem.getEntityShadowState(entity_id_str)
        self.subsystem.broadcastEntityShadowUpdate(entity_id_str, normal_data)
        logger.info("实体 %s 移除特殊效果，恢复正常" % entity_id_str)

    def applyPlayerShadowSuppression(self, player_id):
        """应用玩家暗影抑制效果：能量条始终为空"""
        player_id_str = str(player_id)
        self.subsystem.player_shadow_effects[player_id_str] = "suppression"
        self.subsystem.sendClient(player_id, config.PlayerShadowEffectEvent, {
            "clip_ratio": 1.0,
            "shadow_data": 0,
            "is_full": False,
            "effect": "suppression"
        })
        logger.info("玩家 %s 应用暗影抑制效果" % player_id)

    def applyPlayerShadowCharging(self, player_id):
        """应用玩家暗影充能效果：能量条始终为满"""
        player_id_str = str(player_id)
        self.subsystem.player_shadow_effects[player_id_str] = "charging"
        self.subsystem.sendClient(player_id, config.PlayerShadowEffectEvent, {
            "clip_ratio": 0.0,
            "shadow_data": 100,
            "is_full": True,
            "effect": "charging"
        })
        logger.info("玩家 %s 应用暗影充能效果" % player_id)

        if not hasattr(self.subsystem, 'player_energy_values'):
            self.subsystem.player_energy_values = {}
        self.subsystem.player_energy_values[player_id_str] = 100
        logger.info("[充能效果] 设置玩家 %s 能量值为100" % player_id)

        self.subsystem.sendClient(player_id, config.SetPlayerShadowEnergyEvent, {
            "energy_value": 100
        })
        logger.info("[充能效果] 同步玩家 %s 能量值100给客户端配置" % player_id)

    def removePlayerShadowEffect(self, player_id):
        """移除玩家特殊效果，恢复正常状态"""
        player_id_str = str(player_id)
        if self.subsystem.player_shadow_effects.get(player_id_str) == "berserk":
            logger.info("玩家 %s 处于暗影形态，跳过移除特殊效果" % player_id)
            return
        if player_id_str in self.subsystem.player_shadow_effects:
            del self.subsystem.player_shadow_effects[player_id_str]

        if not hasattr(self.subsystem, 'player_energy_values'):
            self.subsystem.player_energy_values = {}
        current_energy = self.subsystem.player_energy_values.get(player_id_str, 0)
        clip_ratio = 1.0 - (current_energy / 100.0)

        self.subsystem.sendClient(player_id, config.PlayerShadowEffectEvent, {
            "clip_ratio": clip_ratio,
            "shadow_data": current_energy,
            "is_full": (current_energy >= 100),
            "effect": None
        })
        logger.info("玩家 %s 移除特殊效果，恢复能量显示为 %s" % (player_id, current_energy))

        self.subsystem.sendClient(player_id, config.SetPlayerShadowEnergyEvent, {
            "energy_value": current_energy
        })
        logger.info("玩家 %s 同步实际能量值 %s 给客户端配置" % (player_id, current_energy))

    def checkEntityBerserkMode(self, entity_id, energy_value):
        """检查并更新实体暗影形态状态"""
        try:
            entity_id_str = str(entity_id)
            
            entity_identifier = self.subsystem.getEntityIdentifier(entity_id)
            
            if not entity_identifier or not entity_identifier.startswith("sf:") or "trader" in entity_identifier:
                return
            
            if energy_value == 100:
                if self.subsystem.entity_shadow_effects.get(entity_id_str, {}).get("effect") != "berserk":
                    logger.info("实体 %s 能量值已满，激活暗影形态！" % entity_id_str)
                    
                    self.subsystem.entity_shadow_effects[entity_id_str] = {"effect": "berserk"}
                    
                    self.subsystem.broadcastEntityShadowUpdate(entity_id_str, {
                        "shadow_data": 100,
                        "clip_ratio": 0.0,
                        "is_full": True,
                        "effect": "berserk"
                    })
            else:
                if self.subsystem.entity_shadow_effects.get(entity_id_str, {}).get("effect") == "berserk":
                    logger.info("实体 %s 能量值不足，移除暗影形态！" % entity_id_str)
                    
                    if entity_id_str in self.subsystem.entity_shadow_effects:
                        del self.subsystem.entity_shadow_effects[entity_id_str]
                    
                    self.subsystem.broadcastEntityShadowUpdate(entity_id_str, {
                        "shadow_data": energy_value,
                        "clip_ratio": 1.0 - (energy_value / 100.0),
                        "is_full": False,
                        "effect": None
                    })
            
        except Exception as e:
            logger.error("checkEntityBerserkMode error: %s" % str(e))