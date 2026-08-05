# -*- coding: utf-8 -*-

import mod.server.extraServerApi as serverApi
from mod_log import logger
from dn_script_shadow import config

SCF = serverApi.GetEngineCompFactory()
levelId = serverApi.GetLevelId()


class EntityIdentifierManager:
    """实体标识符管理器 - 负责实体标识符的存储和获取"""
    
    def __init__(self, subsystem):
        self.subsystem = subsystem
    
    def getEntityIdentifier(self, entity_id):
        """获取实体的标识符"""
        try:
            entity_id_str = str(entity_id)
            identifier = self.subsystem.entity_identifiers.get(entity_id_str)
            if identifier:
                return identifier
            
            logger.warning("实体 %s 的标识符未在缓存中找到，尝试使用引擎API获取" % entity_id_str)
            try:
                engine_type_comp = serverApi.GetEngineCompFactory().CreateEngineType(entity_id)
                if engine_type_comp:
                    identifier = engine_type_comp.GetEngineTypeStr()
                    if identifier:
                        self.subsystem.entity_identifiers[entity_id_str] = identifier
                        logger.info("通过引擎API获取到实体 %s 的标识符: %s" % (entity_id_str, identifier))
                        return identifier
            except Exception as api_error:
                logger.error("使用引擎API获取实体标识符失败: %s" % str(api_error))
            
            logger.warning("实体 %s 的标识符无法获取" % entity_id_str)
            return None
        except Exception as e:
            logger.error("getEntityIdentifier error: %s" % str(e))
            return None

    def NotifyClientToBindUI(self, entity_id):
        """
        通知客户端为实体绑定UI
        """
        try:
            player_list = serverApi.GetPlayerList()

            event_data = {
                "entityId": entity_id,
                "uiName": config.shadowEntityUIName
            }

            for player_id in player_list:
                time_comp = SCF.CreateGame(levelId)
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
        try:
            comp = serverApi.GetEngineCompFactory().CreatePos(entity_id)
            if comp is None:
                logger.error("延迟检查：实体 %s 已不存在，取消UI绑定通知。" % entity_id)
                return
        except:
            logger.error("延迟检查：实体 %s 无效，取消UI绑定通知。" % entity_id)
            return

        self.subsystem.sendClient(player_id, config.BindEntityUIEvent, event_data)
        logger.info("已向玩家 %s 发送实体 %s 的UI绑定事件。" % (player_id, entity_id))