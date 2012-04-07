#ifndef HAVE_MON_H
#define HAVE_MON_H

#include <stdint.h>
#include <sys/time.h>
#include <sys/types.h>

#include "packetizer.h"

int mon_print_func(struct packet_t* packet, struct timeval timestamp);

#endif
