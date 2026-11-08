# DerenguhGram desktop module — integrate into the tdesktop CMake build.
# SPDX-License-Identifier: GPL-3.0-only
#
# tdesktop bundles Qt, OpenSSL and zlib. Add this directory from the top-level
# Telegram/CMakeLists.txt with:  add_subdirectory(path/to/desktop derenguh)
# then link the `derenguh_desktop` target into Telegram.exe.
cmake_minimum_required(VERSION 3.21)

find_package(Qt6 COMPONENTS Core Network Widgets REQUIRED)
find_package(OpenSSL REQUIRED)
find_package(ZLIB REQUIRED)

set(CMAKE_AUTOMOC ON)

add_library(derenguh_desktop STATIC
    src/derenguh_protocol.h
    src/derenguh_compression.h
    src/derenguh_compression.cpp
    src/derenguh_faketls.h
    src/derenguh_faketls.cpp
    src/derenguh_proxy.h
    src/derenguh_proxy.cpp
    src/clan_secrets_window.h
    src/clan_secrets_window.cpp
    src/privacy_settings.h
    src/privacy_settings.cpp
)

target_include_directories(derenguh_desktop PUBLIC src)
target_link_libraries(derenguh_desktop
    PUBLIC Qt6::Core Qt6::Network Qt6::Widgets
    PRIVATE OpenSSL::Crypto ZLIB::ZLIB
)
target_compile_features(derenguh_desktop PUBLIC cxx_std_17)

# tdesktop historically targets Qt 6.5+; if your fork is Qt5, swap Qt6 -> Qt5 above.
