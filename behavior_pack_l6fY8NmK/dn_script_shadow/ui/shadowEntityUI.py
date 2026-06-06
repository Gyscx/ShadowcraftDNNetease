# -*- coding: utf-8 -*-
import mod.client.extraClientApi as clientApi
from mod_log import logger
from .. import config

from ..client.shadow_clientSystem import ShadowClientSystem

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
        bind_entity_id = param.get("bindEntityId", None)
        self.entity_id = str(bind_entity_id) if bind_entity_id is not None else None

        print "实体头顶UI参数: %s" % param
        print "绑定的实体ID: %s" % self.entity_id
        print "UI实例ID: %d" % id(self)

        # UI路径
        self.mShadowPanel = "/shadowPanel"
        self.mProgressBar = self.mShadowPanel + "/progress_bar"
        self.mFilledProgressBar = self.mProgressBar + "/filled_progress_bar"
        self.mShadowData = self.mShadowPanel + "/shadow_data"

    def Create(self):
        pass

    def UpdateEntityShadow(self, ratio, effect=None):
        """更新暗影能量显示
        effect: "suppression"=暗影抑制(空), "charging"=暗影充能(满), None=正常
        """
        try:
            print "[Debug] UpdateEntityShadow: 实例=%d, entity_id=%s, ratio=%s, effect=%s" % (id(self), self.entity_id, ratio, effect)
            
            if not self.entity_id:
                print "[Error] entity_id 为空，无法更新！"
                return

            # 处理特殊效果
            if effect == "suppression":
                # 暗影抑制：能量条始终为空
                shadow_data = 0
                progress_value = 0.0
                print "[Debug] 暗影抑制效果：能量条为空"
            elif effect == "charging":
                # 暗影充能：能量条始终为满
                shadow_data = 100
                progress_value = 1.0
                print "[Debug] 暗影充能效果：能量条为满"
            else:
                # 正常状态
                shadow_data = int(round(100 * (1 - ratio)))
                progress_value = 1.0 - ratio
                print "[Debug] 正常状态：ratio=%s, shadow_data=%s" % (ratio, shadow_data)

            # 设置进度条 - /progress_bar
            progress_bar = self.GetBaseUIControl(self.mProgressBar)
            if progress_bar:
                progress_ctrl = progress_bar.asProgressBar()
                if progress_ctrl:
                    progress_ctrl.SetValue(progress_value)
                    print "[Debug] SetValue(%s)" % progress_value

            # 设置文本
            shadow_data_label = self.GetBaseUIControl(self.mShadowData)
            if shadow_data_label:
                label_ctrl = shadow_data_label.asLabel()
                if label_ctrl and hasattr(label_ctrl, 'SetText'):
                    label_ctrl.SetText(str(shadow_data))
                    print "[Debug] SetText(%s)" % shadow_data

            print "[Debug] UpdateEntityShadow 完成！"
            
            logger.info("实体 %s UI更新，效果: %s" % (self.entity_id, effect))
        except Exception as e:
            print "[Error] UpdateEntityShadow 异常: %s" % str(e)
            import traceback
            traceback.print_exc()

    def Init(self):
        # 初始化为空能量状态（shadow_data=0, clip_ratio=1）
        print "[Debug] 实体 %s UI初始化" % self.entity_id

        if self.entity_id and client_sys:
            client_sys.requestEntityShadowData(self.entity_id)
            entity_data = client_sys.getEntityShadowData(self.entity_id)
            if entity_data:
                ratio = entity_data.get("clip_ratio", 1.0)
                effect = entity_data.get("effect")
                print "[Debug] 实体 %s 收到初始数据: ratio=%s, effect=%s" % (self.entity_id, ratio, effect)
                # 使用 UpdateEntityShadow 统一更新
                self.UpdateEntityShadow(ratio, effect)
                print "[Debug] 实体 %s UI初始化完成" % self.entity_id