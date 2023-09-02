/*
 * This file is Copyright (c) 2014-2021 Florent Kermarrec <florent@enjoy-digital.fr>
 * This file is Copyright (c) 2013-2014 Sebastien Bourdeauducq <sb@m-labs.hk>
 * This file is Copyright (c) 2018 Ewen McNeill <ewen@naos.co.nz>
 * This file is Copyright (c) 2018 Felix Held <felix-github@felixheld.de>
 * This file is Copyright (c) 2019 Gabriel L. Somlo <gsomlo@gmail.com>
 * This file is Copyright (c) 2017 Tim 'mithro' Ansell <mithro@mithis.com>
 * This file is Copyright (c) 2018 William D. Jones <thor0505@comcast.net>
 * This file is Copyright (c) 2022 Arne Jansen <arne@die-jansens.de>
 * License: BSD
 */

#include <generated/mem.h>
#include <generated/csr.h>
#include <generated/soc.h>

#include <bios/sfl.h>

#include "tryload.h"
#include "flash.h"

enum {
	ACK_TIMEOUT,
	ACK_CANCELLED,
	ACK_OK
};

#define ACK_TIMEOUT_DELAY (CONFIG_CLOCK_FREQUENCY / 4)
#define CMD_TIMEOUT_DELAY (CONFIG_CLOCK_FREQUENCY / 16)

extern void boot_helper(unsigned long r1, unsigned long r2, unsigned long r3,
	unsigned long addr);

static unsigned short
crc16(const unsigned char* data_p, int length)
{
	unsigned char x;
	unsigned short crc = 0;

	while (length--) {
		x = crc >> 8 ^ *data_p++;
		x ^= x >> 4;
		crc = (crc << 8) ^
		      ((unsigned short)(x << 12)) ^
		      ((unsigned short)(x <<5)) ^
		      ((unsigned short)x);
	}

	return crc;
}

static
void timer0_load(unsigned int value) {
	timer0_en_write(0);
	timer0_reload_write(0);
	timer0_load_write(value);
	timer0_en_write(1);
	timer0_update_value_write(1);
}

static void
uart_write(char c)
{
#ifdef CSR_UART_BASE
	while (uart_txfull_read())
		;

	uart_rxtx_write(c);
#endif
}

static void
putstr(const char *s)
{
	while (*s)
		uart_write(*s++);
}

static char
uart_read(void)
{
#ifdef CSR_UART_BASE
	char c = uart_rxtx_read();

	uart_ev_pending_write(2);

	return c;
#else
	return 0;
#endif
}

static int
uart_read_nonblock(void)
{
#ifdef CSR_UART_BASE
	return uart_rxempty_read() == 0;
#else
	return 0;
#endif
}

static void
uart_drain(void)
{
#ifdef CSR_UART_BASE
	while (uart_read_nonblock())
		uart_read();
	while (!uart_txempty_read())
		;
#endif
}

static void
fatal(const char *msg)
{
	uart_drain();
	while (1) {
		putstr("FATAL, loader aborting: ");
		putstr(msg);
		putstr("\n\n");
	}
}

static int
check_ack(void)
{
	int recognized = 0;
	static const char str[SFL_MAGIC_LEN + 1] = SFL_MAGIC_ACK;

	timer0_load(ACK_TIMEOUT_DELAY);
	while(timer0_value_read()) {
		if(uart_read_nonblock()) {
			char c = uart_read();

			if((c == 'Q') || (c == '\e'))
				return ACK_CANCELLED;
			if(c == str[recognized]) {
				recognized++;
				if(recognized == SFL_MAGIC_LEN)
					return ACK_OK;
			} else {
				if(c == str[0])
					recognized = 1;
				else
					recognized = 0;
			}
		}
		timer0_update_value_write(1);
	}
	return ACK_TIMEOUT;
}


static void
copy_frame(uint32_t dstaddr, uint8_t *src, int len)
{
	uint8_t *dst;
	uint8_t readback[32];

#ifdef CSR_SPIFLASH_CORE_BASE
	if (dstaddr < SPIFLASH_BASE ||
	    dstaddr >= (SPIFLASH_BASE + SPIFLASH_SIZE)) {
		dst = (uint8_t *)dstaddr;
		while (len--)
			*dst++ = *src++;
		return;
	}
	/*
	 * write to flash
	 */
	dstaddr -= SPIFLASH_BASE;
	/* split on page border */
	while (len > 0) {
		int i;
		int j;
		int l;
		uint32_t end;

		/* find start of next page */
		end = (dstaddr + FLASH_PAGE_SIZE) & ~(FLASH_PAGE_SIZE - 1);
		if (end > dstaddr + len)
			end = dstaddr + len;
		l = end - dstaddr;
		/*
		 * erase sector first when we are at the beginning of
		 * the sector
		 */
		if ((dstaddr & (FLASH_ERASE_SIZE - 1)) == 0)
			flash_erase_sector(dstaddr);
		flash_write_page(dstaddr, src, l);
		/*
		 * read back and compare. To save RAM we read in blocks
		 * of 32 bytes.
		 */
		for (i = 0; i < l; i += 32) {
			int rl = (l - i) > 32 ? 32 : (l - i);

			flash_read_page(dstaddr + i, readback, rl);
			for (j = 0; j < rl; ++j) {
				if (readback[j] != src[i + j])
					fatal("writing to flash failed!");
			}
		}
		src += l;
		dstaddr += l;
		len -= l;
	}
#else
	dst = (uint8_t *)dstaddr;
	while (len--)
		*dst++ = *src++;
#endif
}

static uint32_t
get_uint32(unsigned char *data)
{
	return ((uint32_t)data[0] << 24) |
	       ((uint32_t)data[1] << 16) |
	       ((uint32_t)data[2] <<  8) |
		(uint32_t)data[3];
}

#define MAX_FAILURES 256

void
tryload(void)
{
	struct sfl_frame frame;
	int failures;
	static const char str[SFL_MAGIC_LEN + 1] = SFL_MAGIC_REQ;
	const char *c;
	int ack_status;

	/* Send the serialboot "magic" request to Host and wait for ACK_OK */
	c = str;
	while(*c) {
		uart_write(*c);
		c++;
	}
	ack_status = check_ack();
	if(ack_status == ACK_TIMEOUT || ack_status == ACK_CANCELLED)
		return;

	/* Assume ACK_OK */
	failures = 0;
	while(1) {
		int i;
		int timeout;
		int computed_crc;
		int received_crc;

		/* Get one Frame */
		i = 0;
		timeout = 1;
		while((i == 0) || timer0_value_read()) {
			if (uart_read_nonblock()) {
				if (i == 0) {
					timer0_load(CMD_TIMEOUT_DELAY);
					frame.payload_length = uart_read();
				}
				if (i == 1)
					frame.crc[0] = uart_read();
				if (i == 2)
					frame.crc[1] = uart_read();
				if (i == 3)
					frame.cmd = uart_read();
				if (i >= 4) {
					frame.payload[i-4] = uart_read();
					if (i == frame.payload_length + 4 - 1) {
						timeout = 0;
						break;
					}
				}
				i++;
			}
			timer0_update_value_write(1);
		}

		/* Check Timeout */
		if (timeout) {
			/*
			 * Acknowledge the Timeout and continue with a new frame
			 */
			uart_write(SFL_ACK_ERROR);
			continue;
		}

		/* Check Frame CRC */
		received_crc = ((int)frame.crc[0] << 8) | (int)frame.crc[1];
		computed_crc = crc16(&frame.cmd, frame.payload_length + 1);
		if (computed_crc != received_crc) {
			/* Acknowledge the CRC error */
			uart_write(SFL_ACK_CRCERROR);

			/* Increment failures and exit when max is reached */
			failures++;
			if(failures == MAX_FAILURES)
				return;
			continue;
		}

		/* Execute Frame CMD */
		switch(frame.cmd) {
		case SFL_CMD_ABORT:
			/* Reset failures */
			failures = 0;
			/* Acknowledge and exit */
			uart_write(SFL_ACK_SUCCESS);
			return;

		case SFL_CMD_LOAD: {
			/* Reset failures */
			failures = 0;

			/* Copy payload */
			copy_frame(get_uint32(&frame.payload[0]),
				frame.payload + 4, frame.payload_length - 4);

			/* Acknowledge and continue */
			uart_write(SFL_ACK_SUCCESS);
			break;
		}
		case SFL_CMD_JUMP: {
			uint32_t jump_addr;

			/* Reset failures */
			failures = 0;

			/* Acknowledge and jump */
			uart_write(SFL_ACK_SUCCESS);
			jump_addr = get_uint32(&frame.payload[0]);
			boot_helper(0, 0, 0, jump_addr);
			break;
		}
		default:
			/* Increment failures */
			failures++;

			/* Acknowledge the UNKNOWN cmd */
			uart_write(SFL_ACK_UNKNOWN);

			/* Increment failures and exit when max is reached */
			if(failures == MAX_FAILURES)
				return;

			break;
		}
	}
	uart_drain();
}
