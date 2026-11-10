UV ?= $(shell command -v uv)
PYTHON ?= $(realpath /usr/bin/python3)

.PHONY: venv sync build

# make build [filter]: the word after build is the filter for invoke build, so it gets an empty rule, not a target's.
ifeq ($(firstword $(MAKECMDGOALS)),build)
ifneq ($(word 3,$(MAKECMDGOALS)),)
$(error make build takes one filter at most)
endif
FILTER := $(word 2,$(MAKECMDGOALS))
ifneq ($(FILTER),)
$(eval $(FILTER):;@:)
endif
endif

venv: .venv/pyvenv.cfg

# uv has no setting for system site packages, so the venv gets them only when it's created.
.venv/pyvenv.cfg:
	$(if $(UV),,$(error uv command not found))
	$(if $(PYTHON),,$(error /usr/bin/python3 not found: set PYTHON to a Python interpreter))
	$(UV) venv --system-site-packages --python $(PYTHON)

sync: venv
	$(UV) sync

build: sync
	$(UV) run invoke build $(if $(FILTER),--filter '$(FILTER)')
