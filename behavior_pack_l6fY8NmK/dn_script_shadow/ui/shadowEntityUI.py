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

class ShadowEntityScreenUI(ScreenNode):
    def __init__(self, namespace, name, param):
        ScreenNode.__init__(self, namespace, name, param)
        logger.info("===== shadowEntityScreenUI Init (Dynamic) =====")

        # 基础属性
        bind_entity_id = param.get("bindEntityId", None)  # 获取绑定的实体ID
        # 确保entity_id是字符串，用于存储和比较
        self.entity_id = str(bind_entity_id) if bind_entity_id is not None else None

        # 检查参数
        print "实体头顶UI参数: %s" % param
        print "绑定的实体ID: %s" % self.entity_id
        print "原始bindEntityId: %s, 类型: %s" % (bind_entity_id, type(bind_entity_id))

        # UI路径
        self.mShadowPanel = "/shadowPanel"
        self.mProgressBar = self.mShadowPanel + "/progress_bar"
        self.mFilledProgressBar = self.mProgressBar + "/filled_progress_bar"
        self.mShadowData = self.mShadowPanel + "/shadow_data"
        self.mShadowAbility = self.mShadowPanel + "/shadow_ability"
        self.mUpgradePanel = self.mShadowPanel + "/upgrade_panel"

        # 绑定属性
        self.entity_shadow = 1.0
        self.shadowDataEntity = 0

        # 调试：检查绑定系统
        print "UI初始化完成，entity_id=%s" % self.entity_id
        print "初始绑定属性: entity_shadow=%s, shadowDataEntity=%s" % (self.entity_shadow, self.shadowDataEntity)

    def Create(self):
        pass

    # 在 shadowEntityUI.py 中修复 UpdateShadow 和 Init 方法

    def UpdateShadow(self, ratio):
        """更新暗影能量显示 - 修复版"""
        if not self.entity_id or not client_sys:
            return

        # 计算新的数值
        shadow_data = int(round(100 * (1 - ratio)))

        # 更新绑定属性
        self.entity_shadow = ratio
        self.shadowDataEntity = shadow_data

        # +++ 关键修复：必须正确触发UI刷新
        # 1. 标记所有绑定属性为脏
        # self.SetAllDirty()
        #
        # # 2. 更新绑定
        # self.UpdateBindings()

        # 3. 更新屏幕
        self.UpdateScreen()

        # 4. 调试日志
        logger.info("实体 %s UI更新，比例: %s, 数值: %s" % (self.entity_id, ratio, shadow_data))
        print "实体 %s UI更新，比例: %s, 数值: %s" % (self.entity_id, ratio, shadow_data)

    def Init(self):
        # 使用实体独立的暗影能量数据
        if self.entity_id and client_sys:
            # 获取该实体的暗影能量数据
            entity_data = client_sys.getEntityShadowData(self.entity_id)
            if entity_data:
                ratio = entity_data.get("clip_ratio", 1.0)
                shadow_value = entity_data.get("shadow_data", 0)

                # 更新绑定属性
                self.entity_shadow = ratio
                self.shadowDataEntity = shadow_value

                # +++ 关键修复：初始化时也要正确刷新UI
                # self.SetAllDirty()
                # self.UpdateBindings()
                self.UpdateScreen()

                logger.info("实体 %s UI初始化，暗影能量: %s, 比例: %s" % (self.entity_id, shadow_value, ratio))
                print "实体 %s UI初始化，暗影能量: %s, 比例: %s" % (self.entity_id, shadow_value, ratio)

    @ViewBinder.binding(ViewBinder.BF_BindFloat, '#entity_shadow')
    def ReturnShadow(self):
        # 绑定到进度条的裁剪比例
        # 确保返回浮点数
        val = float(self.entity_shadow)
        # print "绑定函数ReturnShadow被调用，返回: %s" % val
        return val

    @ViewBinder.binding(ViewBinder.BF_BindString, '#shadow_data_entity')
    def ReturnShadowData(self):
        # 绑定到暗影能量数值文本
        val = str(int(self.shadowDataEntity))
        # print "绑定函数ReturnShadowData被调用，返回: %s" % val
        return val