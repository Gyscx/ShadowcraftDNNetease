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

    def CreateTouchHandler(self, skill_id):
        """为每个技能创建触摸事件处理器"""

        def handler(args):
            if args["TouchEvent"] == touchEventEnum.TouchUp:
                if client_sys.CheckItemForSkill(client_sys.GetSkillConfig(skill_id)):
                    if client_sys.TriggerSkillAbility(skill_id):
                        self.StartCooldown(skill_id)

        return handler

    def Init(self):
        logger.info("===== shadowScreenUI Init (Dynamic) =====")
        ctrl = self.GetBaseUIControl(self.mShadowAbility)
        if ctrl is not None:
            ctrl.SetVisible(False)
        else:
            logger.error("Failed to get control: %s" % self.mShadowAbility)

        # 更新所有技能按钮状态
        self.UpdateAllSkillButtons()
        self.UpdateAbilityVisibility()

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
        """更新所有技能按钮的状态"""
        for skill in config.SKILL_CONFIGS:
            skill_id = skill["skill_id"]
            has_item = client_sys.CheckItemForSkill(skill) if client_sys else False
            self.UpdateSkillButtonState(skill_id, has_item)

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

    def UpdateCooldowns(self):
        """更新所有技能的冷却显示（简化版，仅更新按钮文本）"""
        for skill_id, state in self.skill_states.items():
            time_left = state["cooldown_time"]

            # 获取技能配置
            skill_config = None
            for cfg in config.SKILL_CONFIGS:
                if cfg["skill_id"] == skill_id:
                    skill_config = cfg
                    break

            if not skill_config:
                continue

            # 根据您的描述，冷却时间直接显示在按钮的文本控件上
            # 假设文本控件的路径是按钮路径下名为 "button_label" 的子控件
            time_text_path = skill_config["ui_button_path"] + "/button_label"
            time_text_ctrl = self.GetBaseUIControl(time_text_path)

            if time_text_ctrl:
                label = time_text_ctrl.asLabel()
                if time_left > 0:
                    # 显示剩余冷却时间（保留一位小数）
                    label.SetText(str(round(time_left, 1)))
                else:
                    # 冷却结束，根据是否有物品显示按键标签或清空
                    if state.get("has_item"):
                        # 有物品且无冷却，显示按键标签
                        if clientApi.GetPlatform() == 0:  # PC端
                            label.SetText(skill_config.get("pc_key_label", ""))
                        else:  # 移动端
                            label.SetText("")
                    else:
                        # 无物品
                        label.SetText("")

            # 注意：已完全移除对不存在的 "cooldown_bar" 进度条控件的操作

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