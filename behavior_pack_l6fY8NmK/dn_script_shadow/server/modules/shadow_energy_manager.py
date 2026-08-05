# -*- coding: utf-8 -*-

import mod.server.extraServerApi as serverApi
from mod_log import logger
from dn_script_shadow import config

serverApi.GetServerSystemCls()
SCF = serverApi.GetEngineCompFactory()
levelId = serverApi.GetLevelId()


class ShadowEnergyManager:
    """暗影能量管理器 - 负责实体和玩家的暗影能量状态管理"""
    
    def __init__(self, subsystem):
        self.subsystem = subsystem
    
    def getEntityShadowState(self, entity_id):
        """获取实体暗影能量状态"""
        return self.subsystem.entity_shadow_states.get(str(entity_id), {"shadow_data": 0, "clip_ratio": 1.0})

    def getEntityShadowEffect(self, entity_id):
        """获取实体特殊效果状态"""
        return self.subsystem.entity_shadow_effects.get(str(entity_id), {"effect": None})

    def setEntityShadowState(self, entity_id, data):
        """设置实体暗影能量状态并广播"""
        entity_id_str = str(entity_id)
        self.subsystem.entity_shadow_states[entity_id_str] = data.copy()
        self.subsystem.broadcastEntityShadowUpdate(entity_id_str, data)

    def SendShadowEnergyToEntity(self, entity_id, amount):
        """为指定实体增加暗影能量（服务器权威版本）"""
        try:
            current_state = self.getEntityShadowState(entity_id)
            current_energy = current_state.get("shadow_data", 0)

            new_energy = min(100, current_energy + amount)
            new_ratio = 1.0 - (new_energy / 100.0)

            new_state = {
                "shadow_data": new_energy,
                "clip_ratio": new_ratio,
                "is_full": (new_energy >= 100)
            }

            self.setEntityShadowState(entity_id, new_state)

            logger.info("实体 %s 暗影能量: %s -> %s" % (entity_id, current_energy, new_energy))

            self.subsystem.checkEntityBerserkMode(entity_id, new_energy)

        except Exception as e:
            logger.error("SendShadowEnergyToEntity error: %s" % str(e))

    def shadowSystemPlayer(self, player_id, operation, value=0):
        """
        操作玩家暗影能量值
        :param player_id: 玩家ID
        :param operation: 操作类型 - set(设置)/reduce(减少)/add(增加)/query(查询)
        :param value: 能量值 (0-100)，query操作时忽略此参数
        :return: 当前能量值（query操作时返回），或操作结果布尔值
        """
        try:
            if not hasattr(self.subsystem, 'player_energy_values'):
                self.subsystem.player_energy_values = {}

            player_id_str = str(player_id)
            current_energy = self.subsystem.player_energy_values.get(player_id_str, 0)

            player_list = serverApi.GetPlayerList()
            if player_id not in player_list:
                logger.warning("shadowSystemPlayer: 玩家 %s 不在线" % player_id)
                return False if operation != "query" else 0

            if self.subsystem.player_shadow_effects.get(player_id_str) == "suppression":
                if operation == "add":
                    logger.info("玩家 %s 处于暗影抑制状态，无法增加能量" % player_id)
                    return False
                elif operation == "set" and value > 0:
                    logger.info("玩家 %s 处于暗影抑制状态，无法设置能量为 %s" % (player_id, value))
                    return False

            if operation == "query":
                logger.info("查询玩家 %s 的暗影能量（注：玩家能量存储在客户端）" % player_id)
                return 0

            elif operation == "set":
                if not isinstance(value, int) or value < 0 or value > 100:
                    logger.warning("shadowSystemPlayer: 能量值必须在0-100之间")
                    return False
                
                self.subsystem.player_energy_values[player_id_str] = value
                
                self.subsystem.sendClient(player_id, config.SetPlayerShadowEnergyEvent, {
                    "energy_value": value
                })
                logger.info("玩家 %s 的暗影能量设置为 %s" % (player_id, value))
                
                return True

            elif operation == "add":
                new_energy = min(100, current_energy + value)
                
                self.subsystem.player_energy_values[player_id_str] = new_energy
                
                self.subsystem.sendClient(player_id, config.AddShadowEnergyEvent, {
                    "amount": value,
                    "entityId": None
                })
                
                return True
            elif operation == "reduce":
                if not isinstance(value, int) or value < 0 or value > 100:
                    logger.warning("shadowSystemPlayer: 减少的能量值必须在0-100之间")
                    return False
                
                if current_energy <= 0:
                    logger.info("玩家 %s 能量已为0，无需减少" % player_id)
                    return True
                
                new_energy = max(0, current_energy - value)
                
                self.subsystem.player_energy_values[player_id_str] = new_energy
                
                self.subsystem.sendClient(player_id, config.SetPlayerShadowEnergyEvent, {
                    "energy_value": new_energy
                })
                
                logger.info("玩家 %s 的暗影能量减少 %s" % (player_id, value))
                return True

            else:
                logger.warning("shadowSystemPlayer: 无效的操作类型 %s" % operation)
                return False

        except Exception as e:
            logger.error("shadowSystemPlayer error: %s" % str(e))
            return False if operation != "query" else 0

    def broadcastEntityShadowUpdate(self, entity_id, data):
        """向所有玩家广播实体暗影能量更新"""
        player_list = serverApi.GetPlayerList()
        for player_id in player_list:
            self.subsystem.sendClient(player_id, config.UpdateEntityShadowEvent, {
                "entityId": entity_id,
                "shadow_data": data["shadow_data"],
                "clip_ratio": data["clip_ratio"],
                "is_full": data.get("is_full", False),
                "effect": data.get("effect")
            })