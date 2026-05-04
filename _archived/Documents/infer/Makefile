cc        := g++
nvcc      = /usr/local/cuda/bin/nvcc

include_paths := src        \
			/usr/include/eigen3 \
			/usr/include/opencv4 \
			/usr/include/aarch64-linux-gnu \
			/usr/local/cuda/include

library_paths := /usr/lib/aarch64-linux-gnu \
			/usr/local/cuda/lib64

link_librarys := opencv_core opencv_imgproc opencv_videoio opencv_imgcodecs opencv_highgui \
			nvinfer nvinfer_plugin nvonnxparser \
			cuda cublas cudart cudnn \
			stdc++ dl

cppstrict := -Wall -Werror -Wextra -Wno-deprecated-declarations -Wno-unused-parameter
custrict  := -Werror=all-warnings
cpp_compile_flags := -std=c++11 -fPIC -g -fopenmp $(cppstrict) -O0
cu_compile_flags  := -std=c++11 $(custrict) -O0 -Xcompiler "$(cpp_compile_flags)"
link_flags        := -pthread -fopenmp -Wl,-rpath='$$ORIGIN'

target := main
build_dir := build

cpp_sources := src/main.cpp \
	src/bt_kalman.cpp \
	src/bt_strack.cpp \
	src/bt_byte_tracker.cpp \
	src/traffic_analyzer.cpp
cu_sources := src/infer.cu src/yolo.cu

cpp_objects := $(cpp_sources:src/%.cpp=$(build_dir)/%.o)
cu_objects  := $(cu_sources:src/%.cu=$(build_dir)/%.o)
objects     := $(cpp_objects) $(cu_objects)

cpp_includes := $(addprefix -I, $(include_paths))
lib_paths    := $(addprefix -L, $(library_paths))
link_libs    := $(addprefix -l, $(link_librarys))

.PHONY: all run clean

all: $(target)

$(build_dir):
	mkdir -p $(build_dir)

$(build_dir)/%.o: src/%.cpp | $(build_dir)
	$(cc) $(cpp_compile_flags) $(cpp_includes) -c $< -o $@

$(build_dir)/%.o: src/%.cu | $(build_dir)
	$(nvcc) $(cu_compile_flags) $(cpp_includes) -c $< -o $@

$(target): $(objects)
	$(cc) -o $@ $^ $(lib_paths) $(link_libs) $(link_flags)

run: $(target)
	./$(target)

clean:
	rm -rf $(build_dir) $(target)
