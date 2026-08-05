# -*- coding: utf-8 -*-

"""
怪物AI系统 - 基于通用技能状态树实现

使用 skill_state_tree.py 中的通用状态树架构，
通过不同的配置实现怪物的蓄力-施法逻辑。
"""

import mod.server.extraServerApi as serverApi
from mod_log import logger
from dn_script_shadow import config
from skill_state_tree import (
    SkillTreeManager,
    MonsterSkillExecutor,
    MAX_ENERGY,
    SKILL_ENERGY_COST
)

SCF = serverApi.GetEngineCompFactory()
levelId = serverApi.GetLevelId()


class MonsterAI:
    """怪物AI系统 - 基于通用技能状态树管理怪物状态流转
    
    使用通用状态树实现:
    1. 当能量值达到100后，进入 charge 状态（停止移动，播放蓄力特效）
    2. charge 持续60 ticks后，自动进入 cast 状态（消耗20能量，执行技能）
    3. 技能释放后进入 cooldown 状态，冷却完成后回到 idle
    
    状态流转:
        idle (能量<100) 
            -> charge (能量>=100, 停止移动, 60 ticks, 播放特效) 
            -> cast (消耗20能量, 执行技能) 
            -> cooldown (冷却120 ticks)
            -> idle
    """
    
    def __init__(self, subsystem):
        self.subsystem = subsystem
        self._state_trees = {}
    
    def _isEntityValid(self, entity_id):
        """检查实体是否有效"""
        try:
            defs_comp = SCF.CreateEntityDefinitions(entity_id)
            if not defs_comp:
                return False
            pos_comp = SCF.CreatePos(entity_id)
            if pos_comp:
                pos_comp.GetPos()
            return True
        except:
            return False
    
    def _getOrCreateStateTree(self, monster_id):
        """获取或创建怪物状态树"""
        monster_id_str = str(monster_id)
        if monster_id_str not in self._state_trees:
            config = {
                'get_energy': lambda eid: self.subsystem.getEntityShadowState(eid).get("shadow_data", 0),
                'max_energy': MAX_ENERGY,
                'charge_duration': 60,
                'cooldown_duration': 120,
                'on_charge_start': self._onChargeStart,
                'on_charge_tick': self._onChargeTick,
                'on_cast': self._onCast,
            }
            tree = SkillTreeManager(self.subsystem).createMonsterTree(monster_id_str, config)
            self._state_trees[monster_id_str] = tree
        return self._state_trees[monster_id_str]
    
    def _onChargeStart(self, monster_id, tree):
        """怪物进入蓄力状态 - 播放特效"""
        try:
            cmd_comp = SCF.CreateCommand(levelId)
            particle_cmd = "/particle sf:shadow_smoke ~~~"
            cmd_comp.SetCommand(particle_cmd, monster_id)
            
            target_player = tree.getContext('target_player')
            if target_player:
                title_cmd = "/title @a[r=20] actionbar §b§l===敌人正在蓄力强力技能，注意躲避！==="
                cmd_comp.SetCommand(title_cmd)
            
            logger.info("怪物 %s 开始蓄力，停止移动" % monster_id)
        except Exception as e:
            logger.error("_onChargeStart error: %s" % str(e))
    
    def _onChargeTick(self, monster_id, tree):
        """蓄力中的每20 ticks调用"""
        try:
            cmd_comp = SCF.CreateCommand(levelId)
            particle_cmd = "/particle sf:shadow_smoke ~~~"
            cmd_comp.SetCommand(particle_cmd, monster_id)
        except Exception as e:
            logger.error("_onChargeTick error: %s" % str(e))
    
    def _onCast(self, monster_id, tree):
        """怪物释放技能的回调"""
        try:
            # 消耗能量
            current_state = self.subsystem.getEntityShadowState(monster_id)
            monster_energy = current_state.get("shadow_data", 0)
            
            if monster_energy < SKILL_ENERGY_COST:
                logger.warning("怪物 %s 能量不足(%s)，无法释放技能" % (monster_id, monster_energy))
                return
            
            new_energy = monster_energy - SKILL_ENERGY_COST
            new_state = {
                "shadow_data": new_energy,
                "clip_ratio": 1.0 - (new_energy / 100.0),
                "is_full": (new_energy >= 100)
            }
            self.subsystem.setEntityShadowState(monster_id, new_state)
            logger.info("怪物 %s 消耗20能量，剩余能量 %s" % (monster_id, new_energy))
            
            # 选择并执行技能
            skill_id = MonsterSkillExecutor.selectRandomSkill()
            MonsterSkillExecutor.executeSkill(monster_id, skill_id)
            
        except Exception as e:
            logger.error("_onCast error: %s" % str(e))
    
    def update(self, dt):
        """每帧更新所有怪物的状态树，由Subsystem.onUpdate驱动"""
        if not self._state_trees:
            return
        dead_trees = []
        for monster_id, tree in self._state_trees.items():
            if not self._isEntityValid(monster_id):
                dead_trees.append(monster_id)
                continue
            try:
                tree.execute()
            except Exception as e:
                logger.error("状态树 execute 异常: monster_id=%s, error=%s" % (monster_id, str(e)))
                import traceback
                logger.error(traceback.format_exc())
        for mid in dead_trees:
            del self._state_trees[mid]
    
    def TryReleaseMonsterSkill(self, monster_id, target_player_id):
        """触发怪物技能检测
        
        由事件调用(如怪物攻击玩家时)，设置目标玩家并确保状态树存在。
        状态树的自动流转由update()每帧驱动。
        只处理 sf:man_unique_h 实体。
        """
        entity_identifier = self.subsystem.getEntityIdentifier(monster_id)
        if entity_identifier != "sf:man_unique_h":
            return
        
        try:
            tree = self._getOrCreateStateTree(monster_id)
            tree.setContext('target_player', target_player_id)
            
            current_state = self.subsystem.getEntityShadowState(monster_id)
            monster_energy = current_state.get("shadow_data", 0)
            
            if monster_energy >= MAX_ENERGY:
                logger.info("怪物 %s 能量已满(%s)，状态树已激活，等待蓄力倒计时" % (monster_id, monster_energy))
                    
        except Exception as e:
            logger.error("TryReleaseMonsterSkill error: %s" % str(e))
            import traceback
            logger.error(traceback.format_exc())
    
    def removeStateTree(self, monster_id):
        """移除指定怪物的状态树（怪物死亡时调用）"""
        monster_id_str = str(monster_id)
        if monster_id_str in self._state_trees:
            del self._state_trees[monster_id_str]
    
    def cleanupDeadEntities(self):
        """清理已死亡实体的状态树"""
        dead_ids = []
        for monster_id in self._state_trees:
            defs_comp = SCF.CreateEntityDefinitions(monster_id)
            if not defs_comp:
                dead_ids.append(monster_id)
        for mid in dead_ids:
            del self._state_trees[mid]