import json
import network
import time
import ntptime
import machine
from machine import UART, Pin
import ujson
import urequests

# Needs file hmc5883l.py in the same folder
from hmc5883l import HMC5883L

# Needs file imu.py in the same folder
from imu import MPU6050
from machine import I2C
import math



# Set up UART SCI interface
uart = UART(1, baudrate=115200, tx=17, rx=16)

# Roomba driving commands
START = bytes([128])
# Modes of operation
SAFE_MODE = bytes([131])
FULL_MODE = bytes([132])
POWER_DOWN = bytes([133])
DRIVE = bytes([137]) + bytes([0, 100, 128, 0]) # bytes para 100 mm/s de velocidad y radio 'Directo'
DRIVE_BACK = bytes([137]) + bytes([255, 155, 128, 0]) # bytes para -100 mm/s de velocidad y radio 'Directo'
DRIVE_RIGHT = bytes([137]) + bytes([0, 100, 255, 255])
DRIVE_LEFT = bytes([137]) + bytes([0, 100, 0, 1])
STOP = bytes([137, 0, 0, 0, 0])  # velocidad 0, radio 0
DOCK = bytes([143])  # Seek docking station
CLEAN = bytes([135])   # Start cleaning mode
SPOT = bytes([134])    # Spot cleaning mode
POWER_UP = bytes([138, 4])    # Power up from sleep mode
BUMPERS=bytes([142, 7])

INFRARED = bytes([142, 7])

CLIFF_LEFT=bytes([142, 9])
CLIFF_FRONT_LEFT=bytes([142, 10])
CLIFF_FRONT_RIGHT=bytes([142, 11])
CLIFF_RIGHT=bytes([142, 12])

ASK_BATTERY_CHARGE=bytes([142, 25])
ASK_BATTERY_CAPACITY=bytes([142, 26])

REQUEST_DISTANCE=bytes([142, 19])

def load_config(config="config.json"):
    with open(config, 'r') as file:
        content = json.load(file)
    return content

def wifi(essid, password):
    # Can be improved if checking available networks when Signal Level is too low
    # print(network.WLAN(network.STA_IF).scan())
    # returns a list of networks: https://docs.micropython.org/en/latest/library/network.WLAN.html
    
    # Establish Wi-Fi connection
    print("Connecting to wifi ...")
    sta_if = network.WLAN(network.STA_IF)
    sta_if.active(True)
    sta_if.connect(essid, password)

    # Wait for connection
    while not sta_if.isconnected():
        print("Connecting to wifi ...")
        time.sleep(1)

    return sta_if

def sync_time():
    retries = 5
    for i in range(retries):
        try:
            
            ntptime.host = "time.google.com"
            ntptime.settime()
            rtc = machine.RTC()
            print('Current RTC time:', rtc.datetime())

            # Time sync with Roomba
            now = time.localtime()
            SET_DAY_TIME = bytes([168, now[6], now[3], now[4]])
            uart.write(SET_DAY_TIME)
            time.sleep(0.2)
            return now
        except OSError as e:
            print(f"❌ ntptime failed ({e}), retrying... {i+1}/{retries}")
            time.sleep(1)
    else:
        print("⚠️ No se pudo sincronizar la hora con el servidor NTP.")
        exit (1)

def start_roomba():
    # Switch on physically the roomba 8xx using a relay in pin 32
    power_button=Pin(32, Pin.OUT)
    power_button.value(1)
    time.sleep(0.2)
    power_button.value(0)
    time.sleep(1)
    print("powered on")

    # Initialize Roomba sci port
    uart.write(START)
    time.sleep(0.2)
    uart.write(SAFE_MODE)
    time.sleep(0.2)

    return 1


## Sensors related functions

def get_distance():
    # Get distance from Roomba
    # In roomba 850 25cm are around 30cm o 31cm for get_distance() :-/
    uart.write(REQUEST_DISTANCE)  # Request Distance
    time.sleep(0.02)
    distance_data = uart.read(2)
    if distance_data is not None:
        #print("distance: " + str(distance_data))
        high, low = distance_data
        distance = (high << 8) | low
        if distance > 32767:
            distance -= 65536
        
        # rule of three for model 850:
        # 30.5     -> 25cm
        # distance -> x
        real_distance = distance * 25 / 30.5
        # When going forward returns negative numbers
        return real_distance * -1
    else:
        print("Error reading distance data from Roomba.")
        return None  # Or handle the error differently if needed.

def get_battery_percentage():
    try:
        uart.write(ASK_BATTERY_CHARGE)  # Request battery charge
        time.sleep(0.017)
        raw_charge = uart.read(2)
        if raw_charge is None or len(raw_charge) != 2:
            raise ValueError("Failed to read battery charge")
        battery_charge = int.from_bytes(raw_charge, 'big')
    
        uart.write(ASK_BATTERY_CAPACITY)  # Request battery capacity
        time.sleep(0.017)
        raw_capacity = uart.read(2)
        if raw_capacity is None or len(raw_capacity) != 2:
            raise ValueError("Failed to read battery capacity")
        battery_capacity = int.from_bytes(raw_capacity, 'big')

        battery_percentage = (battery_charge / battery_capacity) * 100
        #print("🔋 Battery %:", battery_percentage)
        return battery_percentage
    except Exception as e:
        print("⚠️ Battery read failed:", e)
        return -1

def get_compass_angle():
    # TODO: Implement this function to read the compass angle from esp32 sensor
    sensor = HMC5883L(scl=21, sda=22)

    x, y, z = sensor.read()
    degrees, minutes = sensor.heading(x, y)
    #print(str(degrees))
    #print(str(minutes))

    return ((degrees - 90) % 360)

def check_for_collision():
    uart.write(BUMPERS)  # Request Bumpers
    time.sleep(0.017)
    output = uart.read(1)
    #print("uart_read: " + str(output))
    
    # bump_and_wheel_drops = uart.read(1)[0]
    # print("bump_and_wheel_drops: " + str(bump_and_wheel_drops))

    if output == bytes([0]):
        collision = False
    elif output == bytes([1]):
        collision = 'right'
    elif output == bytes([2]):
        collision = 'left'
    elif output == bytes([3]):
        collision = 'front'
    else:
        collision = 'unknown'
        
    return collision

def actual_time():
    year   = "{}".format(time.localtime()[0])
    month  = "{:02d}".format(time.localtime()[1])
    day    = "{:02d}".format(time.localtime()[2])
    hour   = "{:02d}".format(time.localtime()[3])
    minute = "{:02d}".format(time.localtime()[4])
    second = "{:02d}".format(time.localtime()[5])
    # Vendrían bien los milisegundos aquí

    return(year + "-" + month + "-" + day + "-" + hour + "-" + minute + "-" + second)

# Se inicializa fuera para no reiniciar en cada llamada
i2c = I2C(0, sda=Pin(22), scl=Pin(21), freq=400000)
imu = MPU6050(i2c)

def get_gyroscope():
    # Lecturas crudas
    gyro = imu.gyro
    accel = imu.accel

    # Convertimos a valores legibles
    gyro_data = {
        'x': round(gyro.x, 2),
        'y': round(gyro.y, 2),
        'z': round(gyro.z, 2)
    }

    accel_data = {
        'x': round(accel.x, 2),
        'y': round(accel.y, 2),
        'z': round(accel.z, 2)
    }

    # Detectamos movimiento si hay rotación significativa (> threshold)
    motion_threshold = 10  # deg/s, depende del ruido del sensor
    is_moving = any(abs(v) > motion_threshold for v in gyro_data.values())

    # Detectamos choque si hay aceleración anómala
    accel_magnitude = math.sqrt(accel.x**2 + accel.y**2 + accel.z**2)
    shock_detected = accel_magnitude > 1.5  # >1g normalmente es un choque

    # Calcular inclinación (pitch y roll en grados)
    pitch = math.atan2(accel.x, math.sqrt(accel.y**2 + accel.z**2)) * (180 / math.pi)
    roll = math.atan2(accel.y, math.sqrt(accel.x**2 + accel.z**2)) * (180 / math.pi)

    tilt_data = {
        'pitch': round(pitch, 2),
        'roll': round(roll, 2)
    }

    return {
        'gyro': gyro_data,
        'accel': accel_data,
        'is_moving': is_moving,
        'shock_detected': shock_detected,
        'tilt': tilt_data
    }

def get_cliff():
    # TODO: implement this function to read the cliff data
    cliff_sensors = {}

    # Cliff Left
    uart.write(CLIFF_LEFT)
    time.sleep(0.017)
    data = uart.read(1)
    cliff_sensors["left"] = int.from_bytes(data, 'big') if data else -1

    # Cliff Front Left
    uart.write(CLIFF_FRONT_LEFT)
    time.sleep(0.017)
    data = uart.read(1)
    cliff_sensors["front_left"] = int.from_bytes(data, 'big') if data else -1

    # Cliff Front Right
    uart.write(CLIFF_FRONT_RIGHT)
    time.sleep(0.017)
    data = uart.read(1)
    cliff_sensors["front_right"] = int.from_bytes(data, 'big') if data else -1

    # Cliff Right
    uart.write(CLIFF_RIGHT)
    time.sleep(0.017)
    data = uart.read(1)
    cliff_sensors["right"] = int.from_bytes(data, 'big') if data else -1

    return cliff_sensors

def get_sensors_data():
    # Get sensors data from Roomba
    # - distance
    # - battery level
    # - compass
    # - bumpers
    # - time
    # - gyroscope
    # - cliff
    sensors_data = {}
    sensors_data['distance'] = get_distance()
    sensors_data['battery'] = get_battery_percentage()
    sensors_data['compass'] = get_compass_angle()
    sensors_data['bumpers'] = check_for_collision()
    sensors_data['time'] = actual_time()
    #sensors_data['gyroscope'] = get_gyroscope()
    sensors_data['cliff'] = get_cliff()

    return sensors_data

def send_sensors_data(sensors_data, service_url):
    request_url = service_url + "/sensors"
    headers = {'Content-Type': 'application/json'}

    try:
        post_data = ujson.dumps(sensors_data)
        try:
            res = urequests.post(request_url, headers=headers, data=post_data)
            return res
        except Exception as e:
            print("⚠️ Error al enviar datos al servidor:", e)
            return None
    except ValueError as e:
        print("⚠️ Error al codificar sensores a JSON:", e)
        return None

## Run instructions

def get_instructions(service_url):
    request_url = service_url + "/instructions"

    try:
        res = urequests.get(request_url)
        try:
            return json.loads(res.text)
        except ValueError:
            print("⚠️ Error: respuesta no es JSON válido")
            return None
    except Exception as e:
        print("⚠️ Error al conectar con el servidor de instrucciones:", e)
        return None

def stop():
    uart.write(STOP)
    time.sleep(0.2)

def dock():
    uart.write(DOCK)
    time.sleep(0.2)

## BEGIN synchronous execute instructions functions
def forward(distance):
    # Input is the requested distance in cm where 4.55 are 50cm
    # 50 cm -> 4.55 seconds
    # distance -> x seconds
    #led("red-up")
    uart.write(STOP)
    uart.write(DRIVE)
    time.sleep((4.55 * distance)/50)
    uart.write(STOP)
    #power_led()

def backward(distance):
    # Input is the requested distance in cm where 4.55 are 50cm
    # 50 cm -> 4.55 seconds
    # distance -> x seconds
    #led("red-down")
    uart.write(STOP)
    uart.write(DRIVE_BACK)
    time.sleep((4.55 * distance)/50)
    #uart.write(STOP)

def turn_left(angle):
    # Input is the requested angle. If 1.65 seconds for 90 degrees rotation
    # then 90/angle = x, where x is the multiplier for 1.65 seconds to get
    # the desired rotation speed.
    
    #led("white-left")
    uart.write(STOP)
    uart.write(DRIVE_LEFT)
    time.sleep((1.65 * angle)/90)
    uart.write(STOP)
    #power_led()

def turn_right(angle):
    # Input is the requested angle. If 1.65 seconds for 90 degrees rotation
    # then 90/angle = x, where x is the multiplier for 1<｜begin▁of▁sentence｜> to get
    # the desired rotation speed.
    
    #led("white-right")
    uart.write(STOP)
    uart.write(DRIVE_RIGHT)
    time.sleep((1.65 * angle)/90)
    uart.write(STOP)
    #power_led()


## Functions for testing motors internally
def forward(distance):
    # Input is the requested distance in cm where 4.55 are 50cm
    # 50 cm -> 4.55 seconds
    # distance -> x seconds
#    led("red-up")
    uart.write(STOP)
    uart.write(DRIVE)
    time.sleep((4.55 * distance)/50)
    uart.write(STOP)
#    power_led()

def backward(distance):
    # Input is the requested distance in cm where 4.55 are 50cm
    # 50 cm -> 4.55 seconds
    # distance -> x seconds
#    led("red-down")
    uart.write(STOP)
    uart.write(DRIVE_BACK)
    time.sleep((4.55 * distance)/50)
    uart.write(STOP)

def turn_left(angle):
    # Input is the requested angle. If 1.65 seconds for 90 degrees rotation
    # then 90/angle = x, where x is the multiplier for 1.65 seconds to get
    # the desired rotation speed.
    
#    led("white-left")
    uart.write(STOP)
    uart.write(DRIVE_LEFT)
    time.sleep((1.65 * angle)/90)
    uart.write(STOP)
#    power_led()

def turn_right(angle):
    # Input is the requested angle. If 1.65 seconds for 90 degrees rotation
    # then 90/angle = x, where x is the multiplier for 1<｜begin▁of▁sentence｜> to get
    # the desired rotation speed.
    
#    led("white-right")
    uart.write(STOP)
    uart.write(DRIVE_RIGHT)
    time.sleep((1.65 * angle)/90)
    uart.write(STOP)
#    power_led()

def execute_instructions(instructions):
    if "steps" in instructions:
        for step in instructions["steps"]:
            # steps has a key value pair. Print the key and value
            if "dock" in step:
                send_roomba_cmd(DOCK)
            if "turn_left" in step:
                degrees = int(step["turn_left"])
                turn_left(degrees)
            if "turn_right" in step:
                degrees = int(step["turn_right"])
                turn_right(degrees)
            if "forward" in step:
                centimeters = int(step["forward"])
                forward(centimeters)
            if "backward" in step:
                centimeters = int(step["backward"])
                backward(centimeters)
            if "scan" in step:
                # Scan the space
                scan(int(step["scan"]))

    else:
        "No instructions"
## END synchronous execute instructions functions

# ## BEGIN NOT synchronous execute instructions functions
# def async_forward(distance):
#     # Input is the requested distance in cm where 4.55 are 50cm
#     # 50 cm -> 4.55 seconds
#     # distance -> x seconds
#     uart.write(STOP)
#     uart.write(DRIVE)
#     # time.sleep((4.55 * distance)/50)
#     # uart.write(STOP)

#     # Calculate how much time must be in movement to reach that distance
#     duration = (4.55 * distance) / 50  # seconds
#     stop_time = time.time() + duration
#     return stop_time  # time when should stop

# def async_backward(distance):
#     # Input is the requested distance in cm where 4.55 are 50cm
#     # 50 cm -> 4.55 seconds
#     # distance -> x seconds
#     uart.write(STOP)
#     uart.write(DRIVE_BACK)
#     # time.sleep((4.55 * distance)/50)
#     # uart.write(STOP)
    
#     # Calculate how much time must be in movement
#     duration = (4.55 * distance) / 50  # seconds
#     stop_time = time.time() + duration
#     return stop_time

# def async_turn_left(angle):
#     # Input is the requested angle. If 1.65 seconds for 90 degrees rotation
#     # then 90/angle = x, where x is the multiplier for 1.65 seconds to get
#     # the desired rotation speed.
    
#     uart.write(STOP)
#     uart.write(DRIVE_LEFT)
#     # time.sleep((1.65 * angle)/90)
#     # uart.write(STOP)
    
#     # calculate how much time must be in movement
#     duration = (1.65 * angle) / 90
#     stop_time = time.time() + duration
#     return stop_time

# def async_turn_right(angle):
#     # Input is the requested angle. If 1.65 seconds for 90 degrees rotation
#     # then 90/angle = x, where x is the multiplier for 1<｜begin▁of▁sentence｜> to get
#     # the desired rotation speed.
    
#     #led("white-right")
#     uart.write(STOP)
#     uart.write(DRIVE_RIGHT)
#     # time.sleep((1.65 * angle)/90)
#     # uart.write(STOP)
#     # power_led()
    
#     # calculate how much time must be in movement
#     duration = (1.65 * angle) / 90
#     stop_time = time.time() + duration
#     return stop_time


# # This variables controll the state of movement of the robot.
# # Useful to know when to stop moving without doing a sleep that blocks the program.
# current_instruction_index = 0
# current_stop_time = None
# is_moving = False

# def async_execute_instructions(instructions):
#     # We expect a list of instructions that can be only:
#     # - forward(distance in centimeters)
#     # - backward(distance in centimeters)
#     # - turn_left(angle in degrees)
#     # - turn_right(angle in degrees)
#     # - stop
#     # - start
#     # - dock

#     global current_instruction_index, current_stop_time, is_moving

#     if "steps" not in instructions or not instructions["steps"]:
#         print("No steps found in the instructions.")
#         return False  # nada que hacer

#     steps = instructions["steps"]

#     if current_instruction_index >= len(steps):
#         return False  # terminamos las instrucciones

#     current_time = time.time()

#     if is_moving:
#         # Si estamos en movimiento, comprobamos si debemos detenernos
#         if current_time >= current_stop_time:
#             stop()
#             is_moving = False
#             current_instruction_index += 1
#             time.sleep(0.1)  # mini delay antes del siguiente paso
#         return True

#     # Ejecutamos el siguiente paso
#     step = steps[current_instruction_index]
#     if "forward" in step:
#         distance = step["forward"]
#         current_stop_time = async_forward(distance)
#         is_moving = True
#     elif "backward" in step:
#         distance = step["backward"]
#         current_stop_time = async_backward(distance)
#         is_moving = True
#     elif "turn_left" in step:
#         angle = step["turn_left"]
#         current_stop_time = async_turn_left(angle)
#         is_moving = True
#     elif "turn_right" in step:
#         angle = step["turn_right"]
#         current_stop_time = async_turn_right(angle)
#         is_moving = True
#     elif "dock" in step:
#         dock()
#         current_instruction_index += 1
#     elif "stop" in step:
#         stop()
#         current_instruction_index += 1
#     elif "start" in step:
#         start_roomba()
#         current_instruction_index += 1
#     else:
#         print(f"Unknown instruction: {step}")
#         current_instruction_index += 1

#     return True  # hay más pasos o estamos en movimiento
# ## END NOT synchronous execute instructions functions

def main_program():
    # Get config from config.json
    config = load_config()
    # Configure wifi
    sta_if = wifi(config["wifi"]["essid"], config["wifi"]["password"])
    # Configure time
    sync_time()
    # Start roomba
    start_roomba()

    # Check motors
    forward(1)
    backward(1)
    turn_left(10)
    turn_right(10)

    while True:
        time.sleep(2)
        try:
            time.sleep(0.1)
        
            sensors_data = get_sensors_data()
            #print("sending sensors data")
            print(sensors_data)
            send_sensors_data(sensors_data, config["serviceUrl"])
            #print("getting instructions")
            instructions = get_instructions(config["serviceUrl"])
            # print("instructions", instructions)
            if instructions != None:
                if not "error" in instructions:
                    execute_instructions(instructions)
        except Exception as e:
            print("⚠️ Error en bucle principal:", e)


main_program()




