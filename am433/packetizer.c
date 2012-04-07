#include <stdlib.h>
#include <assert.h>

#include "packetizer.h"
#include "capture.h"

static struct packet_t* packet_new()
{
	struct packet_t* packet;

	packet = calloc(1, sizeof(struct packet_t));
	packet->data = calloc(1, DATASIZE);
	packet->len = 0;
	packet->start = -1;

	packet->ntran = 0;
	packet->breaklen = 0;

	packet->decoded = calloc(1, DECODESIZE);
	packet->bitcount = 0;

	packet->modulation = MOD_UNKNOWN;

	packet->leader_edges = 0;
	packet->trailer_edges = 0;

	return packet;
}

void packet_free(struct packet_t* packet)
{
	assert(packet != NULL);

	free(packet->data);
	free(packet->decoded);
	free(packet);
}

struct packetizer_state_t* packetizer_state_new()
{
	struct packetizer_state_t* state;

	state = calloc(1, sizeof(struct packetizer_state_t));
	state->sample_cnt = 0;
	state->pv = 0;
	state->packet = NULL;

	return state;
}

struct packet_t* packetizer(struct packetizer_state_t* state, unsigned char** buff, ssize_t* bytesleft) 
{

	if(state->packet == NULL) {
		state->packet = packet_new();
	}

	struct packet_t* packet = state->packet;

	/* calling packetizer with bytesleft = 0 means end of stream.
	 * return any unfinished packet in the buffer */
	if(*bytesleft == 0 && packet->start >= 0) {
		packet->len = packet->end - packet->start;
		state->packet = NULL;
		return packet;
	}

	while(*bytesleft > 0) {
		unsigned char v = **buff;

		(*bytesleft)--;
		(*buff)++;

		if(v != state->pv) {
			//printf("EDGE %d\n", state->sample_cnt);
			if(packet->start < 0) {
				//printf("START %d\n", state->sample_cnt);
				packet->start = state->sample_cnt;
			}
			packet->end = state->sample_cnt;
			state->pv = v;

			packet->ntran++;
			packet->breaklen = ((packet->end - packet->start) / packet->ntran) * PKT_BREAK_NTRAN;
			//printf("packetizer: breaklen=%d\n", packet->breaklen);
			if(packet->breaklen > PKT_BREAK_MAX_SAMP) {
				packet->breaklen = PKT_BREAK_MAX_SAMP;
			} else if(packet->breaklen < PKT_BREAK_MIN_SAMP) {
				packet->breaklen = PKT_BREAK_MIN_SAMP;
			}
		}
	
		if(packet->start >= 0) {
			packet->data[packet->len] = v;
			packet->len++;
			if(packet->len >= DATASIZE) {
				//printf("DATASIZE reached!\n");
				packet->end = packet->start + packet->len;

				state->packet = NULL;
				state->sample_cnt++;
				return packet;
			}
			//printf("== %d %d\n", state->sample_cnt, packet->end);

			if(!v && ((state->sample_cnt - packet->end) > packet->breaklen)) {
				packet->len = packet->end - packet->start;

				state->packet = NULL;
				state->sample_cnt++;
				return packet;
			}
		}

		state->sample_cnt++;
	}

	return NULL;
}
