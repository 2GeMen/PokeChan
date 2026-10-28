/*
 * The character shown as the main face: "stackchan" (the default face) or a Pokémon skin.
 * The choice is saved in NVS ("avatar"/"character") and restored at boot.
 */
#pragma once
#include <string>
#include <vector>

namespace avatar_character {

std::string current();
std::vector<std::string> names();
// Switches the face now and saves the choice; false for an unknown name or before the face exists
bool set(const std::string& name);

// Shows an expression (neutral, happy, angry, sad, doubt, sleepy, cool) for seconds, ignoring the
// emotions the chat sends meanwhile; false for an unknown expression
bool show_expression(const std::string& expression, int seconds);

}  // namespace avatar_character
