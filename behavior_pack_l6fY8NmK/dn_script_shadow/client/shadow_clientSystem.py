# -*- coding: utf-8 -*-
import mod.client.extraClientApi as clientApi
from .. import config
from mod_log import logger

from ..architect.compact import ClientSubsystem, SubsystemClient
from ..architect.compact import EventListener, ChainedEvent

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
    # 在ShadowClientSystem类的__init__方法中添加实体数据存储
    def onInit(self):
        logger.info("=====Shadow Client System Init (Dynamic Skills) =====")
        self.canTick = True
        # 初始化技能冷却时间字典
        self.skill_cooldowns = {}
        for skill in config.SKILL_CONFIGS:
            self.skill_cooldowns[skill["skill_id"]] = 0.0
        self.RegisterCustomKey()
        self.skill_levels = {}  # skill_id -> level
        self.loadSkillLevels()

        # +++ 新增：实体独立的暗影能量数据存储
        self.entity_shadow_data = {}  # entity_id -> {"clip_ratio": float, "shadow_data": int, "is_full": bool}

        # +++ 新增：实体UI节点映射
        self.entity_ui_nodes = {}  # entity_id -> ui_node

        # +++ 新增：向服务端请求技能等级同步
        self.SendSkillLevelSyncRequest()
        self.ui_registered = False

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
                # 更新升级按钮可见性
                ui_node.UpdateUpgradeButtonVisibility(skill_id)

        # 删除以下代码，避免每帧刷新实体UI
        # +++ 新增：更新所有实体UI
        # for entity_id, ui_node in list(self.entity_ui_nodes.items()):
        #     if ui_node and hasattr(ui_node, 'UpdateShadow'):
        #         # 获取该实体的数据
        #         entity_data = self.getEntityShadowData(entity_id)
        #         if entity_data:
        #             try:
        #                 ui_node.UpdateShadow(entity_data["clip_ratio"])
        #             except Exception as e:
        #                 logger.error("更新实体 %s UI失败: %s" % (entity_id, str(e)))
        #                 # 如果UI节点失效，从映射中移除
        #                 del self.entity_ui_nodes[entity_id]

    def SendSkillLevelSyncRequest(self):
        """向服务端发送技能等级同步请求"""
        player_id = clientApi.GetLocalPlayerId()
        self.sendServer(config.RequestSkillLevelsEvent, {
            "playerId": player_id
        })

    def loadSkillLevels(self):
        """加载技能等级数据"""
        level_data = config_comp.GetConfigData("dn_skill_levels")
        if not level_data:
            # 初始化默认等级
            for skill in config.SKILL_CONFIGS:
                self.skill_levels[skill["skill_id"]] = 1
            self.saveSkillLevels()
        else:
            self.skill_levels = level_data

    def saveSkillLevels(self):
        """保存技能等级数据"""
        config_comp.SetConfigData("dn_skill_levels", self.skill_levels)

    def getSkillLevel(self, skill_id):
        """获取技能等级"""
        return self.skill_levels.get(skill_id, 1)

    def getUpgradeInfo(self, skill_id):
        """获取技能升级信息"""
        current_level = self.getSkillLevel(skill_id)

        if current_level >= config.SKILL_UPGRADE_CONFIG["max_level"]:
            return None  # 已达最高等级

        # 获取下一级配置
        next_level = current_level + 1

        # 优先使用技能特定的升级配置
        skill_upgrade_config = config.SKILL_UPGRADE_CONFIG["upgrade_effects"].get(skill_id)
        if skill_upgrade_config and len(skill_upgrade_config) >= next_level:
            return skill_upgrade_config[next_level - 1]  # 列表索引从0开始

        return None

    def canUpgradeSkill(self, skill_id):
        """检查技能是否可以升级"""
        if skill_id not in self.skill_levels:
            return False

        current_level = self.skill_levels[skill_id]
        if current_level >= config.SKILL_UPGRADE_CONFIG["max_level"]:
            return False

        upgrade_info = self.getUpgradeInfo(skill_id)
        if not upgrade_info:
            return False

        # 检查是否有足够的暗影碎片
        fragment_cost = upgrade_info.get("fragment_cost", 0)
        if fragment_cost <= 0:
            return True

        # 检查背包中的暗影碎片数量
        fragment_count = self.getFragmentCount()
        return fragment_count >= fragment_cost

    def getFragmentCount(self):
        """获取暗影碎片数量（苹果）"""
        item_comp = CCF.CreateItem(clientApi.GetLocalPlayerId())
        inv_pos = clientApi.GetMinecraftEnum().ItemPosType.INVENTORY

        total_count = 0
        for slot in range(9):  # 检查快捷栏
            item_dict = item_comp.GetPlayerItem(inv_pos, slot)
            # 修复：检查苹果数量
            if item_dict and item_dict.get('itemName') == config.SKILL_UPGRADE_CONFIG["fragment_item_id"]:
                total_count += item_dict.get('count', 0)

        return total_count

    def upgradeSkill(self, skill_id):
        """升级技能"""
        if not self.canUpgradeSkill(skill_id):
            return False

        # 获取升级信息
        upgrade_info = self.getUpgradeInfo(skill_id)
        if not upgrade_info:
            return False

        fragment_cost = upgrade_info.get("fragment_cost", 0)

        # 不再在客户端消耗碎片，改为发送请求到服务端
        # 发送升级请求到服务端，由服务端处理碎片消耗
        self.sendServer(config.ServerUpgradeSkillEvent, {
            "skill_id": skill_id,
            "playerId": clientApi.GetLocalPlayerId(),
            "fragment_cost": fragment_cost
        })

        return True  # 表示请求已发送，实际结果等待服务端回调

    def getActualCooldown(self, skill_id, base_cooldown):
        """获取实际冷却时间（考虑等级加成）"""
        level = self.getSkillLevel(skill_id)

        # 获取当前等级的冷却时间乘数
        skill_upgrade_config = config.SKILL_UPGRADE_CONFIG["upgrade_effects"].get(skill_id)
        if skill_upgrade_config and len(skill_upgrade_config) >= level:
            cooldown_multiplier = skill_upgrade_config[level - 1].get("cooldown_multiplier", 1.0)
        else:
            # 使用通用配置
            common_config = config.SKILL_UPGRADE_CONFIG["common_upgrade_effects"]
            if len(common_config) >= level:
                cooldown_multiplier = common_config[level - 1].get("cooldown_multiplier", 1.0)
            else:
                cooldown_multiplier = 1.0

        return base_cooldown * cooldown_multiplier

    def getDamageMultiplier(self, skill_id):
        """获取伤害乘数"""
        level = self.getSkillLevel(skill_id)

        # 获取当前等级的伤害乘数
        skill_upgrade_config = config.SKILL_UPGRADE_CONFIG["upgrade_effects"].get(skill_id)
        if skill_upgrade_config and len(skill_upgrade_config) >= level:
            return skill_upgrade_config[level - 1].get("damage_multiplier", 1.0)
        else:
            # 使用通用配置
            common_config = config.SKILL_UPGRADE_CONFIG["common_upgrade_effects"]
            if len(common_config) >= level:
                return common_config[level - 1].get("damage_multiplier", 1.0)
            else:
                return 1.0

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

    def SendShadowMessage(self):
        """获取当前暗影能量数据（当前无实际功能，但保留调用）"""
        shadow_config = config_comp.GetConfigData("dn_shadow_energy")
        # 此方法目前无实际操作，但保留以维持原有调用结构
        pass

    def TriggerSkillAbility(self, skill_id):
        """处理玩家释放技能相关逻辑（修改版，应用等级加成）"""
        skill_cfg = self.GetSkillConfig(skill_id)
        if not skill_cfg:
            return False

        # 获取实际冷却时间（考虑等级）
        actual_cooldown = self.getActualCooldown(skill_id, skill_cfg["cooldown"])

        ui_node = clientApi.GetUI(config.ModName, config.shadowUIName)
        if not ui_node or not hasattr(ui_node, 'ConsumeShadowForAbility'):
            return False

        # 检查冷却
        if self.skill_cooldowns.get(skill_id, 0.0) > 0.0:
            return False

        # 获取当前匹配的物品配置
        matched_item_config = self.GetMatchedItemConfig(skill_id)
        if not matched_item_config:
            return False

        # 消耗能量
        if ui_node.ConsumeShadowForAbility(skill_cfg["energy_cost"]):
            # ... 原有的技能特效代码 ...
            if skill_id == "RW" and matched_item_config["item_identifier"] == "minecraft:arrow":
                render_comp = clientApi.GetEngineCompFactory().CreateActorRender(playerId)
                render_comp.AddPlayerGeometry("default", "geometry.dn.player.custom")
                render_comp.AddPlayerParticleEffect("shadow_blast", "sf:shadow_blast")
                render_comp.RebuildPlayerRender()
                time_comp = clientApi.GetEngineCompFactory().CreateGame(levelId)
                time_comp.AddTimer(2.0, self.ResetPlayerGeo)

            # 发送到服务端，传递伤害乘数
            self.sendServer(config.ServerSkillEvent, {
                "skill": skill_id,
                "playerId": clientApi.GetLocalPlayerId(),
                "itemIdentifier": matched_item_config["item_identifier"],
                "damageMultiplier": self.getDamageMultiplier(skill_id)  # 新增：传递伤害乘数
            })

            # 设置冷却时间（使用实际冷却时间）
            self.skill_cooldowns[skill_id] = actual_cooldown
            if ui_node:
                ui_node.StartCooldown(skill_id, actual_cooldown)
            return True
        return False

    def ResetPlayerGeo(self):
        """重置玩家模型"""
        render_comp = clientApi.GetEngineCompFactory().CreateActorRender(playerId)
        render_comp.AddPlayerGeometry("default", "geometry.humanoid.custom")
        render_comp.RebuildPlayerRender()
        # notify_comp.SetLeftCornerNotify("已恢复原版模型")

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

    @EventListener(config.ClientUpgradeSkillEvent, isCustomEvent=True)
    def OnClientUpgradeSkill(self, args):
        """客户端请求升级技能"""
        skill_id = args.skill_id
        if not skill_id:
            return

        success = self.upgradeSkill(skill_id)

        # 发送升级结果到UI
        ui_node = clientApi.GetUI(config.ModName, config.shadowUIName)
        if ui_node:
            ui_node.OnUpgradeResult(skill_id, success)

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
        # 注册实体头顶UI
        if not self.ui_registered:
            success = clientApi.RegisterUI(config.ModName, config.shadowEntityUIName, config.shadowEntityUIPyClsPath, config.shadowEntityUIScreenDef)
            # self.mshadowEntityUINode = clientApi.CreateUI(config.ModName, config.shadowEntityUIName, {
            #         "bindEntityId": playerId,
            #         "bindOffset": (0, 2, 0),  # UI在实体头顶的偏移量
            #         "autoScale": 1  # 开启自动缩放
            #     })
            self.mshadowEntityUINode = clientApi.GetUI(config.ModName, config.shadowEntityUIName)
            if success:
                logger.info("实体头顶UI注册成功")
                self.ui_registered = True
            else:
                logger.error("实体头顶UI注册失败")
            # if self.mshadowEntityUINode:
            #     logger.info("实体头顶UI创建成功")
            #     self.mshadowEntityUINode.Init()
            # else:
            #     logger.info("实体头顶UI创建失败")

    @EventListener(config.BindEntityUIEvent, isCustomEvent=True)
    def OnBindEntityUI(self, args):
        print "收到绑定实体UI事件"
        print args.dict()
        """
        处理绑定实体UI事件
        """
        try:
            # 使用args.获取参数
            entity_id = args.entityId
            ui_name = args.uiName

            if not entity_id or ui_name != config.shadowEntityUIName:
                return

            logger.info("开始为实体 %s 创建头顶UI" % entity_id)
            print "开始为实体 %s 创建头顶UI" % entity_id

            # +++ 关键修复：确保entity_id是字符串
            entity_id_str = str(entity_id)

            # +++ 关键修复：CheckCanBindUI期望整数
            can_bind = clientApi.CheckCanBindUI(entity_id_str)
            if not can_bind:
                logger.warning("实体 %s 暂时无法绑定UI，等待后重试" % entity_id)
                print "实体 %s 暂时无法绑定UI，等待后重试" % entity_id
                # 延迟1秒后重试
                time_comp = CCF.CreateGame(levelId)
                time_comp.AddTimer(1.0, lambda: self.retryBindUI(entity_id_str))
                return

            # 为实体初始化独立的暗影能量数据
            if entity_id_str not in self.entity_shadow_data:
                self.entity_shadow_data[entity_id_str] = {
                    "clip_ratio": 1.0,
                    "shadow_data": 0,
                    "is_full": False
                }
                logger.info("为实体 %s 初始化暗影能量数据" % entity_id_str)
                print "为实体 %s 初始化暗影能量数据" % entity_id_str

            # +++ 关键修复：检查是否已存在UI节点
            if entity_id_str in self.entity_ui_nodes:
                logger.info("实体 %s 已存在UI节点，跳过创建" % entity_id_str)
                print "实体 %s 已存在UI节点，跳过创建" % entity_id_str
                return

            # 创建绑定实体的UI
            ui_node = clientApi.CreateUI(
                config.ModName, config.shadowEntityUIName,
                {
                    "bindEntityId": entity_id,  # 使用原始整数
                    "bindOffset": (0, 2.5, 0),  # UI在实体头顶的偏移量
                    "autoScale": 1  # 开启自动缩放
                }
            )

            if ui_node:
                logger.info("成功为实体 %s 创建头顶UI" % entity_id_str)
                print "成功为实体 %s 创建头顶UI" % entity_id_str

                # +++ 关键修复：存储UI节点引用
                self.entity_ui_nodes[entity_id_str] = ui_node

                # 初始化UI内容
                ui_node.Init()

                # 使用实体的独立数据更新UI
                entity_data = self.entity_shadow_data.get(entity_id_str)
                if entity_data:
                    print "调用实体 %s UI的UpdateShadow方法，ratio=%s" % (entity_id_str, entity_data["clip_ratio"])
                    ui_node.UpdateShadow(entity_data["clip_ratio"])

                # 打印调试信息
                print "已为实体 %s 创建UI节点，当前UI节点数量: %d" % (entity_id_str, len(self.entity_ui_nodes))
            else:
                logger.error("为实体 %s 创建UI失败" % entity_id_str)
                print "为实体 %s 创建UI失败" % entity_id_str
                # 延迟2秒后重试
                time_comp = CCF.CreateGame(levelId)
                time_comp.AddTimer(2.0, lambda: self.retryBindUI(entity_id_str))

        except Exception as e:
            logger.error("OnBindEntityUI error: %s" % str(e))
            print "OnBindEntityUI error: %s" % str(e)
            import traceback
            traceback.print_exc()  # 打印完整的堆栈信息

    def retryBindUI(self, entity_id_str):
        """重试绑定实体UI"""
        try:
            print "重试为实体 %s 绑定UI" % entity_id_str

            # 检查实体是否仍然存在
            try:
                entity_id_int = int(entity_id_str)
            except:
                print "实体ID %s 不是有效的整数" % entity_id_str
                return

            # +++ 关键修复：CheckCanBindUI期望整数
            can_bind = clientApi.CheckCanBindUI(entity_id_str)
            if not can_bind:
                print "实体 %s 仍然无法绑定UI，放弃重试" % entity_id_str
                return

            # 检查是否已存在UI节点
            if entity_id_str in self.entity_ui_nodes:
                print "实体 %s 已有UI节点，跳过重试" % entity_id_str
                return

            # 创建UI
            ui_node = clientApi.CreateUI(
                config.ModName, config.shadowEntityUIName,
                {
                    "bindEntityId": entity_id_int,  # 使用整数
                    "bindOffset": (0, 2.5, 0),
                    "autoScale": 1
                }
            )

            if ui_node:
                self.entity_ui_nodes[entity_id_str] = ui_node
                ui_node.Init()
                print "重试成功：为实体 %s 创建UI" % entity_id_str
            else:
                print "重试失败：为实体 %s 创建UI失败" % entity_id_str

        except Exception as e:
            print "retryBindUI error: %s" % str(e)
            import traceback
            traceback.print_exc()  # 打印完整的堆栈信息

    def getEntityShadowData(self, entity_id):
        """获取指定实体的暗影能量数据"""
        # 确保entity_id是字符串
        entity_id_str = str(entity_id)

        if entity_id_str in self.entity_shadow_data:
            # 返回数据副本
            return self.entity_shadow_data[entity_id_str].copy()
        else:
            # 如果实体没有数据，初始化并返回默认值
            default_data = {
                "clip_ratio": 1.0,
                "shadow_data": 0,
                "is_full": False
            }
            self.entity_shadow_data[entity_id_str] = default_data.copy()
            logger.info("初始化实体 %s 的暗影能量数据" % entity_id_str)
            return default_data.copy()

    def setEntityShadowData(self, entity_id, data):
        """设置指定实体的暗影能量数据"""
        # 确保entity_id是字符串
        entity_id_str = str(entity_id)

        # 验证数据格式
        required_keys = ["clip_ratio", "shadow_data", "is_full"]
        for key in required_keys:
            if key not in data:
                logger.error("实体数据缺少必要字段: %s" % key)
                return

        # 检查数据是否变化
        current_data = self.entity_shadow_data.get(entity_id_str)
        if (current_data and
                current_data.get("clip_ratio") == data["clip_ratio"] and
                current_data.get("shadow_data") == data["shadow_data"] and
                current_data.get("is_full") == data["is_full"]):
            # 数据无变化，跳过
            return

        # 存储数据
        self.entity_shadow_data[entity_id_str] = data.copy()

        # 详细日志
        logger.info("设置实体 %s 暗影能量数据: clip_ratio=%s, shadow_data=%s" %
                    (entity_id_str, data["clip_ratio"], data["shadow_data"]))
        print "设置实体 %s 暗影能量数据: clip_ratio=%s, shadow_data=%s" % (entity_id_str, data["clip_ratio"],
                                                                           data["shadow_data"])

        # 更新UI
        if entity_id_str in self.entity_ui_nodes:
            ui_node = self.entity_ui_nodes[entity_id_str]
            if ui_node and hasattr(ui_node, 'UpdateShadow'):
                try:
                    print "开始调用实体 %s 的UpdateShadow方法，ratio=%s" % (entity_id_str, data["clip_ratio"])
                    # 调用UpdateShadow
                    ui_node.UpdateShadow(data["clip_ratio"])
                    print "实体 %s 的UpdateShadow方法调用完成" % entity_id_str
                except Exception as e:
                    logger.error("更新实体 %s UI失败: %s" % (entity_id_str, str(e)))
                    print "更新实体 %s UI失败: %s" % (entity_id_str, str(e))
                    # 如果UI节点失效，从映射中移除
                    if entity_id_str in self.entity_ui_nodes:
                        del self.entity_ui_nodes[entity_id_str]
        else:
            # +++ 关键修复：更详细的调试信息
            logger.warning("实体 %s 没有对应的UI节点" % entity_id_str)
            print "警告：实体 %s 没有对应的UI节点" % entity_id_str
            print "当前UI节点列表: %s" % list(self.entity_ui_nodes.keys())
            print "当前实体数据列表: %s" % list(self.entity_shadow_data.keys())

            # 尝试自动创建UI节点
            print "尝试为实体 %s 自动创建UI节点..." % entity_id_str
            self.tryAutoCreateUI(entity_id_str, data)

    def tryAutoCreateUI(self, entity_id_str, data):
        """尝试自动创建UI节点"""
        try:
            # 检查实体ID是否有效
            try:
                entity_id_int = int(entity_id_str)
            except:
                print "实体ID %s 不是有效的整数" % entity_id_str
                return

            # +++ 关键修复：CheckCanBindUI期望整数
            can_bind = clientApi.CheckCanBindUI(entity_id_str)
            if not can_bind:
                print "实体 %s 不存在或无法绑定UI" % entity_id_str
                return

            # 检查UI节点是否已存在
            if entity_id_str in self.entity_ui_nodes:
                print "实体 %s 已有UI节点" % entity_id_str
                return

            # +++ 关键修复：CreateUI的bindEntityId参数需要整数
            ui_node = clientApi.CreateUI(
                config.ModName, config.shadowEntityUIName,
                {
                    "bindEntityId": entity_id_int,  # 使用整数
                    "bindOffset": (0, 2.5, 0),
                    "autoScale": 1
                }
            )

            if ui_node:
                self.entity_ui_nodes[entity_id_str] = ui_node
                ui_node.Init()
                print "自动创建成功：为实体 %s 创建UI" % entity_id_str

                # 更新UI显示
                ui_node.UpdateShadow(data["clip_ratio"])
            else:
                print "自动创建失败：为实体 %s 创建UI失败" % entity_id_str

        except Exception as e:
            print "tryAutoCreateUI error: %s" % str(e)
            import traceback
            traceback.print_exc()  # 打印完整的堆栈信息

    @EventListener(config.ClientItemTryUseEvent)
    def OnClientItemTryUse(self, args):
        """客户端尝试使用物品时触发，处理暗影能量的使用与消耗"""
        # print args.dict()
        itemDict = args.itemDict
        if itemDict.get("newItemName") != "sf:shadow_energy":
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
            notify_comp.SetLeftCornerNotify("客户端：暗影能量已满，无法使用该物品")
            return
        # 能量未满：取消原始事件，通知服务端处理物品消耗和能量增加
        args.cancel = True
        self.sendServer(config.ClientUseShadowEnergyEvent, {"playerId": playerId})

    @EventListener(config.AddShadowEnergyEvent, isCustomEvent=True)
    def OnAddShadowEnergy(self, args):
        """增加暗影能量（服务端通知）"""
        print "收到暗影能量增加事件"
        print args.dict()

        # 使用args.获取参数
        amount = args.amount

        # 使用args.获取entityId
        entity_id = args.entityId

        # 判断是玩家事件还是实体事件
        if entity_id is not None:
            # 实体事件
            print "这是实体 %s 的暗影能量事件，增加 %s 点" % (entity_id, amount)

            # 确保entity_id是字符串形式
            entity_id_str = str(entity_id)

            # 获取当前实体的暗影能量数据
            current_data = self.getEntityShadowData(entity_id_str)
            if not current_data:
                # 如果实体没有数据，初始化
                current_data = {
                    "clip_ratio": 1.0,
                    "shadow_data": 0,
                    "is_full": False
                }
                self.entity_shadow_data[entity_id_str] = current_data.copy()

            current_energy = current_data.get("shadow_data", 0)
            new_energy = current_energy + amount

            if new_energy > 100:
                new_energy = 100

            new_ratio = 1.0 - (new_energy / 100.0)

            # 创建新的数据对象
            updated_data = {
                "clip_ratio": new_ratio,
                "shadow_data": new_energy,
                "is_full": (new_energy >= 100)
            }

            # 更新实体独立数据
            self.setEntityShadowData(entity_id_str, updated_data)

            print "实体 %s 暗影能量：%s -> %s" % (entity_id, current_energy, new_energy)

        else:
            # 玩家事件
            print "这是玩家的暗影能量事件，增加 %s 点" % amount

            current_data = config_comp.GetConfigData("dn_shadow_energy")
            if not current_data:
                current_data = {"clip_ratio": 1.0, "shadow_data": 0, "is_full": False}

            current_energy = current_data.get("shadow_data", 0)
            new_energy = current_energy + amount

            if new_energy > 100:
                new_energy = 100

            new_ratio = 1.0 - (new_energy / 100.0)

            # 创建新的玩家数据对象
            updated_player_data = {
                "clip_ratio": new_ratio,
                "shadow_data": new_energy,
                "is_full": (new_energy >= 100)
            }

            # 更新玩家全局数据
            config_comp.SetConfigData("dn_shadow_energy", updated_player_data)

            print "玩家暗影能量：%s -> %s" % (current_energy, new_energy)

            # 更新玩家UI
            ui_node = clientApi.GetUI(config.ModName, config.shadowUIName)
            if ui_node:
                ui_node.UpdateShadow(new_ratio)

    @EventListener(config.DamageEvent, isCustomEvent=True)
    def OnDamageEvent(self, args):
        """客户端玩家受伤事件"""
        entityId = args.entityId
        print entityId
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

    @EventListener(config.PlayerAttackEntityEvent)
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

    @EventListener(config.UpgradeSkillResultEvent, isCustomEvent=True)
    def OnUpgradeSkillResult(self, args):
        """处理服务端返回的升级结果"""
        skill_id = args.skill_id
        new_level = args.new_level
        success = args.success

        if success:
            # 更新本地技能等级
            self.skill_levels[skill_id] = new_level
            self.saveSkillLevels()

            # 更新UI
            ui_node = clientApi.GetUI(config.ModName, config.shadowUIName)
            if ui_node:
                ui_node.UpdateSkillLevel(skill_id, new_level)

            # +++ 修复：使用更安全的方式获取事件参数
            # 如果属性不存在，则使用getattr返回默认值
            damage_multiplier = args.damage_multiplier
            cooldown_multiplier = args.cooldown_multiplier
            print damage_multiplier,cooldown_multiplier

            # 显示升级成功消息
            level_text = "Lv" + str(new_level)
            damage_bonus = (damage_multiplier - 1.0) * 30
            cooldown_reduction = float((1.0 - cooldown_multiplier) * 5)
            print damage_bonus, cooldown_reduction

            current_damage = int(damage_multiplier * 30)
            current_cooldown = float(cooldown_multiplier * 5)
            print current_damage,current_cooldown

            message = "§a%s技能升级到%s！§r" % (skill_id, level_text)
            if damage_bonus > 0:
                message += " §a造成伤害: §l+%.1f§r (%d)" % (damage_bonus,current_damage)
            if cooldown_reduction > 0:
                message += " §a冷却时间: §l-%.1f秒§r (%.1f秒)" % (cooldown_reduction,current_cooldown)

            notify_comp.SetLeftCornerNotify(message)
        else:
            # 升级失败，显示原因
            reason = args.reason
            notify_comp.SetLeftCornerNotify("升级失败: %s" % reason)

    @EventListener(config.SyncSkillLevelsEvent, isCustomEvent=True)
    def OnSyncSkillLevels(self, args):
        """接收服务端同步的技能等级"""
        skill_levels = args.skill_levels
        if skill_levels:
            self.skill_levels = skill_levels
            self.saveSkillLevels()  # 保存到本地配置
            logger.info("从服务端同步技能等级: %s" % skill_levels)

            # +++ 修复点：确保在数据同步后，UI被创建或刷新
            if not hasattr(self, 'mshadowUINode') or self.mshadowUINode is None:
                # UI可能尚未创建，此时创建UI
                clientApi.RegisterUI(config.ModName, config.shadowUIName, config.shadowUIPyClsPath,
                                     config.shadowUIScreenDef)
                self.mshadowUINode = clientApi.CreateUI(config.ModName, config.shadowUIName, {"isHud": 1})
            # 获取UI节点并更新
            ui_node = clientApi.GetUI(config.ModName, config.shadowUIName)
            if ui_node:
                for skill_id, level in skill_levels.items():
                    ui_node.UpdateSkillLevel(skill_id, level)
                logger.info("UI技能等级已更新为服务端数据。")

    @EventListener("OnEntityDeathEvent")
    def OnEntityDeath(self, args):
        """实体死亡事件"""
        entity_id = args.id
        if entity_id and entity_id in self.entity_shadow_data:
            # 清理实体数据
            del self.entity_shadow_data[entity_id]
            if entity_id in self.entity_ui_nodes:
                del self.entity_ui_nodes[entity_id]
            logger.info("清理已死亡实体 %s 的暗影能量数据" % entity_id)