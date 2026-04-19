# -*- coding: utf-8 -*-
ModName = "shadow_craft"
ModVersion = '0.0.1'

ServerSystemName = "ShadowSystem"
ServerSystemClsPath = "dn_script_shadow.server.shadow_serverSystem.ShadowServerSystem"

ClientSystemName = "ShadowSystem"
ClientSystemClsPath = "dn_script_shadow.client.shadow_clientSystem.ShadowClientSystem"

UiInitFinishedEvent = "UiInitFinished"
DamageEvent = "DamageEvent"
PlayerAttackEntityEvent = "PlayerAttackEntityEvent"
ScriptTickClientEvent = "OnScriptTickClient"
OnKeyPressInGame = "OnKeyPressInGame"
ServerSkillEvent = "ServerSkillEvent"
ClientItemTryUseEvent = "ClientItemTryUseEvent"
ClientUseShadowEnergyEvent = "ClientUseShadowEnergyEvent"
AddShadowEnergyEvent = "AddShadowEnergyEvent"

shadowUIName = "shadow_energy"
shadowUIPyClsPath = "dn_script_shadow.ui.shadowUI.ShadowScreenUI"
shadowUIScreenDef = "shadow_energy.main"

# 在config.py中添加以下配置
# 技能配置列表 - 核心数据结构
SKILL_CONFIGS = [
    {
        "skill_id": "helmet",
        "key_mapping_name": "shadow_helmet_ability",
        "default_key": 73,  # I键
        "ui_button_path": "/shadowPanel/shadow_ability/helmet_ability",
        "pc_key_label": "I",  # PC端显示按键
        "cooldown": 5.0,
        "energy_cost": 20,
        # 新增：该技能可接受的物品列表
        "valid_items": [
            {
                "item_identifier": "sf:eye_of_time",
                "item_slot_type": "armor",
                "hotbar_slot": -1,
                "texture_name": "eruption",  # 使用 eruption 贴图
                "server_commands": [
                    "/damage @e[r=3,type=!player] 30 entity_attack entity @s",
                    "/playanimation @s animation.player.eruption",
                    "/camerashake add @s 2 0.1",
                    "/playsound mob.shulker.shoot @s",
                    "/execute as @s at @s run particle sf:eruption"
                ]
            },
            {
                "item_identifier": "sf:crescent_visor",
                "item_slot_type": "armor",
                "hotbar_slot": -1,
                "texture_name": "shadow_blast",  # 使用 shadow_blast 贴图
                "server_commands": [
                    "/damage @e[r=3,type=!player] 30 entity_attack entity @s",
                    "/playanimation @s animation.player.eruption",
                    "/camerashake add @s 2 0.1",
                    "/playsound mob.shulker.shoot @s",
                    "/execute as @s at @s run particle sf:eruption"
                ]
            }
        ]
    },
    {
        "skill_id": "armor",
        "key_mapping_name": "shadow_armor_ability",
        "default_key": 75,  # K键
        "ui_button_path": "/shadowPanel/shadow_ability/armor_ability",
        "pc_key_label": "K",  # PC端显示按键
        "cooldown": 5.0,
        "energy_cost": 20,
        # 修改为valid_items格式
        "valid_items": [
            {
                "item_identifier": "sf:burden_of_loneliness",
                "item_slot_type": "armor",
                "hotbar_slot": -1,
                "texture_name": "blast",  # 原texture_name字段的值
                "server_commands": [
                    "/damage @e[r=3,type=!player] 30 entity_attack entity @s",
                    "/playanimation @s animation.player.eruption",
                    "/camerashake add @s 2 0.1",
                    "/playsound mob.shulker.shoot @s",
                    "/execute as @s at @s run particle sf:eruption"
                ]
            }
        ]
    },
    {
        "skill_id": "weapon",
        "key_mapping_name": "shadow_weapon_ability",
        "default_key": 74,  # J键
        "ui_button_path": "/shadowPanel/shadow_ability/weapon_ability",
        "pc_key_label": "J",  # PC端显示按键
        "cooldown": 5.0,
        "energy_cost": 20,
        # 修改为valid_items格式
        "valid_items": [
            {
                "item_identifier": "minecraft:bow",
                "item_slot_type": "hotbar",
                "hotbar_slot": 0,  # 快捷栏第1格
                "texture_name": "shadow_onslaught",  # 原texture_name字段的值
                "server_commands": [
                    "/damage @e[r=3,type=!player] 30 entity_attack entity @s",
                    "/playanimation @s animation.player.eruption",
                    "/camerashake add @s 2 0.1",
                    "/playsound mob.shulker.shoot @s",
                    "/execute as @s at @s run particle sf:eruption"
                ]
            }
        ]
    },
    {
        "skill_id": "RW",
        "key_mapping_name": "shadow_RW_ability",
        "default_key": 76,  # L键
        "ui_button_path": "/shadowPanel/shadow_ability/rangedWeapon_ability",
        "pc_key_label": "L",  # PC端显示按键
        "cooldown": 5.0,
        "energy_cost": 20,
        # 修改为valid_items格式
        "valid_items": [
            {
                "item_identifier": "minecraft:arrow",
                "item_slot_type": "hotbar",
                "hotbar_slot": 1,  # 快捷栏第2格
                "texture_name": "shadow_blast",  # 原texture_name字段的值
                "server_commands": [
                    "/playsound mob.shulker.shoot @s",
                    "/playanimation @s animation.player.shadow_blast.particle none 0 \"0\" sf:s1",
                    "/playanimation @s animation.player.shadow_blast none 0 \"0\" sf:s2",
                ]
            }
        ]
    }
]

# 技能状态枚举
SKILL_STATE = {
    "READY": 0,  # 就绪
    "COOLDOWN": 1,  # 冷却中
    "NO_ITEM": 2,  # 无物品
    "NO_ENERGY": 3  # 能量不足
}
