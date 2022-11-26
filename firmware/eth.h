#ifndef __ETH_H__
#define __ETH_H__

#include <stdint.h>

void eth_poll(void);
void eth_init(uint32_t own_ip, uint8_t own_mac[6]);

#endif
