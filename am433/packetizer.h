#ifndef HAVE_PACKETIZER_H
#define HAVE_PACKETIZER_H

#define PKT_BREAK_MIN_MS	4
#define PKT_BREAK_MAX_MS	8
#define PKT_BREAK_NTRAN		10

#define PKT_BREAK_MIN_SAMP	(PKT_BREAK_MIN_MS * FS / 1000)
#define PKT_BREAK_MAX_SAMP	(PKT_BREAK_MAX_MS * FS / 1000)

#define DATASIZE	409600
#define DECODESIZE	4096

struct packet_t {
	int start;
	int end;
	int len;
	unsigned char* data;

	/* number of signal transitions seen by the packetizer */
	int ntran;
	int breaklen;

	unsigned char* decoded;
	int bitcount;
	int cp;

	int modulation;

	int leader_edges, trailer_edges;
};

struct packetizer_state_t {
	int sample_cnt;
	unsigned char pv;

	struct packet_t* packet;
};

void packet_free(struct packet_t* packet);

struct packetizer_state_t* packetizer_state_new();

struct packet_t* packetizer(struct packetizer_state_t* state, unsigned char** buff, ssize_t* bytesleft);
#endif
