CXX:= g++
SRCS:= c2_payload.cpp
OBJS:= $(SRCS:.cpp=.o)
TARGET:= libnvds_msgconv_c2.so

# DeepStream 6.0 Paths
DS_SDK_ROOT:= /opt/nvidia/deepstream/deepstream-6.0
GLIB_CFLAGS:= $(shell pkg-config --cflags glib-2.0 json-glib-1.0)
GLIB_LIBS:= $(shell pkg-config --libs glib-2.0 json-glib-1.0)

CXXFLAGS:= -fPIC -O2 -std=c++17 -I$(DS_SDK_ROOT)/sources/includes $(GLIB_CFLAGS)
LDFLAGS:= -shared $(GLIB_LIBS)

all: $(TARGET)

$(TARGET): $(SRCS)
	$(CXX) $(CXXFLAGS) -o $@ $^ $(LDFLAGS)

clean:
	rm -f $(TARGET) $(OBJS)
