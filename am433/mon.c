#include <stdio.h>

#include "capture.h"
#include "mon.h"

int mon_print_func(struct packet_t* packet, struct timeval timestamp)
{
	size_t retval;
	struct am433_capture_hdr hdr;

	hdr.timestamp_us = ((uint64_t) timestamp.tv_sec) * 1000000 + 
			   ((uint64_t) timestamp.tv_usec) +
			   ((uint64_t) packet->start) * 1000000 / FS;
	hdr.modulation = packet->modulation;
	hdr.leader_edges = packet->leader_edges;
	hdr.trailer_edges = packet->trailer_edges;

	if (packet->modulation == MOD_UNKNOWN) {
		hdr.bitcount = packet->len * 8;
		hdr.clock_hz = FS;
		retval = fwrite(&hdr, sizeof(hdr), 1, stdout);
		if(retval != 1) return -1;
		retval = fwrite(packet->data, packet->len, 1, stdout);
		if(retval != 1) return -1;
	} else {
		int bytecount = packet->bitcount/8;
		if(packet->bitcount % 8) bytecount++;

		hdr.bitcount = packet->bitcount;
		hdr.clock_hz = packet->cp ? FS / packet->cp : 0;
		retval = fwrite(&hdr, sizeof(hdr), 1, stdout);
		if(retval != 1) return -1;
		retval = fwrite(packet->decoded, bytecount, 1, stdout);
		if(retval != 1) return -1;
	}

	fflush(stdout);

	return 0;
}
