# -*- coding: utf-8 -*-

import mod.server.extraServerApi as serverApi
from mod_log import logger

SCF = serverApi.GetEngineCompFactory()
levelId = serverApi.GetLevelId()


class ParticleSystem:
    """粒子效果系统 - 负责实体的粒子效果播放和定时器管理"""
    
    def __init__(self, subsystem):
        self.subsystem = subsystem
    
    def startEntityParticleTimer(self, entity_id_str):
        """启动实体粒子效果定时器"""
        try:
            if entity_id_str in self.subsystem.entity_particle_timers:
                self.stopEntityParticleTimer(entity_id_str)
            
            self.playEntityParticle(entity_id_str)
            
            time_comp = SCF.CreateGame(levelId)
            timer_id = time_comp.AddTimer(1.0, lambda eid=entity_id_str: self._particleTimerCallback(eid))
            self.subsystem.entity_particle_timers[entity_id_str] = timer_id
            
            logger.info("实体 %s 粒子效果定时器已启动" % entity_id_str)
            
        except Exception as e:
            logger.error("startEntityParticleTimer error: %s" % str(e))

    def stopEntityParticleTimer(self, entity_id_str):
        """停止实体粒子效果定时器"""
        try:
            logger.info("[停止粒子定时器] 尝试停止实体 %s 的粒子定时器" % entity_id_str)
            logger.info("[停止粒子定时器] 当前活跃的粒子定时器: %s" % str(self.subsystem.entity_particle_timers.keys()))
            if entity_id_str in self.subsystem.entity_particle_timers:
                timer_id = self.subsystem.entity_particle_timers[entity_id_str]
                time_comp = SCF.CreateGame(levelId)
                time_comp.CancelTimer(timer_id)
                del self.subsystem.entity_particle_timers[entity_id_str]
                logger.info("实体 %s 粒子效果定时器已停止" % entity_id_str)
            else:
                logger.info("[停止粒子定时器] 实体 %s 没有活跃的粒子定时器" % entity_id_str)
            
        except Exception as e:
            logger.error("stopEntityParticleTimer error: %s" % str(e))

    def _particleTimerCallback(self, entity_id_str):
        """粒子定时器回调函数"""
        try:
            if self.subsystem.entity_shadow_effects.get(entity_id_str, {}).get("effect") == "berserk":
                self.playEntityParticle(entity_id_str)
                time_comp = SCF.CreateGame(levelId)
                timer_id = time_comp.AddTimer(1.0, lambda eid=entity_id_str: self._particleTimerCallback(eid))
                self.subsystem.entity_particle_timers[entity_id_str] = timer_id
            else:
                self.stopEntityParticleTimer(entity_id_str)
                
        except Exception as e:
            logger.error("_particleTimerCallback error: %s" % str(e))

    def playEntityParticle(self, entity_id_str):
        """为实体播放粒子效果"""
        try:
            particle_command = "/execute at @s run particle sf:shadow_smoke ~ ~ ~ "
            
            cmd_comp = SCF.CreateCommand(levelId)
            cmd_comp.SetCommand(particle_command, entity_id_str)
            
        except Exception as e:
            logger.error("playEntityParticle error: %s" % str(e))