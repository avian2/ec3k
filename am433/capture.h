#ifndef HAVE_CAPTURE_H
#define HAVE_CAPTURE_H

#include <stdint.h>

#define FS		48000

#define MOD_PWM		0
#define MOD_FSK		1
#define MOD_UNKNOWN	2
#define MOD_MANCHESTER	3
#define MOD_PPK		4

struct am433_capture_hdr {
	uint64_t timestamp_us;
	uint32_t bitcount; 
	uint32_t clock_hz;
	uint8_t modulation;
	uint8_t leader_edges;
	uint8_t trailer_edges;
} __attribute__((__packed__));

#endif
