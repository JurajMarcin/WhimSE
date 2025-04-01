PREFIX ?= /usr
BINDIR ?= $(PREFIX)/bin

CILDIFF = cildiff
SRCS = $(sort $(wildcard *.c))
HDRS = $(sort $(wildcard *.h))
OBJS = $(patsubst %.c,%.o,$(SRCS))
ifdef DEBUG
override CFLAGS += -g
else
override CFLAGS += -Werror
endif

override CFLAGS += -std=c11 -pedantic -Wall -Wextra -D_GNU_SOURCE

override CFLAGS += \
	-I "../selinux/libsepol/include/" \
	-I "../selinux/libsepol/cil/src/" \
	-I "../selinux/libsepol/cil/include/"

override CFLAGS += \
	$(shell pkg-config --cflags bzip2) \
	$(shell pkg-config --cflags openssl)

override LDLIBS += \
	$(shell pkg-config --libs bzip2) \
	$(shell pkg-config --libs openssl) \
	../selinux/libsepol/src/libsepol.a


all: $(CILDIFF)
.PHONY: all


$(CILDIFF): $(OBJS) ../selinux/libsepol/src/libsepol.a


$(OBJS): $(HDRS)


../selinux/libsepol/src/libsepol.a:
	@echo "Use Makefile in parent directory to compile static libsepol"
	@exit 1


install:
	-mkdir -p $(DESTDIR)$(BINDIR)
	install -m 755 $(CILDIFF) $(DESTDIR)$(BINDIR)
.PHONY: install


clean:
	$(RM) $(OBJS)
.PHONY: clean


distclean:
	$(RM) $(CILDIFF)
.PHONY: distclean


compile_commands.json: $(SRCS) $(HDRS)
	$(MAKE) clean
	$(MAKE) distclean
	bear -- $(MAKE)
