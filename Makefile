CONFIGS=$(wildcard configs/*.conf)
TARGETS=$(basename $(notdir $(CONFIGS)))
BITSTREAMS=$(addprefix bitstreams/,$(addsuffix .bit,$(TARGETS)))

all: $(BITSTREAMS)

bitstreams/%.bit: configs/%.conf
	make -f Makefile.target TARGET=$*

clean:
	rm -rf build bitstreams/*.bit bitstreams/*.bin
