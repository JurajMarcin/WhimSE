all: libsepol
	$(MAKE) -C src
.PHONY: all


libsepol:
	$(MAKE) -C selinux/libsepol/src libsepol.a
.PHONY: libsepol


install:
	$(MAKE) -C src install
.PHONY: install


clean:
	$(MAKE) -C src clean
.PHONY: clean


distclean:
	$(MAKE) -C src distclean
.PHONY: distclean
