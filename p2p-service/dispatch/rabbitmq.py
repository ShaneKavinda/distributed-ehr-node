class RabbitPublisher:
    async def publish(self, entry):
        # publish persistent message
        # wait for publisher confirm
