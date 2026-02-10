import asyncio
from .rabbitmq import RabbitPublisher

class EventDispatcher:
    def __init__(self, publisher=None):
        self.queue = asyncio.Queue(maxsize=1000)
        self.publisher = publisher or RabbitPublisher()

    def enqueue(self, entry):
        self.queue.put_nowait(entry)

    async def worker(self):
        while True:
            entry = await self.queue.get()
            await self.publisher.publish(entry)
            self.queue.task_done()

    def start(self):
        """Start the dispatcher worker. If an asyncio event loop is running, schedule the worker as a task; otherwise run it in a background thread."""
        try:
            loop = asyncio.get_running_loop()
            loop.create_task(self.worker())
        except RuntimeError:
            # No running loop; start a new loop in a background thread
            import threading
            def _run_loop():
                asyncio.run(self.worker())
            t = threading.Thread(target=_run_loop, daemon=True)
            t.start()
