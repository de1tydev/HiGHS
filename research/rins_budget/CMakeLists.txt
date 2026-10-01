cmake_minimum_required(VERSION 3.15)
project(rins_budget_probe LANGUAGES CXX)

# Point HIGHS_DIR at one independently built, pinned HiGHS tree.
# Do not add this directory to the production solver build.
find_package(HIGHS CONFIG REQUIRED)
add_executable(milp_probe milp_probe.cpp)
target_compile_features(milp_probe PRIVATE cxx_std_11)
target_link_libraries(milp_probe PRIVATE highs::highs)
