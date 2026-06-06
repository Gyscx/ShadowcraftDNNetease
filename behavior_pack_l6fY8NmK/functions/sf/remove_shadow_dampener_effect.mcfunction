# Remove shadow dampener effect from entities
# This function is called after 60 seconds

# Use script block event to notify server about entities losing the effect
execute as @e[tag=has_shadow_dampener_effect] run scriptevent shadow_dampener_removed {"entityId":"@s"}

# Remove the effect tag from entities
tag @e[tag=has_shadow_dampener_effect] remove has_shadow_dampener_effect

# Notify players about the effect ending
tellraw @a [{"text":"§a暗影抑制效果§r结束了。","color":"gray"}]

# Clean up any remaining temporary tags
tag @e[tag=shadow_dampener_target] remove shadow_dampener_target