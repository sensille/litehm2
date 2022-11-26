#include <generated/csr.h>
#include <generated/soc.h>
#include <irq.h>
#include <uart.h>

void isr(void);

#ifdef CONFIG_CPU_HAS_INTERRUPT

void isr(void)
{
	__attribute__((unused)) unsigned int irqs;

	irqs = irq_pending() & irq_getmask();

#if 0
#ifndef UART_POLLING
	if(irqs & (1 << UART_INTERRUPT))
		uart_isr();
#endif
#endif
}

#else

void isr(void){};

#endif
