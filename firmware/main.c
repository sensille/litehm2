#include <generated/csr.h>
#include <generated/mem.h>

#include "hostmot2.h"
#include "debug.h"
#include "flash.h"
#include "util.h"
#include "tryload.h"
#include "eth.h"

#define HM2_UDP_PORT	27181
#undef WITH_LOADER


/* config block at the start of the last sector */
#define CONF_ADDR (SPIFLASH_SIZE - FLASH_ERASE_SIZE)
#define CONF_MAGIC 0xc0e13af2
eeconfig_t eeconfig;

static void reboot(void)
{
	ctrl_reset_write(1);
}

static void
uart_init(void)
{
	uart_ev_enable_write(0);
	uart_ev_pending_write(3);
}

int blocking_uart = 0;

#define TX_RING_SIZE 256
uint8_t tx_ring[TX_RING_SIZE];
int tx_ring_head = 0;
int tx_ring_tail = 0;
#define TX_NEXT(x) (((x) + 1) & (TX_RING_SIZE - 1))
static void
putc(const char c)
{
	while (TX_NEXT(tx_ring_head + 1) == tx_ring_tail) {
		/* full */
		if (!blocking_uart)
			return;
		if (!uart_rxempty_read()) {
			 uart_rxtx_read();
			uart_ev_pending_write(2);
		}
	}
	tx_ring[tx_ring_head] = c;
	tx_ring_head = TX_NEXT(tx_ring_head);
}

static void
uart_tx(void)
{
	if (tx_ring_head == tx_ring_tail)
		return;
	if (uart_txfull_read())
		return;

	uart_rxtx_write(tx_ring[tx_ring_tail]);
	tx_ring_tail = TX_NEXT(tx_ring_tail);
}

void
puts(const char *s)
{
	while (*s)
		putc(*s++);
}

static void
putnibble(const unsigned char n)
{
	putc(n >= 10 ? ('a' + n - 10) : '0' + n);
}

void
puthex8(const unsigned char h)
{
	putnibble(h >> 4);
	putnibble(h & 15);
}

void
puthex16(uint16_t h)
{
	puthex8(h >> 8);
	puthex8(h);
}

void
puthex32(uint32_t h)
{
	puthex8(h >> 24);
	puthex8(h >> 16);
	puthex8(h >> 8);
	puthex8(h);
}

void
hexdump(const void *_d, int l)
{
	int n = 0;
	const uint8_t *d = _d;

	while (l > 0) {
		puthex8(*d++);
		putc(' ');
		--l;
		if (++n == 16) {
			puts("\n");
			n = 0;
		}
	}
	if (n != 0)
		puts("\n");
}

static void
write_config(void)
{
	flash_erase_sector(CONF_ADDR);
	flash_write_page(CONF_ADDR, (uint8_t *)&eeconfig, sizeof(eeconfig));
}

static void
read_config(void)
{
	uint8_t uuid[8];

	flash_read_page(CONF_ADDR, (uint8_t *)&eeconfig, sizeof(eeconfig));
	if (eeconfig.magic == CONF_MAGIC)
		return;

	puts("config magic not valid, using defaults\n");
	flash_read_uuid(uuid);
	memcpy(eeconfig.w.mac, uuid, 6);
	eeconfig.w.mac[0] |= 0x02;	/* make it a private mac addr */
	eeconfig.w.ipaddr = 0x0a0a0a0a;
	eeconfig.magic = CONF_MAGIC;
	write_config();
}

static void
flash_led(void)
{
	static uint16_t last_ustimer = 0;
	static int ms = 0;
	uint16_t ustimer;

	ustimer = hostmot2_ustimer_read();

	/* rough 1ms timing */
	if ((ustimer & ~0x3ff) == last_ustimer)
		return;
	last_ustimer = ustimer & ~0x3ff;
	++ms;
	if (ms < 100)
		leds_out_write(0);
	else
		leds_out_write(1);
	if (ms == 1000)
		ms = 0;
}

int
main(void)
{
	int c;

	uart_init();

	/* writes are blocking until the main loop runs */
	blocking_uart = 1;

	flash_init();
	read_config();

	puts("\nlitehm2 starting\n");
	puts("mac address: ");
	hexdump(eeconfig.w.mac, 6);
	puts("ip address:  ");
	puthex8(eeconfig.w.ipaddr >> 24);
	puts(" ");
	puthex8(eeconfig.w.ipaddr >> 16);
	puts(" ");
	puthex8(eeconfig.w.ipaddr >> 8);
	puts(" ");
	puthex8(eeconfig.w.ipaddr);
	puts("\n");

	eth_init(eeconfig.w.ipaddr, eeconfig.w.mac);

	leds_out_write(1);
	blocking_uart = 0;

	while (1) {
		eth_poll();
		uart_tx();

		c = -1;
		if (!uart_rxempty_read()) {
			c = uart_rxtx_read();
			uart_ev_pending_write(2);
		}

		if (c != -1) {
			puts("got ");
			putc(c);
			puts("\n");
		}
		if (c == 's') {
			puts(" ethmac errors 0x");
			puthex32(ethmac_sram_writer_errors_read());
			puts("\n");
		}
		if (c == 'r')
			reboot();
#ifdef WITH_LOADER
		if (c == 'l')
			tryload();
#endif

		if (do_reset)
			reboot();
		if (config_changed) {
			write_config();
			config_changed = 0;
		}

		flash_led();
	}
}
