cmake_minimum_required(VERSION 3.15)
project(sqlmates_db)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

# ── Release build flags ────────────────────────────────────────────────────────
if(NOT CMAKE_BUILD_TYPE)
  set(CMAKE_BUILD_TYPE Release)
endif()
if(MSVC)
  add_compile_options(/O2 /W4)
else()
  add_compile_options(-O3 -Wall -Wextra -fPIC)
endif()

# ── Find Python + pybind11 ─────────────────────────────────────────────────────
find_package(Python3 REQUIRED COMPONENTS Interpreter Development)

# pybind11: try cmake package first, fall back to python -m pybind11
find_package(pybind11 CONFIG QUIET)
if(NOT pybind11_FOUND)
  execute_process(
    COMMAND "${Python3_EXECUTABLE}" -m pybind11 --cmakedir
    OUTPUT_VARIABLE PYBIND11_CMAKE_DIR
    OUTPUT_STRIP_TRAILING_WHITESPACE
  )
  find_package(pybind11 REQUIRED PATHS "${PYBIND11_CMAKE_DIR}")
endif()

message(STATUS "Python:   ${Python3_EXECUTABLE}")
message(STATUS "pybind11: ${pybind11_VERSION}")
message(STATUS "Build:    ${CMAKE_BUILD_TYPE}")

# ── Shared source files (storage layer — used by both modules) ─────────────────
set(SHARED_SOURCES
    disk_manager.cpp
    buffer_pool_manager.cpp
    data_file.cpp
)

# ── KD-Tree sources ────────────────────────────────────────────────────────────
set(KDTREE_SOURCES
    ${SHARED_SOURCES}
    lru_replacer.cpp
    kdtree_disk.cpp
    search_engine.cpp
    bind_kdtree.cpp         
)

# ── R-Tree sources ─────────────────────────────────────────────────────────────
set(RTREE_SOURCES
    ${SHARED_SOURCES}
    rtree_file.cpp
    rtree.cpp
    bind_rtree.cpp    
)

# ── Module 1: sqlmates_core  (KD-Tree) ────────────────────────────────────────
pybind11_add_module(sqlmates_core ${KDTREE_SOURCES})

target_include_directories(sqlmates_core PRIVATE ${CMAKE_CURRENT_SOURCE_DIR})

# Output goes to ../build/ (i.e. sqlmates_db/build/)
set_target_properties(sqlmates_core PROPERTIES
    LIBRARY_OUTPUT_DIRECTORY "${CMAKE_CURRENT_SOURCE_DIR}/../build"
)

# ── Module 2: rtree_core  (R-Tree) ────────────────────────────────────────────
pybind11_add_module(rtree_core ${RTREE_SOURCES})

target_include_directories(rtree_core PRIVATE ${CMAKE_CURRENT_SOURCE_DIR})

set_target_properties(rtree_core PROPERTIES
    LIBRARY_OUTPUT_DIRECTORY "${CMAKE_CURRENT_SOURCE_DIR}/../build"
)

# ── Print summary ──────────────────────────────────────────────────────────────
message(STATUS "")
message(STATUS "Targets:")
message(STATUS "  sqlmates_core → ../build/sqlmates_core*.so  (KD-Tree)")
message(STATUS "  rtree_core    → ../build/rtree_core*.so     (R-Tree)")
message(STATUS "")