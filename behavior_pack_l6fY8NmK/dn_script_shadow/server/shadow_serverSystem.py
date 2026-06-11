# -*- coding: utf-8 -*-

import mod.server.extraServerApi as serverApi
from mod_log import logger
from .. import config

from ..architect.compact import ServerSubsystem, SubsystemServer
from ..architect.compact import EventListener, CustomEvent

SS = serverApi.GetServerSystemCls()
SCF = serverApi.GetEngineCompFactory()
levelId = serverApi.GetLevelId()


@SubsystemServer
class ShadowServerSystem(ServerSubsystem):
    def onInit(self):
        print "===== Shadow Server System Init (Dynamic) ====="
        # 服务器维护所有实体的暗影能量状态
        self.entity_shadow_states = {}  # entity_id -> {"shadow_data": int, "clip_ratio": float}
        # 实体特殊效果状态
        self.entity_shadow_effects = {}  # entity_id -> {"effect": "suppression"/"charging"/None}
        # 玩家特殊效果状态（按玩家存储）
        self.player_shadow_effects = {}  # player_id -> "suppression"/"charging"/"berserk"/None
        # 存储实体标识符
        self.entity_identifiers = {}  # entity_id -> identifier
        # 存储实体粒子效果定时器
        self.entity_particle_timers = {}  # entity_id -> timer_id
        # 存储玩家粒子效果定时器
        self.player_particle_timers = {}  # player_id -> timer_id
        # 存储玩家能量递减定时器
        self.player_energy_decay_timers = {}  # player_id -> timer_id
        # 防止定时器回调重入的标志
        self.player_particle_timer_running = {}  # player_id -> bool
        self.player_energy_decay_timer_running = {}  # player_id -> bool
        # 防止定时器回调重入的标志
        self.player_particle_timer_running = {}  # player_id -> bool
        self.player_energy_decay_timer_running = {}  # player_id -> bool
        # 防止定时器回调重入的标志
        self.player_particle_timer_running = {}  # player_id -> bool
        self.player_energy_decay_timer_running = {}  # player_id -> bool
        # 存储玩家效果剩余时间
        self.player_effect_durations = {}  # player_id -> {"suppression": int, "charging": int}
        # 存储实体效果剩余时间
        self.entity_effect_durations = {}  # entity_id -> {"suppression": int, "charging": int}
        # 存储玩家技能伤害乘数（用于传递给抛射物相关技能）
        self.player_skill_damage_multipliers = {}  # player_id -> damage_multiplier
    
    def _removeEffectAndNotify(self, entity_id, effect_name):
        """
        移除玩家身上的药剂效果并通知客户端
        :param entity_id: 实体ID
        :param effect_name: 效果名称
        """
        cmd_comp = SCF.CreateCommand(serverApi.GetLevelId())
        remove_effect_cmd = "/effect @s clear %s" % effect_name
        cmd_comp.SetCommand(remove_effect_cmd, str(entity_id))
        logger.info("[药剂冷却] 移除玩家 %s 的 %s 效果" % (entity_id, effect_name))

    def getEntityShadowState(self, entity_id):
        """获取实体暗影能量状态"""
        return self.entity_shadow_states.get(str(entity_id), {"shadow_data": 0, "clip_ratio": 1.0})

    def getEntityShadowEffect(self, entity_id):
        """获取实体特殊效果状态"""
        return self.entity_shadow_effects.get(str(entity_id), {"effect": None})

    def setEntityShadowState(self, entity_id, data):
        """设置实体暗影能量状态并广播"""
        entity_id_str = str(entity_id)
        self.entity_shadow_states[entity_id_str] = data.copy()

        # 广播给所有玩家
        self.broadcastEntityShadowUpdate(entity_id_str, data)

    def applyShadowSuppression(self, entity_id):
        """应用暗影抑制效果：能量条始终为空（clip_ratio=1）"""
        entity_id_str = str(entity_id)
        self.entity_shadow_effects[entity_id_str] = {"effect": "suppression"}
        # 广播特殊状态
        self.broadcastEntityShadowUpdate(entity_id_str, {
            "shadow_data": 0,
            "clip_ratio": 1.0,
            "is_full": False,
            "effect": "suppression"
        })
        logger.info("实体 %s 应用暗影抑制效果，能量条为空" % entity_id_str)

    def applyShadowCharging(self, entity_id):
        """应用暗影充能效果：能量条始终为满（clip_ratio=0）"""
        entity_id_str = str(entity_id)
        self.entity_shadow_effects[entity_id_str] = {"effect": "charging"}
        # 广播特殊状态
        self.broadcastEntityShadowUpdate(entity_id_str, {
            "shadow_data": 100,
            "clip_ratio": 0.0,
            "is_full": True,
            "effect": "charging"
        })
        logger.info("实体 %s 应用暗影充能效果，能量条为满" % entity_id_str)

    def removeShadowEffect(self, entity_id):
        """移除特殊效果，恢复正常状态"""
        entity_id_str = str(entity_id)
        if entity_id_str in self.entity_shadow_effects:
            del self.entity_shadow_effects[entity_id_str]
        # 恢复正常能量数据
        normal_data = self.getEntityShadowState(entity_id_str)
        self.broadcastEntityShadowUpdate(entity_id_str, normal_data)
        logger.info("实体 %s 移除特殊效果，恢复正常" % entity_id_str)

    def applyPlayerShadowSuppression(self, player_id):
        """应用玩家暗影抑制效果：能量条始终为空"""
        player_id_str = str(player_id)
        self.player_shadow_effects[player_id_str] = "suppression"
        self.sendClient(player_id, config.PlayerShadowEffectEvent, {
            "clip_ratio": 1.0,
            "shadow_data": 0,
            "is_full": False,
            "effect": "suppression"
        })
        logger.info("玩家 %s 应用暗影抑制效果" % player_id)

    def applyPlayerShadowCharging(self, player_id):
        """应用玩家暗影充能效果：能量条始终为满"""
        player_id_str = str(player_id)
        self.player_shadow_effects[player_id_str] = "charging"
        self.sendClient(player_id, config.PlayerShadowEffectEvent, {
            "clip_ratio": 0.0,
            "shadow_data": 100,
            "is_full": True,
            "effect": "charging"
        })
        logger.info("玩家 %s 应用暗影充能效果" % player_id)

    def removePlayerShadowEffect(self, player_id):
        """移除玩家特殊效果，恢复正常状态"""
        player_id_str = str(player_id)
        # 如果玩家处于暗影形态，不要移除
        if self.player_shadow_effects.get(player_id_str) == "berserk":
            logger.info("玩家 %s 处于暗影形态，跳过移除特殊效果" % player_id)
            return
        if player_id_str in self.player_shadow_effects:
            del self.player_shadow_effects[player_id_str]
        # 恢复正常状态（默认空能量条）
        self.sendClient(player_id, config.PlayerShadowEffectEvent, {
            "clip_ratio": 1.0,
            "shadow_data": 0,
            "is_full": False,
            "effect": None
        })
        logger.info("玩家 %s 移除特殊效果" % player_id)

    def broadcastEntityShadowUpdate(self, entity_id, data):
        """向所有玩家广播实体暗影能量更新"""
        player_list = serverApi.GetPlayerList()
        for player_id in player_list:
            self.sendClient(player_id, config.UpdateEntityShadowEvent, {
                "entityId": entity_id,
                "shadow_data": data["shadow_data"],
                "clip_ratio": data["clip_ratio"],
                "is_full": data.get("is_full", False),
                "effect": data.get("effect")  # 包含特殊效果标记
            })

    def SendShadowEnergyToEntity(self, entity_id, amount):
        """为指定实体增加暗影能量（服务器权威版本）"""
        try:
            # 获取当前状态
            current_state = self.getEntityShadowState(entity_id)
            current_energy = current_state.get("shadow_data", 0)

            # 计算新状态
            new_energy = min(100, current_energy + amount)
            new_ratio = 1.0 - (new_energy / 100.0)

            new_state = {
                "shadow_data": new_energy,
                "clip_ratio": new_ratio,
                "is_full": (new_energy >= 100)
            }

            # 更新并广播
            self.setEntityShadowState(entity_id, new_state)

            logger.info("实体 %s 暗影能量: %s -> %s" % (entity_id, current_energy, new_energy))

            # 检查能量值是否为100，触发或移除暗影形态
            self.checkEntityBerserkMode(entity_id, new_energy)

        except Exception as e:
            logger.error("SendShadowEnergyToEntity error: %s" % str(e))

    def checkEntityBerserkMode(self, entity_id, energy_value):
        """检查并更新实体暗影形态状态"""
        try:
            entity_id_str = str(entity_id)
            
            # 获取实体标识符
            entity_identifier = self.getEntityIdentifier(entity_id)
            
            # 只为符合sf:开头且不包含trader的实体处理暗影形态
            if not entity_identifier or not entity_identifier.startswith("sf:") or "trader" in entity_identifier:
                return
            
            cmd_comp = SCF.CreateCommand(levelId)
            
            if energy_value == 100:
                # 能量值=100，给予速度2和力量2效果
                if self.entity_shadow_effects.get(entity_id_str, {}).get("effect") != "berserk":
                    logger.info("实体 %s 能量值已满，激活暗影形态！" % entity_id_str)
                    
                    # 速度 III 效果
                    speed_command = "/effect @s speed 60 2 false"
                    cmd_comp.SetCommand(speed_command, entity_id_str)
                    logger.info("为实体 %s 施加速度 III 效果" % entity_id_str)
                    
                    # 力量 III 效果
                    strength_command = "/effect @s strength 60 2 false"
                    cmd_comp.SetCommand(strength_command, entity_id_str)
                    logger.info("为实体 %s 施加力量 III 效果" % entity_id_str)
                    
                    # 设置暗影形态标记
                    self.entity_shadow_effects[entity_id_str] = {"effect": "berserk"}
                    
                    # 广播暗影形态
                    self.broadcastEntityShadowUpdate(entity_id_str, {
                        "shadow_data": 100,
                        "clip_ratio": 0.0,
                        "is_full": True,
                        "effect": "berserk"
                    })
                    
                    # 启动粒子效果定时器
                    self.startEntityParticleTimer(entity_id_str)
            else:
                # 能量值<100，移除效果
                if self.entity_shadow_effects.get(entity_id_str, {}).get("effect") == "berserk":
                    logger.info("实体 %s 能量值不足，移除暗影形态！" % entity_id_str)
                    
                    # 移除速度效果
                    remove_speed_command = "/effect @s speed 0 0 true"
                    cmd_comp.SetCommand(remove_speed_command, entity_id_str)
                    
                    # 移除力量效果
                    remove_strength_command = "/effect @s strength 0 0 true"
                    cmd_comp.SetCommand(remove_strength_command, entity_id_str)
                    
                    # 移除暗影形态标记
                    if entity_id_str in self.entity_shadow_effects:
                        del self.entity_shadow_effects[entity_id_str]
                    
                    # 停止粒子效果定时器
                    self.stopEntityParticleTimer(entity_id_str)
                    
                    # 广播恢复正常状态
                    self.broadcastEntityShadowUpdate(entity_id_str, {
                        "shadow_data": energy_value,
                        "clip_ratio": 1.0 - (energy_value / 100.0),
                        "is_full": False,
                        "effect": None
                    })
            
        except Exception as e:
            logger.error("checkEntityBerserkMode error: %s" % str(e))

    def startEntityParticleTimer(self, entity_id_str):
        """启动实体粒子效果定时器"""
        try:
            # 如果已有定时器，先停止
            if entity_id_str in self.entity_particle_timers:
                self.stopEntityParticleTimer(entity_id_str)
            
            # 播放一次粒子
            self.playEntityParticle(entity_id_str)
            
            # 创建循环定时器，每1秒播放一次粒子
            time_comp = SCF.CreateGame(levelId)
            timer_id = time_comp.AddTimer(1.0, lambda eid=entity_id_str: self._particleTimerCallback(eid))
            self.entity_particle_timers[entity_id_str] = timer_id
            
            logger.info("实体 %s 粒子效果定时器已启动" % entity_id_str)
            
        except Exception as e:
            logger.error("startEntityParticleTimer error: %s" % str(e))

    def stopEntityParticleTimer(self, entity_id_str):
        """停止实体粒子效果定时器"""
        try:
            logger.info("[停止粒子定时器] 尝试停止实体 %s 的粒子定时器" % entity_id_str)
            logger.info("[停止粒子定时器] 当前活跃的粒子定时器: %s" % str(self.entity_particle_timers.keys()))
            if entity_id_str in self.entity_particle_timers:
                timer_id = self.entity_particle_timers[entity_id_str]
                # 真正取消定时器
                time_comp = SCF.CreateGame(levelId)
                time_comp.CancelTimer(timer_id)
                # 移除定时器记录
                del self.entity_particle_timers[entity_id_str]
                logger.info("实体 %s 粒子效果定时器已停止" % entity_id_str)
            else:
                logger.info("[停止粒子定时器] 实体 %s 没有活跃的粒子定时器" % entity_id_str)
            
        except Exception as e:
            logger.error("stopEntityParticleTimer error: %s" % str(e))

    def _particleTimerCallback(self, entity_id_str):
        """粒子定时器回调函数"""
        try:
            # 检查实体是否仍然处于暗影形态
            if self.entity_shadow_effects.get(entity_id_str, {}).get("effect") == "berserk":
                # 继续播放粒子
                self.playEntityParticle(entity_id_str)
                # 重新设置定时器
                time_comp = SCF.CreateGame(levelId)
                timer_id = time_comp.AddTimer(1.0, lambda eid=entity_id_str: self._particleTimerCallback(eid))
                self.entity_particle_timers[entity_id_str] = timer_id
            else:
                # 不再处于暗影形态，停止定时器
                self.stopEntityParticleTimer(entity_id_str)
                
        except Exception as e:
            logger.error("_particleTimerCallback error: %s" % str(e))

    def playEntityParticle(self, entity_id_str):
        """为实体播放粒子效果"""
        try:
            # 使用/execute命令在实体位置播放粒子
            # 语法: /execute at <实体> run particle <粒子名称> ~ ~ ~
            particle_command = "/execute at @s run particle sf:shadow_smoke ~ ~ ~ "
            
            cmd_comp = SCF.CreateCommand(levelId)
            cmd_comp.SetCommand(particle_command, entity_id_str)
            
        except Exception as e:
            logger.error("playEntityParticle error: %s" % str(e))

    def shadowSystemPlayer(self, player_id, operation, value=0):
        """
        操作玩家暗影能量值
        :param player_id: 玩家ID
        :param operation: 操作类型 - set(设置)/reduce(减少)/add(增加)/query(查询)
        :param value: 能量值 (0-100)，query操作时忽略此参数
        :return: 当前能量值（query操作时返回），或操作结果布尔值
        """
        try:
            # 在方法开头添加
            if not hasattr(self, 'player_energy_values'):
                self.player_energy_values = {}

            player_id_str = str(player_id)
            current_energy = self.player_energy_values.get(player_id_str, 0)

            player_list = serverApi.GetPlayerList()
            if player_id not in player_list:
                logger.warning("shadowSystemPlayer: 玩家 %s 不在线" % player_id)
                return False if operation != "query" else 0

            # 获取当前能量值（从配置或默认值）
            # 注意：玩家能量值存储在客户端，服务端需要通过事件查询
            # 这里使用一个简化的方式：通过发送查询事件获取当前值
            
            if operation == "query":
                # 查询操作：请求客户端返回当前能量值
                # 由于玩家能量存储在客户端，这里返回一个默认值
                # 实际应用中可能需要维护服务端的状态副本
                logger.info("查询玩家 %s 的暗影能量（注：玩家能量存储在客户端）" % player_id)
                return 0  # 默认返回0，实际需要客户端同步

            elif operation == "set":
                # 设置操作：直接设置为指定值
                if not isinstance(value, int) or value < 0 or value > 100:
                    logger.warning("shadowSystemPlayer: 能量值必须在0-100之间")
                    return False
                
                # 保存到服务端字典
                self.player_energy_values[player_id_str] = value
                
                # 发送设置事件给客户端
                self.sendClient(player_id, config.SetPlayerShadowEnergyEvent, {
                    "energy_value": value
                })
                logger.info("玩家 %s 的暗影能量设置为 %s" % (player_id, value))
                
                # 检查能量值是否为100，启动或停止粒子效果
                self.checkPlayerBerserkMode(player_id, value)
                
                return True

            elif operation == "add":
                # 计算新能量值
                new_energy = min(100, current_energy + value)
                
                # 更新服务端副本
                self.player_energy_values[player_id_str] = new_energy
                
                # 发送增加事件
                self.sendClient(player_id, config.AddShadowEnergyEvent, {
                    "amount": value,
                    "entityId": None
                })
                
                # 检查暗影形态
                self.checkPlayerBerserkMode(player_id, new_energy)
                
                return True
            elif operation == "reduce":
                # 减少操作：在当前值基础上减少
                if not isinstance(value, int) or value < 0 or value > 100:
                    logger.warning("shadowSystemPlayer: 减少的能量值必须在0-100之间")
                    return False
                
                # 如果当前能量已经是0，不需要减少
                if current_energy <= 0:
                    logger.info("玩家 %s 能量已为0，无需减少" % player_id)
                    return True
                
                # 计算新能量值
                new_energy = max(0, current_energy - value)
                
                # 更新服务端副本
                self.player_energy_values[player_id_str] = new_energy
                
                # 如果新能量为0，直接同步状态（不发送递减事件，避免客户端出现负数）
                if new_energy <= 0:
                    self.sendClient(player_id, config.SetPlayerShadowEnergyEvent, {
                        "energy_value": 0
                    })
                else:
                    # 发送减少事件
                    self.sendClient(player_id, config.AddShadowEnergyEvent, {
                        "amount": -value,
                        "entityId": None
                    })
                
                # 检查暗影形态
                # self.checkPlayerBerserkMode(player_id, new_energy)
                
                logger.info("玩家 %s 的暗影能量减少 %s" % (player_id, value))
                return True

            else:
                logger.warning("shadowSystemPlayer: 无效的操作类型 %s" % operation)
                return False

        except Exception as e:
            logger.error("shadowSystemPlayer error: %s" % str(e))
            return False if operation != "query" else 0

    def checkPlayerBerserkMode(self, player_id, energy_value):
        """检查并更新玩家暗影形态状态"""
        try:
            player_id_str = str(player_id)
            
            # 检测玩家是否有暗影形态tag
            has_berserk_tag = False
            try:
                tag_comp = SCF.CreateTag(player_id)
                has_berserk_tag = tag_comp.EntityHasTag("shadow_berserk")
            except Exception as e:
                logger.warning("Tag API调用失败，使用字典后备方案: %s" % str(e))
                has_berserk_tag = self.player_shadow_effects.get(player_id_str) == "berserk"
            
            if energy_value == 100 and not has_berserk_tag:
                # 能量值=100且没有暗影形态tag，激活暗影形态
                logger.info("玩家 %s 能量值已满，激活暗影形态！" % player_id_str)
                
                # 同步能量值给客户端
                self.sendClient(player_id, config.SetPlayerShadowEnergyEvent, {
                    "energy_value": 100
                })
                
                # 给予tag
                cmd_comp = SCF.CreateCommand(levelId)
                add_tag_command = "/tag @s add shadow_berserk"
                cmd_comp.SetCommand(add_tag_command, player_id_str)
                print("已给予玩家 %s shadow_berserk tag" % player_id_str)
                # 记录到字典作为后备
                self.player_shadow_effects[player_id_str] = "berserk"
                # 给予暗影形态效果
                self.givePlayerEffects(player_id_str)
                # 启动粒子效果定时器
                self.startPlayerParticleTimer(player_id_str)
                
                # 启动能量递减定时器
                self.startPlayerEnergyDecayTimer(player_id_str)
            
            elif energy_value == 0 and has_berserk_tag:
                # 能量值=0且有暗影形态tag，移除暗影形态
                logger.info("玩家 %s 能量值为0，移除暗影形态！" % player_id_str)
                # 移除tag
                cmd_comp = SCF.CreateCommand(levelId)
                remove_tag_command = "/tag @s remove shadow_berserk"
                cmd_comp.SetCommand(remove_tag_command, player_id_str)
                logger.info("已移除玩家 %s 的 shadow_berserk tag" % player_id_str)
                # 清除所有暗影形态效果
                self.clearPlayerEffects(player_id_str)
                # 清除字典记录
                if player_id_str in self.player_shadow_effects:
                    del self.player_shadow_effects[player_id_str]
                # 停止粒子效果定时器
                self.stopPlayerParticleTimer(player_id_str)
                # 停止能量递减定时器
                self.stopPlayerEnergyDecayTimer(player_id_str)
            
        except Exception as e:
            logger.error("checkPlayerBerserkMode error: %s" % str(e))

    def givePlayerEffects(self, player_id_str):
        """给予玩家暗影形态效果（速度 III、力量 III、夜视）"""
        try:
            cmd_comp = SCF.CreateCommand(levelId)
            # 给予速度 III 效果
            speed_command = "/effect @s speed 60 2 false"
            cmd_comp.SetCommand(speed_command, player_id_str)
            logger.info("已给予玩家 %s 速度 III 效果" % player_id_str)
            # 给予力量 III 效果
            strength_command = "/effect @s strength 60 2 false"
            cmd_comp.SetCommand(strength_command, player_id_str)
            logger.info("已给予玩家 %s 力量 III 效果" % player_id_str)
            # 给予夜视效果
            night_vision_command = "/effect @s night_vision 60 0 false"
            cmd_comp.SetCommand(night_vision_command, player_id_str)
            logger.info("已给予玩家 %s 夜视效果" % player_id_str)
        except Exception as e:
            logger.error("givePlayerEffects error: %s" % str(e))

    def clearPlayerEffects(self, player_id_str):
        """清除玩家的所有暗影形态效果（速度 III、力量 III、夜视）"""
        try:
            cmd_comp = SCF.CreateCommand(levelId)
            remove_speed_command = "/effect @s speed 0 0 true"
            cmd_comp.SetCommand(remove_speed_command, player_id_str)
            logger.info("已移除玩家 %s 的速度 III 效果" % player_id_str)
            # 移除力量效果
            remove_strength_command = "/effect @s strength 0 0 true"
            cmd_comp.SetCommand(remove_strength_command, player_id_str)
            logger.info("已移除玩家 %s 的力量 III 效果" % player_id_str)
            # 移除夜视效果
            remove_night_vision_command = "/effect @s night_vision 0 0 true"
            cmd_comp.SetCommand(remove_night_vision_command, player_id_str)
            logger.info("已移除玩家 %s 的夜视效果" % player_id_str)
        except Exception as e:
            logger.error("clearPlayerEffects error: %s" % str(e))

    def startPlayerParticleTimer(self, player_id_str):
        """启动玩家粒子效果定时器"""
        try:
            # 如果已有定时器，先停止
            if player_id_str in self.player_particle_timers:
                self.stopPlayerParticleTimer(player_id_str)
            
            # 播放一次粒子
            self.playPlayerParticle(player_id_str)
            
            # 创建循环定时器，每1秒播放一次粒子
            time_comp = SCF.CreateGame(levelId)
            timer_id = time_comp.AddTimer(1.0, lambda pid=player_id_str: self._playerParticleTimerCallback(pid))
            self.player_particle_timers[player_id_str] = timer_id
            
            logger.info("玩家 %s 粒子效果定时器已启动" % player_id_str)
            
        except Exception as e:
            logger.error("startPlayerParticleTimer error: %s" % str(e))

    def stopPlayerParticleTimer(self, player_id_str):
        """停止玩家粒子效果定时器"""
        try:
            if player_id_str in self.player_particle_timers:
                timer_id = self.player_particle_timers[player_id_str]
                # 真正取消定时器
                time_comp = SCF.CreateGame(levelId)
                time_comp.CancelTimer(timer_id)
                # 移除定时器记录
                del self.player_particle_timers[player_id_str]
                logger.info("玩家 %s 粒子效果定时器已停止" % player_id_str)
            else:
                logger.info("玩家 %s 没有活跃的粒子定时器，无需停止" % player_id_str)
            
        except Exception as e:
            logger.error("stopPlayerParticleTimer error: %s" % str(e))

    def _playerParticleTimerCallback(self, player_id_str):
        """玩家粒子定时器回调函数"""
        try:
            # 防止重入：如果已经在运行，直接返回
            if self.player_particle_timer_running.get(player_id_str, False):
                logger.warning("[粒子回调] 玩家 %s 的粒子回调正在运行，跳过本次执行" % player_id_str)
                return
            
            self.player_particle_timer_running[player_id_str] = True
            
            logger.info("[粒子回调] 检查玩家 %s 的暗影形态" % player_id_str)
            # 检查玩家是否有暗影形态tag
            tag_comp = SCF.CreateTag(player_id_str)
            has_berserk_tag = tag_comp.EntityHasTag("shadow_berserk")
            
            if has_berserk_tag:
                logger.info("[粒子回调] 玩家 %s 有暗影形态tag，播放粒子" % player_id_str)
                # 继续播放粒子
                self.playPlayerParticle(player_id_str)
                # 先停止旧定时器，再创建新定时器（防止重复）
                if player_id_str in self.player_particle_timers:
                    old_timer_id = self.player_particle_timers[player_id_str]
                    time_comp = SCF.CreateGame(levelId)
                    time_comp.CancelTimer(old_timer_id)
                    logger.info("[粒子回调] 已取消玩家 %s 的旧粒子定时器" % player_id_str)
                # 重新设置定时器
                time_comp = SCF.CreateGame(levelId)
                timer_id = time_comp.AddTimer(1.0, lambda pid=player_id_str: self._playerParticleTimerCallback(pid))
                self.player_particle_timers[player_id_str] = timer_id
            else:
                logger.info("[粒子回调] 玩家 %s 没有暗影形态tag，停止粒子定时器" % player_id_str)
                # 没有暗影形态tag，停止定时器
                self.stopPlayerParticleTimer(player_id_str)
                
        except Exception as e:
            logger.error("_playerParticleTimerCallback error: %s" % str(e))
        finally:
            # 确保无论如何都重置运行标志
            self.player_particle_timer_running[player_id_str] = False

    def playPlayerParticle(self, player_id_str):
        """为玩家播放粒子效果"""
        try:
            # 使用/execute命令在玩家位置播放粒子
            particle_command = "/execute at @s run particle sf:shadow_smoke ~ ~ ~ "
            
            cmd_comp = SCF.CreateCommand(levelId)
            cmd_comp.SetCommand(particle_command, player_id_str)
            
        except Exception as e:
            logger.error("playPlayerParticle error: %s" % str(e))

    def startPlayerEnergyDecayTimer(self, player_id_str):
        """启动玩家能量递减定时器"""
        try:
            # 创建循环定时器，每1秒减少1点能量
            time_comp = SCF.CreateGame(levelId)
            timer_id = time_comp.AddTimer(1.0, lambda pid=player_id_str: self._playerEnergyDecayCallback(pid))
            # 存储定时器ID（如果需要后续停止）
            if not hasattr(self, 'player_energy_decay_timers'):
                self.player_energy_decay_timers = {}
            self.player_energy_decay_timers[player_id_str] = timer_id
            
            logger.info("玩家 %s 能量递减定时器已启动" % player_id_str)
            
        except Exception as e:
            logger.error("startPlayerEnergyDecayTimer error: %s" % str(e))

    def stopPlayerEnergyDecayTimer(self, player_id_str):
        """停止玩家能量递减定时器"""
        try:
            if hasattr(self, 'player_energy_decay_timers') and player_id_str in self.player_energy_decay_timers:
                timer_id = self.player_energy_decay_timers[player_id_str]
                # 真正取消定时器
                time_comp = SCF.CreateGame(levelId)
                time_comp.CancelTimer(timer_id)
                # 移除定时器记录
                del self.player_energy_decay_timers[player_id_str]
                logger.info("玩家 %s 能量递减定时器已停止" % player_id_str)
            else:
                logger.info("玩家 %s 没有活跃的能量递减定时器，无需停止" % player_id_str)
            
        except Exception as e:
            logger.error("stopPlayerEnergyDecayTimer error: %s" % str(e))

    def _playerEnergyDecayCallback(self, player_id_str):
        """玩家能量递减回调函数"""
        try:
            # 防止重入：如果已经在运行，直接返回
            if self.player_energy_decay_timer_running.get(player_id_str, False):
                logger.warning("[能量递减回调] 玩家 %s 的能量递减回调正在运行，跳过本次执行" % player_id_str)
                return
            
            self.player_energy_decay_timer_running[player_id_str] = True
            
            # 检查玩家是否有暗影形态tag
            has_berserk_tag = False
            try:
                tag_comp = SCF.CreateTag(player_id_str)
                has_berserk_tag = tag_comp.EntityHasTag("shadow_berserk")
            except Exception as e:
                logger.warning("[能量递减回调] Tag API调用失败，使用字典后备方案: %s" % str(e))
                has_berserk_tag = self.player_shadow_effects.get(player_id_str) == "berserk"
            
            # 如果没有tag，停止定时器
            if not has_berserk_tag:
                logger.info("[能量递减回调] 玩家 %s 没有暗影形态tag，停止能量递减定时器" % player_id_str)
                self.stopPlayerEnergyDecayTimer(player_id_str)
                self.player_energy_decay_timer_running[player_id_str] = False
                return

            # 获取当前能量值
            current_energy = self.player_energy_values.get(player_id_str, 0)
            
            # 计算新能量值
            new_energy = current_energy - 1
            
            # 如果能量会减到0或以下
            if new_energy <= 0:
                logger.info("[能量递减回调] 玩家 %s 能量从 %s 减至0，移除tag并停止所有效果" % (player_id_str, current_energy))
                # 更新服务端副本
                self.player_energy_values[player_id_str] = 0
                # 同步能量为0
                self.sendClient(player_id_str, config.SetPlayerShadowEnergyEvent, {
                    "energy_value": 0
                })
                # 移除tag
                cmd_comp = SCF.CreateCommand(levelId)
                remove_tag_command = "/tag @s remove shadow_berserk"
                cmd_comp.SetCommand(remove_tag_command, player_id_str)
                # 清除字典记录
                if player_id_str in self.player_shadow_effects:
                    del self.player_shadow_effects[player_id_str]
                # 停止粒子效果定时器
                self.stopPlayerParticleTimer(player_id_str)
                # 停止能量递减定时器
                self.stopPlayerEnergyDecayTimer(player_id_str)
                self.player_energy_decay_timer_running[player_id_str] = False
                return
            
            # 更新服务端副本
            self.player_energy_values[player_id_str] = new_energy
            
            # 发送减少事件
            self.shadowSystemPlayer(player_id_str, "reduce", 1)
            
            # 播放粒子效果
            self.playPlayerParticle(player_id_str)
            
            # 重置运行标记
            self.player_energy_decay_timer_running[player_id_str] = False
            
            # 重新设置定时器（先停止旧定时器，防止重复）
            if player_id_str in self.player_energy_decay_timers:
                old_timer_id = self.player_energy_decay_timers[player_id_str]
                time_comp = SCF.CreateGame(levelId)
                time_comp.CancelTimer(old_timer_id)
                logger.info("[能量递减回调] 已取消玩家 %s 的旧能量递减定时器" % player_id_str)
            
            time_comp = SCF.CreateGame(levelId)
            timer_id = time_comp.AddTimer(1.0, lambda pid=player_id_str: self._playerEnergyDecayCallback(pid))
            if not hasattr(self, 'player_energy_decay_timers'):
                self.player_energy_decay_timers = {}
            self.player_energy_decay_timers[player_id_str] = timer_id
            
        except Exception as e:
            logger.error("_playerEnergyDecayCallback error: %s" % str(e))
        finally:
            # 确保无论如何都重置运行标志
            self.player_energy_decay_timer_running[player_id_str] = False

    def GetSkillConfig(self, skill_id):
        """获取技能配置"""
        for skill in config.SKILL_CONFIGS:
            if skill["skill_id"] == skill_id:
                return skill
        return None

    @CustomEvent(config.ClientUseShadowEnergyEvent)
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
        self.shadowSystemPlayer(playerId, "add", 8)
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

    @CustomEvent(config.ClientUpgradeSkillEvent)
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

    @CustomEvent(config.ServerUpgradeSkillEvent)
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

    @CustomEvent(config.RequestSkillLevelsEvent)
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

    @CustomEvent(config.ServerSkillEvent)
    def OnSkillEvent(self, args):
        """服务端释放技能事件（使用命令）"""
        try:
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
            cmd_comp = SCF.CreateCommand(levelId)
            for command in commands_to_execute:
                cmd_comp.SetCommand(command, player_id)
            if skill_id == "RW" and item_identifier_used == "minecraft:arrow":
                time_comp = SCF.CreateGame(levelId)
                time_comp.AddTimer(1.0, DelayCommand)
            if skill_id == "armor" and item_identifier_used == "sf:burden_of_loneliness":
                damage_command = "/execute as @s at @s run damage @e[r=5,type=!player] {} entity_attack entity @s".format(int(30 * damage_multiplier))
                cmd_comp.SetCommand(damage_command,player_id)
            if skill_id == "helmet" and item_identifier_used == "sf:eye_of_time":
                self.player_skill_damage_multipliers[player_id] = damage_multiplier
                pos_comp = SCF.CreatePos(player_id)
                rot_comp = SCF.CreateRot(player_id)
                if pos_comp and rot_comp:
                    player_foot_pos = pos_comp.GetFootPos()
                    player_rot = rot_comp.GetRot()
                    if player_foot_pos and player_rot:
                        dir_x, dir_y, dir_z = serverApi.GetDirFromRot(player_rot)
                        eye_height = 1.5
                        spawn_pos = (player_foot_pos[0] + dir_x * 1.0, player_foot_pos[1] + eye_height, player_foot_pos[2] + dir_z * 1.0)
                        direction = (dir_x, dir_y, dir_z)
                        param = {
                            "position": spawn_pos,
                            "direction": direction,
                            "power": 1.0,
                            "gravity": 0.0
                        }
                        projectile_comp = SCF.CreateProjectile(levelId)
                        projectile_id = projectile_comp.CreateProjectileEntity(player_id, "sf:shadowball_eruption", param)
                        if projectile_id != "-1":
                            logger.info("玩家 %s 释放头盔技能，发射暗影爆发球，抛射物ID: %s" % (player_id, projectile_id))
                        else:
                            logger.warning("玩家 %s 释放头盔技能失败，无法创建抛射物" % player_id)

                logger.info("玩家 %s 释放了技能: %s (物品: %s)" % (player_id, skill_id, item_identifier_used or "默认"))
        except Exception as e:
            logger.error("OnSkillEvent error: %s" % str(e))
    @EventListener("ServerSpawnMobEvent")
    def OnServerSpawnMob(self, args):
        """服务端生成生物事件"""
        try:
            entity_id = args.entityId
            identifier = args.identifier
            entity_id_str = str(entity_id)

            # 存储所有实体的标识符（不仅限于sf:开头）
            self.entity_identifiers[entity_id_str] = identifier
            logger.info("实体 %s 生成，标识符: %s" % (entity_id_str, identifier))

            # 只对 sf: 开头且不包含 trader 的实体创建UI
            if identifier.startswith("sf:") and "trader" not in identifier:
                # 确保初始化实体暗影能量状态为0
                initial_state = {
                    "shadow_data": 0,  # 强制为0
                    "clip_ratio": 1.0,
                    "is_full": False
                }

                # 先检查是否已存在，避免重复初始化
                if entity_id_str not in self.entity_shadow_states:
                    self.entity_shadow_states[entity_id_str] = initial_state.copy()

                    # 立即广播初始状态给所有玩家
                    self.broadcastEntityShadowUpdate(entity_id_str, initial_state)

                    logger.info("新实体 %s 初始化，暗影能量: 0" % entity_id_str)

                    # 延迟发送UI绑定通知
                    self.NotifyClientToBindUI(entity_id)
                else:
                    logger.warning("实体 %s 已存在，跳过重复初始化" % entity_id_str)
            else:
                logger.info("实体 %s 不是 sf: 开头，跳过UI创建" % identifier)

        except Exception as e:
            logger.error("OnServerSpawnMob error: %s" % str(e))

        except Exception as e:
            logger.error("OnServerSpawnMob error: %s" % str(e))

    def getEntityIdentifier(self, entity_id):
        """获取实体的标识符"""
        try:
            entity_id_str = str(entity_id)
            # 先从存储的字典中获取标识符
            identifier = self.entity_identifiers.get(entity_id_str)
            if identifier:
                return identifier
            
            # 如果字典中没有，尝试使用引擎API获取
            logger.warning("实体 %s 的标识符未在缓存中找到，尝试使用引擎API获取" % entity_id_str)
            try:
                engine_type_comp = serverApi.GetEngineCompFactory().CreateEngineType(entity_id)
                if engine_type_comp:
                    identifier = engine_type_comp.GetEngineTypeStr()
                    if identifier:
                        # 缓存获取到的标识符
                        self.entity_identifiers[entity_id_str] = identifier
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
        """实体受伤事件 - 实体被玩家攻击"""
        try:
            hurt_entity_id = args.entityId
            attacker_id = args.srcId
            projectile_id = args.projectileId

            if not hurt_entity_id or not attacker_id:
                logger.warning("OnEntityHurtEvent: 无效的事件参数")
                return

            # 检查是否是抛射物造成的伤害
            if projectile_id:
                # 获取抛射物的标识符
                projectile_identifier = self.getEntityIdentifier(projectile_id)
                # 如果是暗影抑制药水抛射物，跳过增加能量
                if projectile_identifier == "sf:shadow_dampener_splash_potion_projectile":
                    logger.info("抛射物 %s 对实体 %s 造成伤害，跳过增加能量" % (projectile_id, hurt_entity_id))
                    return

            # 检查攻击者是否是玩家
            player_list = serverApi.GetPlayerList()
            if attacker_id in player_list:
                # 检查受伤实体是否是玩家（避免玩家攻击玩家也触发）
                if hurt_entity_id not in player_list:
                    # 检查受伤实体的标识符是否为 sf: 开头且不包含 trader
                    entity_identifier = self.getEntityIdentifier(hurt_entity_id)
                    if entity_identifier and entity_identifier.startswith("sf:") and "trader" not in entity_identifier:
                        logger.info("玩家 %s 攻击实体 %s (标识符: %s)，玩家和实体都获得暗影能量" % (attacker_id, hurt_entity_id, entity_identifier))
                        # 给玩家增加暗影能量
                        self.shadowSystemPlayer(attacker_id, "add", 3)
                        # 给实体增加暗影能量
                        self.SendShadowEnergyToEntity(hurt_entity_id, 10)
                        # 为实体绑定头顶UI
                        self.NotifyClientToBindUI(hurt_entity_id)
                    else:
                        logger.info("玩家 %s 攻击实体 %s，但标识符为 '%s'，不符合条件，跳过UI绑定" % (attacker_id, hurt_entity_id, entity_identifier))
                else:
                    logger.info("玩家攻击玩家，不增加暗影能量")
            else:
                logger.info("攻击者不是玩家，是实体 %s" % attacker_id)

        except Exception as e:
            logger.error("OnEntityHurtEvent error: %s" % str(e))

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
                # 检查攻击实体的标识符是否为 sf: 开头且不包含 trader
                entity_identifier = self.getEntityIdentifier(attacker_id)
                if entity_identifier and entity_identifier.startswith("sf:") and "trader" not in entity_identifier:
                    # 玩家被实体攻击，玩家和实体都获得暗影能量
                    logger.info("玩家 %s 被实体 %s (标识符: %s) 攻击，玩家和实体都获得暗影能量" % (hurt_player_id, attacker_id, entity_identifier))
                    # 给玩家增加暗影能量
                    self.shadowSystemPlayer(hurt_player_id, "add", 10)
                    # 给实体增加暗影能量
                    self.SendShadowEnergyToEntity(attacker_id, 3)
                    # 为实体绑定头顶UI
                    self.NotifyClientToBindUI(attacker_id)
                else:
                    logger.info("玩家 %s 被实体 %s 攻击，但标识符不符合条件，跳过UI绑定" % (hurt_player_id, attacker_id))

        except Exception as e:
            logger.error("PlayerHurtEvent error: %s" % str(e))

    @CustomEvent(config.RequestEntityShadowDataEvent)
    def OnRequestEntityShadowData(self, args):
        """处理客户端请求实体数据"""
        entity_id = args.entityId
        player_id = args.playerId

        if not entity_id or not player_id:
            return

        # 获取实体数据
        entity_data = self.getEntityShadowState(entity_id)

        # 发送给请求的客户端
        self.sendClient(player_id, config.ResponseEntityShadowDataEvent, {
            "entityId": entity_id,
            "shadow_data": entity_data.get("shadow_data", 0),
            "clip_ratio": entity_data.get("clip_ratio", 1.0),
            "is_full": entity_data.get("is_full", False)
        })

    @EventListener("AddEffectServerEvent")
    def OnEffectAdded(self, args):
        logger.info("AddEffectServerEvent")
        entityId = args.entityId
        effectName = args.effectName
        player_list = serverApi.GetPlayerList()

        if entityId in player_list:
            # 玩家获得效果
            player_id_str = str(entityId)
            
            if effectName == "sf:shadow_dampener_effect":
                logger.info("玩家 %s 应用暗影抑制效果" % entityId)
                
                # 检查玩家是否处于暗影形态
                if self.player_shadow_effects.get(player_id_str) == "berserk":
                    logger.info("[抑制剂] 玩家 %s 处于暗影形态，喝下暗影抑制剂，停止暗影形态" % entityId)
                    
                    # 清除暗影形态标记
                    if player_id_str in self.player_shadow_effects:
                        del self.player_shadow_effects[player_id_str]
                        logger.info("[抑制剂] 清除玩家 %s 的暗影形态标记" % entityId)
                    
                    # 设置能量为0
                    if not hasattr(self, 'player_energy_values'):
                        self.player_energy_values = {}
                    self.player_energy_values[player_id_str] = 0
                    
                    # 同步能量值0给客户端
                    self.sendClient(entityId, config.SetPlayerShadowEnergyEvent, {
                        "energy_value": 0
                    })
                    logger.info("[抑制剂] 同步玩家 %s 能量值为0给客户端" % entityId)
                    
                    # 移除玩家的 shadow_berserk tag
                    cmd_comp = SCF.CreateCommand(serverApi.GetLevelId())
                    remove_tag_command = "/tag @s remove shadow_berserk"
                    cmd_comp.SetCommand(remove_tag_command, player_id_str)
                    logger.info("[抑制剂] 移除玩家 %s 的 shadow_berserk tag" % entityId)
                    
                    # 停止粒子效果定时器
                    if hasattr(self, 'player_particle_timers') and player_id_str in self.player_particle_timers:
                        timer_id = self.player_particle_timers[player_id_str]
                        time_comp = SCF.CreateGame(levelId)
                        time_comp.CancelTimer(timer_id)
                        del self.player_particle_timers[player_id_str]
                        logger.info("[抑制剂] 停止玩家 %s 的粒子效果定时器" % entityId)
                    
                    # 停止能量递减定时器
                    if hasattr(self, 'player_energy_decay_timers') and player_id_str in self.player_energy_decay_timers:
                        timer_id = self.player_energy_decay_timers[player_id_str]
                        time_comp = SCF.CreateGame(levelId)
                        time_comp.CancelTimer(timer_id)
                        del self.player_energy_decay_timers[player_id_str]
                        logger.info("[抑制剂] 停止玩家 %s 的能量递减定时器" % entityId)
                    
                    # 清除玩家的所有effect效果
                    self.clearPlayerEffects(player_id_str)
                
                # 设置抑制状态
                self.player_shadow_effect = "suppression"
                
                # 通知客户端更新UI为抑制状态
                self.sendClient(entityId, config.PlayerShadowEffectEvent, {
                    "clip_ratio": 1.0,
                    "shadow_data": 0,
                    "is_full": False,
                    "effect": "suppression"
                })
                logger.info("[抑制剂] 通知客户端玩家 %s 进入抑制状态" % entityId)
                
            elif effectName == "sf:shadow_overcharger_effect":
                # 先移除抑制效果（如果存在）
                if hasattr(self, 'player_shadow_effect') and self.player_shadow_effect == "suppression":
                    logger.info("玩家 %s 移除暗影抑制效果" % entityId)
                self.player_shadow_effect = "charging"
                self.sendClient(entityId, config.PlayerShadowEffectEvent, {
                    "clip_ratio": 0.0,
                    "shadow_data": 100,
                    "is_full": True,
                    "effect": "charging"
                })
                logger.info("玩家 %s 应用暗影充能效果" % entityId)
                
                # 设置玩家能量值为100（关键：必须在触发暗影形态之前设置）
                if not hasattr(self, 'player_energy_values'):
                    self.player_energy_values = {}
                self.player_energy_values[str(entityId)] = 100
                logger.info("[充能药剂] 设置玩家 %s 能量值为100" % entityId)
                
                # 触发暗影形态：粒子效果、能量递减、持续effect
                logger.info("[充能药剂] 玩家 %s 使用暗影充能药剂，触发暗影形态" % entityId)
                self.checkPlayerBerserkMode(entityId, 100)
        else:
            # 实体获得效果
            entity_id_str = str(entityId)
            if effectName == "sf:shadow_dampener_effect":
                # 立即清除该实体的所有效果和粒子
                cmd_comp = SCF.CreateCommand(levelId)
                
                # 清除所有效果
                clear_effects_command = "/effect @s clear"
                cmd_comp.SetCommand(clear_effects_command, entity_id_str)
                logger.info("实体 %s 被喷洒抑制药水，清除所有效果" % entity_id_str)
                
                # 清除暗影形态标记
                if self.entity_shadow_effects.get(entity_id_str, {}).get("effect") == "berserk":
                    logger.info("实体 %s 被喷洒抑制药水，清除暗影形态标记" % entity_id_str)
                if entity_id_str in self.entity_shadow_effects:
                    del self.entity_shadow_effects[entity_id_str]
                
                # 停止粒子效果定时器
                self.stopEntityParticleTimer(entity_id_str)
                
                # 设置抑制状态
                self.entity_shadow_effects[entity_id_str] = {"effect": "suppression"}
                self.broadcastEntityShadowUpdate(entity_id_str, {
                    "shadow_data": 0,
                    "clip_ratio": 1.0,
                    "is_full": False,
                    "effect": "suppression"
                })
                logger.info("实体 %s 应用暗影抑制效果，已清除所有效果和粒子" % entity_id_str)
            elif effectName == "sf:shadow_overcharger_effect":
                # 先移除抑制效果（如果存在）
                if entity_id_str in self.entity_shadow_effects and self.entity_shadow_effects[entity_id_str].get("effect") == "suppression":
                    logger.info("实体 %s 移除暗影抑制效果" % entity_id_str)
                self.entity_shadow_effects[entity_id_str] = {"effect": "charging"}
                self.broadcastEntityShadowUpdate(entity_id_str, {
                    "shadow_data": 100,
                    "clip_ratio": 0.0,
                    "is_full": True,
                    "effect": "charging"
                })
                logger.info("实体 %s 应用暗影充能效果" % entity_id_str)

    # @EventListener("RemoveEffectServerEvent")
    # def OnEffectRemoved(self, args):
    #     logger.info("RemoveEffectServerEvent")
    #     entityId = args.entityId
    #     effectName = args.effectName
    #     player_list = serverApi.GetPlayerList()

    #     if entityId in player_list:
    #         # 玩家移除效果
    #         self.removePlayerShadowEffect(entityId)
    #     else:
    #         # 实体移除效果
    #         self.removeShadowEffect(entityId)
    
    @EventListener("RefreshEffectServerEvent")
    def OnEffectRefreshed(self, args):
        # logger.info("RefreshEffectServerEvent")
        entityId = args.entityId
        effectName = args.effectName
        effectDuration = args.effectDuration if hasattr(args, 'effectDuration') else 0
        player_list = serverApi.GetPlayerList()

        if entityId in player_list:
            player_id_str = str(entityId)
            # 如果玩家处于暗影形态，不要覆盖
            if self.player_shadow_effects.get(player_id_str) == "berserk":
                # 静默跳过，不记录日志以避免 spam
                return
            
            # 只处理暗影抑制和充能效果
            if effectName not in ["sf:shadow_dampener_effect", "sf:shadow_overcharger_effect"]:
                return
            
            # 初始化效果时间存储
            if player_id_str not in self.player_effect_durations:
                self.player_effect_durations[player_id_str] = {"suppression": 0, "charging": 0}
            
            # 更新当前效果的时间
            if effectName == "sf:shadow_dampener_effect":
                self.player_effect_durations[player_id_str]["suppression"] = effectDuration
            elif effectName == "sf:shadow_overcharger_effect":
                self.player_effect_durations[player_id_str]["charging"] = effectDuration
            
            # 比较两个效果的时间，使用较大的那个
            suppression_time = self.player_effect_durations[player_id_str]["suppression"]
            charging_time = self.player_effect_durations[player_id_str]["charging"]
            
            if suppression_time >= charging_time:
                # 暗影抑制时间更长或相等，应用抑制效果
                self.applyPlayerShadowSuppression(entityId)
                logger.info("玩家 %s 暗影抑制时间(%d) >= 暗影充能时间(%d)，应用抑制效果" % (entityId, suppression_time, charging_time))
            else:
                # 暗影充能时间更长，应用充能效果
                self.applyPlayerShadowCharging(entityId)
                logger.info("玩家 %s 暗影充能时间(%d) > 暗影抑制时间(%d)，应用充能效果" % (entityId, charging_time, suppression_time))
        else:
            # 实体获得效果
            entity_id_str = str(entityId)
            
            # 只处理暗影抑制和充能效果
            if effectName not in ["sf:shadow_dampener_effect", "sf:shadow_overcharger_effect"]:
                return
            
            # 初始化效果时间存储
            if entity_id_str not in self.entity_effect_durations:
                self.entity_effect_durations[entity_id_str] = {"suppression": 0, "charging": 0}
            
            # 更新当前效果的时间
            if effectName == "sf:shadow_dampener_effect":
                self.entity_effect_durations[entity_id_str]["suppression"] = effectDuration
            elif effectName == "sf:shadow_overcharger_effect":
                self.entity_effect_durations[entity_id_str]["charging"] = effectDuration
            
            # 比较两个效果的时间，使用较大的那个
            suppression_time = self.entity_effect_durations[entity_id_str]["suppression"]
            charging_time = self.entity_effect_durations[entity_id_str]["charging"]
            
            if suppression_time >= charging_time:
                # 暗影抑制时间更长或相等，应用抑制效果
                self.applyShadowSuppression(entityId)
                logger.info("实体 %s 暗影抑制时间(%d) >= 暗影充能时间(%d)，应用抑制效果" % (entityId, suppression_time, charging_time))
            else:
                # 暗影充能时间更长，应用充能效果
                self.applyShadowCharging(entityId)
                logger.info("实体 %s 暗影充能时间(%d) > 暗影抑制时间(%d)，应用充能效果" % (entityId, charging_time, suppression_time))

    @EventListener("ProjectileDoHitEffectEvent")
    def OnProjectileHitBlock(self, args):
        """抛射物碰撞事件 - 处理暗影抑制药水效果和暗影爆发球"""
        try:
            projectile_id = args.id
            
            # 获取抛射物的标识符
            projectile_identifier = self.getEntityIdentifier(projectile_id)
            
            # 处理暗影爆发球
            if projectile_identifier == "sf:shadowball_eruption":
                logger.info("暗影爆发球碰撞事件触发，projectile_id: %s, hitTargetType: %s, targetId: %s" % (projectile_id, args.hitTargetType, args.targetId))
                
                # 检查是否击中了实体
                if args.targetId:
                    target_entity_id = args.targetId
                    target_identifier = self.getEntityIdentifier(target_entity_id)
                    logger.info("暗影爆发球击中目标 %s，类型: %s，标识符: %s" % (target_entity_id, args.hitTargetType, target_identifier))
                    cmd_comp = SCF.CreateCommand(levelId)
                    time_comp = SCF.CreateGame(levelId)
                    
                    shooter_id = args.srcId if hasattr(args, 'srcId') else None
                    dmg_multi = self.player_skill_damage_multipliers.get(shooter_id, 1.0)
                    
                    time_comp.AddTimer(1.0, lambda eid=target_entity_id, dmg=dmg_multi: self.EruptionDamageDelay(eid, dmg))   
                    # 给被击中的实体一个向上的速度向量
                    motion_comp = SCF.CreateActorMotion(target_entity_id)
                    par_command1 = "execute as @s at @s run particle sf:eruption1"
                    par_command2 = "execute as @s at @s run particle sf:eruption2"
                    if motion_comp:
                        engine_type_comp = SCF.CreateEngineType(target_entity_id)
                        if engine_type_comp:
                            engine_type = engine_type_comp.GetEngineType()
                            if engine_type == 1:
                                motion_comp.SetPlayerMotion((0, 0.75, 0))
                                cmd_comp.SetCommand(par_command1,target_entity_id)
                                cmd_comp.SetCommand(par_command2,target_entity_id)
                                logger.info("成功给玩家 %s 设置向上速度 (0, 0.75, 0)" % target_entity_id)
                            else:
                                motion_comp.SetMotion((0, 0.75, 0))
                                cmd_comp.SetCommand(par_command1,target_entity_id)
                                cmd_comp.SetCommand(par_command2,target_entity_id)
                                logger.info("成功给实体 %s 设置向上速度 (0, 0.75, 0)" % target_entity_id)
                        else:
                            motion_comp.SetMotion((0, 0.75, 0))   
                            cmd_comp.SetCommand(par_command1,target_entity_id)
                            cmd_comp.SetCommand(par_command2,target_entity_id) 
                            logger.info("成功给实体 %s 设置向上速度 (0, 0.75, 0)" % target_entity_id)
                    else:
                        logger.warning("无法获取实体 %s 的 ActorMotion 组件" % target_entity_id)
                else:
                    logger.info("暗影爆发球未击中实体或目标ID为空")
                return
            
            # 只处理暗影抑制药水抛射物
            if projectile_identifier != "sf:shadow_dampener_splash_potion_projectile":
                return

            logger.info("暗影抑制药水抛射物碰撞方块: %s" % projectile_id)

            # 使用 /execute 配合 /shadow_system 指令
            # 语法: /execute at <抛射物> run shadow_system @e[r=5,type=!player] 0
            command = "/execute at @s run shadow_system @e[r=5,type=!player] 0"
            
            # 执行命令
            result = SCF.CreateCommand(projectile_id).SetCommand(command)
            
            if result:
                logger.info("暗影抑制药水效果命令执行成功: %s" % command)
            else:
                logger.warning("暗影抑制药水效果命令执行失败: %s" % command)

        except Exception as e:
            logger.error("OnProjectileHitBlock error: %s" % str(e))

    def EruptionDamageDelay(self, eid, damage_multiplier=1.0):
        """暗影爆发球伤害延迟"""
        cmd_comp = SCF.CreateCommand(levelId)
        damage_command = "/execute as @s at @s run damage @s {} entity_attack entity @s"
        cmd_comp.SetCommand(damage_command.format(int(30 * damage_multiplier)), eid)
    @EventListener("PlayerIntendLeaveServerEvent")
    def OnPlayerLeave(self, args):
        """玩家离开世界时重置暗影能量"""
        player_id = args.playerId
        logger.info("玩家 %s 离开世界，重置暗影能量" % player_id)
        self.shadowSystemPlayer(player_id, "set", 0)

    @EventListener("PlayerJoinMessageEvent")
    def OnPlayerJoin(self, args):
        """玩家进入世界时初始化暗影能量为0"""
        player_id = args.id
        logger.info("玩家 %s 进入世界，初始化暗影能量为0" % player_id)
        self.shadowSystemPlayer(player_id, "set", 0)

    @EventListener("PlayerDieEvent")
    def OnPlayerDie(self, args):
        """玩家死亡时重置暗影能量为0"""
        player_id = args.id
        logger.info("玩家 %s 死亡，重置暗影能量为0" % player_id)
        self.shadowSystemPlayer(player_id, "set", 0)

    @EventListener("PlayerRespawnFinishServerEvent")
    def OnPlayerRespawn(self, args):
        """玩家重生完毕后初始化暗影能量为0"""
        player_id = args.playerId
        logger.info("玩家 %s 重生完毕，初始化暗影能量为0" % player_id)
        self.shadowSystemPlayer(player_id, "set", 0)

    @EventListener("CustomCommandTriggerServerEvent")
    def OnShadowSystemCommand(self, args):
        """
        处理 /shadow_system 自定义命令
        用法: /shadow_system <目标选择器> <能量值0-100>
        """
        try:
            command_name = args.command
            logger.info("收到自定义命令: %s" % command_name)
            if command_name != "shadow_system":
                return

            # 获取命令参数
            command_args = args.args
            logger.info("命令参数: %s" % str(command_args))
            if not command_args or len(command_args) < 2:
                args.return_failed = True
                args.return_msg_key = "用法: /shadow_system <目标> <能量值(0-100)>"
                return

            # 解析目标选择器 - target类型参数返回的是实体ID列表
            target_arg = command_args[0]
            target_value = target_arg.get("value", [])
            logger.info("目标选择器参数: name=%s, type=%s, value=%s" % (target_arg.get("name"), target_arg.get("type"), target_value))
            
            # target类型参数返回的是实体ID列表（可能是list或tuple）
            if isinstance(target_value, (list, tuple)):
                target_entities = list(target_value)
            elif isinstance(target_value, str):
                # 如果是字符串，可能是单个实体ID
                target_entities = [target_value]
            else:
                args.return_failed = True
                args.return_msg_key = "无效的目标选择器"
                return

            logger.info("解析后的目标实体列表: %s" % target_entities)
            if not target_entities:
                args.return_failed = True
                args.return_msg_key = "未找到目标实体"
                return

            # 解析能量值
            energy_arg = command_args[1]
            energy_value = energy_arg.get("value", 0)
            logger.info("能量值参数: name=%s, type=%s, value=%s" % (energy_arg.get("name"), energy_arg.get("type"), energy_value))
            if not isinstance(energy_value, int) or energy_value < 0 or energy_value > 100:
                args.return_failed = True
                args.return_msg_key = "能量值必须在0-100之间"
                return

            # 获取玩家列表用于判断
            player_list = serverApi.GetPlayerList()
            logger.info("当前玩家列表: %s" % player_list)

            # 处理每个目标实体
            success_count = 0
            for entity_id in target_entities:
                # target类型返回的是实体ID字符串列表
                if not entity_id:
                    continue

                logger.info("处理目标实体: %s" % entity_id)

                # 计算新的能量状态
                new_ratio = 1.0 - (energy_value / 100.0)
                new_state = {
                    "shadow_data": energy_value,
                    "clip_ratio": new_ratio,
                    "is_full": (energy_value >= 100)
                }

                # 判断是玩家还是实体
                if entity_id in player_list:
                    # 玩家：使用 shadowSystemPlayer 方法设置能量
                    logger.info("目标 %s 是玩家，使用 shadowSystemPlayer 设置能量" % entity_id)
                    self.shadowSystemPlayer(entity_id, "set", energy_value)
                    logger.info("玩家 %s 的暗影能量设置为 %s" % (entity_id, energy_value))
                    # 检查暗影形态
                    self.checkPlayerBerserkMode(entity_id, energy_value)
                else:
                    # 实体：检查标识符是否符合条件
                    entity_id_str = str(entity_id)
                    logger.info("目标 %s 是实体" % entity_id_str)
                    
                    # 获取实体标识符
                    entity_identifier = self.getEntityIdentifier(entity_id)
                    
                    # 排除抛射物实体
                    if entity_identifier and "projectile" in entity_identifier:
                        logger.info("实体 %s 标识符为 %s，是抛射物，跳过" % (entity_id_str, entity_identifier))
                        success_count += 1
                        continue
                    
                    # 只为符合sf:开头且不包含trader的实体处理
                    if entity_identifier and entity_identifier.startswith("sf:") and "trader" not in entity_identifier:
                        logger.info("实体 %s 标识符为 %s，符合条件" % (entity_id_str, entity_identifier))
                        
                        # 如果实体没有UI，先为其创建UI
                        if entity_id_str not in self.entity_shadow_states:
                            logger.info("实体 %s 没有头顶UI，正在创建..." % entity_id_str)
                            # 初始化状态
                            self.entity_shadow_states[entity_id_str] = new_state.copy()
                            # 通知客户端绑定UI
                            self.NotifyClientToBindUI(entity_id)
                        else:
                            # 更新状态并广播
                            self.setEntityShadowState(entity_id, new_state)
                        
                        logger.info("实体 %s 的暗影能量设置为 %s" % (entity_id_str, energy_value))
                        
                        # 检查暗影形态（能量值变化时可能需要移除效果）
                        self.checkEntityBerserkMode(entity_id, energy_value)
                    else:
                        logger.info("实体 %s 标识符为 '%s'，不符合条件，跳过" % (entity_id_str, entity_identifier))

                success_count += 1

            if success_count > 0:
                args.return_failed = False
                args.return_msg_key = "成功设置 %s 个目标的暗影能量为 %s" % (success_count, energy_value)
                logger.info("命令执行成功: %s" % args.return_msg_key)
            else:
                args.return_failed = True
                args.return_msg_key = "未能设置任何目标的暗影能量"
                logger.info("命令执行失败: %s" % args.return_msg_key)

        except Exception as e:
            logger.error("OnShadowSystemCommand error: %s" % str(e))
            args.return_failed = True
            args.return_msg_key = "命令执行出错: %s" % str(e)