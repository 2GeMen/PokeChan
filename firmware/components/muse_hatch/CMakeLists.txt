# StackChan <-> Muse bridge. muse_chat_session.cpp, muse_chat.c, muse_chat_text.c,
# muse_text.c, muse_account_api.c and the muse_*.h headers come unchanged from
# facebookincubator/muse-gadget-sdk (Apache-2.0, see LICENSE.muse-gadget-sdk);
# muse_hatch_shim.c, muse_bridge.c, muse_ask.c and muse_state.h adapt them to
# StackChan; muse_chat.h, muse_chat_text.c (console hook), muse_chat_session.cpp
# (32-bit log formats, msg3 error detail) carry small marked changes.
idf_component_register(
    SRCS
        "muse_chat_session.cpp"
        "muse_chat.c"
        "muse_chat_text.c"
        "muse_text.c"
        "muse_account_api.c"
        "muse_hatch_shim.c"
        "muse_bridge.c"
        "muse_ask.c"
    INCLUDE_DIRS "include"
    PRIV_INCLUDE_DIRS "."
    PRIV_REQUIRES
        noise_core minimp3 json esp-tls esp_http_client mbedtls nvs_flash esp_wifi
        esp_driver_usb_serial_jtag esp_timer lwip
)

target_compile_features(${COMPONENT_LIB} PRIVATE cxx_std_17)
target_compile_options(${COMPONENT_LIB} PRIVATE
    $<$<COMPILE_LANGUAGE:CXX>:-fno-exceptions>
    -Wno-unused-function
    -Wno-format-truncation
)
