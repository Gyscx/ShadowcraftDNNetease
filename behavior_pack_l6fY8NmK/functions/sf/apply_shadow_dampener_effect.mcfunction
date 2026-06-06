# Apply shadow dampener effect to entities in range
# This function will be called when splash potion hits

# Store the affected entities temporarily
tag @e[r=3,type=!player] add shadow_dampener_target

# Notify players about the effect
tellraw @a [{"text":"§a暗影抑制喷溅药水§r在附近爆炸了！","color":"yellow"}]

# Use script block event to notify server about entities getting the effect
execute as @e[tag=shadow_dampener_target] run scriptevent shadow_dampener_applied {"entityId":"@s"}

# Schedule the removal of the effect after 60 seconds (1200 ticks)
schedule function sf:remove_shadow_dampener_effect 1200t

# Add a marker tag to indicate the entity has the effect
execute as @e[tag=shadow_dampener_target] run tag @s add has_shadow_dampener_effect

# Clean up temporary tag
tag @e[tag=shadow_dampener_target] remove shadow_dampener_target