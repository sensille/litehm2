BUILD_DIR=../build/

include $(BUILD_DIR)/software/include/generated/variables.mak
include $(SOC_DIRECTORY)/software/common.mak

L_OBJS=crt0.o isr.o loader.o boot-helper.o flash.o tryload.o
F_OBJS=crt0.o isr.o main.o hostmot2.o flash.o util.o boot-helper.o eth.o
OBJECTS=$(L_OBJS) $(F_OBJS)


all: firmware.bin loader.bin

# pull in dependency info for *existing* .o files
-include $(OBJECTS:.o=.d)

%.bin: %.elf
	$(OBJCOPY) -O binary $< $@
	chmod -x $@

firmware.elf: $(F_OBJS)
	$(CC) $(LDFLAGS) \
		-T linker-fw.ld \
		-N -o $@ \
		$(F_OBJS) \
		$(PACKAGES:%=-L$(BUILD_DIR)/software/%) \
		$(LIBS:lib%=-l%) -lbase -lcompiler_rt -llitespi
	chmod -x $@

loader.elf: $(L_OBJS)
	$(CC) $(LDFLAGS) \
		-T linker-ld.ld \
		-N -o $@ \
		$(L_OBJS) \
		$(PACKAGES:%=-L$(BUILD_DIR)/software/%) \
		$(LIBS:lib%=-l%) -lbase -lcompiler_rt
	chmod -x $@

main.o: main.c
	$(compile)

crt0.o: $(CPU_DIRECTORY)/crt0.S
	$(assemble)

boot-helper.o: $(CPU_DIRECTORY)/boot-helper.S
	$(assemble)

%.o: %.c
	$(compile)

%.o: %.S
	$(assemble)

clean:
	$(RM) $(OBJECTS) $(OBJECTS:.o=.d) firmware.elf firmware.bin .*~ *~

.PHONY: all main.o clean load
