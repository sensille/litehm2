#include <stdint.h>

#include "util.h"

void
memcpy(void *_dst, const void *_src, int len)
{
	uint8_t *dst = _dst;
	const uint8_t *src = _src;

	while (len--)
		*dst++ = *src++;
}
