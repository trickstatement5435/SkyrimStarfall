cmake_minimum_required(VERSION 3.24)

project(StarfallSite VERSION 1.0.0 LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 23)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_MSVC_RUNTIME_LIBRARY "MultiThreaded$<$<CONFIG:Debug>:Debug>DLL")

if(MSVC)
    add_compile_options(/permissive- /Zc:preprocessor /Zc:__cplusplus /EHsc /MP /utf-8 /bigobj)
    add_compile_definitions(WIN32_LEAN_AND_MEAN NOMINMAX UNICODE _UNICODE)
endif()

# CommonLibSSE-NG (alandtse fork, pinned release tag), same setup as the Gravity Gun plugin.
# All three runtimes are enabled so CI can download CommonLib's official prebuilt binary
# instead of compiling it. The plugin itself refuses to run on VR.
set(BUILD_TESTS OFF CACHE BOOL "" FORCE)
set(ENABLE_SKYRIM_SE ON CACHE BOOL "" FORCE)
set(ENABLE_SKYRIM_AE ON CACHE BOOL "" FORCE)
set(ENABLE_SKYRIM_VR ON CACHE BOOL "" FORCE)
set(COMMONLIB_PREBUILT_MULTICONFIG ON CACHE BOOL "" FORCE)  # we only ever build Release

include(FetchContent)
FetchContent_Declare(
    CommonLibSSE
    GIT_REPOSITORY https://github.com/alandtse/CommonLibSSE-NG.git
    GIT_TAG v10.1.0
    GIT_SHALLOW TRUE
)
FetchContent_MakeAvailable(CommonLibSSE)
if(NOT COMMAND add_commonlibsse_plugin)
    include("${commonlibsse_SOURCE_DIR}/cmake/CommonLibSSE.cmake")
endif()

add_commonlibsse_plugin(${PROJECT_NAME}
    NAME "StarfallSite"
    AUTHOR "Ashton"
    SOURCES
        src/plugin.cpp
        src/Config.cpp
        src/Forms.cpp
        src/Json.cpp
        src/Papyrus.cpp
        src/Spawner.cpp
        src/Pounce.cpp
        src/Site.cpp
        src/Dialogue.cpp
        src/Gate.cpp
        src/Save.cpp
)
target_precompile_headers(${PROJECT_NAME} PRIVATE src/PCH.h)
target_include_directories(${PROJECT_NAME} PRIVATE src)
