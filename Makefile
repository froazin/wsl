# Builds the user-data from the fragments, as docs/build.md describes.

FRAGMENTS := $(sort $(wildcard src/*.user-data))
USER_DATA := dist/Ubuntu.user-data

ifeq ($(FRAGMENTS),)
ifneq ($(MAKECMDGOALS),clean)
$(error No fragments in src/)
endif
endif

# A fragment whose first line is the Jinja header is a jinja2 part, and any other a cloud-config part.
JINJA_HEADER := \#\# template: jinja
# The x keeps an empty first line from matching.
part_type = $(if $(subst $(JINJA_HEADER)x,,$(shell head -n 1 $(1))x),cloud-config,jinja2)

# make-mime picks a random MIME boundary on every build. Replacing it with a fixed one makes the same fragments build
# the same file, so a release can compare hashes. Every part is base64, so the boundary can't appear in one.
BOUNDARY := ==============wsl-user-data==

# Each file in test/ is instance data that make lint renders every fragment with.
LINT_CASES := $(wildcard test/*.json)

.DELETE_ON_ERROR:
.PHONY: build lint clean

build: $(USER_DATA)

# The folder is a prerequisite too, because its time changes when a fragment is added, removed or renamed. make-mime
# names each part after the path it's given, so it runs in src/. A failed build leaves no user-data, old or new, and
# no temporary file.
$(USER_DATA): $(FRAGMENTS) src Makefile
	mkdir -p $(@D)
	rm -f $@ $@.tmp
	cd src && cloud-init devel make-mime $(foreach f,$(FRAGMENTS),--attach $(notdir $(f)):$(call part_type,$(f))) > "$(CURDIR)/$@.tmp" || { rm -f "$(CURDIR)/$@.tmp"; exit 1; }
	sed -E 's/={15}[0-9]+==/$(BOUNDARY)/g' $@.tmp > $@ || { rm -f $@.tmp; exit 1; }
	rm $@.tmp

# Writes each fragment as cloud-init reads it with each case's instance data, rendered when it's a Jinja fragment, to
# dist/lint/<case>/, then checks every result with yamllint and cloud-init's schema.
lint:
	rm -rf dist/lint
	for c in $(LINT_CASES); do \
		d=dist/lint/$$(basename $$c .json); mkdir -p $$d; \
		for f in $(FRAGMENTS); do \
			o=$$d/$$(basename $$f .user-data).yaml; \
			if [ "$$(head -n 1 $$f)" = "$(JINJA_HEADER)" ]; then \
				cloud-init devel render --instance-data $$c $$f > $$o || exit 1; \
			else \
				cp $$f $$o; \
			fi; \
		done; \
	done
	yamllint --strict dist/lint
	for o in dist/lint/*/*.yaml; do cloud-init schema -c $$o || exit 1; done

clean:
	rm -rf dist
