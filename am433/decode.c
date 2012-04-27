#include <assert.h>
#include <math.h>
#include <string.h>
#include <stdio.h>
#include <stdarg.h>
#include <unistd.h>

#include "capture.h"
#include "packetizer.h"
#include "decode.h"

int verbose = 0;

int debug(const char *format, ...)
{
	va_list ap;
	int r;

	va_start(ap, format);
	if(verbose) {
		r = vfprintf(stderr, format, ap);
		fputc('\n', stderr);
	} else {
		r = 0;
	}
	va_end(ap);
	return r;
}

static void push_bit(struct packet_t* packet, int bit) {
	int last_byte = packet->bitcount / 8;
	assert(last_byte < DECODESIZE);
	packet->decoded[last_byte] |= (bit << (7 - packet->bitcount % 8));
	packet->bitcount++;
}

static void sync_bit(struct packet_t* packet) {
	int bits = (-packet->bitcount) % 8;
	int n;
	for(n = 0; n < bits; n++) {
		push_bit(packet, 0);
	}
}

int decode_ppk(struct packet_t* packet, int start, int cp_hint) {
	int t;

	int pt = start;
	int pv = pt < 0 ? 0 : packet->data[pt];
	int polarity = pv;

	int cp = cp_hint;

	int pl_detect[3];
	int clock = 0;

	if(cp == 0) {
		for(t = start; t < packet->len; t++) {
			int v = t < 0 ? 0 : packet->data[t];

			if(pv != v) {
				//debug("pl %d", t - pt);
				pl_detect[clock] = t - pt;
				clock++;
				if(clock >= 3) break;

				pv = v;
				pt = t;
			}
		}

		int retval = decode_ppk(packet, start, pl_detect[0]);
		if(!retval) return 0;

		retval = decode_ppk(packet, start, pl_detect[1]);
		if(!retval) return 0;

		retval = decode_ppk(packet, start-pl_detect[1], pl_detect[1]);
		if(!retval) return 0;

		retval = decode_ppk(packet, start-pl_detect[2], pl_detect[2]);
		if(!retval) return 0;

		return -1;
	} else {
		debug("ppk: guess start=%d cp=%d", start, cp_hint);
		packet->bitcount = 0;
		memset(packet->decoded, 0, DECODESIZE);

		int pl_zero = -1;
		int pl_one = -1;

		for(t = start; t < packet->len; t++) {
			int v = t < 0 ? 0 : packet->data[t];

			if(pv != v) {
				if (pv == 1) {
					pl_one = t - pt;
				} else {
					pl_zero = t - pt;
				}

				if (pv != polarity) {

					if(pl_one > 0.6*cp && pl_one < 1.5*cp) {
						push_bit(packet, 1);
						// ok, one
					} else if(pl_zero > 0.6*cp && pl_zero < 1.5*cp) {
						push_bit(packet, 0);
						// ok, zero
					} else {
						debug("inconsistent pl_one=%d pl_zero=%d t=%d",
								pl_one, pl_zero, t);
						return -1;
					}
				}

				pv = v;
				pt = t;
			}
		}

		packet->modulation = MOD_PPK;
		packet->cp = cp;

		return 0;
	}
}

int decode_manchester(struct packet_t* packet, int start, int cp_hint) {
	int t;

	int pt = 0;
	int pv = pt < 0 ? 0 : packet->data[pt];

	packet->bitcount = 0;
	memset(packet->decoded, 0, DECODESIZE);

	int cp = 0;
	int pl_zero = -1;
	int pl_one = -1;

	int leader_bits = 0;
	/* manchester encoded packets usually have a leader consisting of zeros where the
	 * transmitter is warming up (?) and the duty cycle might drift up or down.
	 *
	 * so we skip through this leading string of zeros, only checking for constant
	 * frequency. The first bit that has a significantly different frequency is the 
	 * first non-zero bit. */
	for(t = 0; t < packet->len; t++) {
		int v = t < 0 ? 0 : packet->data[t];

		if(pv != v) {
			if (pv == 1) {
				pl_one = t - pt;
				//debug("manchester: pl_one=%d", pl_one);
			} else {
				pl_zero = t - pt;
				//debug("manchester: pl_zero=%d", pl_zero);
				leader_bits++;
			}
			if (pl_one != -1 && pl_zero != -1) {
				int pl = pl_one + pl_zero;
				if (cp == 0) {
					cp = pl;
				} else {
					if (pl > 0.9*cp && pl < 1.1*cp) {
						// ok
					} else {
						debug("manchester: leader not constant frequency t=%d", t);
						return -1;
					}
				}
				if (pl_one > 0.8*pl_zero && pl_one <= 1.1*pl_zero) {
					/* so this is kind of a hack. we ignore the start offset that
					 * results from offset restarts below because that usually
					 * messes up the clock pulse length (transmitter frequency
					 * drifts somewhat between the leader zero bits and the data
					 * part). So we check whether there was an offset restart
					 * and finish on a zero in that case instead of a one. */
					if ((start == 0 && v) || (!v)) break;
				}
			}

			pv = v;
			pt = t;
		}
	}

	debug("manchester: %d leading zeros t=%d", leader_bits, t);
	for(;leader_bits > 0; leader_bits--) {
		push_bit(packet, 0);
	}

	cp = 0;
	int clock = 0;

	for(; t < packet->len; t++) {
		int v = t < 0 ? 0 : packet->data[t];

		if (pv != v) {
			int pl = t - pt;

			if (cp == 0) {
				// unknown clock period, set it to the first pulse length
				clock++;
				cp = pl;
			} else if (pl > (0.25*cp) && pl <= (0.5*cp)) {
				// looks like we misidentified clock period
				// by two. restart.
				
				if (cp_hint != 0 || start != 0) {
					debug("manchester: double clock restart");
					return -1;
				}

				debug("manchester: period restart");

				// move start one period to the left
				return decode_manchester(packet, start-pl, pl);
			} else if (pl > (0.5*cp) && pl <= (1.5 * cp)) {
				// seems like a single clock period has 
				// passed since the last edge.
				clock++;
			} else if (pl > (1.5*cp) && pl <= (3.0 * cp)) {
				// seems like two clock periods have passed
				
				if (clock%2 == 0) {
					// we should have seen a transition here.
					// clock is off by one period. restart.

					if (cp_hint != 0 || start != 0) {
						debug("manchester: double offset restart");
						return -1;
					}

					debug("manchester: offset restart t=%d start=%d", t, start-cp);
					return decode_manchester(packet, start-cp, cp);
				} else {
					clock += 2;
				}
			} else {
				debug("manchester: sync pl=%d cp=%d", pl, cp);
				clock += ((int) (((double) pl)/cp + 0.5));
				//return -1;
			}

			if (clock%2 == 1) {
				int bit = (v - pv) > 0 ? 1 : 0;
				//debug("manchester: bit %d", bit);
				push_bit(packet, bit);
			}

			pv = v;
			pt = t;
		}
	}

	packet->modulation = MOD_MANCHESTER;
	packet->cp = cp;

	return 0;
}

int decode_fsk(struct packet_t* packet, int start, int cp_hint) {
	int t;

	int pt = start;
	int dc = 0;
	int pv = pt < 0 ? 0 : packet->data[pt];

	packet->bitcount = 0;
	memset(packet->decoded, 0, DECODESIZE);

	int cp_one = 0;
	int dc_one = 0;
	int cp_zero = 0;
	int dc_zero = 0;

	for(t = start; t < packet->len; t++) {
		int v = t < 0 ? 0 : packet->data[t];

		if(pv != v) {
			if (pv == 0) {
				int pl = dc + t - pt;
				if(cp_one == 0) {
					cp_one = pl;
					dc_one = dc;
				} else if(pl <= 0.9*cp_one) {
					if (cp_zero == 0) {
						cp_zero = pl;
						dc_zero = dc;
					} else if(pl > 0.9*cp_zero && pl <= 1.1*cp_zero) {
						if(dc > 0.6*dc_zero && dc <= 1.2*dc_zero) {
							// zero, ok
						} else {
							debug("fsk: dc inconsistent at %d: %d != %d", t, dc, dc_zero);
							return -1;
						}
					} else {
						debug("fsk: cp inconsistent: too short at %d", t);
						return -1;
					}
				} else if(pl > 0.9*cp_one && pl <= 1.1*cp_one) {
					if(dc > 0.6*dc_one && dc <= 1.2*dc_one) {
						// one, ok
					} else {
						debug("fsk: dc inconsistent at %d: %d != %d", t, dc, dc_one);
						return -1;
					}
				} else if(pl > 1.1*cp_one) {
					if (cp_zero == 0) {
						// misidentified one as zero
						cp_zero = cp_one;
						dc_zero = dc_one;
						cp_one = pl;
						dc_one = dc;
					} else {
						debug("fsk: cp inconsistent: too long at %d", t);
						return -1;
					}
				}

			} else {
				dc = t - pt;
			}

			pv = v;
			pt = t;
		}
	}

	debug("fsk: guess cp=%d + %d, dc_one=%d, dc_zero=%d", 
			(cp_one+cp_zero)/2, (cp_one-cp_zero)/2,
			dc_one, dc_zero);

	pt = start;
	pv = pt < 0 ? 0 : packet->data[pt];

	for(t = start; t < packet->len; t++) {
		int v = t < 0 ? 0 : packet->data[t];

		if(pv != v) {
			if (pv == 0) {
				int pl = t - pt;
				if(pl > 0.9*cp_zero && pl <= 1.1*cp_zero) {
					push_bit(packet, 0);
				} else if(pl > 0.9*cp_one && pl <= 1.1*cp_one) {
					push_bit(packet, 1);
				} else {
					// should detect inconsistency earlier
					assert(0);
				}

				pt = t;
			}

			pv = v;
		}
	}

	// get the last bit
	dc = t - pt;
	if(dc > 0.6*dc_zero && dc < 1.2*dc_zero) {
		push_bit(packet, 0);
	} else if(dc > 0.6*dc_one && dc <= 1.2*dc_one) {
		push_bit(packet, 1);
	} 

	packet->modulation = MOD_FSK;
	packet->cp = (cp_one+cp_zero)/2;

	return 0;
}

int decode_pwm(struct packet_t* packet, int start, int cp_hint) {
	int t;

	int pv = start < 0 ? 0 : packet->data[start];

	packet->bitcount = 0;
	memset(packet->decoded, 0, DECODESIZE);

	int cp_rise = 0;
	int cp_fall = 0;
	int pt_rise = start;
	int pt_fall = -1;

	int ok_rise = 1;
	int ok_fall = 1;

	for(t = start; t < packet->len; t++) {
		int v = t < 0 ? 0 : packet->data[t];

		if(pv != v) {
			if(v == 1) {
				int pl = t - pt_rise;
				//debug("pl_rise=%d", pl);
				if(cp_rise == 0) {
					cp_rise = pl;
				} else {
					if((pl > 0.8*cp_rise && pl < 1.3*cp_rise) || ok_rise == 0) {
						// ok
					} else {
						ok_rise = 0;
					}
				}
				pt_rise = t;
			} else {
				if(pt_fall >= 0) {
					int pl = t - pt_fall;
					//debug("pl_fall=%d", pl);
					if(cp_fall == 0) {
						cp_fall = pl;
					} else {
						if((pl > 0.8*cp_fall && pl < 1.3*cp_fall) || ok_fall == 0) {
							// ok
						} else {
							ok_fall = 0;
						}
					}
				}
				pt_fall = t;
			}

			pv = v;
		}
	}

	int edge;
	int cp;
	int pt = start;
	pv = pt < 0 ? 0 : packet->data[pt];

	if(ok_rise) {
		debug("pwm: rising edge clock");
		cp = cp_rise;
		edge = 1;
	} else if(ok_fall) {
		debug("pwm: falling edge clock");
		cp = cp_fall;
		edge = 0;
	} else {
		debug("pwm: err: clock not constant on either edge");
		return -1;
	}

	if(cp == 0) {
		debug("pwm: err: too short");
		return -1;
	}

	debug("pwm: guess cp=%d", cp);

	int v = 0;
	for(t = start; t < packet->len; t++) {
		v = t < 0 ? 0 : packet->data[t];

		if(pv != v) {
			int pl = t - pt;
			if(v == edge) {
				if(pl > 0.55*cp) {
					push_bit(packet, 1);
				} else if(pl < 0.45*cp) {
					push_bit(packet, 0);
				} else {
					debug("pwm: err: ambigous bit pl=%d %d", pl, t);
					return -1;
				}
			}
			pv = v;
			pt = t;
		}
	}

	// get the last bit
	if(v == edge) {
		int pl = t - pt;
		if(pl > 0.55*cp) {
			push_bit(packet, 0);
		} else if(pl < 0.45*cp) {
			push_bit(packet, 1);
		} else {
			debug("pwm: err: ambigous bit pl=%d %d", pl, t);
			return -1;
		}
	}

	packet->modulation = MOD_PWM;
	packet->cp = cp;

	return 0;
}

int decode_binary(struct packet_t* packet, int start, int cp_hint)
{
	int t;

	packet->bitcount = 0;
	memset(packet->decoded, 0, DECODESIZE);

	double cp = -1;

	/* find the shortest pulse length in the packet. take that as the
	 * first estimate of clock pulse length */
	int pt = start;
	int pv = start < 0 ? 0 : packet->data[start];
	for(t = start; t < packet->len; t++) {
		int v = t < 0 ? 0 : packet->data[t];

		if(pv != v) {
			int pl = t - pt;
			if(pl < 2) {
				debug("binary: pulse too short t=%d", t);
				return -1;
			}
			if(cp == -1 || pl < cp) {
				cp = pl;
			}

			pv = v;
			pt = t;
		}
	}

	debug("binary: first guess cp=%.2f", cp);

	/* do a second pass and fine tune the first clock estimate as well as look
	 * for inconsistencies */
	pt = start;
	pv = start < 0 ? 0 : packet->data[start];
	for(t = start; t < packet->len; t++) {
		int v = t < 0 ? 0 : packet->data[t];

		if(pv != v) {
			int pl = t - pt;
			if(pl < cp) {
				/* encountered pulse is shorter than current clock guess.
				 * this can only be due to jitter in the clock */
				cp = (cp*2.0 + pl) / 3.0;
			} else if(pl > cp) {
				/* encountered pulse is longer than current clock guess.
				 * the pulse should be approximately an integer multiple of
				 * the clock */
				double r = pl / cp;
				double n = round(r);
				double e = fabs((r - n)/n);
				if(e > 0.3) {
					debug("binary: inconsistent pulse length cp=%.2f pl=%d t=%d", cp, pl, t);
					return -1;
				}
				if(n > 20.0) {
					debug("binary: too many consecutive bits %d t=%d", n, t);
					return -1;
				}
				cp = (cp*2.0 + pl/n) / 3.0;
			}

			pv = v;
			pt = t;
		}
	}

	debug("binary: cp=%.2f", cp);

	pt = start;
	pv = start < 0 ? 0 : packet->data[start];
	for(t = start; t < packet->len; t++) {
		int v = t < 0 ? 0 : packet->data[t];

		if(pv != v) {
			int pl = t - pt;

			//debug("binary: pl=%d t=%d", pl, t);

			double r = pl / cp;
			int nbits = round(r);

			int n;
			for(n = 0; n < nbits; n++) {
				push_bit(packet, pv);
			}

			pv = v;
			pt = t;
		}
	}

	packet->modulation = MOD_BINARY;
	packet->cp = cp;

	return 0;
}
