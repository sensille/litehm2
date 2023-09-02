#include <generated/csr.h>
#include <generated/mem.h>

#include "hostmot2.h"
#include "debug.h"
#include "util.h"
#include "flash.h"

#define DEBUG

#ifdef DEBUG
#define DBG(x) puts x
#else
#define DBG(x)
#endif

#define LBPWriteMask		0x8000
#define LBPAddrThereMask	0x4000
#define LBPContMask		0x2000
#define LBPMemMask		0x1c00
#define LBPMemShift		10
#define LBPSizeMask		0x0300
#define LBPSizeShift		8
#define LBPAddrIncMask		0x0080
#define LBPCountMask		0x007f
#define LBPCountShift		0

#define E_PARSE	-2
#define E_MEM	-3
#define E_WRITE	-4

static uint32_t fladdr;
int do_reset = 0;
int config_changed = 0;

static union {
	uint16_t m[16];
	struct _mem4 {
		uint16_t ustimer;	/* overlayed */
		uint16_t uwait;
		uint16_t htimeout;
		uint16_t refoutwait;	/* overlayed */
		uint16_t htimer1wait;	/* overlayed */
		uint16_t htimer2wait;	/* overlayed */
		uint16_t htimer3wait;	/* overlayed */
		uint16_t htimer4wait;	/* overlayed */
		uint16_t scratch4[8];
	} w;
} mem4;

#define TIMEOUTBIT	0x20
#define PARSEERRBIT	0x01
#define MEMERRBIT	0x02
#define WRITEERRBIT	0x04
static union {
	uint16_t m[15];
	struct _mem6 {
		uint16_t errorreg;
		uint16_t lbpparseerrors;
		uint16_t lbpmemerrors;
		uint16_t lbpwriteerrors;
		uint16_t recvpktcount;
		uint16_t recvudpcount;
		uint16_t recvbadcount;
		uint16_t sendpktcount;
		uint16_t sendudpcount;
		uint16_t sendbadcount;
		uint16_t ledmodeset;
		uint16_t leddebugptr;
		uint16_t udppkttime;
		uint16_t eepromwena;
		uint16_t lbpreset;
		uint16_t scratch;
	} w;
} mem6;

static union {
	uint16_t m[0x20];
	struct _mem7 {
		uint16_t cardname[8];
		uint16_t lbpversion;
		uint16_t firmwareversion;
		uint16_t optionjprs;
		uint16_t spare;
		uint16_t recvstart_ts;
		uint16_t recvend_ts;
		uint16_t sendstart_ts;
		uint16_t sendend_ts;
	} w;
} mem7 = {
	.w = {
		.cardname = {
			'l' + 'i' * 256,
			't' + 'e' * 256,
			'h' + 'm' * 256,
			'2' +  0  * 256,
			0x0000, 0x0000, 0x0000, 0x0000,
		},
		.lbpversion = 3,
		.firmwareversion = 15,
	}
};

static union {
	uint16_t m[8];
	struct _cmem {
		uint16_t cookie;
		uint16_t memsizes;
		uint16_t memranges;
		uint16_t lbpaddr;
		uint16_t spacename0;
		uint16_t spacename1;
		uint16_t spacename2;
		uint16_t spacename3;
	} w;
} cmem[8] = {
	{{ 0x5a00, 0x8104, 0x0010, 0,
		'H' + 'o' * 256,
		's' + 't' * 256,
		'M' + 'o' * 256,
		't' + '2' * 256,
	}},
	{{ 0 }},
	{{ 0x5a02, 0x8e02, 0x0007, 0,
		'E' + 't' * 256,
		'h' + 'e' * 256,
		'r' + 'E' * 256,
		'E' + 'P' * 256,
	}},
	{{ 0x5a03, 0x8f04, 0x8200, 0,
		'F' + 'P' * 256,
		'G' + 'A' * 256,
		'F' + 'l' * 256,
		's' + 'h' * 256,
	}},
	{{ 0x5a04, 0x8202, 0x0004, 0,
		'T' + 'i' * 256,
		'm' + 'e' * 256,
		'r' + 's' * 256,
		 0  +  0  * 256,
	}},
	{{ 0 }},
	{{ 0x5a06, 0x8202, 0x0004, 0,
		'L' + 'B' * 256,
		'P' + '1' * 256,
		'6' + 'R' * 256,
		'W' +  0  * 256,
	}},
	{{ 0x5a07, 0x0202, 0x0004, 0,
		'L' + 'B' * 256,
		'P' + '1' * 256,
		'6' + 'R' * 256,
		'O' +  0  * 256,
	}},
};

static int sizes[8] = { 4, -1, 2, 4, 2, -1, 2, 2 };
static int limits[8] = {
	0x10000 / 4,
	0,
	0x40 / 2,
	16 / 4,
	0x20 / 2,
	0,
	0x20 / 2,
	0x20 / 2,
};

static uint16_t lbpcaddr_local;

static int
sndput8(uint8_t **sndbuf, int *sndlen, uint8_t v)
{
	if (*sndlen == 0) {
		DBG(("sndput failed\n"));
		return E_PARSE;
	}

	*(*sndbuf)++ = v;
	--*sndlen;

	return 0;
}

static int
sndput16(uint8_t **sndbuf, int *sndlen, uint16_t v)
{
	int ret;

	ret = sndput8(sndbuf, sndlen, v & 0xff);
	ret |= sndput8(sndbuf, sndlen, v >> 8);

	return ret;
}

static int
sndput32(uint8_t **sndbuf, int *sndlen, uint32_t v)
{
	int ret;

	ret = sndput8(sndbuf, sndlen, v & 0xff);
	ret |= sndput8(sndbuf, sndlen, (v >> 8) & 0xff);
	ret |= sndput8(sndbuf, sndlen, (v >> 16) & 0xff);
	ret |= sndput8(sndbuf, sndlen, (v >> 24) & 0xff);

	return ret;
}

#ifndef HOSTMOT2_BASE
static uint16_t
hostmot2_ustimer_read(void)
{
	return 0;
}

static uint16_t
hostmot2_rates_read(void)
{
	return 0;
}
#endif

static int write_mspace(int mspace, uint16_t lbpaddr, uint32_t v);
static int read_mspace(int mspace, uint16_t lbpaddr, uint32_t *v);
int
hostmot2_packet(const void *data, int rlen, void *out, int outlen)
{
	const uint8_t *rp = data;
	uint8_t *sp = out;
	int slen = outlen;
	int ret;
	int i;
	uint16_t ust;

	mem7.w.recvstart_ts = hostmot2_ustimer_read();
	while (rlen > 1) {
		uint16_t lbpcmd;
		uint16_t lbpaddr;
		int n;
		int w;
		int mspace;
		int sz;
		int sz_shift;

		lbpcmd = rp[0] + (rp[1] << 8);
		rp += 2;
		rlen -= 2;
		n = (lbpcmd & LBPCountMask) >> LBPCountShift;
		if (n == 0) {
			DBG(("bad lbpcount 0\n"));
			goto parseerr;
		}
		sz_shift = (lbpcmd & LBPSizeMask) >> LBPSizeShift;
		sz = 1 << sz_shift;
		mspace = (lbpcmd & LBPMemMask) >> LBPMemShift;
		w = !!(lbpcmd & LBPWriteMask);
		if (lbpcmd & LBPAddrThereMask) {
			if (rlen < 2) {
				DBG(("short packet received\n"));
				goto parseerr;
			}
			lbpaddr = rp[0] + (rp[1] << 8);
			rp += 2;
			rlen -= 2;
		} else {
			lbpaddr = cmem[mspace].w.lbpaddr;
			DBG(("implicit addr not tested yet\n"));
		}
		if (lbpcmd & LBPContMask) {
			uint16_t v;

			if (sz != 2) {
				DBG(("control with bad size\n"));
				goto parseerr;
			}
			if (w) {
				DBG(("write to control area\n"));
				goto writeerr;
			}
			if (!(lbpcmd & LBPAddrThereMask))
				lbpaddr = lbpcaddr_local;
			if (mspace == 1 || mspace == 5) {
				/* all other spaces are implemented */
				DBG(("access to memc5\n"));
				goto parseerr;
			}
			for (i = 0; i < n; ++i) {
				if (n >= 8) {
					DBG(("control area >= 8\n"));
					goto memerr;
				}
				v = cmem[mspace].m[n];
				ret = sndput16(&sp, &slen, v);
				if (ret < 0)
					goto err;
			}
			lbpaddr = lbpcaddr_local;
			goto parseerr;
		}
		if (sz != sizes[mspace]) {
			DBG(("invalid size for mspace\n"));
			goto parseerr;
		}
		lbpaddr >>= sz_shift;
		for (i = 0; i < n; ++i) {
			uint32_t v = 0;

			if (lbpaddr >= limits[mspace]) {
#ifdef DEBUG
				puts("access out of range ");
				puthex16(lbpcmd);
				puts(" ");
				puthex16(lbpaddr);
				puts("\n");
				goto memerr;
#endif
			}
			if (w) {
				if (rlen < sz) {
					DBG(("short packet (w)\n"));
					goto memerr;
				}
				if (sz == 1)
					v = rp[0];
				else if (sz == 2)
					v = rp[0] + (rp[1] << 8);
				else if (sz == 4)
					v = rp[0] + (rp[1] << 8) +
					    (rp[2] << 16) + (rp[3] << 24);
				rp += sz;
				rlen -= sz;
				ret = write_mspace(mspace, lbpaddr, v);
			} else {
				ret = read_mspace(mspace, lbpaddr, &v);
				if (ret < 0)
					goto err;
				else if (sz == 1)
					ret = sndput8(&sp, &slen, v);
				else if (sz == 2)
					ret = sndput16(&sp, &slen, v);
				else if (sz == 4)
					ret = sndput32(&sp, &slen, v);
			}
			if (ret < 0)
				goto err;
			if (lbpcmd & LBPAddrIncMask)
				++lbpaddr;
			else if (n > 1 && mspace != 3)
				DBG(("no autoinc not yet tested\n"));
		}
		cmem[mspace].w.lbpaddr = lbpaddr;
	}
	if (rlen != 0) {
		DBG(("odd rlen\n"));
		goto memerr;
	}

	++mem6.w.recvudpcount;
	mem6.w.eepromwena = 0;

	do_reset = mem6.w.lbpreset;

	ust = hostmot2_ustimer_read();
	mem7.w.recvend_ts = ust;
	mem7.w.sendstart_ts = ust;
	mem7.w.sendend_ts = ust;

	return outlen - slen;

parseerr:
	ret = E_PARSE;
	goto err;

memerr:
	ret = E_MEM;
	goto err;

writeerr:
	ret = E_WRITE;

err:
	mem6.w.errorreg |= ret;
	if (ret == E_PARSE) {
		mem6.w.errorreg |= PARSEERRBIT;
		if (mem6.w.lbpparseerrors != 0xffff)
			++mem6.w.lbpparseerrors;
	} else if (ret == E_MEM) {
		mem6.w.errorreg |= MEMERRBIT;
		if (mem6.w.lbpmemerrors != 0xffff)
			++mem6.w.lbpmemerrors;
	} else if (ret == E_WRITE) {
		mem6.w.errorreg |= WRITEERRBIT;
		if (mem6.w.lbpwriteerrors != 0xffff)
			++mem6.w.lbpwriteerrors;
	}
	mem6.w.eepromwena = 0;
	mem7.w.recvend_ts = hostmot2_ustimer_read();

	return -1;
}

static uint16_t
wait_htimer(int timer)
{
	uint16_t waitmask = 1 << timer;
	uint16_t start = hostmot2_ustimer_read();
	uint16_t oldstate = hostmot2_rates_read() & waitmask;
	uint16_t state;
	uint16_t delta = 0;

	while (delta < mem4.w.htimeout) {
		state = hostmot2_rates_read() & waitmask;
		if (state == 0) {
			oldstate = 0;
		} else if (oldstate == 0) {
			return delta;
		}
		delta = hostmot2_ustimer_read() - start;
	}
	mem6.w.errorreg |= TIMEOUTBIT;
	return delta;
}

static void
wait_ustimer(uint16_t t)
{
	int start = hostmot2_ustimer_read();

	while ((hostmot2_ustimer_read() - start) - t >= 0)
		;
}

static int
write_mspace(int mspace, uint16_t lbpaddr, uint32_t v)
{
	switch (mspace) {
	case 0: /* HostMot2 space, content */
#ifdef HOSTMOT2_BASE
		((uint32_t *)HOSTMOT2_BASE)[lbpaddr] = v;
#endif
		break;
	case 2:	/* Ethernet EEPROM space */
		if (mem6.w.eepromwena == 0x5a02) {
			if (lbpaddr < 16)
				return E_WRITE;
		} else if (mem6.w.eepromwena != 0x3602) {
			DBG(("eeprom writes not enabled\n"));
			return E_WRITE;
		}
		eeconfig.m[lbpaddr] = v;
		config_changed = 1;
		break;
	case 3: /* FPGA flash */
		if (lbpaddr == 0) {
			fladdr = v;
		} else if (lbpaddr == 1) {
			uint8_t data[4];

			if (fladdr & 3) {
				DBG(("unaligned fladdr\n"));
				return E_MEM;
			}

			if (mem6.w.eepromwena != 0x5a03)
				return E_WRITE;

			data[0] = v & 0xff;
			data[1] = (v >> 8) & 0xff;
			data[2] = (v >> 16) & 0xff;
			data[3] = (v >> 24) & 0xff;
			flash_write_page(fladdr, data, 4);
			fladdr += 4;
		} else if (lbpaddr == 3) {
			if (mem6.w.eepromwena != 0x5a03)
				return E_WRITE;

			flash_erase_block64(fladdr);
		} else {
			return E_MEM;
		}
		break;
	case 4: /* timers */
		mem4.m[lbpaddr] = v;
		if (lbpaddr == 1) {
			/* wait v microseconds */
			wait_ustimer(v);
		} else if (lbpaddr >= 3 && lbpaddr <= 7) {
			wait_htimer(lbpaddr - 3);
		}
		break;
	case 6:
		if (lbpaddr == 15) {
			DBG(("icap port not supported\n"));
			return E_PARSE;
		}
		/* recvpktcount, udpcount, badoucnt, sdnpkg ... */
		mem6.m[lbpaddr] = v;
		break;
	case 7: /* Card Information */
		DBG(("write to cardinfo area not allowed\n"));
		return E_WRITE;
	default:
		DBG(("unimplemented region\n"));
		return E_PARSE;
	}
	return 0;
}

static int
read_mspace(int mspace, uint16_t lbpaddr, uint32_t *v)
{
	switch (mspace) {
	case 0: /* HostMot2 space, content */
#ifdef HOSTMOT2_BASE
		*v = ((uint32_t *)HOSTMOT2_BASE)[lbpaddr];
#else
		*v = 0;
#endif
		break;
	case 2:	/* Ethernet EEPROM space */
		*v = eeconfig.m[lbpaddr];
		break;
	case 3: /* fpga flash */
		if (lbpaddr == 0) {
			*v = fladdr;
		} else if (lbpaddr == 1) {
			uint8_t data[4];

			if (fladdr & 3) {
				DBG(("unaligned fladdr\n"));
				return E_MEM;
			}
			flash_read_page(fladdr, data, 4);
			*v = (data[3] << 24) | (data[2] << 16) |
			     (data[1] << 8) | data[0];
			fladdr += 4;
		} else if (lbpaddr == 2) {
			uint8_t id;

			flash_read_id(&id);
			*v = id;
		} else {
			return E_MEM;
		}
		break;
	case 4: /* htimeout or scratch4 */
		if (lbpaddr == 0) {
			*v = hostmot2_ustimer_read();
		} else if (lbpaddr >= 3 && lbpaddr <= 7) {
			*v = wait_htimer(lbpaddr - 3);
		} else  {
			*v = mem4.m[lbpaddr];
		}
		break;
	case 6:
		if (lbpaddr == 15) {
			DBG(("icap port not supported\n"));
			return E_PARSE;
		}
		/* recvpktcount, udpcount, badoucnt, sdnpkg ... */
		*v = mem6.m[lbpaddr];
		break;
	case 7: /* Card Information */
		*v = mem7.m[lbpaddr];
		break;
	default:
		DBG(("unimplemented region\n"));
		return E_PARSE;
	}
	return 0;
}
