import os
import time
from datetime import datetime

from dotenv import load_dotenv
from influxdb_client import InfluxDBClient, Point, WritePrecision
from influxdb_client.client.write_api import SYNCHRONOUS
from smbus2 import SMBus
import logging

load_dotenv()  # take environment variables from .env.


# RPi Channel 1
channel = 1
# ADS1115 address and registers
address = 0x48
reg_config = 0x01
reg_conversion = 0x00

bus = SMBus(channel)
# Config value:
# - Single conversion
# - A0 input
# - 4.096V reference
config = [0xC2, 0xB3]


db_connection = InfluxDBClient(
    url="https://westeurope-1.azure.cloud2.influxdata.com",
    token=os.getenv("INFLUXDB_TOKEN"),
    org=os.getenv("INFLUXDB_ORG"),
)
write_api = db_connection.write_api(write_options=SYNCHRONOUS)


def get_value():
    # Start conversion
    bus.write_i2c_block_data(address, reg_config, config)
    # Wait for conversion
    time.sleep(0.01)
    # Read 16-bit result
    result = bus.read_i2c_block_data(address, reg_conversion, 2)
    # Convert from 2-complement
    value = ((result[0] & 0xFF) << 8) | (result[1] & 0xFF)
    if value & 0x8000 != 0:
        value -= 1 << 16
    # Convert value to voltage
    v = value * 4.096 / 32768
    return v


buffer = []
counter = 1

while True:
    counter += 1
    value = get_value()
    buffer.append(value)
    buffer = buffer[-60:]
    if counter % 60 == 0:
        counter = 0
        point = (
            Point("mem")
            .tag("host", "host1")
            .field("voltage umidity", sum(buffer) / len(buffer))
            .time(datetime.utcnow(), WritePrecision.NS)
        )
        write_api.write(os.getenv("INFLUXDB_BUCKET"),
                        os.getenv("INFLUXDB_ORG"), point)
        logging.info('Logging to influx')
    time.sleep(1)
