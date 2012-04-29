#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/stat.h>
#include <sys/time.h>
#include <fcntl.h>
#include <assert.h>
#include <alsa/asoundlib.h>

#include "capture.h"
#include "packetizer.h"
#include "mon.h"
#include "decode.h"

#define BUFFSIZE	4096

int do_stats = 0;
int sample_limit = 0;
char* log_file = NULL;
int stats_interval_s = 60;

typedef int (*decode_func)(struct packet_t* packet, int start, int cp_hint);
typedef int (*print_func)(struct packet_t* packet, struct timeval timestamp);

print_func use_print_func;

int ascii_print_func(struct packet_t* packet, struct timeval timestamp)
{
	int n;

	printf("PACKET: %ld (%.2f s) %ld (%.2f s) %d (%.2f s)\n",
			packet->start, 
			((double) packet->start)/FS,
			packet->end, 
			((double) packet->end)/FS,
			packet->len,
			((double) packet->len)/FS);

	if(packet->modulation != MOD_UNKNOWN) {
		int m = packet->bitcount/8;
		if(packet->bitcount % 8 > 0) m++;

		printf("    mod   %d\n", packet->modulation);
		if(packet->cp > 0) {
			printf("    clock %d Hz\n", FS / packet->cp);
		}
		printf("    data  ");

		for(n = 0; n < m; n++) {
			printf("%02x ", packet->decoded[n]);
		}
	} else {
		printf("    mod   unknown\n\n");
		/*
		for(n = 0; n < packet->len; n++) {
			if(n != 0 && n % 80 == 0) {
				printf("\n");
			}
			if(packet->data[n] > 0) {
				printf("1");
			} else {
				printf("0");
			}
		}
		*/
	}
	printf("\n\n");
	fflush(stdout);

	return 0;
}

void restore_dc(unsigned char* buff, ssize_t len) {

	const int threshold = 245;
	ssize_t n;
	
	for(n = 0; n < len; n++) {
		if(buff[n] >= threshold) {
			//putchar(255);
			buff[n] = 0;
		} else {
			//putchar(0);
			buff[n] = 1;
		}
		//printf("%d\n", buff[n]);
	}
}

int lfind_edge(struct packet_t* packet, int start, int n) {

	if(n == 0) {
		return start;
	} else {
		int pv = start < 0 ? 0 : packet->data[start];
		int t;

		for(t = start; t < packet->len; t++) {
			int v = t < 0 ? 0 : packet->data[t];

			if(pv != v && v == 1) {
				n--;
				if(n == 0) {
					return t;
				}
			}
			pv = v;
		}
		return -1;
	}
}

int rfind_edge(struct packet_t* packet, int start, int n) {

	if(n == 0) {
		return packet->len;
	} else {
		int pv = packet->data[packet->len-1];
		int t;

		for(t = packet->len-1; t >= 0; t--) {
			int v = packet->data[t];

			if(pv != v && v == 1) {
				n--;
				if(n == 0) {
					return t;
				}
			}
			pv = v;
		}
		return -1;
	}
}

int decode_leader(struct packet_t* packet, int start, int cp_hint, decode_func f) {
	int lstartn, lstopn;
	int lstart, lstop;
	for(lstopn = 0; lstopn < 4; lstopn++) {
		lstop = rfind_edge(packet, start, lstopn);
		if(lstop < 0) return -1;
		
		for(lstartn = 0; lstartn < 4; lstartn++) {
			lstart = lfind_edge(packet, start, lstartn);
			if(lstart < 0) return -1;

			debug("leader: start=%d stop=%d", lstart, lstop);

			int oldlen = packet->len;
			packet->len = lstop;

			int retval = f(packet, lstart, cp_hint);

			packet->len = oldlen;

			if(!retval) {
				packet->leader_edges = lstartn;
				packet->trailer_edges = lstopn;
				return retval;
			}
		}
	}
	return -1;
}

int is_noise(struct packet_t* packet) {
	int is_all_ones = 1;
	int is_all_zeros = 1;
	int n;

	if (packet->bitcount <= 8) {
		if (packet->modulation == MOD_UNKNOWN) {
			return 0;
		} else {
			debug("is_noise: too few bits: %d", packet->bitcount);
			return 1;
		}
	}

	unsigned char last_mask = (1<<(8-(packet->bitcount%8))) - 1;

	for (n = 0; n < packet->bitcount/8; n++) {
		if (packet->decoded[n] != 0xff) {
			is_all_ones = 0;
		}
		if (packet->decoded[n] != 0x00) {
			is_all_zeros = 0;
		}
	}

	if (is_all_ones) {
		unsigned char last_byte = packet->decoded[n] | last_mask;
		if (last_byte == 0xff) {
			debug("is_noise: %d ones", packet->bitcount);
			return 1;
		}
	}
	if (is_all_zeros) {
		unsigned char last_byte = packet->decoded[n];
		if (last_byte == 0x00) {
			debug("is_noise: %d zeros", packet->bitcount);
			return 1;
		}
	}

	return 0;
}

static void
print_packet_stats(int ones, int len, struct timeval timestamp)
{
	printf("%lu\t%3.2f\t%d\t%d\n", timestamp.tv_sec,  
			((double)ones)/((double) len)*100.0,
			ones, len);
	fflush(stdout);
}

static void
process_packet_stats(struct packet_t* packet, struct timeval timestamp)
{
	static int ones = 0;
	static int last_interval = -1;

	const int interval_len = FS * stats_interval_s;

        /*        intervals
         *        0     1     2     3     4 
	 * |-----|-----|-----|-----|-----|-----|
	 *       |start recording
	 */

	int i, n;
	if (last_interval != -1) {
		int missed_intervals = (packet->start/interval_len) 
				- last_interval;

		for(n = 0; n < missed_intervals; n++) {
			struct timeval t = timestamp;
			t.tv_sec += (interval_len * (last_interval + n)) / FS;
			print_packet_stats(ones, interval_len, t);
			ones = 0;
		}
	}
	assert(packet->len > 0);
	for(i = 0; i < packet->len; i++) {
		n = packet->start + i;
		if (packet->data[i]) ones++;

		if ((n % interval_len) == 0) {
			struct timeval t = timestamp;
			t.tv_sec += (n - interval_len) / FS;
			print_packet_stats(ones, interval_len, t);
			ones = 0;
		}
	}
	assert(n == packet->end - 1);
	last_interval = packet->end / interval_len;
}

int process_packet(struct packet_t* packet, struct timeval timestamp) 
{
	if(packet->len < 2) {
		return 0;
	}
		
	int retval = -1;

	if(retval) retval = decode_binary(packet, 0, 0);
//	if(retval) retval = decode_pwm(packet, 0, 0);
//	if(retval) retval = decode_fsk(packet, 0, 0);
//	if(retval) retval = decode_leader(packet, 0, 0, decode_pwm);
//	if(retval) retval = decode_leader(packet, 0, 0, decode_fsk);
//	if(retval) retval = decode_manchester(packet, 0, 0);
//	if(retval) retval = decode_ppk(packet, 0, 0);

	if(!is_noise(packet)) {
		return use_print_func(packet, timestamp);	
	} else {
		return 0;
	}
}

int process_file(char *path) {
	unsigned char buff[BUFFSIZE];

	int fd = open(path, O_RDONLY);
	if(fd < 0) {
		perror("capture");
		return -1;
	}

	ssize_t len;

	struct packetizer_state_t* state = packetizer_state_new();

	struct timeval timestamp;
	timestamp.tv_sec = 0;
	timestamp.tv_usec = 0;

	do {
		len = read(fd, buff, BUFFSIZE);
		if(len < 0) {
			perror("capture");
			return -1;
		};
		restore_dc(buff, len);

		struct packet_t* packet;
		unsigned char* buffp = buff;
		ssize_t bytesleft = len;
		while((packet = packetizer(state, &buffp, &bytesleft)) != NULL) {
			assert(packet->len == packet->end - packet->start);

			if(do_stats) {
				process_packet_stats(packet, timestamp);
			} else {
				int err = process_packet(packet, timestamp);
				if(err) return err;
			}
			packet_free(packet);

			if(bytesleft <= 0) break;
		}
	} while(len > 0);

	free(state);
	close(fd);

	return 0;
}

int process_alsa(char* device)
{
	int err;
	unsigned char buf[BUFFSIZE];
	snd_pcm_t *capture_handle;
	snd_pcm_hw_params_t *hw_params;
	snd_pcm_status_t *status;

	err = snd_pcm_open(&capture_handle, device, SND_PCM_STREAM_CAPTURE, 0);
	if (err < 0) {
		fprintf(stderr, "cannot open audio device %s (%s)\n", 
			 device,
			 snd_strerror(err));
		return -1;
	}
	   
	if ((err = snd_pcm_hw_params_malloc(&hw_params)) < 0) {
		fprintf(stderr, "cannot allocate hardware parameter structure "
			"(%s)\n", snd_strerror (err));
		return -1;
	}
			 
	if ((err = snd_pcm_hw_params_any(capture_handle, hw_params)) < 0) {
		fprintf (stderr, "cannot initialize hardware parameter structure (%s)\n",
			 snd_strerror (err));
		return -1;
	}

	err = snd_pcm_hw_params_set_access(capture_handle, hw_params,
			SND_PCM_ACCESS_RW_INTERLEAVED);
	if (err < 0) {
		fprintf (stderr, "cannot set access type (%s)\n",
			 snd_strerror (err));
		return -1;
	}

	err = snd_pcm_hw_params_set_format(capture_handle, hw_params,
			SND_PCM_FORMAT_U8);
	if (err < 0) {
		fprintf (stderr, "cannot set sample format (%s)\n",
			 snd_strerror (err));
		return -1;
	}

	if ((err = snd_pcm_hw_params_set_rate(capture_handle, hw_params, FS, 0)) < 0) {
		fprintf (stderr, "cannot set sample rate (%s)\n",
			 snd_strerror (err));
		return -1;
	}

	if ((err = snd_pcm_hw_params_set_channels (capture_handle, hw_params, 1)) < 0) {
		fprintf (stderr, "cannot set channel count (%s)\n",
			 snd_strerror (err));
		return -1;
	}

	if ((err = snd_pcm_hw_params (capture_handle, hw_params)) < 0) {
		fprintf (stderr, "cannot set parameters (%s)\n",
			 snd_strerror (err));
		return -1;
	}

	snd_pcm_hw_params_free (hw_params);

	if ((err = snd_pcm_prepare (capture_handle)) < 0) {
		fprintf (stderr, "cannot prepare audio interface for use (%s)\n",
			 snd_strerror (err));
		return -1;
	}

	if ((err = snd_pcm_start(capture_handle)) < 0) {
		fprintf(stderr, "cannot start stream (%s)\n", 
			snd_strerror(err));
		return -1;
	}

	snd_pcm_status_alloca(&status);
	if ((err = snd_pcm_status(capture_handle, status)) < 0) {
		fprintf(stderr, "cannot get stream status (%s)\n",
			snd_strerror(err));
		return -1;
	}

	struct timeval timestamp;
	snd_pcm_status_get_trigger_tstamp(status, &timestamp);

	// Very stupid way of accounting for monotonic clock offset
	struct timespec rt, mon;
	clock_gettime(CLOCK_REALTIME, &rt);
	clock_gettime(CLOCK_MONOTONIC, &mon);
	timestamp.tv_sec += rt.tv_sec - mon.tv_sec;
	timestamp.tv_usec += (rt.tv_nsec - mon.tv_nsec) / 1000;

	struct packetizer_state_t* state = packetizer_state_new();

	int fd = -1;
	if (log_file != NULL) {
		fd = open(log_file, O_TRUNC|O_WRONLY|O_CREAT, 0644);
	}

	while((!sample_limit) || state->sample_cnt < sample_limit) {
		err = snd_pcm_readi(capture_handle, buf, BUFFSIZE);
		if(err != BUFFSIZE) {
			fprintf(stderr, 
				"read from audio interface failed (%s)\n",
				snd_strerror (err));
			return -1;
		}

		if (fd >= 0) write(fd, buf, BUFFSIZE);

		restore_dc(buf, BUFFSIZE);

		struct packet_t* packet;
		unsigned char* buffp = buf;
		ssize_t bytesleft = BUFFSIZE;
		while((packet = packetizer(state, &buffp, &bytesleft)) != NULL) {
			assert(packet->len == packet->end - packet->start);

			if(do_stats) {
				process_packet_stats(packet, timestamp);
			} else {
				int err = process_packet(packet, timestamp);
				if(err) return err;
			}
			packet_free(packet);

			if (bytesleft <= 0) break;
		}
	}

	if (fd >= 0) close(fd);

	free(state);
	snd_pcm_close (capture_handle);

	return 0;
}

void usage() {
	printf(	"Usage: capture [OPTION]... [-f FILE|-d DEVICE]\n"
		"Read baseband data from FILE or DEVICE and write decoded packets to stdout.\n\n"
		"  -d DEVICE     read baseband data from ALSA DEVICE (e.g. \"plughw:1,0\")\n"
		"  -f FILE       read baseband data from FILE\n"
		"  -l FILE       log input baseband data into FILE (raw mono unsigned 8 bit)\n"
		"  -m            use binary format for packet data on stdout\n"
		"  -s [SECONDS]  write aggregate channel statistics instead of packet data,\n"
		"                updating every SECONDS\n"
		"  -t SECONDS    exit after SECONDS elapsed\n"
		"  -v            enable verbose decoder debug output on stderr\n");
}

int main(int argc, char** argv) {
	int opt;
	int retval = 0;

	int cmd = 0;
	char *input = NULL;
	
	use_print_func = ascii_print_func;
	
	while((opt = getopt(argc, argv, "mpvf:d:l:s::t:")) != -1) {
		switch(opt) {
			case 'f':
			case 'd':
				cmd = opt;
				input = strdup(optarg);
				break;
			case 'v':
				verbose = 1;
				break;
			case 'l':
				log_file = strdup(optarg);
				break;
			case 'm':
				use_print_func = mon_print_func;
				break;
			case 's':
				do_stats = 1;
				if(optarg) {
					stats_interval_s = atoi(optarg);
				}
				printf("#time\t\tutil\tacts\talls\n");
				break;
			case 't':
				sample_limit = atoi(optarg) * FS;
				break;
			default:
				usage();
				exit(1);
		}
	}

	switch(cmd) {
		case 'f':
			retval = process_file(input);
			break;
		case 'd':
			retval = process_alsa(input);
			break;
		default:
			usage();
			retval = 0;
			break;
	}

	if (log_file != NULL) free(log_file);
	if (input != NULL) free(input);

	return -retval;
}
