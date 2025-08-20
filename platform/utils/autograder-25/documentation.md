## Part 1

### Check l2 host ipv4 connection within DCN

1. print each DCN l2 host's ipv4 interface (ifconfig) facing to the l2 switch
2. print each DCN l2 host's ipv4 gateway address (ip r)
3. print each DCN gateway router's vlan 10 and vlan 20 ipv4 interface (show interface brief json)
4. print each DCN switch vlan tag on each interface (ovs-vsctl show)
5. get ipv4 ping loss (-c 2) for each pair of DCN l2 hosts with the same vlan tag
6. if the ping is successful, get 1 ipv4 traceroute for each pair of DCN l2 hosts with the same vlan tag, a correct traceroute should only contain the destination address
7. get ipv4 ping loss for each pair of DCN l2 hosts with different vlan tags
8. if the ping is successful, get 1 ipv4 traceroute for each pair of DCN l2 hosts with different vlan tags, a correct traceroute should contain gateway router
9. report total success rate for all pair of connection checks

### Check l3 interface configuration (only ipv4)

0. cache each router's interface json (show interface brief json)
1. check each router's loopback interface is as expected
2. check each router and host's interfaces (ifconfig) facing each other are as expected
3. check each pair of routers interfaces facing each other are as expected
4. check each router interface connected to the service (matrix, measurement, dns) are as expected
5. report total success rate for all configuration checks

### Check all l3-l2 host connection

1. get ipv4 ping loss for each pair of l3 hosts using their expected interfaces (TODO: check the route is either directly connected or learnt via ospf)
2. print a random pair of l3 hosts traceroute with DNS flag
3. get ipv4 ping loss for each pair of l3 and DCN l2 hosts
4. get ipv4 ping loss for each l3/l2 host and DNS
5. report total success rate for all pair of connection checks

### Check l3 load balancing

1. get each router's ospf interface json (show ip ospf interface json)
2. compute a directed ospf graph and cache it
3. compute the theoretical shortest paths between src and dst routers for both directions and compare the results with the expected shortest paths
4. get ping loss from src to dst host (already did it before, but didn't cache all ping results, so just do it again), if the ping is successful, get 10 traceroutes from src to dst, and check each hop always display expected links, and report all violated hop-link combinations
5. repeat 4 from dst to src
6. report total success rate for each theoretical and data plane path checks

### Check l2 host ipv6 connection within same DC (similar to l2 host ipv4 check)

1. print each DCN/DCS l2 host's ipv6 interface facing to the l2 switch
2. print each l2 host's ipv6 gateway address (ip -6 r)
3. print each DCS switch vlan tag on each interface
5. get ipv6 ping loss for each pair of DCN/DCS l2 hosts with the same vlan tag
6. if the ping is successful, get 1 ipv6 traceroute (traceroute -6) for each pair of DCN/DCS l2 hosts with the same vlan tag, a correct traceroute should only contain the destination address
7. get ipv6 ping loss for each pair of DCN/DCS l2 hosts with different vlan tags
8. if the ping is successful, get 1 ipv6 traceroute for each pair of DCN/DCS l2 hosts with different vlan tags, a correct traceroute should contain gateway router
9. report total success rate for all pair of connection checks


### Check l2 host ipv6 connection across DC

1. print 6in4 tunnel configuration on both ends of the expected tunnel (ip tunnel show)
2. get ipv6 ping loss for each pair of across DC l2 hosts
3. if the ping is successful, get 1 ipv6 traceroute for each pair of across DC l2 hosts, a correct traceroute should have its gateway as the first hop and the dst host ip as the last hop
4. report total success rate for each pair of connection checks

### VPN (cannot check atm, as it requires students to operate on their local machines, one way could be to ask students to scp a unique file to mini-internet)

> Note: connection check involving l2 hosts tend to be much slower than l3, hence going through the entire part 1 check could take ~2min

## Part 2

### Check ibgp full mesh

0. cache each router's bgp neighbor json (show bgp neighobrs json) 
1. check each router has all other AS router as bgp neighbors and their local router id (lo) and remoteAs are as expected, also check the bgpstate is established
2. report total success rate for all pairs of ibgp sessions  

### Check AS-level interface configuration

1. get expected configuration from `aslevel_links_students.txt`
2. get each router's external link interfaces (all sources required have be acquired in previous checks) and check they are within the expected subnets
3. report total success rate for all interface checks

### Set up shadow AS

1. create containers for each router and for the routinator host, here I need access to folder `groups/rpki/` and mount some of some files to routinator container
2. create internal links without using ovs bridge, instead I connect two containers directly
3. load router and routinator configuration, here I need to download each router's full running config and the entire `/root/.rpki-cache/repository/` in BASEhost container
4. create ExaBGP container and set up eBGP sessions with shadow AS, the configuration I need here is already required from previous checks, let each eBGP neighobr announce its own network to the AS
5. wait for 1min BGP convergence for routinator validation to take effect, and start below checks on the shadow AS 

### Update shadow AS

1. whenever a new student AS is checked, first remove ExaBGP container, then recreate it and its links with the new interface configuration
2. clear any legacy interface names on routers, load new router and routinator configuration

### Check eBGP sessions

1. check all eBGP sessions with ExaBGP are active and Exabgp receives the student network at all eBGP sessions
2. check each router selects all external neighbors' own networks, check the network is only learnt via one source (either from the neighbor directly or from the border router) and check if it is learnt via border router, the peer id is the loopback address of the border router
3. report total success rate for all route checks

### Check business relationship

### Check IXP policy

### Check RPKI configuration 