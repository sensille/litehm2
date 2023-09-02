#include <generated/mem.h>
#include <generated/csr.h>
#include <generated/soc.h>

#include <bios/sfl.h>

#include "tryload.h"
#include "flash.h"

extern void boot_helper(unsigned long r1, unsigned long r2, unsigned long r3,
	unsigned long addr);

#ifndef CSR_LEDS_BASE
static void leds_out_write(int) {}
#endif

int
main(void)
{
#ifdef CSR_UART_BASE
	uart_ev_enable_write(0);
	uart_ev_pending_write(3);

	flash_init();

	tryload();
#endif

	/* jump to pre-loaded program in main_ram */
	boot_helper(0, 0, 0, MAIN_RAM_BASE);
}
