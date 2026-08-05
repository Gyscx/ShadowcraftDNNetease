# -*- coding: utf-8 -*-

"""
通用技能状态树 - 玩家和怪物共用同一套 StateTree 架构

状态流转：
    idle → charge → cast → cooldown → idle

玩家逻辑：能量 > 20 且按下技能键 → 跳过 charge 直接 cast
怪物逻辑：能量满 → 进入 charge 状态（播放蓝光特效，持续5秒）→ charge 结束后自动 cast

设计策略：
    - 非叶子节点作为守卫（策略一）：skill_ready 守卫节点控制是否进入技能流程
    - 上下文继承 + copy 复用（策略二）：通过 setContext 注入不同的触发策略和回调
    - copy(deep=True) 创建玩家/怪物变体，复用同一套状态节点
"""

import mod.server.extraServerApi as serverApi
from mod_log import logger
from dn_script_shadow.engine.architect.fsm.stateTree.common import StateTree, StateNode
from dn_script_shadow.engine.architect.fsm.stateTree.server import StateNodeServer

SCF = serverApi.GetEngineCompFactory()
levelId = serverApi.GetLevelId()

MONSTER_SKILL_IDS = ["helmet", "armor", "weapon", "RW"]
IDLE_FULL_TICKS = 60
SKILL_ENERGY_COST = 20
MAX_ENERGY = 100


# ============================================================
# 状态节点定义
# ============================================================

class IdleNode(StateNodeServer):
    """空闲状态 - 等待技能触发条件"""
    
    def __init__(self, name='idle', subsystem=None):
        StateNodeServer.__init__(self, name, subsystem)
    
    def canEnter(self, tree):
        return True
    
    def canExit(self, tree):
        """只有当触发条件满足时才允许退出 idle 状态"""
        trigger_fn = tree.getContext('check_trigger')
        if trigger_fn and trigger_fn(tree.entityId, tree):
            return True
        return False
    
    def enter(self, previous, tree):
        logger.info("[%s] 进入 idle 状态" % tree.entityId)
    
    def update(self, tree):
        trigger_fn = tree.getContext('check_trigger')
        if trigger_fn and trigger_fn(tree.entityId, tree):
            tree.finishTasks()


class ChargeNode(StateNodeServer):
    """蓄力状态 - 播放特效，持续指定时长"""
    
    def __init__(self, name='charge', subsystem=None):
        StateNodeServer.__init__(self, name, subsystem)
    
    def canEnter(self, tree):
        skip_charge = tree.getContext('should_skip_charge')
        if skip_charge and skip_charge(tree.entityId, tree):
            return False
        return True
    
    def enter(self, previous, tree):
        tree.setContext('charge_ticks', 0)
        self._playChargeEffect(tree)
        logger.info("[%s] 进入 charge 状态，开始蓄力" % tree.entityId)
    
    def update(self, tree):
        charge_ticks = tree.getContext('charge_ticks') or 0
        charge_ticks += 1
        tree.setContext('charge_ticks', charge_ticks)
        
        charge_duration = tree.getContext('charge_duration') or IDLE_FULL_TICKS
        
        if charge_ticks % 20 == 0:
            self._tickChargeEffect(tree)
        
        if charge_ticks >= charge_duration:
            tree.finishTasks()
    
    def canExit(self, tree):
        charge_ticks = tree.getContext('charge_ticks') or 0
        charge_duration = tree.getContext('charge_duration') or IDLE_FULL_TICKS
        return charge_ticks >= charge_duration
    
    def exit(self, nextNode, tree):
        self._stopChargeEffect(tree)
        logger.info("[%s] 蓄力完成(%s ticks)，退出 charge 状态" % (tree.entityId, tree.getContext('charge_ticks')))
    
    def _playChargeEffect(self, tree):
        effect_fn = tree.getContext('on_charge_start')
        if effect_fn:
            effect_fn(tree.entityId, tree)
    
    def _tickChargeEffect(self, tree):
        effect_fn = tree.getContext('on_charge_tick')
        if effect_fn:
            effect_fn(tree.entityId, tree)
    
    def _stopChargeEffect(self, tree):
        effect_fn = tree.getContext('on_charge_end')
        if effect_fn:
            effect_fn(tree.entityId, tree)


class CastNode(StateNodeServer):
    """施法状态 - 释放技能"""
    
    def __init__(self, name='cast', subsystem=None):
        StateNodeServer.__init__(self, name, subsystem)
        self._cast_done = False
    
    def canEnter(self, tree):
        return True
    
    def enter(self, previous, tree):
        self._cast_done = False
        cast_fn = tree.getContext('on_cast')
        if cast_fn:
            cast_fn(tree.entityId, tree)
        logger.info("[%s] 进入 cast 状态，释放技能" % tree.entityId)
    
    def update(self, tree):
        if not self._cast_done:
            self._cast_done = True
            tree.finishTasks()
    
    def exit(self, nextNode, tree):
        logger.info("[%s] 退出 cast 状态，准备进入 %s" % (tree.entityId, nextNode.name if nextNode else 'None'))


class CooldownNode(StateNodeServer):
    """冷却状态 - 技能冷却中"""
    
    def __init__(self, name='cooldown', subsystem=None):
        StateNodeServer.__init__(self, name, subsystem)
    
    def canEnter(self, tree):
        return True
    
    def enter(self, previous, tree):
        tree.setContext('cooldown_ticks', 0)
        logger.info("[%s] 进入 cooldown 状态" % tree.entityId)
    
    def update(self, tree):
        cooldown_ticks = tree.getContext('cooldown_ticks') or 0
        cooldown_ticks += 1
        tree.setContext('cooldown_ticks', cooldown_ticks)
        
        cooldown_duration = tree.getContext('cooldown_duration') or 60
        
        if cooldown_ticks >= cooldown_duration:
            tree.finishTasks()
    
    def canExit(self, tree):
        cooldown_ticks = tree.getContext('cooldown_ticks') or 0
        cooldown_duration = tree.getContext('cooldown_duration') or 60
        return cooldown_ticks >= cooldown_duration
    
    def exit(self, nextNode, tree):
        logger.info("[%s] 退出 cooldown 状态" % tree.entityId)


class SkillReadyGuardNode(StateNode):
    """技能就绪守卫节点 - 非叶子，控制是否进入技能流程"""
    
    def __init__(self, name='skill_ready'):
        StateNode.__init__(self, name)
    
    def canEnter(self, tree):
        check_fn = tree.getContext('check_skill_ready')
        if check_fn:
            return check_fn(tree.entityId, tree)
        return False


# ============================================================
# 状态树构建器
# ============================================================

class SkillStateTree(StateTree):
    """通用技能状态树 - 玩家和怪物共用
    
    树结构:
        root
        +-- idle          (空闲，等待触发)
        +-- skill_ready   (守卫节点：检查是否满足技能释放条件)
            +-- charge    (蓄力：播放特效，持续指定时长)
            +-- cast      (施法：释放技能)
        +-- cooldown      (冷却)
    
    玩家变体：通过 should_skip_charge=True 跳过 charge 节点
    怪物变体：通过 charge_duration 控制蓄力时长
    """
    
    def __init__(self, entityId, subsystem, config=None):
        StateTree.__init__(self, entityId)
        self.subsys = subsystem
        self._config = config or {}
        self._ctx = {}
        self._buildTree()
    
    def getContext(self, k):
        """获取上下文值"""
        value = self._ctx.get(k)
        if value is not None:
            return value
        return self.root.getContext(k)
    
    def setContext(self, k, v):
        """设置上下文值"""
        self._ctx[k] = v
    
    def _buildTree(self):
        root = self.getRoot()
        
        idle = IdleNode('idle', self.subsys)
        skill_ready = SkillReadyGuardNode('skill_ready')
        charge = ChargeNode('charge', self.subsys)
        cast = CastNode('cast', self.subsys)
        cooldown = CooldownNode('cooldown', self.subsys)
        
        root.addChildren(idle)
        root.addChildren(skill_ready)
        root.addChildren(cooldown)
        
        skill_ready.addChildren(charge)
        skill_ready.addChildren(cast)
        
        self._injectConfig()
    
    def _injectConfig(self):
        root = self.getRoot()
        
        root.setContext('check_trigger', self._config.get('check_trigger'))
        root.setContext('check_skill_ready', self._config.get('check_skill_ready'))
        root.setContext('should_skip_charge', self._config.get('should_skip_charge'))
        root.setContext('charge_duration', self._config.get('charge_duration', IDLE_FULL_TICKS))
        root.setContext('cooldown_duration', self._config.get('cooldown_duration', 60))
        root.setContext('on_charge_start', self._config.get('on_charge_start'))
        root.setContext('on_charge_tick', self._config.get('on_charge_tick'))
        root.setContext('on_charge_end', self._config.get('on_charge_end'))
        root.setContext('on_cast', self._config.get('on_cast'))
    
    def execute(self):
        self.stateTicks += 1
        if self._current:
            for node in self.findAllActivatedStateNodes():
                node.update(self)
        self._finished = True
        
        searchResult = self.searchNode()
        if searchResult is None:
            return
        
        finalNode, path = searchResult
        if finalNode is self._current:
            return
        
        for node in path:
            self.switchNode(node)


# ============================================================
# 怪物技能执行器
# ============================================================

class MonsterSkillExecutor:
    """怪物技能执行器 - 提供怪物技能释放的具体实现"""
    
    @staticmethod
    def executeSkill(monster_id, skill_id):
        """执行指定的怪物技能"""
        try:
            cmd_comp = SCF.CreateCommand(levelId)
            time_comp = SCF.CreateGame(levelId)
            
            if skill_id == "helmet":
                MonsterSkillExecutor._executeHelmetSkill(monster_id, cmd_comp, time_comp)
            elif skill_id == "armor":
                MonsterSkillExecutor._executeArmorSkill(monster_id, cmd_comp, time_comp)
            elif skill_id == "weapon":
                MonsterSkillExecutor._executeWeaponSkill(monster_id, cmd_comp, time_comp)
            elif skill_id == "RW":
                MonsterSkillExecutor._executeRWSkill(monster_id, cmd_comp, time_comp)
            
            logger.info("怪物 %s 释放技能 %s" % (monster_id, skill_id))
        
        except Exception as e:
            logger.error("MonsterSkillExecutor.executeSkill error: %s" % str(e))
    
    @staticmethod
    def selectRandomSkill():
        import random
        return random.choice(MONSTER_SKILL_IDS)
    
    @staticmethod
    def _executeHelmetSkill(monster_id, cmd_comp, time_comp):
        pos_comp = SCF.CreatePos(monster_id)
        rot_comp = SCF.CreateRot(monster_id)
        if pos_comp and rot_comp:
            monster_pos = pos_comp.GetFootPos()
            monster_rot = rot_comp.GetRot()
            if monster_pos and monster_rot:
                dir_x, dir_y, dir_z = serverApi.GetDirFromRot(monster_rot)
                spawn_pos = (monster_pos[0], monster_pos[1] + 1.5, monster_pos[2])
                direction = (dir_x, dir_y, dir_z)
                param = {
                    "position": spawn_pos,
                    "direction": direction,
                    "power": 1.5,
                    "gravity": 0.0
                }
                projectile_comp = SCF.CreateProjectile(levelId)
                projectile_comp.CreateProjectileEntity(monster_id, "sf:shadowball_eruption", param)
        cmd_list = [
            "/playsound shadow.ability.eruption @e[r=5,type=player]",
            "/playanimation @s animation.player.eruption"
        ]
        for cmd in cmd_list:
            cmd_comp.SetCommand(cmd, monster_id)
    
    @staticmethod
    def _executeArmorSkill(monster_id, cmd_comp, time_comp):
        cmd_list = [
            "/playsound shadow.ability.blast @e[r=5,type=player]",
            "/playanimation @s animation.player.blast",
            "/camerashake add @e[r=5,type=player] 2 0.1",
            "/execute as @s at @s run particle sf:blast",
            "/execute as @s at @s run damage @e[r=3,type=player] 5 entity_attack entity @s"
        ]
        for idx, cmd in enumerate(cmd_list):
            cmd_comp.SetCommand(cmd, monster_id)
            if idx == len(cmd_list) - 1:
                time_comp.AddTimer(0.5, lambda tid=monster_id: MonsterSkillExecutor._monsterAoeDamage(tid, 3))
    
    @staticmethod
    def _executeWeaponSkill(monster_id, cmd_comp, time_comp):
        cmd_list = [
            "/playsound shadow.ability.shadow_onslaught @e[r=5,type=player]",
            "/playanimation @s animation.player.shadow_onslaught"
        ]
        MonsterSkillExecutor._monsterMotion(monster_id, 3.0)
        time_comp.AddTimer(1.0, lambda mid=monster_id: MonsterSkillExecutor._monsterMotion(mid, -1.0))
        for cmd in cmd_list:
            cmd_comp.SetCommand(cmd, monster_id)
        for i in range(8):
            time_comp.AddTimer(i * 0.15, lambda tid=monster_id, rid=5: MonsterSkillExecutor._monsterAoeDamage(tid, rid))
    
    @staticmethod
    def _executeRWSkill(monster_id, cmd_comp, time_comp):
        cmd_list = [
            "/playsound shadow.ability.shadow_blast @e[r=5,type=player]",
            "/playanimation @s animation.player.shadow_blast.particle",
            "/playanimation @s animation.player.shadow_blast"
        ]
        for cmd in cmd_list:
            cmd_comp.SetCommand(cmd, monster_id)
        
        def delayCommands():
            command_list = [
                "execute as @s at @s positioned ^ ^ ^8 run damage @e[r=3] {} entity_attack entity @s",
                "execute as @s at @s positioned ^ ^ ^7.5 run damage @e[r=3] {} entity_attack entity @s",
                "execute as @s at @s positioned ^ ^ ^7 run damage @e[r=3] {} entity_attack entity @s",
                "execute as @s at @s positioned ^ ^ ^6.5 run damage @e[r=3] {} entity_attack entity @s",
                "execute as @s at @s positioned ^ ^ ^6 run damage @e[r=3] {} entity_attack entity @s",
                "execute as @s at @s positioned ^ ^ ^5.5 run damage @e[r=3] {} entity_attack entity @s",
                "execute as @s at @s positioned ^ ^ ^5 run damage @e[r=3] {} entity_attack entity @s",
                "execute as @s at @s positioned ^ ^ ^4.5 run damage @e[r=3] {} entity_attack entity @s",
                "execute as @s at @s positioned ^ ^ ^4 run damage @e[r=3] {} entity_attack entity @s",
                "execute as @s at @s positioned ^ ^ ^3.5 run damage @e[r=3] {} entity_attack entity @s",
                "execute as @s at @s positioned ^ ^ ^3 run damage @e[r=3] {} entity_attack entity @s",
                "execute as @s at @s positioned ^ ^ ^2.5 run damage @e[r=3] {} entity_attack entity @s",
                "execute as @s at @s positioned ^ ^ ^2 run damage @e[r=3] {} entity_attack entity @s",
                "execute as @s at @s positioned ^ ^ ^1.5 run damage @e[r=3] {} entity_attack entity @s",
                "execute as @s at @s positioned ^ ^ ^1 run damage @e[r=3] {} entity_attack entity @s",
                "execute as @s at @s positioned ^ ^ ^0.5 run damage @e[r=3] {} entity_attack entity @s"
            ]
            for delay_command in command_list:
                cmd_comp.SetCommand(delay_command.format(5, monster_id))
        
        time_comp.AddTimer(1.0, delayCommands)
    
    @staticmethod
    def _monsterMotion(monster_id, motion_size):
        try:
            motion_comp = SCF.CreateActorMotion(monster_id)
            rot_comp = SCF.CreateRot(monster_id)
            if rot_comp:
                monster_rot = rot_comp.GetRot()
                if monster_rot:
                    dir_x, dir_y, dir_z = serverApi.GetDirFromRot(monster_rot)
                    motion_comp.SetPlayerMotion((dir_x * motion_size, 0, dir_z * motion_size))
        except Exception as e:
            logger.error("_monsterMotion error: %s" % str(e))
    
    @staticmethod
    def _monsterAoeDamage(monster_id, radius):
        try:
            cmd_comp = SCF.CreateCommand(levelId)
            damage_cmd = "/execute as @s at @s run damage @e[r={},type=player] 5 entity_attack entity @s".format(radius)
            cmd_comp.SetCommand(damage_cmd, monster_id)
            logger.info("怪物 %s AOE伤害，半径%s" % (monster_id, radius))
        except Exception as e:
            logger.error("_monsterAoeDamage error: %s" % str(e))


# ============================================================
# 工厂函数 - 创建玩家/怪物状态树
# ============================================================

def createPlayerSkillTree(entityId, subsystem, config_overrides=None):
    """创建玩家技能状态树
    
    玩家逻辑：能量 > 20 且按下技能键 → 跳过 charge 直接 cast
    """
    def check_player_trigger(entity_id, tree):
        energy_fn = config_overrides.get('get_energy') if config_overrides else None
        input_fn = config_overrides.get('check_skill_key') if config_overrides else None
        
        if not energy_fn or not input_fn:
            return False
        
        energy = energy_fn(entity_id)
        skill_key_pressed = input_fn(entity_id)
        
        return energy > 20 and skill_key_pressed
    
    def check_player_skill_ready(entity_id, tree):
        return check_player_trigger(entity_id, tree)
    
    def player_skip_charge(entity_id, tree):
        return True
    
    base_config = {
        'check_trigger': check_player_trigger,
        'check_skill_ready': check_player_skill_ready,
        'should_skip_charge': player_skip_charge,
        'cooldown_duration': 60,
    }
    
    if config_overrides:
        base_config.update(config_overrides)
    
    tree = SkillStateTree(entityId, subsystem, base_config)
    return tree


def createMonsterSkillTree(entityId, subsystem, config_overrides=None):
    """创建怪物技能状态树
    
    怪物逻辑：能量满 → 进入 charge 状态（播放特效）→ charge 结束后自动 cast
    """
    def check_monster_trigger(entity_id, tree):
        energy_fn = config_overrides.get('get_energy') if config_overrides else None
        if not energy_fn:
            return False
        
        energy = energy_fn(entity_id)
        max_energy = config_overrides.get('max_energy', MAX_ENERGY)
        
        return energy >= max_energy
    
    def check_monster_skill_ready(entity_id, tree):
        return check_monster_trigger(entity_id, tree)
    
    def monster_skip_charge(entity_id, tree):
        return False
    
    base_config = {
        'check_trigger': check_monster_trigger,
        'check_skill_ready': check_monster_skill_ready,
        'should_skip_charge': monster_skip_charge,
        'charge_duration': IDLE_FULL_TICKS,
        'cooldown_duration': 120,
    }
    
    if config_overrides:
        base_config.update(config_overrides)
    
    tree = SkillStateTree(entityId, subsystem, base_config)
    return tree


# ============================================================
# 管理器
# ============================================================

class SkillTreeManager:
    """技能状态树管理器 - 管理多个实体的状态树"""
    
    def __init__(self, subsystem):
        self.subsystem = subsystem
        self._trees = {}
    
    def createPlayerTree(self, player_id, config=None):
        tree = createPlayerSkillTree(player_id, self.subsystem, config)
        self._trees[player_id] = tree
        return tree
    
    def createMonsterTree(self, monster_id, config=None):
        tree = createMonsterSkillTree(monster_id, self.subsystem, config)
        self._trees[monster_id] = tree
        return tree
    
    def getTree(self, entity_id):
        return self._trees.get(entity_id)
    
    def updateAll(self, dt=1):
        for tree in self._trees.values():
            tree.execute()
    
    def removeTree(self, entity_id):
        if entity_id in self._trees:
            del self._trees[entity_id]