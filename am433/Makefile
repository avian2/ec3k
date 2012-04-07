SRCS = capture.c packetizer.c mon.c decode.c

OBJS = $(SRCS:.c=.o)

all: capture

%.d: %.c
	$(SHELL) -ec "$(CPP) -M $(CPPFLAGS) $< | sed 's#$*.o#& $@#g' > $@"

%.o: %.c
	gcc -g -O2 -Wall -c -o $@ $<

capture: $(OBJS)
	gcc -g -lasound -o $@ $^

clean:
	rm -f *.o *.d capture

test: all
	cd tests && ./runner.sh

include $(SRCS:.c=.d)

.PHONY: all clean test
