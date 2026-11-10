# Builds each distro's user-data into dist/, as docs/build.md describes.

MANIFESTS := $(sort $(wildcard src/manifests/*.json))
DISTROS := $(notdir $(basename $(MANIFESTS)))
USER_DATA := $(DISTROS:%=dist/%.user-data)
FRAGMENTS := $(wildcard src/fragments/*.user-data)

# make clean skips the checks, so it can run when the manifests are broken.
ifneq ($(MAKECMDGOALS),clean)
ifeq ($(MANIFESTS),)
$(error No manifests in src/manifests/)
endif

# WSL matches a user-data to an instance by name without regard to case, so two manifests whose names differ only in
# case would build the same instance's user-data.
CLASHES := $(shell printf '%s\n' $(DISTROS) | awk '{ n[tolower($$0)]++; s[tolower($$0)] = s[tolower($$0)] " " $$0 } END { for (k in n) if (n[k] > 1) printf "%s", s[k] }')
ifneq ($(CLASHES),)
$(error Manifests in src/manifests/ whose names differ only in case:$(CLASHES))
endif
endif

.DELETE_ON_ERROR:
.PHONY: build version clean

build: $(USER_DATA)

# Every fragment is a prerequisite, so a change to any of them rebuilds every user-data.
dist/%.user-data: src/manifests/%.json $(FRAGMENTS) scripts/user-data.sh scripts/manifest.jq
	scripts/user-data.sh $< $@

# Prints the version of the release, which every manifest shares. Fails when they differ.
version:
	@jq -nr -f scripts/version.jq $(MANIFESTS)

clean:
	rm -rf dist
