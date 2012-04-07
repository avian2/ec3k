all: recv.netlist

%.netlist: %.sch
	gnetlist -g PCB -o $@ $^

clean:
	rm -f *.netlist

.PHONY: all clean
