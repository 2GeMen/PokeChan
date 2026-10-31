/*
 * SPDX-FileCopyrightText: 2026 M5Stack Technology CO LTD
 *
 * SPDX-License-Identifier: MIT
 */
#pragma once
#include <lvgl.h>
#include <string_view>

LV_FONT_DECLARE(MontserratSemiBold26);

extern const char ogg_camera_shutter_start[] asm("_binary_camera_shutter_ogg_start");
extern const char ogg_camera_shutter_end[] asm("_binary_camera_shutter_ogg_end");
static const std::string_view OGG_CAMERA_SHUTTER{
    static_cast<const char*>(ogg_camera_shutter_start),
    static_cast<size_t>(ogg_camera_shutter_end - ogg_camera_shutter_start)};

extern const char ogg_new_notification_start[] asm("_binary_new_notification_ogg_start");
extern const char ogg_new_notification_end[] asm("_binary_new_notification_ogg_end");
static const std::string_view OGG_NEW_NOTIFICATION{
    static_cast<const char*>(ogg_new_notification_start),
    static_cast<size_t>(ogg_new_notification_end - ogg_new_notification_start)};

extern const char ogg_im_here_start[] asm("_binary_im_here_ogg_start");
extern const char ogg_im_here_end[] asm("_binary_im_here_ogg_end");
static const std::string_view OGG_IM_HERE{
    static_cast<const char*>(ogg_im_here_start),
    static_cast<size_t>(ogg_im_here_end - ogg_im_here_start)};

namespace assets {

lv_image_dsc_t get_image(std::string_view name);

}  // namespace assets
