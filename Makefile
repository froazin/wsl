# Builds the user-data from the fragments, as docs/build.md describes.

FRAGMENTS := $(sort $(wildcard src/fragments/*.user-data))
USER_DATA := dist/Ubuntu.user-data

ifeq ($(FRAGMENTS),)
ifneq ($(MAKECMDGOALS),clean)
$(error No fragments in src/fragments/)
endif
endif

# A fragment whose first line is the Jinja header is a jinja2 part, and any other a cloud-config part.
JINJA_HEADER := \#\# template: jinja
# The x keeps an empty first line from matching.
part_type = $(if $(subst $(JINJA_HEADER)x,,$(shell head -n 1 $(1))x),cloud-config,jinja2)

# make-mime picks a random MIME boundary on every build. Replacing it with a fixed one makes the same fragments build
# the same file, so a release can compare hashes. Every part is base64, so the boundary can't appear in one.
BOUNDARY := ==============wsl-user-data==

.DELETE_ON_ERROR:
.PHONY: build clean

build: $(USER_DATA)

# The folder is a prerequisite too, because its time changes when a fragment is added, removed or renamed. make-mime
# names each part after the path it's given, so it runs in the fragments' folder. A failed build leaves no user-data,
# old or new, and no temporary file.
$(USER_DATA): $(FRAGMENTS) src/fragments Makefile
	mkdir -p $(@D)
	rm -f $@ $@.tmp
	cd src/fragments && cloud-init devel make-mime $(foreach f,$(FRAGMENTS),--attach $(notdir $(f)):$(call part_type,$(f))) > "$(CURDIR)/$@.tmp" || { rm -f "$(CURDIR)/$@.tmp"; exit 1; }
	sed -E 's/={15}[0-9]+==/$(BOUNDARY)/g' $@.tmp > $@ || { rm -f $@.tmp; exit 1; }
	rm $@.tmp

clean:
	rm -rf dist
