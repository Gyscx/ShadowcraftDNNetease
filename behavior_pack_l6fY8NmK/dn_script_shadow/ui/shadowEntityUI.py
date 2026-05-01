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

        print param
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

        # 强制初始化绑定属性
        self.entity_shadow = 1.0
        self.shadowDataEntity = 0
        self.entity_id = str(param.get("bindEntityId", "")) if param.get("bindEntityId") else None

        # 立即更新绑定属性
        self.UpdateScreen()

        # 调试：检查绑定系统
        print "UI初始化完成，entity_id=%s" % self.entity_id
        print "初始绑定属性: entity_shadow=%s, shadowDataEntity=%s" % (self.entity_shadow, self.shadowDataEntity)

    def Create(self):
        pass

    def UpdateEntityShadow(self, ratio):
        """更新暗影能量显示 - 修复版"""
        if not self.entity_id or not client_sys:
            return

        # 计算新的数值
        shadow_data = int(round(100 * (1 - ratio)))

        # 1. 更新自身UI的绑定属性
        # 为了避免浮点数精度问题，可以四舍五入到2位小数
        self.entity_shadow = round(ratio, 2)
        self.shadowDataEntity = shadow_data
        self.UpdateScreen()

        # 2. 【关键修复】不再回调系统，避免循环调用
        # 系统已经通过setEntityShadowData更新了数据，这里只负责UI显示

        # 3. 调试日志
        logger.info("实体 %s UI更新，比例: %s, 数值: %s" % (self.entity_id, ratio, shadow_data))

    def Init(self):
        # 强制初始化为0
        self.entity_shadow = 1.0
        self.shadowDataEntity = 0
        self.UpdateScreen()

        print "[Debug] 实体 %s UI强制初始化为0" % self.entity_id

        # 然后从服务器请求最新数据
        if self.entity_id and client_sys:
            # 立即向服务器请求该实体的暗影能量数据
            client_sys.requestEntityShadowData(self.entity_id)

            # 同时，从本地获取一次（可能有延迟）
            entity_data = client_sys.getEntityShadowData(self.entity_id)
            if entity_data:
                ratio = entity_data.get("clip_ratio", 1.0)
                shadow_value = entity_data.get("shadow_data", 0)

                if shadow_value != 0:
                    print "[警告] 实体 %s 本地数据不为0: %s" % (self.entity_id, shadow_value)
                    # 仍然使用本地数据，但记录警告
                    self.entity_shadow = round(ratio, 2)
                    self.shadowDataEntity = shadow_value
                    self.UpdateScreen()

                print "[Debug] 实体 %s UI初始化完成，暗影能量: %s" % (self.entity_id, shadow_value)

    @ViewBinder.binding(ViewBinder.BF_BindFloat, '#entity_shadow')
    def ReturnShadow(self):
        # print "绑定函数ReturnShadow被调用，返回: %s" % val
        return float(self.entity_shadow)

    @ViewBinder.binding(ViewBinder.BF_BindString, '#shadow_data_entity')
    def ReturnShadowData(self):
        # 绑定到暗影能量数值文本
        # print "绑定函数ReturnShadowData被调用，返回: %s" % val
        return str(int(self.shadowDataEntity))