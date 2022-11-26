#ifndef __DEBUG_H__
#define __DEBUG_H__

#include <stdint.h>

void puts(const char *s);
void puthex8(uint8_t h);
void puthex16(uint16_t h);
void puthex32(uint32_t h);
void hexdump(const void *d, int l);

#endif
