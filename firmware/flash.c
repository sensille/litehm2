#include <generated/csr.h>
#include <generated/mem.h>

#include "debug.h"
#include "flash.h"

#ifdef CSR_SPIFLASH_CORE_BASE
#define MAC_ADDR (SPIFLASH_SIZE - 0x100)
#else
#define MAC_ADDR 0
#endif

#define IP_ADDR (MAC_ADDR + 16)

static int
spiflash_rx_ready_read(void)
{
	return (spiflash_core_master_status_read() >> CSR_SPIFLASH_CORE_MASTER_STATUS_RX_READY_OFFSET) & 1;
}

static void
spiflash_len_mask_width_write(uint32_t len, uint32_t width, uint32_t mask)
{
	uint32_t tmp;
	uint32_t word;

	tmp = len & ((2 ^ CSR_SPIFLASH_CORE_MASTER_PHYCONFIG_LEN_SIZE) - 1);
	word = tmp << CSR_SPIFLASH_CORE_MASTER_PHYCONFIG_LEN_OFFSET;
	tmp = width & ((2 ^ CSR_SPIFLASH_CORE_MASTER_PHYCONFIG_WIDTH_SIZE) - 1);
	word |= tmp << CSR_SPIFLASH_CORE_MASTER_PHYCONFIG_WIDTH_OFFSET;
	tmp = mask & ((2 ^ CSR_SPIFLASH_CORE_MASTER_PHYCONFIG_MASK_SIZE) - 1);
	word |= tmp << CSR_SPIFLASH_CORE_MASTER_PHYCONFIG_MASK_OFFSET;

	spiflash_core_master_phyconfig_write(word);
}

#ifdef CSR_SPIFLASH_CORE_BASE
/* for now transfer x1 */
static void
flash_transfer(const uint8_t *wr1, int wr1_len, const uint8_t *wr2, int wr2_len,
	int rd_skip, uint8_t *rd, int rd_len)
{
	uint32_t w;

	/* something is wrong then there are still rx bytes ready */
	while (spiflash_rx_ready_read()) {
		w = spiflash_core_master_rxtx_read();
	}
	spiflash_core_master_cs_write(1);
	while (rd_len > 0 || wr1_len > 0 || wr2_len > 0 || rd_skip > 0) {
		if (wr1_len > 0) {
			spiflash_core_master_rxtx_write(*wr1++);
			--wr1_len;
		} else if (wr2_len > 0) {
			spiflash_core_master_rxtx_write(*wr2++);
			--wr2_len;
		} else {
			spiflash_core_master_rxtx_write(0x00);
		}

		while (!spiflash_rx_ready_read())
			;

		w = spiflash_core_master_rxtx_read();

		if (rd_skip > 0) {
			--rd_skip;
		} else if (rd_len > 0) {
			*rd++ = w;
			--rd_len;
		}
	}
	spiflash_core_master_cs_write(0);
}
#else
static void
flash_transfer(const uint8_t *wr1, int wr1_len, const uint8_t *wr2, int wr2_len,
	int rd_skip, uint8_t *rd, int rd_len)
{
}
#endif

void
flash_read_uuid(uint8_t *uuid)
{
	uint8_t cmd = 0x4b;

	flash_transfer(&cmd, 1, 0, 0, 5, uuid, 8);
}

void
flash_read_id(uint8_t *id)
{
	uint8_t cmd = 0xab;

	flash_transfer(&cmd, 1, 0, 0, 4, id, 1);
}

static void
flash_wait_busy(void)
{
	uint8_t rbuf[1];
	uint8_t cmd = 0x05;

	do {
		flash_transfer(&cmd, 1, 0, 0, 1, rbuf, 1); /* read status */
	} while (rbuf[0] & 1);
}

void
flash_erase_sector(uint32_t addr)
{
	uint8_t cmd[4];

	cmd[0] = 0x06;
	flash_transfer(cmd, 1, 0, 0, 0, 0, 0); /* write enable */

	cmd[0] = 0x20;	 /* sector erase (4k) */
	cmd[1] = (addr >> 16) & 0xff;
	cmd[2] = (addr >> 8) & 0xff;
	cmd[3] = addr & 0xff;
	flash_transfer(cmd, 4, 0, 0, 0, 0, 0);
	flash_wait_busy();
}

void
flash_erase_block64(uint32_t addr)
{
	uint8_t cmd[4];

	cmd[0] = 0x06;
	flash_transfer(cmd, 1, 0, 0, 0, 0, 0); /* write enable */

	cmd[0] = 0xd8;	 /* block erase (64k) */
	cmd[1] = (addr >> 16) & 0xff;
	cmd[2] = (addr >> 8) & 0xff;
	cmd[3] = addr & 0xff;
	flash_transfer(cmd, 4, 0, 0, 0, 0, 0);
	flash_wait_busy();
}

void
flash_write_page(uint32_t addr, const uint8_t *data, int len)
{
	uint8_t cmd[4];

	cmd[0] = 0x06;
	flash_transfer(cmd, 1, 0, 0, 0, 0, 0); /* write enable */

	cmd[0] = 0x02;
	cmd[1] = (addr >> 16) & 0xff;
	cmd[2] = (addr >> 8) & 0xff;
	cmd[3] = addr & 0xff;
	flash_transfer(cmd, 4, data, len, 0, 0, 0); /* write data */

	flash_wait_busy();
}

void
flash_read_page(uint32_t addr, uint8_t *data, int len)
{
	uint8_t cmd[4];

	cmd[0] = 0x0b;
	cmd[1] = (addr >> 16) & 0xff;
	cmd[2] = (addr >> 8) & 0xff;
	cmd[3] = addr & 0xff;
	flash_transfer(cmd, 4, 0, 0, 5, data, len);
}

void
flash_init(void)
{
#ifdef CSR_SPIFLASH_CORE_BASE
#ifdef SPIFLASH_MODULE_DUMMY_BITS
	spiflash_dummy_bits_setup(SPIFLASH_MODULE_DUMMY_BITS);
#endif
	spiflash_phy_clk_divisor_write(4);	/* XXX not needed */
	spiflash_len_mask_width_write(8, 1, 1);
#endif
}
