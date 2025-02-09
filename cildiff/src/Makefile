PREFIX ?= /usr

TARGET = cildiff
SRCS = $(sort $(wildcard *.c))
HDRS = $(sort $(wildcard *.h))
OBJS = $(patsubst %.c,%.o,$(SRCS))
CFLAGS ?= -std=c23 -Wall -Wextra -pedantic
ifdef DEBUG
CFLAGS += -g
endif

override CFLAGS += -D_GNU_SOURCE

override CFLAGS += \
	-I "../selinux/libsepol/cil/src/" \
	-I "../selinux/libsepol/cil/include/"

override CFLAGS += \
	$(shell pkg-config --cflags bzip2) \
	$(shell pkg-config --cflags openssl)

override LDLIBS += \
	$(shell pkg-config --libs bzip2) \
	$(shell pkg-config --libs openssl) \
	../selinux/libsepol/src/libsepol.a

all: $(TARGET)
.PHONY: all

$(TARGET): $(OBJS)

clean:
	$(RM) $(OBJS)
.PHONY: clean

distclean:
	$(RM) $(TARGET)
.PHONY: distclean

compile_commands.json: $(SRCS) $(HDRS)
	$(MAKE) clean
	$(MAKE) distclean
	bear -- $(MAKE)
