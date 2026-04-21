# -*- coding: utf-8 -*-
import mod.client.extraClientApi as clientApi
from mod_log import logger
from .. import config

from ..client.shadow_clientSystem import ShadowClientSystem

ViewBinder = clientApi.GetViewBinderCls()
ScreenNode = clientApi.GetScreenNodeCls()
levelId = clientApi.GetLevelId()
CCF = clientApi.GetEngineCompFactory()
notify_comp = CCF.CreateTextNotifyClient(levelId)
config_comp = CCF.CreateConfigClient(levelId)
client_sys = ShadowClientSystem.getInstance()
touchEventEnum = clientApi.GetMinecraftEnum().TouchEvent


class ShadowScreenUI(ScreenNode):
    def __init__(self, namespace, name, param):
        ScreenNode.__init__(self, namespace, name, param)
        logger.info("===== shadowScreenUI Init (Dynamic) =====")

        # 基础属性
        self.shadow = 1.0
        self.shadowData = 0
        self.ability_visible = False

        # UI路径
        self.mShadowPanel = "/shadowPanel"
        self.mProgressBar = self.mShadowPanel + "/progress_bar"
        self.mShadowData = self.mShadowPanel + "/shadow_data"
        self.mShadowAbility = self.mShadowPanel + "/shadow_ability"

        # 动态技能状态存储
        self.skill_button_paths = {}  # skill_id -> button_path
        # 移除 cooldown_times 字典，统一使用 skill_states
        self.skill_states = {}

        # 新增：技能等级相关属性
        self.skill_levels = {}  # skill_id -> level
        self.current_upgrade_skill = None
        self.upgrade_cost_text = ""

        # 绑定升级相关变量
        self.helmet_level_text = "LV1"
        self.armor_level_text = "LV1"
        self.weapon_level_text = "LV1"
        self.RW_level_text = "LV1"

        # 初始化技能状态
        for skill in config.SKILL_CONFIGS:
            skill_id = skill["skill_id"]

            # 安全地获取纹理名称，兼容新旧配置结构
            texture_name = self._get_skill_texture_name(skill)

            self.skill_states[skill_id] = {
                "cooldown_time": 0.0,
                "texture": "textures/ui/%s_button_locked" % texture_name,  # 修复：使用安全获取的纹理名称
                "has_item": False
            }
            self.skill_button_paths[skill_id] = skill["ui_button_path"]

        # 绑定变量
        for skill in config.SKILL_CONFIGS:
            skill_id = skill["skill_id"]
            # 同样安全地获取纹理名称
            texture_name = self._get_skill_texture_name(skill)
            setattr(self, "%s_default_texture" % skill_id, "textures/ui/%s_button_locked" % texture_name)

    def Create(self):
        logger.info("===== shadowScreenUI Create =====")
        # 动态绑定触摸事件
        for skill in config.SKILL_CONFIGS:
            skill_id = skill["skill_id"]
            button_path = skill["ui_button_path"]
            # 为每个技能按钮创建触摸事件处理
            self.AddTouchEventHandler(button_path, self.CreateTouchHandler(skill_id), {"isSwallow": True})

        # 为升级按钮添加触摸事件
        for skill in config.SKILL_CONFIGS:
            skill_id = skill["skill_id"]
            # 升级按钮路径
            upgrade_button_path = skill["ui_button_path"] + "/upgrade_button"
            self.AddTouchEventHandler(upgrade_button_path, self.CreateUpgradeHandler(skill_id), {"isSwallow": True})

        # 为升级确认面板添加事件
        self.AddTouchEventHandler("/shadowPanel/upgrade_panel/confirm_button", self.OnConfirmUpgrade,
                                  {"isSwallow": True})
        self.AddTouchEventHandler("/shadowPanel/upgrade_panel/cancel_button", self.OnCancelUpgrade,
                                  {"isSwallow": True})

        upgrade_panel = self.GetBaseUIControl("/shadowPanel/upgrade_panel")
        if upgrade_panel:
            upgrade_panel.SetVisible(False)

    def CreateTouchHandler(self, skill_id):
        """为每个技能创建触摸事件处理器"""

        def handler(args):
            if args["TouchEvent"] == touchEventEnum.TouchUp:
                if client_sys.CheckItemForSkill(client_sys.GetSkillConfig(skill_id)):
                    if client_sys.TriggerSkillAbility(skill_id):
                        self.StartCooldown(skill_id)

        return handler

    # 文件: shadowUI.py
    # 方法: __init__ 或 Init
    # 建议修改：在UI初始化时，主动从客户端系统获取最新等级
    def Init(self):
        logger.info("===== shadowScreenUI Init (Dynamic) =====")
        ctrl = self.GetBaseUIControl(self.mShadowAbility)
        if ctrl is not None:
            ctrl.SetVisible(False)
        else:
            logger.error("Failed to get control: %s" % self.mShadowAbility)

        # +++ 修复点：从客户端系统实例获取最新技能等级，而不是用默认值
        client_sys = ShadowClientSystem.getInstance()
        if client_sys and hasattr(client_sys, 'skill_levels'):
            self.skill_levels = client_sys.skill_levels.copy()
            # 立即更新UI上的等级文本显示
            for skill_id, level in self.skill_levels.items():
                level_text_attr = "%s_level_text" % skill_id
                if hasattr(self, level_text_attr):
                    setattr(self, level_text_attr, "LV%s" % level)
        # 更新所有技能按钮状态
        self.UpdateAllSkillButtons()
        self.UpdateAbilityVisibility()
        self.UpdateScreen()  # 触发数据绑定刷新

    def _get_skill_texture_name(self, skill_cfg):
        """获取技能纹理名称（仅使用新结构valid_items）

        Args:
            skill_cfg: 技能配置字典

        Returns:
            str: 技能对应的纹理名称
        """
        # 新结构：技能配置必须包含valid_items列表
        if "valid_items" in skill_cfg and skill_cfg["valid_items"]:
            # 返回第一个物品的纹理名称作为该技能的默认纹理
            texture_name = skill_cfg["valid_items"][0].get("texture_name")
            if texture_name:
                return texture_name

        # 如果没有有效的valid_items配置，记录错误并返回安全默认值
        logger.error(
            "技能配置错误：技能ID=%s 缺少有效的valid_items配置或texture_name字段" %
            skill_cfg.get("skill_id", "unknown")
        )
        return "button_locked"

    def UpdateAllSkillButtons(self):
        """更新所有技能按钮的状态（扩展版）"""
        for skill in config.SKILL_CONFIGS:
            skill_id = skill["skill_id"]
            has_item = client_sys.CheckItemForSkill(skill) if client_sys else False
            self.UpdateSkillButtonState(skill_id, has_item)

            # +++ 确保每次更新技能按钮时，也同步更新其升级按钮的可见性
            self.UpdateUpgradeButtonVisibility(skill_id)

    def UpdateSkillButtonState(self, skill_id, has_item):
        """更新单个技能按钮的状态
        Args:
            skill_id: 技能ID
            has_item: 布尔值，表示玩家是否持有该技能所需的任何有效物品
        """
        # 1. 获取技能配置
        skill_cfg = None
        for skill in config.SKILL_CONFIGS:
            if skill["skill_id"] == skill_id:
                skill_cfg = skill
                break
        if not skill_cfg:
            return

        # 2. 获取该技能的默认纹理基础名称（从valid_items的第一个物品中获取）
        default_texture_for_skill = self._get_skill_texture_name(skill_cfg)  # 例如: "eruption"

        # 3. 确定最终使用的纹理基础名称和状态
        texture_base = default_texture_for_skill  # 默认使用技能配置中的第一个纹理
        if has_item and client_sys:
            # 有物品时，尝试获取当前实际匹配的物品配置
            matched_config = client_sys.GetMatchedItemConfig(skill_id)
            if matched_config:
                # 成功匹配到具体物品，使用其纹理
                texture_base = matched_config.get("texture_name", default_texture_for_skill)
            # 如果 has_item 为 True 但 matched_config 为 None，仍使用默认纹理，但状态应为“就绪”

        # 4. 关键修复：根据 has_item 决定贴图后缀，直接而明确
        if has_item:
            # 有有效物品 -> 使用“就绪”状态贴图 (_button)
            final_texture_path = "textures/ui/%s_button" % texture_base
            skill_state_for_logic = config.SKILL_STATE["READY"]
        else:
            # 无有效物品 -> 使用“锁定”状态贴图 (_button_locked)
            final_texture_path = "textures/ui/%s_button_locked" % texture_base
            skill_state_for_logic = config.SKILL_STATE["NO_ITEM"]

        # 5. 获取UI按钮控件
        button_path = skill_cfg.get("ui_button_path")
        button_control = self.GetBaseUIControl(button_path) if button_path else None
        if not button_control:
            return

        # 6. 应用纹理到UI控件
        image_control = button_control.asButton().GetChildByName("default")
        if image_control:
            image_control.asImage().SetSprite(final_texture_path)
        self.UpdateScreen()

        # 7. 更新按钮可点击状态和内部状态存储
        # 按钮可点击性直接与是否有有效物品挂钩
        button_control.SetTouchEnable(has_item)

        # 更新内部状态字典
        if skill_id in self.skill_states:
            self.skill_states[skill_id]["has_item"] = has_item
            self.skill_states[skill_id]["texture"] = final_texture_path
            # 同步更新用于数据绑定的属性，确保UI其他部分状态一致
            setattr(self, "%s_default_texture" % skill_id, final_texture_path)

    def StartCooldown(self, skill_id, cooldown_duration=None):
        """开始技能冷却"""
        skill_cfg = None
        for skill in config.SKILL_CONFIGS:
            if skill["skill_id"] == skill_id:
                skill_cfg = skill
                break

        if skill_cfg:
            # 使用传入的冷却时间，或使用配置中的默认值
            duration = cooldown_duration if cooldown_duration is not None else skill_cfg["cooldown"]
            self.skill_states[skill_id]["cooldown_time"] = duration
            # 直接调用UpdateSkillButtonState，传入has_item=True，因为能释放技能肯定持有物品
            self.UpdateSkillButtonState(skill_id, True)

    # 文件: shadowUI.py
    # 方法: UpdateCooldowns
    # 修改后的代码段
    def UpdateCooldowns(self):
        """更新所有技能的冷却显示"""
        for skill_id, state in self.skill_states.items():
            time_left = state["cooldown_time"]
            skill_config = None
            for cfg in config.SKILL_CONFIGS:
                if cfg["skill_id"] == skill_id:
                    skill_config = cfg
                    break
            if not skill_config:
                continue
            time_text_path = skill_config["ui_button_path"] + "/button_label"
            time_text_ctrl = self.GetBaseUIControl(time_text_path)
            if not time_text_ctrl:
                continue
            label = time_text_ctrl.asLabel()
            if time_left > 0:
                # +++ 修复点1：冷却中，始终显示时间
                label.SetText(str(round(time_left, 1)))
                label.SetVisible(True)
            else:
                # +++ 修复点2：冷却结束，根据是否有物品来决定显示内容
                if state.get("has_item", False):
                    # 有物品，显示按键标签
                    if clientApi.GetPlatform() == 0:  # PC端
                        label.SetText(skill_config.get("pc_key_label", ""))
                    else:
                        label.SetText("")
                        label.SetVisible(False)
                else:
                    # 无物品，清空文本
                    label.SetText("")
                    label.SetVisible(False)

    def UpdateShadow(self, new_value):
        """更新暗影能量显示（保持原有逻辑）"""
        old_energy = self.shadowData
        if new_value < 0.0:
            new_value = 0.0
        self.shadow = new_value
        energy = int(round(100 * (1 - self.shadow)))
        energy = max(0, min(energy, 100))
        self.shadowData = energy

        if old_energy < 100 and energy >= 100:
            notify_comp.SetLeftCornerNotify("暗影能量条已填充完毕，可以释放技能")
            logger.info("UI: 暗影能量满，发送通知")

        if energy >= 100:
            self.ability_visible = True
        elif energy <= 0:
            self.ability_visible = False

        self.UpdateAbilityVisibility()
        self.UpdateScreen()

    def UpdateAbilityVisibility(self):
        """更新技能面板可见性"""
        ctrl = self.GetBaseUIControl(self.mShadowAbility)
        if ctrl is None:
            logger.error("无法获取技能面板控件: %s" % self.mShadowAbility)
            return
        ctrl.SetVisible(self.ability_visible)

        current_data = config_comp.GetConfigData("dn_shadow_energy")
        if current_data:
            current_data["is_full"] = self.ability_visible
            config_comp.SetConfigData("dn_shadow_energy", current_data)

    def ConsumeShadowForAbility(self, amount):
        """消耗暗影能量"""
        if self.shadowData >= amount:
            new_shadow = self.shadow + amount / 100.0
            if new_shadow > 1.0:
                new_shadow = 1.0
            self.UpdateShadow(new_shadow)

            current_data = config_comp.GetConfigData("dn_shadow_energy") or {
                "clip_ratio": 1.0, "shadow_data": 0, "is_full": False
            }
            current_data["clip_ratio"] = new_shadow
            current_data["shadow_data"] = int(round(100 * (1 - new_shadow)))
            config_comp.SetConfigData("dn_shadow_energy", current_data)
            return True
        return False

    def CreateUpgradeHandler(self, skill_id):
        """创建升级按钮触摸事件处理器"""

        def handler(args):
            if args["TouchEvent"] == touchEventEnum.TouchUp:
                # 调试信息
                logger.info("升级按钮被点击: %s" % skill_id)
                self.ShowUpgradePanel(skill_id)

        return handler

    def ShowUpgradePanel(self, skill_id):
        """显示升级确认面板"""
        client_sys = ShadowClientSystem.getInstance()
        if not client_sys:
            logger.error("无法获取客户端系统实例")
            return

        # 检查是否可以升级
        if not client_sys.canUpgradeSkill(skill_id):
            logger.info("技能 %s 不可升级" % skill_id)
            return

        upgrade_info = client_sys.getUpgradeInfo(skill_id)
        if not upgrade_info:
            logger.error("无法获取升级信息: %s" % skill_id)
            return

        self.current_upgrade_skill = skill_id
        current_level = client_sys.getSkillLevel(skill_id)
        next_level = upgrade_info["level"]

        # 构建升级信息文本
        cost_text = "升级到 LV%s" % next_level
        fragment_cost = upgrade_info.get("fragment_cost", 0)

        if fragment_cost > 0:
            fragment_count = client_sys.getFragmentCount()
            cost_text += "，需要暗影能量: %d" % fragment_cost
            cost_text += "\n当前拥有: %d" % fragment_count

            if fragment_count < fragment_cost:
                cost_text += " §c(不足)§f"
            else:
                cost_text += " §a(足够)§f"

        # 显示升级效果
        damage_bonus = int((upgrade_info.get("damage_multiplier", 1.0) - 1.0) * 100)
        cooldown_reduction = int((1.0 - upgrade_info.get("cooldown_multiplier", 1.0)) * 100)

        if damage_bonus > 0:
            cost_text += "\n§a伤害增加: +%d%%§f" % damage_bonus
        if cooldown_reduction > 0:
            cost_text += "§a，冷却减少: -%d%%§f" % cooldown_reduction

        self.upgrade_cost_text = cost_text

        # 显示升级面板
        upgrade_panel = self.GetBaseUIControl("/shadowPanel/upgrade_panel")
        if upgrade_panel:
            upgrade_panel.SetVisible(True)
            logger.info("升级面板显示: %s" % skill_id)

        self.UpdateScreen()

    def OnConfirmUpgrade(self, args):
        """确认升级"""
        if args["TouchEvent"] != touchEventEnum.TouchUp:
            return

        if not self.current_upgrade_skill:
            return

        # 发送升级请求
        client_sys = ShadowClientSystem.getInstance()
        if client_sys:
            # 直接调用升级方法，而不是发送事件
            success = client_sys.upgradeSkill(self.current_upgrade_skill)

            # 可以在这里立即处理UI反馈
            if success:
                # 升级请求已发送，等待服务端返回结果
                pass
            else:
                # 客户端检查失败（如碎片不足）
                notify_comp.SetLeftCornerNotify("升级条件不满足")

        # 隐藏升级面板
        self.HideUpgradePanel()

    def OnCancelUpgrade(self, args):
        """取消升级"""
        if args["TouchEvent"] == touchEventEnum.TouchUp:
            self.HideUpgradePanel()

    def HideUpgradePanel(self):
        """隐藏升级面板"""
        self.current_upgrade_skill = None
        upgrade_panel = self.GetBaseUIControl("/shadowPanel/upgrade_panel")
        if upgrade_panel:
            upgrade_panel.SetVisible(False)
        self.UpdateScreen()

    def UpdateSkillLevel(self, skill_id, level):
        """更新技能等级显示"""
        # 更新内部状态
        self.skill_levels[skill_id] = level

        # 更新绑定变量
        level_text_attr = "%s_level_text" % skill_id
        if hasattr(self, level_text_attr):
            setattr(self, level_text_attr, "LV%s" % level)

        # 更新UI控件可见性
        self.UpdateUpgradeButtonVisibility(skill_id)

        self.UpdateScreen()

    def UpdateUpgradeButtonVisibility(self, skill_id):
        """更新升级按钮可见性"""
        client_sys = ShadowClientSystem.getInstance()
        if not client_sys:
            return

        # 获取技能按钮路径
        skill_button_path = None
        upgrade_button_path = None
        for skill in config.SKILL_CONFIGS:
            if skill["skill_id"] == skill_id:
                skill_button_path = skill["ui_button_path"]
                upgrade_button_path = skill["ui_button_path"] + "/upgrade_button"
                break

        if not skill_button_path or not upgrade_button_path:
            return

        # 检查技能按钮是否可见
        skill_button = self.GetBaseUIControl(skill_button_path)
        if not skill_button or not skill_button.GetVisible():
            # 如果技能按钮不可见，升级按钮也应该不可见
            upgrade_button = self.GetBaseUIControl(upgrade_button_path)
            if upgrade_button:
                upgrade_button.SetVisible(False)
            return

        # 检查是否可以升级
        can_upgrade = client_sys.canUpgradeSkill(skill_id)

        # 更新升级按钮可见性
        upgrade_button = self.GetBaseUIControl(upgrade_button_path)
        if upgrade_button:
            upgrade_button.SetVisible(can_upgrade)

    def UpdateAllSkillButtons(self):
        """更新所有技能按钮的状态（扩展版）"""
        for skill in config.SKILL_CONFIGS:
            skill_id = skill["skill_id"]
            has_item = client_sys.CheckItemForSkill(skill) if client_sys else False
            self.UpdateSkillButtonState(skill_id, has_item)

            # 同时更新升级按钮可见性
            self.UpdateUpgradeButtonVisibility(skill_id)

    # 文件: shadowUI.py
    # 方法: OnUpgradeResult
    # 修改后的代码段
    def OnUpgradeResult(self, skill_id, success):
        """处理升级结果"""
        # +++ 修复点：UI只负责视觉和音效反馈，不发送文本提示，避免重复。
        if success:
            # 升级成功，播放特效
            self.PlayUpgradeEffect(skill_id)
            # 确保这里没有类似下面的通知代码：
            # notify_comp.SetLeftCornerNotify("升级成功！")  # 此类代码应删除
        # else:  # 失败提示应由客户端系统统一处理，这里也不应重复提示
        #     pass

    def PlayUpgradeEffect(self, skill_id):
        """播放升级特效"""
        # 可以添加粒子效果、声音等
        player_id = clientApi.GetLocalPlayerId()

        # 示例：播放升级粒子效果
        particle_comp = CCF.CreateParticle(player_id)
        # 这里需要根据实际情况调整粒子效果

        # 播放升级音效
        audio_comp = CCF.CreateAudio(player_id)
        audio_comp.PlayUI("random.levelup", 1.0, 1.0)

    def __getattr__(self, name):
        """动态处理技能纹理和冷却时间的获取"""
        # 处理纹理属性
        if name.endswith("_default_texture"):
            skill_id = name.replace("_default_texture", "")
            if skill_id in self.skill_states:
                return self.skill_states[skill_id].get("texture", "textures/ui/button_locked")

        # 处理冷却时间属性
        elif name.endswith("_cooldown_time"):
            skill_id = name.replace("_cooldown_time", "")
            if skill_id in self.skill_states:
                return "%.1f" % self.skill_states[skill_id].get("cooldown_time", 0.0)

        # 处理其他动态属性
        elif name.endswith("_has_item"):
            skill_id = name.replace("_has_item", "")
            if skill_id in self.skill_states:
                return self.skill_states[skill_id].get("has_item", False)

        # 如果属性不存在，抛出 AttributeError
        raise AttributeError("'ShadowScreenUI' object has no attribute '%s'" % name)

    # 数据绑定方法扩展
    @ViewBinder.binding(ViewBinder.BF_BindString, '#helmet_level_text')
    def ReturnHelmetLevelText(self):
        return self.helmet_level_text

    @ViewBinder.binding(ViewBinder.BF_BindString, '#armor_level_text')
    def ReturnArmorLevelText(self):
        return self.armor_level_text

    @ViewBinder.binding(ViewBinder.BF_BindString, '#weapon_level_text')
    def ReturnWeaponLevelText(self):
        return self.weapon_level_text

    @ViewBinder.binding(ViewBinder.BF_BindString, '#RW_level_text')
    def ReturnRWLevelText(self):
        return self.RW_level_text

    @ViewBinder.binding(ViewBinder.BF_BindString, '#upgrade_cost_text')
    def ReturnUpgradeCostText(self):
        return self.upgrade_cost_text

    # 数据绑定方法
    @ViewBinder.binding(ViewBinder.BF_BindFloat, '#shadow')
    def ReturnShadow(self):
        return self.shadow

    @ViewBinder.binding(ViewBinder.BF_BindString, '#shadow_data')
    def ReturnShadowData(self):
        return str(self.shadowData)

    @ViewBinder.binding(ViewBinder.BF_BindString, '#helmet_default_texture')
    def ReturnHelmetDefaulTtexture(self):
        return self.helmet_default_texture

    @ViewBinder.binding(ViewBinder.BF_BindString, '#armor_default_texture')
    def ReturnArmorDefaultTexture(self):
        return self.armor_default_texture

    @ViewBinder.binding(ViewBinder.BF_BindString, '#weapon_default_texture')
    def ReturnWeaponDefaultTexture(self):
        return self.weapon_default_texture

    @ViewBinder.binding(ViewBinder.BF_BindString, '#RW_default_texture')
    def ReturnRWDefaultTexture(self):
        return self.RW_default_texture

