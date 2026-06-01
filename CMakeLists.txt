cmake_minimum_required(VERSION 3.16.3...3.19.7 FATAL_ERROR)

project(CameraAxisAutoReslice)

#-----------------------------------------------------------------------------
# Extension metadata
set(EXTENSION_HOMEPAGE "https://github.com/your-github-username/CameraAxisAutoReslice")
set(EXTENSION_CATEGORY "IGT")
set(EXTENSION_CONTRIBUTORS "Your Name")
set(EXTENSION_DESCRIPTION "A 3D Slicer scripted module for automatic camera-axis oblique MRI reslicing from a cortical surface view.")
set(EXTENSION_ICONURL "")
set(EXTENSION_SCREENSHOTURLS "")
set(EXTENSION_DEPENDS "")

#-----------------------------------------------------------------------------
find_package(Slicer REQUIRED)
include(${Slicer_USE_FILE})

#-----------------------------------------------------------------------------
add_subdirectory(CameraAxisAutoReslice)

#-----------------------------------------------------------------------------
include(${Slicer_EXTENSION_GENERATE_CONFIG})
include(${Slicer_EXTENSION_CPACK})

