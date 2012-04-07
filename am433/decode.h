#ifndef HAVE_DECODE_H
#define HAVE_DECODE_H

extern int verbose;

int debug(const char *format, ...);

int decode_ppk(struct packet_t* packet, int start, int cp_hint);
int decode_manchester(struct packet_t* packet, int start, int cp_hint);
int decode_fsk(struct packet_t* packet, int start, int cp_hint);
int decode_pwm(struct packet_t* packet, int start, int cp_hint);
int decode_binary(struct packet_t* packet, int start, int cp_hint);

#endif
