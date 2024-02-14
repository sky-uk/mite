import asyncio
from mite_kafka import _KafkaWrapper

async def producer_test():
    wrapper = _KafkaWrapper()
    producer = await wrapper.create_producer(bootstrap_servers='localhost:9092')
    await wrapper.send_and_wait(producer,'test-topic' , value=b'Testing the kafka component')
    print("Message sent succesfully")

async def consumer_test():
    wrapper = _KafkaWrapper()
    consumer = await wrapper.create_consumer('test-topic',bootstrap_servers ='localhost:9092' )
    kafka_message = await wrapper.get_message(consumer)
    print(f"Received message: {kafka_message.value.decode()}")
    print("Message received successfully")
    
async def main():
    await asyncio.gather(producer_test(),consumer_test())
    
if __name__ == "__main__":
    asyncio.run(main())
    
    
    

