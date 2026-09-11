# -*- coding: utf-8 -*-

"""
怪物AI系统 - 利用API仇恨目标+内置寻路，代码控制技能释放

核心思路：
1. 使用 SetAttackTarget API 设置仇恨目标，白嫖内置寻路系统
2. 怪物自动追踪目标，当距离足够近时触发技能释放
3. 技能释放由代码控制，使用状态树管理蓄力-施法流程
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
    """怪物AI系统 - 利用API仇恨目标+内置寻路，代码控制技能释放
    
    工作流程:
    1. 每帧检测 sf:man_unique_h 附近20格内的实体
    2. 有实体时调用 SetAttackTarget，让怪物自动寻路追踪
    3. 无实体时调用 ResetAttackTarget，清除仇恨
    4. 当怪物接近目标且能量满时，触发技能状态树
    5. 技能状态树控制蓄力-施法-冷却流程
    
    状态流转:
        idle (追踪目标，能量<100) 
            -> charge (能量>=100, 停止移动, 60 ticks, 播放特效) 
            -> cast (消耗20能量, 执行技能) 
            -> cooldown (冷却120 ticks, 继续追踪)
            -> idle
    """
    
    def __init__(self, subsystem):
        self.subsystem = subsystem
        self._state_trees = {}
        self._monster_targets = {}
        self._registered_monsters = set()
        self._last_entity_count = 0
        self._scan_counter = 0
    
    def _isEntityValid(self, entity_id):
        """检查实体是否有效"""
        try:
            defs_comp = SCF.CreateEntityDefinitions(entity_id)
            if not defs_comp:
                return False
            pos_comp = SCF.CreatePos(entity_id)
            if not pos_comp:
                return False
            pos = pos_comp.GetPos()
            if not pos:
                return False
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
        """怪物进入蓄力状态 - 停止移动，播放特效"""
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
            
            skill_id = MonsterSkillExecutor.selectRandomSkill()
            MonsterSkillExecutor.executeSkill(monster_id, skill_id)
            
        except Exception as e:
            logger.error("_onCast error: %s" % str(e))
    
    def update(self, dt):
        """每帧更新所有怪物的状态树，由Subsystem.onUpdate驱动"""
        if not hasattr(self, '_update_log_counter'):
            self._update_log_counter = 0
        self._update_log_counter += 1
        
        if self._update_log_counter % 100 == 1:
            logger.info("[怪物AI] update 被调用, _state_trees数量: %d, _scan_counter: %d" % (len(self._state_trees), self._scan_counter))
        
        self._updateMonsterAttackTargets()
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
    
    def _updateMonsterAttackTargets(self):
        """检测sf:man_unique_h附近20格内的实体，设置或清除仇恨目标
        
        使用 SetAttackTarget API 设置仇恨目标，让怪物自动使用内置寻路系统追踪目标。
        当范围内无实体时，调用 ResetAttackTarget 清除仇恨目标。
        """
        try:
            from dn_script_shadow.engine.architect.math.utilsServer import around
            from dn_script_shadow.engine.architect.core.basic import Location
            from dn_script_shadow.engine.architect.level.server import LevelServer
            import math
            
            self._scan_counter += 1
            
            if self._scan_counter % 60 == 0:
                logger.info("[怪物AI] 开始扫描实体, _scan_counter: %d" % self._scan_counter)
                try:
                    from dn_script_shadow.engine.architect.math.utilsServer import around
                    from dn_script_shadow.engine.architect.core.basic import Location
                    
                    player_list = serverApi.GetPlayerList()
                    logger.info("[怪物AI] 当前玩家数量: %d" % len(player_list))
                    
                    new_monsters_found = []
                    
                    for player_id in player_list:
                        player_id_str = str(player_id)
                        pos_comp = SCF.CreatePos(player_id)
                        dim_comp = SCF.CreateDimension(player_id)
                        
                        if not pos_comp or not dim_comp:
                            continue
                        
                        player_pos = pos_comp.GetFootPos()
                        if not player_pos:
                            continue
                        
                        dim_id = dim_comp.GetEntityDimensionId()
                        loc = Location(player_pos, dim_id)
                        
                        nearby_entities = around(loc, 100)
                        logger.info("[怪物AI] 玩家 %s 附近100格找到 %d 个实体" % (player_id_str, len(nearby_entities)))
                        
                        for entity_id in nearby_entities:
                            entity_id_str = str(entity_id)
                            
                            if entity_id_str in self._registered_monsters:
                                continue
                            
                            entity_identifier = self.subsystem.getEntityIdentifier(entity_id_str)
                            
                            if entity_identifier != "sf:man_unique_h":
                                continue
                            
                            if not self._isEntityValid(entity_id_str):
                                continue
                            
                            logger.info("[怪物AI] 扫描发现新怪物: %s (标识符: %s)" % (entity_id_str, entity_identifier))
                            self._registered_monsters.add(entity_id_str)
                            self._getOrCreateStateTree(entity_id_str)
                            new_monsters_found.append(entity_id_str)
                    
                    if new_monsters_found:
                        logger.info("[怪物AI] 本次扫描发现 %d 个新怪物" % len(new_monsters_found))
                    else:
                        logger.info("[怪物AI] 本次扫描未发现新怪物")
                        
                except Exception as scan_error:
                    logger.error("[怪物AI] 扫描实体失败: %s" % str(scan_error))
                    import traceback
                    logger.error(traceback.format_exc())
            
            if not self._state_trees:
                return
            
            for monster_id_str in list(self._state_trees.keys()):
                # 检查实体是否有效
                if not self._isEntityValid(monster_id_str):
                    if self._debug_frame_counter % 100 == 1:
                        logger.info("[怪物AI] 怪物 %s 无效（可能已死亡），从状态树中移除" % monster_id_str)
                    # 清理无效怪物
                    if monster_id_str in self._monster_targets:
                        del self._monster_targets[monster_id_str]
                    del self._state_trees[monster_id_str]
                    self._registered_monsters.discard(monster_id_str)
                    continue
                
                pos_comp = SCF.CreatePos(monster_id_str)
                if not pos_comp:
                    continue
                
                monster_pos = pos_comp.GetFootPos()
                if not monster_pos:
                    continue
                
                dim_comp = SCF.CreateDimension(monster_id_str)
                dim_id = dim_comp.GetEntityDimensionId() if dim_comp else 0
                
                loc = Location(monster_pos, dim_id)
                nearby_entities = around(loc, 20)
                
                # 只筛选玩家实体，并找到最近的一个
                nearest_target = None
                nearest_distance = float('inf')
                player_count = 0
                
                for entity_id in nearby_entities:
                    if entity_id == monster_id_str:
                        continue
                    if not self._isEntityValid(entity_id):
                        continue
                    
                    # 只处理玩家
                    entity_identifier = self.subsystem.getEntityIdentifier(entity_id)
                    if entity_identifier != "minecraft:player":
                        continue
                    
                    player_count += 1
                    
                    # 计算距离
                    target_pos_comp = SCF.CreatePos(entity_id)
                    if target_pos_comp:
                        target_pos = target_pos_comp.GetPos()
                        if target_pos:
                            dx = monster_pos[0] - target_pos[0]
                            dy = monster_pos[1] - target_pos[1]
                            dz = monster_pos[2] - target_pos[2]
                            distance = dx * dx + dy * dy + dz * dz
                            
                            if distance < nearest_distance:
                                nearest_distance = distance
                                nearest_target = entity_id
                
                if nearest_target:
                    old_target = self._monster_targets.get(monster_id_str)
                    self._monster_targets[monster_id_str] = nearest_target
                    
                    if old_target != nearest_target:
                        logger.info("[怪物AI] 怪物 %s 设置仇恨目标: %s (范围内%d个玩家，最近距离%.1f格)" % 
                                   (monster_id_str, nearest_target, player_count, nearest_distance ** 0.5))
                    
                    try:
                        action_comp = SCF.CreateAction(monster_id_str)
                        if action_comp:
                            action_comp.SetAttackTarget(nearest_target)
                        else:
                            logger.warning("[怪物AI] 怪物 %s CreateAction 返回 None，无法设置仇恨目标" % monster_id_str)
                    except Exception as e:
                        logger.error("[怪物AI] 设置仇恨目标失败: monster_id=%s, target_id=%s, error=%s" % (monster_id_str, nearest_target, str(e)))
                    
                    tree = self._state_trees.get(monster_id_str)
                    if tree:
                        tree.setContext('target_player', nearest_target)
                else:
                    had_target = monster_id_str in self._monster_targets
                    if had_target:
                        logger.info("[怪物AI] 怪物 %s 范围内无玩家，清除仇恨目标: %s" % (monster_id_str, self._monster_targets[monster_id_str]))
                        del self._monster_targets[monster_id_str]
                    
                        try:
                            action_comp = SCF.CreateAction(monster_id_str)
                            if action_comp:
                                action_comp.ResetAttackTarget()
                                logger.info("[怪物AI] 怪物 %s 成功调用 ResetAttackTarget" % monster_id_str)
                            else:
                                logger.warning("[怪物AI] 怪物 %s CreateAction 返回 None，无法清除仇恨目标" % monster_id_str)
                        except Exception as e:
                            logger.error("[怪物AI] 清除仇恨目标失败: monster_id=%s, error=%s" % (monster_id_str, str(e)))
                        
        except Exception as e:
            logger.error("[怪物AI] _updateMonsterAttackTargets error: %s" % str(e))
            import traceback
            logger.error(traceback.format_exc())
    
    def registerMonster(self, monster_id):
        """注册怪物到AI系统（由ServerSpawnMobEvent调用）"""
        monster_id_str = str(monster_id)
        
        if monster_id_str in self._registered_monsters:
            return
        
        entity_identifier = self.subsystem.getEntityIdentifier(monster_id_str)
        if entity_identifier != "sf:man_unique_h":
            return
        
        logger.info("[怪物AI] 注册新怪物: %s (标识符: %s)" % (monster_id_str, entity_identifier))
        self._registered_monsters.add(monster_id_str)
        self._getOrCreateStateTree(monster_id_str)
    
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
        if monster_id_str in self._monster_targets:
            del self._monster_targets[monster_id_str]
    
    def cleanupDeadEntities(self):
        """清理已死亡实体的状态树"""
        dead_ids = []
        for monster_id in self._state_trees:
            defs_comp = SCF.CreateEntityDefinitions(monster_id)
            if not defs_comp:
                dead_ids.append(monster_id)
        for mid in dead_ids:
            del self._state_trees[mid]