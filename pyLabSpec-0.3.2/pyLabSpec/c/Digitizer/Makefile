
all default: SimpleAcquisition

%: %.cpp
	$(CXX) $(CPPFLAGS) $(CXXFLAGS) $< $(LDFLAGS) -lAgMD2 -ldl -lpthread -o $@

clean:
	rm -f *.o
	rm -f SimpleAcquisition
	echo clean done !
