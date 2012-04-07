#include <alsa/asoundlib.h>

/* Handle for the PCM device */ 
snd_pcm_t *pcm_handle;          

/* Playback stream */
snd_pcm_stream_t stream = SND_PCM_STREAM_PLAYBACK;

/* This structure contains information about    */
/* the hardware and can be used to specify the  */      
/* configuration to be used for the PCM stream. */ 
snd_pcm_hw_params_t *hwparams;

/* Name of the PCM device, like plughw:0,0          */
/* The first number is the number of the soundcard, */
/* the second number is the number of the device.   */
char *pcm_name;
