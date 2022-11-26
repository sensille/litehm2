#ifndef __HOSTMOT2_H__
#define __HOSTMOT2_H__

int hostmot2_packet(const void *data, int rlen, void *out, int outlen);

/*
 * eeprom layout, used to store configuration
 */
typedef struct _eeconfig {
	uint32_t magic;
	union {
		uint16_t m[0x40];
		struct {
			uint16_t reserved1;
			uint8_t mac[6];
			uint16_t reserved2[4];
			uint16_t cardname[8];
			uint32_t ipaddr;
			uint16_t netmwask[2];
			uint16_t debug_led_mode;
			uint16_t reserved3[3];
			uint16_t unused[0x28];
		} w;
	};
} eeconfig_t;
extern eeconfig_t eeconfig;

extern int do_reset;
extern int config_changed;

#endif
