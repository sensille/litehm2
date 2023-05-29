OUTPUT_DIR=$(BUILD_DIR)/firmware

include $(BUILD_DIR)/software/include/generated/variables.mak
include $(SOC_DIRECTORY)/software/common.mak

L_OBJS=$(addprefix $(OUTPUT_DIR)/,crt0.o isr.o loader.o boot-helper.o flash.o tryload.o)
F_OBJS=$(addprefix $(OUTPUT_DIR)/,crt0.o isr.o main.o hostmot2.o flash.o util.o boot-helper.o eth.o)
OBJECTS=$(L_OBJS) $(F_OBJS)


all: $(OUTPUT_DIR)/firmware.bin $(OUTPUT_DIR)/loader.bin

# pull in dependency info for *existing* .o files
-include $(OBJECTS:.o=.d)

%.bin: %.elf
	$(OBJCOPY) -O binary $< $@
	chmod -x $@

$(OUTPUT_DIR)/firmware.elf: $(F_OBJS)
	$(CC) $(LDFLAGS) \
		-T linker-fw.ld \
		-N -o $@ \
		$(F_OBJS) \
		$(PACKAGES:%=-L$(BUILD_DIR)/software/%) \
		$(LIBS:lib%=-l%) -lbase -lcompiler_rt -llitespi
	chmod -x $@

$(OUTPUT_DIR)/loader.elf: $(L_OBJS)
	$(CC) $(LDFLAGS) \
		-T linker-ld.ld \
		-N -o $@ \
		$(L_OBJS) \
		$(PACKAGES:%=-L$(BUILD_DIR)/software/%) \
		$(LIBS:lib%=-l%) -lbase -lcompiler_rt
	chmod -x $@

$(OUTPUT_DIR)/main.o: main.c
	$(compile)

$(OUTPUT_DIR)/crt0.o: $(CPU_DIRECTORY)/crt0.S
	$(assemble)

$(OUTPUT_DIR)/boot-helper.o: $(CPU_DIRECTORY)/boot-helper.S
	$(compile)

$(OUTPUT_DIR)/%.o: %.c
	$(compile)

$(OUTPUT_DIR)/%.o: %.S
	$(assemble)

clean:
	$(RM) $(OBJECTS) $(OBJECTS:.o=.d) $(OUTPUT_DIR)/firmware.elf
	$(RM) $(OUTPUT_DIR)/firmware.bin $(OUTPUT_DIR)/loader.bin
	$(RM) $(OUTPUT_DIR)/loader.elf .*~ *~

.PHONY: all $(OUTPUT_DIR)/main.o clean load

# compile
# $(CC) -c $(CFLAGS) $(1) $< -o $(OUTPUT_DIR)/$@
# assemble
# $(CC) -c $(CFLAGS) -o $(OUTPUT_DIR)/$@ $<
