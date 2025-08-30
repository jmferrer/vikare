#!/bin/bash
ADDRESS=192.168.43.113
# y max = 1500
# y
ssh root@$ADDRESS motors -d h -y 2000
sleep 5
ssh root@$ADDRESS motors -d h -y 0
sleep 5
ssh root@$ADDRESS motors -d h -y 300
sleep 5

# x max = 4050
# x
ssh root@$ADDRESS motors -d h -x 6000
sleep 10
ssh root@$ADDRESS motors -d h -x 0
sleep 10
ssh root@$ADDRESS motors -d h -x 2025
sleep 5
