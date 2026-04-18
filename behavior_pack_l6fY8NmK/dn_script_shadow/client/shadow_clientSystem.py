# -*- coding: utf-8 -*-
import mod.client.extraClientApi as clientApi
from .. import config
from mod_log import logger

from ..architect.subsystem import ClientSubsystem, SubsystemClient
from ..architect.event import EventListener
from ..architect.event.core import ChainedEvent

CS = clientApi.GetClientSystemCls()
CCF = clientApi.GetEngineCompFactory()
levelId = clientApi.GetLevelId()
notify_comp = CCF.CreateTextNotifyClient(levelId)
config_comp = CCF.CreateConfigClient(levelId)
damage_shadow = -0.15
attack_shadow = -1
playerId = clientApi.GetLocalPlayerId()

@SubsystemClient
class ShadowClientSystem(ClientSubsystem):
    def onInit(self):
        logger.info("=====Shadow Client System Init (Dynamic Skills) =====")
        self.canTick = True
        # 初始化技能冷却时间字典
        self.skill_cooldowns = {}
        for skill in config.SKILL_CONFIGS:
            self.skill_cooldowns[skill["skill_id"]] = 0.0
        self.RegisterCustomKey()

    def RegisterCustomKey(self):
        """动态注册所有技能按键"""
        levelId = clientApi.GetLevelId()
        playerViewComp = clientApi.GetEngineCompFactory().CreatePlayerView(levelId)
        for skill in config.SKILL_CONFIGS:
            playerViewComp.RegisterCustomKeyMapping(
                skill["key_mapping_name"],
                skill["default_key"],
                "shadow_ability"
            )

    def GetSkillConfig(self, skill_id):
        """根据技能ID获取配置"""
        for skill in config.SKILL_CONFIGS:
            if skill["skill_id"] == skill_id:
                return skill
        return None

    def GetMatchedItemConfig(self, skill_id, player_id=None):
        """根据技能ID和玩家当前装备，获取匹配的物品配置"""
        if player_id is None:
            player_id = clientApi.GetLocalPlayerId()
        skill_cfg = self.GetSkillConfig(skill_id)
        if not skill_cfg or "valid_items" not in skill_cfg:
            return None
        item_comp = clientApi.GetEngineCompFactory().CreateItem(player_id)
        for item_config in skill_cfg["valid_items"]:
            item_identifier = item_config["item_identifier"]
            slot_type = item_config["item_slot_type"]
            if slot_type == "armor":
                # 检查盔甲栏
                armor_pos = clientApi.GetMinecraftEnum().ItemPosType.ARMOR
                for slot in range(4):
                    item_dict = item_comp.GetPlayerItem(armor_pos, slot)
                    if item_dict and item_dict.get('itemName') == item_identifier:
                        # 返回匹配到的具体物品配置
                        return item_config
            elif slot_type == "hotbar":
                # 检查快捷栏指定槽位
                inv_pos = clientApi.GetMinecraftEnum().ItemPosType.INVENTORY
                slot = item_config.get("hotbar_slot", -1)
                if 0 <= slot <= 8:
                    item_dict = item_comp.GetPlayerItem(inv_pos, slot)
                    if item_dict and item_dict.get('itemName') == item_identifier:
                        return item_config
        return None

    def CheckItemForSkill(self, skill_cfg):
        """检查玩家是否持有技能所需物品（适配新结构）"""
        # 此方法可能需要调整，因为现在skill_cfg可能不直接包含item_identifier
        # 建议改为调用 GetMatchedItemConfig
        matched = self.GetMatchedItemConfig(skill_cfg["skill_id"])
        return matched is not None

    @EventListener(config.OnKeyPressInGame)
    def OnKeyPressInGame(self, args):
        """处理按键按下事件"""
        if args.isDown != "1":
            return
        key = int(args.key)
        ui_node = clientApi.GetUI(config.ModName, config.shadowUIName)
        if not ui_node:
            return
        # 确保UI控件已初始化
        if not hasattr(ui_node, 'mShadowAbility'):
            return
        ability_ctrl = ui_node.GetBaseUIControl(ui_node.mShadowAbility)
        if not ability_ctrl or not ability_ctrl.GetVisible():
            return
        # 获取按键映射组件
        levelId = clientApi.GetLevelId()
        playerViewComp = clientApi.GetEngineCompFactory().CreatePlayerView(levelId)
        # 遍历所有技能配置，检查按键匹配
        for skill_cfg in config.SKILL_CONFIGS:
            mapped_key = playerViewComp.GetKeyMappings(skill_cfg["key_mapping_name"])
            if key == mapped_key and self.CheckItemForSkill(skill_cfg):
                # 触发技能
                if self.TriggerSkillAbility(skill_cfg["skill_id"]):
                    ui_node.StartCooldown(skill_cfg["skill_id"])
                break

    def TriggerSkillAbility(self, skill_id):
        """处理玩家释放技能相关逻辑"""
        skill_cfg = self.GetSkillConfig(skill_id)
        if not skill_cfg:
            return False
        ui_node = clientApi.GetUI(config.ModName, config.shadowUIName)
        if not ui_node or not hasattr(ui_node, 'ConsumeShadowForAbility'):
            return False
        # 检查冷却
        if self.skill_cooldowns.get(skill_id, 0.0) > 0.0:
            return False
        # 获取当前匹配的物品配置
        matched_item_config = self.GetMatchedItemConfig(skill_id)
        if not matched_item_config:
            return False  # 没有穿戴任何有效的物品
        # 消耗能量
        if ui_node.ConsumeShadowForAbility(skill_cfg["energy_cost"]):
            if skill_id == "RW" and matched_item_config["item_identifier"] == "minecraft:arrow":
                render_comp = clientApi.GetEngineCompFactory().CreateActorRender(playerId)
                render_comp.AddPlayerGeometry("default", "geometry.dn.player.custom")
                render_comp.AddPlayerParticleEffect("shadow_blast","sf:shadow_blast")
                render_comp.RebuildPlayerRender()
                time_comp = clientApi.GetEngineCompFactory().CreateGame(levelId)
                time_comp.AddTimer(2.0, self.ResetPlayerGeo)

            # 通知服务器，并传递具体物品标识符
            self.sendServer(config.ServerSkillEvent,{
                "skill": skill_id,
                "playerId": clientApi.GetLocalPlayerId(),
                "itemIdentifier": matched_item_config["item_identifier"]  # 新增
            })
            # 设置冷却时间
            cooldown_duration = skill_cfg["cooldown"]
            self.skill_cooldowns[skill_id] = cooldown_duration
            if ui_node:
                ui_node.StartCooldown(skill_id, cooldown_duration)
            return True
        return False

    def ResetPlayerGeo(self):
        """重置玩家模型"""
        render_comp = clientApi.GetEngineCompFactory().CreateActorRender(playerId)
        render_comp.AddPlayerGeometry("default", "geometry.humanoid.custom")
        render_comp.RebuildPlayerRender()
        # notify_comp.SetLeftCornerNotify("已恢复原版模型")

    def onUpdate(self, dt):
        """每帧更新"""
        ui_node = clientApi.GetUI(config.ModName, config.shadowUIName)
        self.SendShadowMessage()
        if ui_node:
            # 减少冷却时间，并同步到UI
            delta = 0.05
            for skill_id in list(self.skill_cooldowns.keys()):
                if self.skill_cooldowns[skill_id] > 0.0:
                    new_time = max(0.0, self.skill_cooldowns[skill_id] - delta)
                    self.skill_cooldowns[skill_id] = new_time
                    # 关键同步：将新的冷却时间设置到UI的状态字典中
                    if skill_id in ui_node.skill_states:
                        ui_node.skill_states[skill_id]["cooldown_time"] = new_time
            # 更新UI冷却显示
            ui_node.UpdateCooldowns()
            # 更新所有技能按钮状态
            for skill_cfg in config.SKILL_CONFIGS:
                skill_id = skill_cfg["skill_id"]
                has_item = self.CheckItemForSkill(skill_cfg)
                cooldown_left = self.skill_cooldowns.get(skill_id, 0.0)
                # 冷却结束后恢复默认状态
                if cooldown_left <= 0.0:
                    ui_node.UpdateSkillButtonState(skill_id, has_item)

    @EventListener(config.UiInitFinishedEvent)
    def OnUIInitFinished(self, args):
        """UI初始化完成"""
        print "Client: UI init finished, initializing shadow data..."
        shadowEnergyData = config_comp.GetConfigData("dn_shadow_energy")
        if not shadowEnergyData:
            shadowEnergyData = {
                "is_full": False,
                "clip_ratio": 1.0,
                "shadow_data": 0
            }
            print "Client: No existing data found, initialized with defaults:", shadowEnergyData
        else:
            print "Client: Loaded existing data:", shadowEnergyData
            if shadowEnergyData.get("shadow_data", 0) >= 100:
                shadowEnergyData["is_full"] = True
                shadowEnergyData["clip_ratio"] = 0.0
            else:
                shadowEnergyData["is_full"] = False
                shadowEnergyData["clip_ratio"] = 1.0 - (shadowEnergyData.get("shadow_data", 0) / 100.0)
            print "Client: State corrected after loading:", shadowEnergyData
        config_comp.SetConfigData("dn_shadow_energy", shadowEnergyData)
        # 注册并创建UI
        clientApi.RegisterUI(config.ModName, config.shadowUIName, config.shadowUIPyClsPath, config.shadowUIScreenDef)
        self.mshadowUINode = clientApi.CreateUI(config.ModName, config.shadowUIName, {"isHud": 1})
        self.mshadowUINode = clientApi.GetUI(config.ModName, config.shadowUIName)
        if self.mshadowUINode:
            self.mshadowUINode.UpdateShadow(shadowEnergyData["clip_ratio"])
            self.mshadowUINode.Init()
            print "Client: Data initialized and UI synced successfully."
        else:
            logger.error("create ui %s failed!" % config.shadowUIScreenDef)

    @EventListener(config.ClientItemTryUseEvent)
    def OnClientItemTryUse(self, args):
        """客户端尝试使用物品时触发，处理暗影能量的使用与消耗"""
        itemDict = args.itemDict
        if itemDict.get("itemName") != "minecraft:stone_sword":
            return
        playerId = args.playerId  # 从事件参数获取玩家ID
        # 获取当前暗影能量数据
        current_data = config_comp.GetConfigData("dn_shadow_energy")
        if not current_data:
            current_data = {"clip_ratio": 1.0, "shadow_data": 0, "is_full": False}
        current_energy = current_data.get("shadow_data", 0)
        # 能量已满：取消使用，物品不消耗
        if current_energy >= 100:
            args.cancel = True
            notify_comp.SetLeftCornerNotify("暗影能量已满，无法使用该物品")
            return
        # 能量未满：取消原始事件，通知服务端处理物品消耗和能量增加
        args.cancel = True
        self.sendServer(config.ClientUseShadowEnergyEvent, {"playerId": playerId})

    @EventListener(config.AddShadowEnergyEvent, isCustomEvent=True)
    def OnAddShadowEnergy(self, args):
        """增加暗影能量（服务端通知）"""
        amount = args.amount
        # 获取当前能量数据
        current_data = config_comp.GetConfigData("dn_shadow_energy")
        if not current_data:
            current_data = {"clip_ratio": 1.0, "shadow_data": 0, "is_full": False}
        current_energy = current_data.get("shadow_data", 0)
        new_energy = current_energy + amount
        if new_energy > 100:
            new_energy = 100
        new_ratio = 1.0 - (new_energy / 100.0)
        # 更新数据
        current_data["shadow_data"] = new_energy
        current_data["clip_ratio"] = new_ratio
        current_data["is_full"] = (new_energy >= 100)
        config_comp.SetConfigData("dn_shadow_energy", current_data)
        # 更新UI
        ui_node = clientApi.GetUI(config.ModName, config.shadowUIName)
        if ui_node:
            ui_node.UpdateShadow(new_ratio)

    @EventListener(config.DamageEvent, isCustomEvent=True)
    def OnDamageEvent(self, args):
        """客户端玩家受伤事件"""
        entityId = args.entityId
        if entityId in clientApi.GetPlayerList():
            print("客户端-玩家已受伤")
            # 获取当前数据（包含 is_full 字段）
            current_data = config_comp.GetConfigData("dn_shadow_energy")
            if not current_data:
                current_data = {"clip_ratio": 1.0, "shadow_data": 0, "is_full": False}
            current_ratio = current_data.get("clip_ratio", 1.0)
            new_ratio = current_ratio + damage_shadow
            if new_ratio < 0.0:
                new_ratio = 0.0
            # 可选：限制上限，避免能量超过100时无法正常触发
            if new_ratio > 1.0:
                new_ratio = 1.0
            new_shadow_data = int(round(100 * (1 - new_ratio)))
            # 直接修改原字典，保留 is_full
            current_data["clip_ratio"] = new_ratio
            current_data["shadow_data"] = new_shadow_data
            config_comp.SetConfigData("dn_shadow_energy", current_data)
            print("客户端-受伤后数据更新: %s" % current_data)
            ui_node = clientApi.GetUI(config.ModName, config.shadowUIName)
            if ui_node:
                ui_node.UpdateShadow(new_ratio)

    @EventListener(config.PlayerAttackEntityEvent, isCustomEvent=True)
    def OnPlayerAttackEvent(self, args):
        """客户端玩家攻击事件"""
        playerId = args.playerId
        print playerId
        if playerId in clientApi.GetPlayerList():
            print("客户端-玩家已攻击")
            current_data = config_comp.GetConfigData("dn_shadow_energy") or {"clip_ratio": 1.0, "shadow_data": 0, "is_full": False}
            current_ratio = current_data.get("clip_ratio", 1.0)
            # 根据实际逻辑调整加减方向
            new_ratio = current_ratio + attack_shadow  # 若攻击应消耗能量，请改为减法
            if new_ratio < 0.0:
                new_ratio = 0.0
            if new_ratio > 1.0:
                new_ratio = 1.0
            new_shadow_data = int(round(100 * (1 - new_ratio)))
            current_data["clip_ratio"] = new_ratio
            current_data["shadow_data"] = new_shadow_data
            config_comp.SetConfigData("dn_shadow_energy", current_data)
            print("客户端-攻击后数据更新: %s" % current_data)
            ui_node = clientApi.GetUI(config.ModName, config.shadowUIName)
            if ui_node:
                ui_node.UpdateShadow(new_ratio)

    def SendShadowMessage(self):
        """获取当前暗影能量数据（当前无实际功能，但保留调用）"""
        shadow_config = config_comp.GetConfigData("dn_shadow_energy")
        # 此方法目前无实际操作，但保留以维持原有调用结构
        pass