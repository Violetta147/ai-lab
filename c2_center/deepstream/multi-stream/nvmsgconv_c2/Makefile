# Makefile for nvmsgconv_c2 payload builder
# Build inside DeepStream SDK environment (Linux/WSL2) where g++ and DeepStream
# headers/libs are available. This Makefile is a template.

CXX=g++
CXXFLAGS=-fPIC -O2 -std=c++17
LDFLAGS=-shared
TARGET=libnvds_msgconv_c2.so
SOURCES=c2_payload.cpp

all: $(TARGET)

$(TARGET): $(SOURCES)
	$(CXX) $(CXXFLAGS) -o $@ $(SOURCES) $(LDFLAGS)

clean:
	rm -f $(TARGET) *.o
