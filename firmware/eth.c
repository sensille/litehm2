#include <generated/csr.h>
#include <generated/mem.h>
#include <generated/soc.h>

#include <libliteeth/inet.h>

#include "eth.h"
#include "hostmot2.h"
#include "debug.h"

#define HOSTMOT2_PORT	27181

#define ETH_MTU	1536

#define ETHMAC_EV_SRAM_WRITER	0x1
#define ETHMAC_EV_SRAM_READER	0x1

#pragma pack(push)
#pragma pack(1)
typedef struct _eth_header {
	/* ethernet */
	uint16_t	dst_mac1;
	uint16_t	dst_mac2;
	uint16_t	dst_mac3;
	uint16_t	src_mac1;
	uint16_t	src_mac2;
	uint16_t	src_mac3;
	uint16_t	type;
} eth_header_t;
#define ETHERTYPE_IP	0x800
#define ETHERTYPE_ARP	0x806

typedef struct  _ip_header {
	/* IP */
	union {
		struct {
			uint8_t		vers_ihl;
			uint8_t		tos;
			uint16_t	length;
		};
		uint32_t	vers_ihl_tos_length;
	};
	uint32_t	id_flags_fragoff;
	union {
		struct {
			uint8_t		ttl;
			uint8_t		proto;
			uint16_t	cs;
		};
		uint32_t	ttl_proto_cs;
	};
	uint32_t	src;
	uint32_t	dst;
} ip_header_t;
#define PROTO_ICMP	1
#define PROTO_UDP	17

typedef struct _udp_header {
	/* UDP */
	union {
		struct {
			uint16_t	sport;
			uint16_t	dport;
			uint16_t	len;
			uint16_t	cs;
		};
		struct {
			uint32_t	sport_dport;
			uint32_t	len_cs;
		};
	};
} udp_header_t;

typedef struct _icmp_header {
	uint8_t		type;
	uint8_t		code;
	uint16_t	cs;
	uint32_t	rest;
} icmp_header_t;
#define ICMP_ECHO_REQUEST	8
#define ICMP_ECHO_REPLY		0

typedef struct _arp_header {
	uint16_t	htype;
	uint16_t	ptype;
	uint8_t		hlen;
	uint8_t		plen;
	uint16_t	oper;
	uint16_t	sha1;
	uint16_t	sha2;
	uint16_t	sha3;
	uint16_t	spa1;
	uint16_t	spa2;
	uint16_t	tha1;
	uint16_t	tha2;
	uint16_t	tha3;
	uint16_t	tpa1;
	uint16_t	tpa2;
} arp_header_t;
#define ARP_HTYPE_ETHERNET	1
#define ARP_PTYPE_IP		0x800
#define ARP_OPER_REQUEST	1
#define ARP_OPER_REPLY		2
#pragma pack(pop)

/* in network byte order */
static uint32_t own_ip;
static uint32_t own_ip_cs;	/* precomputed for header checksum */
static uint16_t own_mac1;
static uint16_t own_mac2;
static uint16_t own_mac3;

static int txslot = 0;
static uint16_t ip_id = 0;

static int
arp_packet(arp_header_t *arp_in, arp_header_t *arp_out)
{
	if (arp_in->htype != htons(ARP_HTYPE_ETHERNET))
		return 0;
	if (arp_in->ptype != htons(ARP_PTYPE_IP))
		return 0;
	if (arp_in->hlen != 6)
		return 0;
	if (arp_in->plen != 4)
		return 0;
	if (arp_in->oper != htons(ARP_OPER_REQUEST))
		return 0;
	if (arp_in->tpa1 != htons(ntohl(own_ip) >> 16))
		return 0;
	if (arp_in->tpa2 != htons(ntohl(own_ip) & 0xffff))
		return 0;

	arp_out->htype = htons(ARP_HTYPE_ETHERNET);
	arp_out->ptype = htons(ARP_PTYPE_IP);
	arp_out->hlen = 6;
	arp_out->plen = 4;
	arp_out->oper = htons(ARP_OPER_REPLY);
	arp_out->sha1 = own_mac1;
	arp_out->sha2 = own_mac2;
	arp_out->sha3 = own_mac3;
	arp_out->spa1 = htons(ntohl(own_ip) >> 16);
	arp_out->spa2 = htons(ntohl(own_ip) & 0xffff);
	arp_out->tha1 = arp_in->sha1;
	arp_out->tha2 = arp_in->sha2;
	arp_out->tha3 = arp_in->sha3;
	arp_out->tpa1 = arp_in->spa1;
	arp_out->tpa2 = arp_in->spa2;

	return sizeof(*arp_out);
}

/* rxlen is without the eth header */
static int
ip_packet(ip_header_t *ip_in, int rxlen, ip_header_t *ip_out)
{
	icmp_header_t *icmp_in = (icmp_header_t *)(ip_in + 1);
	icmp_header_t *icmp_out = (icmp_header_t *)(ip_out + 1);
	uint16_t *body_in = (uint16_t *)(icmp_in + 1);
	uint16_t *body_out = (uint16_t *)(icmp_out + 1);
	uint32_t hcs;
	uint32_t rest;
	int ip_len;
	int i;
	int bodylen;

	if (ip_in->vers_ihl != 0x45)
		return 0;
	if (ip_in->dst != own_ip)
		return 0;
	if (ip_in->proto != PROTO_ICMP)
		return 0;
	if (rxlen < sizeof(*ip_in) + sizeof(*icmp_in))
		return -1;
	if (icmp_in->type != ICMP_ECHO_REQUEST)
		return 0;

	/* compose ping reply */
	ip_len = rxlen;

	/* ip header */
	hcs = 0x45 << 8;
	hcs += ip_len;
	ip_out->vers_ihl_tos_length = htonl((0x45 << 24) | ip_len);
	hcs += ip_id;
	hcs += 1 << 14;
	ip_out->id_flags_fragoff = htonl((ip_id << 16) | (1 << 14));
	hcs += own_ip_cs;
	ip_out->src = own_ip;
	hcs += ntohl(ip_in->src) >> 16;
	hcs += ntohl(ip_in->src) & 0xffff;
	ip_out->dst = ip_in->src;
	hcs += (0x40 << 8) | PROTO_ICMP;
	while (hcs > 0xffff)
		hcs = (hcs >> 16) + (hcs & 0xffff);
	hcs = ~hcs & 0xffff;
	ip_out->ttl_proto_cs = htonl((0x40 << 24) | (PROTO_ICMP << 16) | hcs);
	++ip_id;

	icmp_out->type = ICMP_ECHO_REPLY;
	icmp_out->code = 0;
	icmp_out->rest = icmp_in->rest;
	rest = ntohl(icmp_in->rest);
	hcs = (rest >> 16) + (rest & 0xffff) + ICMP_ECHO_REPLY;
	bodylen = rxlen - sizeof(*ip_in) - sizeof(*icmp_in);
	for (i = 0; i < (bodylen >> 1); ++i) {
		hcs += ntohs(*body_in);
		*body_out++ = *body_in++;
	}
	while (hcs > 0xffff)
		hcs = (hcs >> 16) + (hcs & 0xffff);
	hcs = ~hcs & 0xffff;
	icmp_out->cs = htons(hcs);

	return rxlen;
}

#ifdef ETHMAC_BASE
void
eth_poll(void)
{
	int rxslot;
	int rxlen;
	int txlen = 0;
	eth_header_t *eth_in;
	ip_header_t *ip_in;
	udp_header_t *udp_in;
	eth_header_t *eth_out;
	ip_header_t *ip_out;
	udp_header_t *udp_out;
	uint32_t hcs;
	int ret;

	/* no incoming packet, nothing to do */
	if (~ethmac_sram_writer_ev_pending_read() & ETHMAC_EV_SRAM_WRITER)
		return;

	/* no outgoing packet availabe, postpone processing */
	if (!ethmac_sram_reader_ready_read())
		return;

	flush_cpu_dcache();

	rxslot = ethmac_sram_writer_slot_read();
	rxlen = ethmac_sram_writer_length_read();

	eth_in = (eth_header_t *)(ETHMAC_BASE + ETHMAC_SLOT_SIZE * rxslot);
	ip_in = (ip_header_t *)(eth_in + 1);
	udp_in = (udp_header_t *)(ip_in + 1);
	eth_out = (eth_header_t *)(ETHMAC_BASE +
		ETHMAC_SLOT_SIZE * (ETHMAC_RX_SLOTS + txslot));
	ip_out = (ip_header_t *)(eth_out + 1);
	udp_out = (udp_header_t *)(ip_out + 1);

	/*
	 * for maximum performance, we check for hostmot2 first
	 */
	if (rxlen < sizeof(*eth_in) + sizeof(*ip_in) + sizeof(*udp_in))
		goto other;
	if (eth_in->type != ntohs(ETHERTYPE_IP))
		goto other;
	if (ip_in->proto != PROTO_UDP)
		goto other;
	if (udp_in->dport != ntohs(HOSTMOT2_PORT))
		goto other;
	if (ip_in->vers_ihl != 0x45)
		goto other;
	if (ip_in->dst != own_ip)
		goto other;
	int paylen = rxlen - sizeof(*eth_in) - sizeof(*ip_in) - sizeof(*udp_in);
	int udplen = ntohs(udp_in->len) - sizeof(*udp_in);
	if (udplen > paylen)
		goto other;

	/*
	 * only pass the payload to hostmot2_packet
	 */
	ret = hostmot2_packet(
		(void *)(udp_in + 1),
		udplen,
		(void *)(udp_out + 1),
		ETH_MTU - sizeof(*eth_out) - sizeof(*ip_out) - sizeof(*udp_out)
	);

	if (ret <= 0)
		goto ignore;

	/*
	 * we could still save a few cycles here by doing 32 bit operations
	 * for the ethernet header
	 */
	int ip_len = ret + sizeof(*ip_out) + sizeof(*udp_out);
	int udp_len = ret + sizeof(*udp_out);

	/* ethernet header */
	eth_out->src_mac1 = own_mac1;
	eth_out->src_mac2 = own_mac2;
	eth_out->src_mac3 = own_mac3;
	eth_out->dst_mac1 = eth_in->src_mac1;
	eth_out->dst_mac2 = eth_in->src_mac2;
	eth_out->dst_mac3 = eth_in->src_mac3;
	eth_out->type = htons(ETHERTYPE_IP);

	/* ip header */
	hcs = 0x45 << 8;
	hcs += ip_len;
	ip_out->vers_ihl_tos_length = htonl((0x45 << 24) | ip_len);
	hcs += ip_id;
	hcs += 1 << 14;
	ip_out->id_flags_fragoff = htonl((ip_id << 16) | (1 << 14));
	hcs += own_ip_cs;
	ip_out->src = own_ip;
	hcs += ntohl(ip_in->src) >> 16;
	hcs += ntohl(ip_in->src) & 0xffff;
	ip_out->dst = ip_in->src;
	hcs += (0x40 << 8) | PROTO_UDP;
	while (hcs > 0xffff)
		hcs = (hcs >> 16) + (hcs & 0xffff);
	hcs = ~hcs & 0xffff;
	ip_out->ttl_proto_cs = htonl((0x40 << 24) | (PROTO_UDP << 16) | hcs);
	++ip_id;

	/* udp header. we don't calculate a checksum. 0 == don't care */
	udp_out->sport = htons(HOSTMOT2_PORT);
	udp_out->dport = udp_in->sport;
	udp_out->len_cs = htonl(udp_len << 16);

	txlen = ret + sizeof(*eth_out) + sizeof(*ip_out) + sizeof(*udp_out);

	goto reply;

other:
	/*
	 * no hostmot2 packet
	 */
	if (rxlen < sizeof(*eth_in))
		goto ignore;
	if (eth_in->type == ntohs(ETHERTYPE_ARP)) {
		if (rxlen < sizeof(eth_header_t) + sizeof(arp_header_t))
			goto ignore;
		ret = arp_packet((arp_header_t *)(eth_in + 1),
			(arp_header_t *)(eth_out + 1));
	} else if (eth_in->type == ntohs(ETHERTYPE_IP)) {
		if (rxlen < sizeof(eth_header_t) + sizeof(ip_header_t))
			goto ignore;
		ret = ip_packet(ip_in, rxlen - sizeof(*eth_in),
			(ip_header_t *)(eth_out + 1));
	} else {
		goto ignore;
	}

	if (ret <= 0)
		goto ignore;

	eth_out->src_mac1 = own_mac1;
	eth_out->src_mac2 = own_mac2;
	eth_out->src_mac3 = own_mac3;
	eth_out->dst_mac1 = eth_in->src_mac1;
	eth_out->dst_mac2 = eth_in->src_mac2;
	eth_out->dst_mac3 = eth_in->src_mac3;
	eth_out->type = eth_in->type;
	txlen = ret + sizeof(*eth_out);

	goto reply;

ignore:
	txlen = 0;

reply:
	/* acknowledge rx */
	ethmac_sram_writer_ev_pending_write(ETHMAC_EV_SRAM_WRITER);

	if (txlen > 0) {
		ethmac_sram_reader_slot_write(txslot);
		ethmac_sram_reader_length_write(txlen < 64 ? 64 : txlen);
		ethmac_sram_reader_start_write(1);
		txslot = (txslot + 1) % ETHMAC_TX_SLOTS;
	}

	return;
}

/* my_ip in host byte order */
void
eth_init(uint32_t my_ip, uint8_t my_mac[6])
{
#ifdef CSR_ETHPHY_CRG_RESET_ADDR
#ifndef ETH_PHY_NO_RESET
	ethphy_crg_reset_write(1);
	busy_wait(200);
	ethphy_crg_reset_write(0);
	busy_wait(200);
#endif
#endif
	ethmac_sram_reader_ev_pending_write(ETHMAC_EV_SRAM_READER);
	ethmac_sram_writer_ev_pending_write(ETHMAC_EV_SRAM_WRITER);

	own_ip = htonl(my_ip);
	own_ip_cs = (uint16_t)((my_ip >> 16) + (my_ip & 0xffff));
	own_mac1 = htons(my_mac[0] | (my_mac[1] << 8));
	own_mac2 = htons(my_mac[2] | (my_mac[3] << 8));
	own_mac3 = htons(my_mac[4] | (my_mac[5] << 8));
}
#else

void
eth_poll(void)
{
}

void
eth_init(uint32_t my_ip, uint8_t my_mac[6])
{
}

#endif
