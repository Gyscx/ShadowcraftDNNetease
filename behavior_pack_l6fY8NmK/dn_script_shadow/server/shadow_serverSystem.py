# -*- coding: utf-8 -*-

import mod.server.extraServerApi as serverApi
from mod_log import logger
from dn_script_shadow import config

from dn_script_shadow.engine.architect.compact import ServerSubsystem, SubsystemServer
from dn_script_shadow.engine.architect.compact import EventListener, CustomEvent

from .modules import (
    ShadowEnergyManager,
    EffectSystem,
    ParticleSystem,
    MonsterAI,
    SkillSystem,
    EntityIdentifierManager
)

SS = serverApi.GetServerSystemCls()
SCF = serverApi.GetEngineCompFactory()
levelId = serverApi.GetLevelId()

energy_shadow = 8

@SubsystemServer
class ShadowServerSystem(ServerSubsystem):
    def onInit(self):
        print "===== Shadow Server System Init (Dynamic) ====="
        self.entity_shadow_states = {}
        self.entity_shadow_effects = {}
        self.player_shadow_effects = {}
        self.entity_identifiers = {}
        self.entity_particle_timers = {}
        self.player_suppression_timers = {}
        self.player_effect_durations = {}
        self.entity_effect_durations = {}
        self.player_skill_damage_multipliers = {}
        self.monster_attack_trees = {}
        self.player_energy_values = {}
        
        self.energy_manager = ShadowEnergyManager(self)
        self.effect_system = EffectSystem(self)
        self.particle_system = ParticleSystem(self)
        self.monster_ai = MonsterAI(self)
        self.skill_system = SkillSystem(self)
        self.entity_manager = EntityIdentifierManager(self)
        
        self.canTick = True
    
    def onUpdate(self, dt):
        self.monster_ai.update(dt)
        # logger.debug("ShadowServerSystem onUpdate called with dt: %s" % dt)
    
    def getEntityShadowState(self, entity_id):
        return self.energy_manager.getEntityShadowState(entity_id)

    def getEntityShadowEffect(self, entity_id):
        return self.energy_manager.getEntityShadowEffect(entity_id)

    def setEntityShadowState(self, entity_id, data):
        self.energy_manager.setEntityShadowState(entity_id, data)

    def SendShadowEnergyToEntity(self, entity_id, amount):
        self.energy_manager.SendShadowEnergyToEntity(entity_id, amount)

    def shadowSystemPlayer(self, player_id, operation, value=0):
        return self.energy_manager.shadowSystemPlayer(player_id, operation, value)

    def broadcastEntityShadowUpdate(self, entity_id, data):
        self.energy_manager.broadcastEntityShadowUpdate(entity_id, data)

    def applyShadowSuppression(self, entity_id):
        self.effect_system.applyShadowSuppression(entity_id)

    def applyShadowCharging(self, entity_id):
        self.effect_system.applyShadowCharging(entity_id)

    def removeShadowEffect(self, entity_id):
        self.effect_system.removeShadowEffect(entity_id)

    def applyPlayerShadowSuppression(self, player_id):
        self.effect_system.applyPlayerShadowSuppression(player_id)

    def applyPlayerShadowCharging(self, player_id):
        self.effect_system.applyPlayerShadowCharging(player_id)

    def removePlayerShadowEffect(self, player_id):
        self.effect_system.removePlayerShadowEffect(player_id)

    def checkEntityBerserkMode(self, entity_id, energy_value):
        self.effect_system.checkEntityBerserkMode(entity_id, energy_value)

    def startEntityParticleTimer(self, entity_id_str):
        self.particle_system.startEntityParticleTimer(entity_id_str)

    def stopEntityParticleTimer(self, entity_id_str):
        self.particle_system.stopEntityParticleTimer(entity_id_str)

    def playEntityParticle(self, entity_id_str):
        self.particle_system.playEntityParticle(entity_id_str)

    def _particleTimerCallback(self, entity_id_str):
        self.particle_system._particleTimerCallback(entity_id_str)

    def _getOrCreateMonsterAttackTree(self, monster_id):
        return self.monster_ai._getOrCreateMonsterAttackTree(monster_id)

    def _playMonsterPrepareEffect(self, monster_id, skill_id):
        self.monster_ai._playMonsterPrepareEffect(monster_id, skill_id)

    def TryReleaseMonsterSkill(self, monster_id, target_player_id):
        self.monster_ai.TryReleaseMonsterSkill(monster_id, target_player_id)

    def _monsterAoeDamage(self, monster_id, radius):
        self.monster_ai._monsterAoeDamage(monster_id, radius)

    def GetSkillConfig(self, skill_id):
        return self.skill_system.GetSkillConfig(skill_id)

    def GetSkillLevel(self, player_id, skill_id):
        return self.skill_system.GetSkillLevel(player_id, skill_id)

    def SetSkillLevel(self, player_id, skill_id, level):
        self.skill_system.SetSkillLevel(player_id, skill_id, level)

    def SyncSkillLevelsToPlayer(self, player_id):
        self.skill_system.SyncSkillLevelsToPlayer(player_id)

    def getUpgradeInfo(self, skill_id, current_level):
        return self.skill_system.getUpgradeInfo(skill_id, current_level)

    def consumeFragments(self, player_id, count):
        return self.skill_system.consumeFragments(player_id, count)

    def ProcessSkillUpgrade(self, player_id, skill_id, fragment_cost, current_level):
        return self.skill_system.ProcessSkillUpgrade(player_id, skill_id, fragment_cost, current_level)

    def getEntityIdentifier(self, entity_id):
        return self.entity_manager.getEntityIdentifier(entity_id)

    def NotifyClientToBindUI(self, entity_id):
        self.entity_manager.NotifyClientToBindUI(entity_id)

    def _delayedBindNotify(self, player_id, entity_id, event_data):
        self.entity_manager._delayedBindNotify(player_id, entity_id, event_data)

    def _removeEffectAndNotify(self, entity_id, effect_name):
        cmd_comp = SCF.CreateCommand(serverApi.GetLevelId())
        remove_effect_cmd = "/effect @s clear %s" % effect_name
        cmd_comp.SetCommand(remove_effect_cmd, str(entity_id))
        logger.info("[药剂冷却] 移除玩家 %s 的 %s 效果" % (entity_id, effect_name))

    @CustomEvent(config.ClientUseShadowEnergyEvent)
    def OnClientUseShadowEnergy(self, args):
        # print "222"
        playerId = args.playerId
        print playerId
        if not playerId:
            return

        player_id_str = str(playerId)
        if self.player_shadow_effects.get(player_id_str) == "suppression":
            logger.info("[暗影能量物品] 玩家 %s 处于暗影抑制状态，无法使用物品增加能量" % playerId)
            cmd_comp = SCF.CreateCommand(levelId)
            title_cmd = "/title @s actionbar §c你处于暗影抑制状态，无法增加能量！"
            cmd_comp.SetCommand(title_cmd, player_id_str)
            return

        item_comp = serverApi.GetEngineCompFactory().CreateItem(playerId)
        selectedSlot = item_comp.GetSelectSlotId()
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
        self.shadowSystemPlayer(playerId, "add", energy_shadow)
        # print "333"

    @EventListener(config.DamageEvent)
    def OnDamageEvent(self, args):
        entityId = args.entityId
        player_list = serverApi.GetPlayerList()
        if entityId in player_list:
            print "服务端-玩家已受伤"
            # print args.dict()
            # print entityId
            self.sendClient(entityId, config.DamageEvent, args.dict())

    @EventListener(config.PlayerAttackEntityEvent)
    def OnPlayerAttackEvent(self, args):
        playerId = args.playerId
        player_list = serverApi.GetPlayerList()
        print "服务端-玩家已攻击"
        # print args.dict()
        # print playerId

    @CustomEvent(config.ClientUpgradeSkillEvent)
    def OnClientUpgradeSkill(self, args):
        skill_id = args.skill_id
        player_id = args.playerId

        if not skill_id or not player_id:
            return

        current_level = self.GetSkillLevel(player_id, skill_id)
        if current_level >= 5:
            return

        next_level = current_level + 1

        upgrade_info = self.getUpgradeInfo(skill_id, current_level)
        if not upgrade_info:
            return

        fragment_cost = upgrade_info.get("fragment_cost", 0)

        self.ProcessSkillUpgrade(player_id, skill_id, fragment_cost, current_level)

    @CustomEvent(config.ServerUpgradeSkillEvent)
    def OnServerUpgradeSkill(self, args):
        skill_id = args.skill_id
        player_id = args.playerId
        fragment_cost = args.fragment_cost

        if not skill_id or not player_id:
            return

        current_level = self.GetSkillLevel(player_id, skill_id)
        if current_level >= 5:
            return

        self.ProcessSkillUpgrade(player_id, skill_id, fragment_cost, current_level)

    @CustomEvent(config.RequestSkillLevelsEvent)
    def OnRequestSkillLevels(self, args):
        player_id = args.playerId
        if not player_id:
            return

        skill_levels = {}
        for skill in config.SKILL_CONFIGS:
            skill_id = skill["skill_id"]
            level = self.GetSkillLevel(player_id, skill_id)
            skill_levels[skill_id] = level

        self.sendClient(player_id, config.SyncSkillLevelsEvent, {
            "skill_levels": skill_levels
        })

    @EventListener("ClientLoadAddonsFinishServerEvent")
    def OnPlayerJoin(self, args):
        print "玩家已加入游戏"
        player_id = args.playerId
        if player_id:
            player_id_str = str(player_id)
            time_comp = SCF.CreateGame(levelId)
            time_comp.AddTimer(3.0, lambda: self._resetPlayerEnergy(player_id_str))
            time_comp.AddTimer(4.0, lambda: self.SyncSkillLevelsToPlayer(player_id))
    
    def _resetPlayerEnergy(self, player_id_str):
        cmd_comp = SCF.CreateCommand(levelId)
        cmd_comp.SetCommand("/shadow_system @s 0", player_id_str)
        logger.info("玩家 %s 加入游戏，延迟3秒后使用指令重置能量为0" % player_id_str)

    @EventListener("PlayerDieEvent")
    def OnPlayerDie(self, args):
        player_id = args.id
        if player_id:
            player_id_str = str(player_id)
            cmd_comp = SCF.CreateCommand(levelId)
            cmd_comp.SetCommand("/shadow_system @s 0", player_id_str)
            logger.info("玩家 %s 死亡，使用指令重置能量为0" % player_id_str)

    @EventListener("PlayerRespawnFinishServerEvent")
    def OnPlayerRespawnFinish(self, args):
        player_id = args.playerId
        if player_id:
            player_id_str = str(player_id)
            cmd_comp = SCF.CreateCommand(levelId)
            cmd_comp.SetCommand("/shadow_system @s 0", player_id_str)
            logger.info("玩家 %s 复活完毕，使用指令重置能量为0" % player_id_str)

    @CustomEvent(config.ServerSkillEvent)
    def OnSkillEvent(self, args):
        try:
            skill_id = args.skill
            player_id = args.playerId
            item_identifier_used = args.itemIdentifier
            damage_multiplier = args.damageMultiplier 
            cmd_comp = SCF.CreateCommand(levelId)
            time_comp = SCF.CreateGame(levelId) 
            def Juhedao():
                PlayerMotion(2.0)
                time_comp.AddTimer(0.1, WindmillDelayDamage)
                time_comp.AddTimer(0.2, WindmillDelayDamage)
                time_comp.AddTimer(0.3, WindmillDelayDamage)
                time_comp.AddTimer(0.4, WindmillDelayDamage)
            def PlayerMotion(motion_size):
                motion_comp = SCF.CreateActorMotion(player_id)
                rot_comp = SCF.CreateRot(player_id)
                if rot_comp:
                    player_rot = rot_comp.GetRot()
                    if player_rot:
                        dir_x, dir_y, dir_z = serverApi.GetDirFromRot(player_rot)
                        motion_comp.SetPlayerMotion((dir_x * motion_size, 0, dir_z * motion_size))
            def ShadowOnslaughtDelayDamage():
                damage_command = "/execute as @s at @s run damage @e[r=2,type=!player] {} entity_attack entity @s".format(int(30 * damage_multiplier))
                cmd_comp.SetCommand(damage_command, player_id)
            def WindmillDelayDamage():
                damage_command = "/execute as @s at @s run damage @e[r=2,type=!player] {} entity_attack entity @s".format(int(5 * damage_multiplier))
                cmd_comp.SetCommand(damage_command, player_id)
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

            energy_cost = skill_cfg.get("energy_cost", 0)
            
            player_id_str = str(player_id)
            current_energy = self.player_energy_values.get(player_id_str, 0)
            if current_energy < energy_cost:
                logger.warning("玩家 %s 能量不足，无法释放技能 %s" % (player_id_str, skill_id))
                return
            
            self.shadowSystemPlayer(player_id_str, "reduce", energy_cost)

            commands_to_execute = []
            if item_identifier_used and "valid_items" in skill_cfg:
                for item_config in skill_cfg["valid_items"]:
                    if item_config["item_identifier"] == item_identifier_used:
                        commands_to_execute = item_config.get("server_commands", [])
                        break

            if not commands_to_execute and skill_cfg.get("valid_items"):
                commands_to_execute = skill_cfg["valid_items"][0].get("server_commands", [])

            for command in commands_to_execute:
                cmd_comp.SetCommand(command, player_id)
            if skill_id == "weapon" and item_identifier_used == "sf:world_slicer":
                PlayerMotion(2.0)
                time_comp.AddTimer(1.0, lambda: PlayerMotion(-1.0))
                time_comp.AddTimer(1.0, ShadowOnslaughtDelayDamage)
            if skill_id == "weapon" and (item_identifier_used == "sf:purple_peeler" or item_identifier_used == "sf:fates_end"):
                Juhedao()
            if skill_id == "RW" and item_identifier_used == "minecraft:arrow":
                time_comp.AddTimer(1.0, DelayCommand)
            if skill_id == "armor" and item_identifier_used == "sf:burden_of_loneliness":
                damage_command = "/execute as @s at @s run damage @e[r=3,type=!player] {} entity_attack entity @s".format(int(30 * damage_multiplier))
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
        try:
            entity_id = args.entityId
            identifier = args.identifier
            entity_id_str = str(entity_id)

            self.entity_identifiers[entity_id_str] = identifier
            logger.info("实体 %s 生成，标识符: %s" % (entity_id_str, identifier))

            if identifier.startswith("sf:") and "trader" not in identifier:
                initial_state = {
                    "shadow_data": 0,
                    "clip_ratio": 1.0,
                    "is_full": False
                }

                if entity_id_str not in self.entity_shadow_states:
                    self.entity_shadow_states[entity_id_str] = initial_state.copy()

                    self.broadcastEntityShadowUpdate(entity_id_str, initial_state)

                    logger.info("新实体 %s 初始化，暗影能量: 0" % entity_id_str)

                    self.NotifyClientToBindUI(entity_id)
                else:
                    logger.warning("实体 %s 已存在，跳过重复初始化" % entity_id_str)
            else:
                logger.info("实体 %s 不是 sf: 开头，跳过UI创建" % identifier)

        except Exception as e:
            logger.error("OnServerSpawnMob error: %s" % str(e))

    @EventListener("DamageEvent")
    def OnEntityHurtEvent(self, args):
        try:
            hurt_entity_id = args.entityId
            attacker_id = args.srcId
            projectile_id = args.projectileId

            if not hurt_entity_id or not attacker_id:
                logger.warning("OnEntityHurtEvent: 无效的事件参数")
                return

            if projectile_id:
                projectile_identifier = self.getEntityIdentifier(projectile_id)
                if projectile_identifier == "sf:shadow_dampener_splash_potion_projectile":
                    logger.info("抛射物 %s 对实体 %s 造成伤害，跳过增加能量" % (projectile_id, hurt_entity_id))
                    return

            player_list = serverApi.GetPlayerList()
            if attacker_id in player_list:
                if hurt_entity_id not in player_list:
                    entity_identifier = self.getEntityIdentifier(hurt_entity_id)
                    if entity_identifier and entity_identifier.startswith("sf:") and "trader" not in entity_identifier:
                        logger.info("玩家 %s 攻击实体 %s (标识符: %s)，玩家和实体都获得暗影能量" % (attacker_id, hurt_entity_id, entity_identifier))
                        add_result = self.shadowSystemPlayer(attacker_id, "add", 3)
                        if add_result is False:
                            cmd_comp = SCF.CreateCommand(levelId)
                            title_cmd = "/title @s actionbar §c你处于暗影抑制状态，无法增加能量！"
                            cmd_comp.SetCommand(title_cmd, str(attacker_id))
                        self.SendShadowEnergyToEntity(hurt_entity_id, 10)
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
        try:
            hurt_player_id = args.id
            attacker_id = args.attacker

            if not hurt_player_id or not attacker_id:
                return

            player_list = serverApi.GetPlayerList()
            if attacker_id not in player_list:
                entity_identifier = self.getEntityIdentifier(attacker_id)
                if entity_identifier and entity_identifier.startswith("sf:") and "trader" not in entity_identifier:
                    logger.info("玩家 %s 被实体 %s (标识符: %s) 攻击，玩家和实体都获得暗影能量" % (hurt_player_id, attacker_id, entity_identifier))
                    add_result = self.shadowSystemPlayer(hurt_player_id, "add", 10)
                    if add_result is False:
                        cmd_comp = SCF.CreateCommand(levelId)
                        title_cmd = "/title @s actionbar §c你处于暗影抑制状态，无法增加能量！"
                        cmd_comp.SetCommand(title_cmd, str(hurt_player_id))
                    self.SendShadowEnergyToEntity(attacker_id, 3)
                    self.NotifyClientToBindUI(attacker_id)
                    self.monster_ai.TryReleaseMonsterSkill(attacker_id, hurt_player_id)
                else:
                    logger.info("玩家 %s 被实体 %s 攻击，但标识符不符合条件，跳过UI绑定" % (hurt_player_id, attacker_id))

        except Exception as e:
            logger.error("PlayerHurtEvent error: %s" % str(e))

    @CustomEvent(config.RequestEntityShadowDataEvent)
    def OnRequestEntityShadowData(self, args):
        entity_id = args.entityId
        player_id = args.playerId

        if not entity_id or not player_id:
            return

        entity_data = self.getEntityShadowState(entity_id)

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
            player_id_str = str(entityId)
            
            if effectName == "sf:shadow_dampener_effect":
                logger.info("玩家 %s 应用暗影抑制效果" % entityId)

                if self.player_shadow_effects.get(player_id_str) == "berserk":
                    logger.info("[抑制剂] 玩家 %s 处于暗影形态，喝下暗影抑制剂，停止暗影形态" % entityId)

                    if player_id_str in self.player_shadow_effects:
                        del self.player_shadow_effects[player_id_str]
                        logger.info("[抑制剂] 清除玩家 %s 的暗影形态标记" % entityId)

                self.player_shadow_effects[player_id_str] = "suppression"
                logger.info("[抑制剂] 玩家 %s 进入暗影抑制状态" % entityId)

                if not hasattr(self, 'player_energy_values'):
                    self.player_energy_values = {}
                self.player_energy_values[player_id_str] = 0

                self.sendClient(entityId, config.SetPlayerShadowEnergyEvent, {
                    "energy_value": 0
                })
                logger.info("[抑制剂] 同步玩家 %s 能量值为0给客户端" % entityId)

                cmd_comp = SCF.CreateCommand(levelId)
                strength_command = "/effect @s strength 60 4 false"
                cmd_comp.SetCommand(strength_command, player_id_str)
                logger.info("[抑制剂] 为玩家 %s 施加强量5效果，持续60秒" % entityId)

                self.sendClient(entityId, config.PlayerShadowEffectEvent, {
                    "clip_ratio": 1.0,
                    "shadow_data": 0,
                    "is_full": False,
                    "effect": "suppression"
                })
                logger.info("[抑制剂] 通知客户端玩家 %s 进入抑制状态" % entityId)
                
            elif effectName == "sf:shadow_overcharger_effect":
                if self.player_shadow_effects.get(player_id_str) == "suppression":
                    logger.info("[充能药剂] 玩家 %s 处于暗影抑制状态，无法应用充能效果" % entityId)
                    cmd_comp = SCF.CreateCommand(levelId)
                    clear_charging_cmd = "/title @s actionbar §c你处于暗影抑制状态，无法充能！"
                    cmd_comp.SetCommand(clear_charging_cmd, player_id_str)
                    return

                if self.player_shadow_effects.get(player_id_str) == "suppression":
                    logger.info("玩家 %s 移除暗影抑制效果" % entityId)
                self.player_shadow_effects[player_id_str] = "charging"
                self.sendClient(entityId, config.PlayerShadowEffectEvent, {
                    "clip_ratio": 0.0,
                    "shadow_data": 100,
                    "is_full": True,
                    "effect": "charging"
                })
                logger.info("玩家 %s 应用暗影充能效果" % entityId)

                if not hasattr(self, 'player_energy_values'):
                    self.player_energy_values = {}
                self.player_energy_values[str(entityId)] = 100
                logger.info("[充能药剂] 设置玩家 %s 能量值为100" % entityId)

                self.sendClient(entityId, config.SetPlayerShadowEnergyEvent, {
                    "energy_value": 100
                })
                logger.info("[充能药剂] 同步玩家 %s 能量值100给客户端配置" % entityId)
        else:
            entity_id_str = str(entityId)
            if effectName == "sf:shadow_dampener_effect":
                cmd_comp = SCF.CreateCommand(levelId)
                
                clear_effects_command = "/effect @s clear"
                cmd_comp.SetCommand(clear_effects_command, entity_id_str)
                logger.info("实体 %s 被喷洒抑制药水，清除所有效果" % entity_id_str)
                
                if self.entity_shadow_effects.get(entity_id_str, {}).get("effect") == "berserk":
                    logger.info("实体 %s 被喷洒抑制药水，清除暗影形态标记" % entity_id_str)
                if entity_id_str in self.entity_shadow_effects:
                    del self.entity_shadow_effects[entity_id_str]
                
                self.particle_system.stopEntityParticleTimer(entity_id_str)
                
                self.entity_shadow_effects[entity_id_str] = {"effect": "suppression"}
                self.broadcastEntityShadowUpdate(entity_id_str, {
                    "shadow_data": 0,
                    "clip_ratio": 1.0,
                    "is_full": False,
                    "effect": "suppression"
                })
                logger.info("实体 %s 应用暗影抑制效果，已清除所有效果和粒子" % entity_id_str)
            elif effectName == "sf:shadow_overcharger_effect":
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

    @EventListener("RemoveEffectServerEvent")
    def OnEffectRemoved(self, args):
        logger.info("RemoveEffectServerEvent")
        entityId = args.entityId
        effectName = args.effectName
        player_list = serverApi.GetPlayerList()

        if entityId in player_list:
            self.removePlayerShadowEffect(entityId)
        else:
            self.removeShadowEffect(entityId)

    @EventListener("RefreshEffectServerEvent")
    def OnEffectRefreshed(self, args):
        entityId = args.entityId
        effectName = args.effectName
        player_list = serverApi.GetPlayerList()

        if entityId in player_list:
            player_id_str = str(entityId)
            if self.player_shadow_effects.get(player_id_str) == "berserk":
                return

            if effectName not in ["sf:shadow_dampener_effect", "sf:shadow_overcharger_effect"]:
                return

            if effectName == "sf:shadow_dampener_effect":
                self.applyPlayerShadowSuppression(entityId)
                logger.info("玩家 %s 刷新暗影抑制效果，应用抑制效果" % entityId)
            elif effectName == "sf:shadow_overcharger_effect":
                if self.player_shadow_effects.get(player_id_str) == "suppression":
                    logger.info("[充能药剂] 玩家 %s 处于暗影抑制状态，无法刷新充能效果" % entityId)
                    cmd_comp = SCF.CreateCommand(levelId)
                    title_cmd = "/title @s actionbar §c你处于暗影抑制状态，无法充能！"
                    cmd_comp.SetCommand(title_cmd, player_id_str)
                    return
                self.applyPlayerShadowCharging(entityId)
                logger.info("玩家 %s 刷新暗影充能效果，应用充能效果" % entityId)
        else:
            entity_id_str = str(entityId)

            if effectName not in ["sf:shadow_dampener_effect", "sf:shadow_overcharger_effect"]:
                return

            if effectName == "sf:shadow_dampener_effect":
                self.applyShadowSuppression(entityId)
                logger.info("实体 %s 刷新暗影抑制效果，应用抑制效果" % entityId)
            elif effectName == "sf:shadow_overcharger_effect":
                self.applyShadowCharging(entityId)
                logger.info("实体 %s 刷新暗影充能效果，应用充能效果" % entityId)

    @EventListener("ProjectileDoHitEffectEvent")
    def OnProjectileHitBlock(self, args):
        try:
            projectile_id = args.id
            target_id = args.targetId
            hit_position = (args.x, args.y, args.z)

            if not projectile_id:
                return

            projectile_identifier = self.getEntityIdentifier(projectile_id)

            if projectile_identifier == "sf:shadow_dampener_splash_potion_projectile":
                logger.info("暗影抑制药水抛射物 %s 在位置 %s 碰撞，应用抑制效果" % (projectile_id, hit_position))
                
                cmd_comp = SCF.CreateCommand(levelId)
                
                aoe_effect_command = "/shadow_system @e[r=5,type=!player] 0"
                cmd_comp.SetCommand(aoe_effect_command, projectile_id)
                
                time_comp = SCF.CreateGame(levelId)
                time_comp.AddTimer(0.1, lambda pid=projectile_id: self._removeProjectile(pid))
                
            elif projectile_identifier == "sf:shadowball_eruption":
                logger.info("暗影爆发球抛射物 %s 在位置 %s 碰撞，触发爆炸" % (projectile_id, hit_position))
                
                cmd_comp = SCF.CreateCommand(levelId)
                
                time_comp = SCF.CreateGame(levelId)
                
                if target_id:
                    self._applyEruptionEffectToNearbyEntities(target_id)
                    time_comp.AddTimer(0.5, lambda tid=target_id: self._executeEruptionDamage(tid))
                else:
                    time_comp.AddTimer(3.0, lambda pid=projectile_id: self._removeProjectile(pid))
                
        except Exception as e:
            logger.error("OnProjectileHitBlock error: %s" % str(e))

    def _applyEruptionEffectToNearbyEntities(self, target_id):
        try:
            target_id_str = str(target_id)
            
            player_list = serverApi.GetPlayerList()
            if target_id in player_list:
                logger.info("目标实体 %s 是玩家，跳过爆发效果" % target_id_str)
                return
            
            motion_comp = SCF.CreateActorMotion(target_id)
            if motion_comp:
                motion_comp.SetMotion((0, 0.8, 0))
                logger.info("实体 %s 被击飞，施加向上向量" % target_id_str)
            
            particle_cmd1 = "/execute at @s run particle sf:eruption1 ~ ~ ~"
            particle_cmd2 = "/execute at @s run particle sf:eruption2 ~ ~ ~"
            cmd_comp = SCF.CreateCommand(levelId)
            cmd_comp.SetCommand(particle_cmd1, target_id_str)
            cmd_comp.SetCommand(particle_cmd2, target_id_str)
            logger.info("实体 %s 播放粒子效果" % target_id_str)
            
        except Exception as e:
            logger.error("_applyEruptionEffectToNearbyEntities error: %s" % str(e))

    def _executeEruptionDamage(self, target_id):
        try:
            cmd_comp = SCF.CreateCommand(levelId)
            damage_command = "/execute as @s at @s run damage @s 30 entity_attack entity @s"
            cmd_comp.SetCommand(damage_command, target_id)
            logger.info("对实体 %s 执行爆发伤害" % target_id)
        except Exception as e:
            logger.error("_executeEruptionDamage error: %s" % str(e))

    def _removeProjectile(self, projectile_id):
        try:
            cmd_comp = SCF.CreateCommand(levelId)
            remove_command = "/kill @s"
            cmd_comp.SetCommand(remove_command, projectile_id)
            logger.info("抛射物 %s 已移除" % projectile_id)
        except Exception as e:
            logger.error("_removeProjectile error: %s" % str(e))

    @EventListener("CustomCommandTriggerServerEvent")
    def OnShadowSystemCommand(self, args):
        try:
            if args.command != "shadow_system":
                return

            command_args = args.args
            logger.info("shadow_system 命令参数: %s" % str(command_args))
            if not command_args or len(command_args) < 2:
                args.return_failed = True
                args.return_msg_key = "用法: /shadow_system <目标> <能量值(0-100)>"
                return

            target_arg = command_args[0]
            target_value = target_arg.get("value", [])
            logger.info("目标选择器参数: name=%s, type=%s, value=%s" % (target_arg.get("name"), target_arg.get("type"), target_value))
            
            if isinstance(target_value, (list, tuple)):
                target_entities = list(target_value)
            elif isinstance(target_value, str):
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

            energy_arg = command_args[1]
            energy_value = energy_arg.get("value", 0)
            logger.info("能量值参数: name=%s, type=%s, value=%s" % (energy_arg.get("name"), energy_arg.get("type"), energy_value))
            if not isinstance(energy_value, int) or energy_value < 0 or energy_value > 100:
                args.return_failed = True
                args.return_msg_key = "能量值必须在0-100之间"
                return

            player_list = serverApi.GetPlayerList()
            logger.info("当前玩家列表: %s" % player_list)

            success_count = 0
            for entity_id in target_entities:
                if not entity_id:
                    continue

                entity_id_str = str(entity_id)
                logger.info("处理目标实体: %s (类型: %s)" % (entity_id, type(entity_id)))

                new_ratio = 1.0 - (energy_value / 100.0)
                new_state = {
                    "shadow_data": energy_value,
                    "clip_ratio": new_ratio,
                    "is_full": (energy_value >= 100)
                }

                is_player = False
                for pid in player_list:
                    if str(pid) == entity_id_str:
                        is_player = True
                        break

                if is_player:
                    logger.info("目标 %s 是玩家，使用 shadowSystemPlayer 设置能量" % entity_id_str)
                    result = self.shadowSystemPlayer(entity_id_str, "set", energy_value)
                    logger.info("玩家 %s 的暗影能量设置结果: %s" % (entity_id_str, result))
                else:
                    logger.info("目标 %s 是实体" % entity_id_str)
                    
                    entity_identifier = self.getEntityIdentifier(entity_id)
                    
                    if entity_identifier and "projectile" in entity_identifier:
                        logger.info("实体 %s 标识符为 %s，是抛射物，跳过" % (entity_id_str, entity_identifier))
                        success_count += 1
                        continue
                    
                    if entity_identifier and entity_identifier.startswith("sf:") and "trader" not in entity_identifier:
                        logger.info("实体 %s 标识符为 %s，符合条件" % (entity_id_str, entity_identifier))
                        
                        if entity_id_str not in self.entity_shadow_states:
                            logger.info("实体 %s 没有头顶UI，正在创建..." % entity_id_str)
                            self.entity_shadow_states[entity_id_str] = new_state.copy()
                            self.NotifyClientToBindUI(entity_id)
                        else:
                            self.setEntityShadowState(entity_id, new_state)
                        
                        logger.info("实体 %s 的暗影能量设置为 %s" % (entity_id_str, energy_value))
                        
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