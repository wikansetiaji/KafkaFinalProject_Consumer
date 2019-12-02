from django.shortcuts import render
from threading import Thread
import websocket
from websocket import create_connection
import time, json
from main.models import Bus, GpsPing
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
from kafka import KafkaConsumer
from json import loads
from KafkaFinalProject_Consumer import settings

trackingThread = None
tripThread = None
bus_code = "MYS"

def storing_thread1(message):
    msg = message.value['payload']['after']
    try:
        buscode = msg['bus_code']
        trip_id = msg['trip_id']
        koridor = msg['koridor']
        timestamp = msg['timestamp']
        bus = Bus.create(buscode, trip_id, koridor, timestamp)
        bus.save()
        print("[STORE] " + str(bus))
    except Exception as e:
        print(str(e))

def storing_thread2(message):
    msg = message.value
    try:
        buscode = msg['bus_code']
        trip_id = msg['latitude']
        koridor = msg['longitude']
        timestamp = msg['gps_timestamp']
        ping = GpsPing.create(buscode, trip_id, koridor, timestamp)
        ping.save()
        print("[STORE] " + str(ping))
    except Exception as e:
        print(str(e))


def tracking_thread():
    consumer = KafkaConsumer(
        'trackingtj',
        bootstrap_servers=[settings.KAFKA_PRODUCER_IP+':9092'],
        group_id='my-group',
        value_deserializer=lambda x: loads(x.decode('utf-8')))
    #dummy poll
    consumer.poll()
    #go to end of the stream
    consumer.seek_to_end()
    for message in consumer:
        print(message.value)
        try:
            channel_layer = get_channel_layer()
            if (bus_code in message.value['bus_code']):
                async_to_sync(channel_layer.group_send)("events", {"type": "tracking.message","message": message.value})
            thread = Thread(target=storing_thread2,args=(message,))
            thread.start()
        except Exception as e:
            print(str(e))

def trip_thread():
    consumer = KafkaConsumer(
        'pg1.public.trips',
        bootstrap_servers=[settings.KAFKA_PRODUCER_IP+':9092'],
        auto_offset_reset='earliest',
        enable_auto_commit=True,
        value_deserializer=lambda x: loads(x.decode('utf-8')))
    for message in consumer:
        try:
            print(message.value['payload']['after'])
            channel_layer = get_channel_layer()
            async_to_sync(channel_layer.group_send)("events", {"type": "trip.message","message": message.value['payload']['after']})
            thread = Thread(target=storing_thread1,args=(message,))
            thread.start()
        except Exception as e:
            print(str(e))
        time.sleep(2)

def index(request):
    global bus_code
    bus_code = request.GET['bus_code']
    global trackingThread
    if trackingThread is None:
        thread = Thread(target=tracking_thread)
        thread.daemon = True
        thread.start()

    global tripThread
    if tripThread is None:
        thread = Thread(target=trip_thread)
        thread.daemon = True
        thread.start()

    print(settings.KAFKA_PRODUCER_IP)

    response = {"bus_code":bus_code}
    return render(request, 'index.html', response)