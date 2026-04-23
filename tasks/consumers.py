import json

from channels.generic.websocket import AsyncWebsocketConsumer


class TaskDetailConsumer(AsyncWebsocketConsumer):
    """
    WebSocket consumer for a single task's detail page.
    Clients connect to ws/tasks/<task_id>/ and receive status update events
    whenever a worker updates that task via the API.
    """

    async def connect(self):
        user = self.scope.get("user")
        if not user or not user.is_authenticated:
            await self.close()
            return

        self.task_id = self.scope["url_route"]["kwargs"]["task_id"]
        self.group_name = f"task_{self.task_id}"

        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()

    async def disconnect(self, close_code):
        if hasattr(self, "group_name"):
            await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def receive(self, text_data):
        try:
            data = json.loads(text_data)
        except (json.JSONDecodeError, ValueError):
            return
        if data.get("type") == "ping":
            await self.send(text_data=json.dumps({"type": "pong"}))

    # Receive message from the channel group (sent by workers/views.py)
    async def task_update(self, event):
        await self.send(text_data=json.dumps(event["data"]))


class DashboardConsumer(AsyncWebsocketConsumer):
    """
    WebSocket consumer for the member dashboard.
    Clients connect to ws/dashboard/ and receive activity feed events for all
    tasks belonging to the authenticated user.
    """

    async def connect(self):
        user = self.scope.get("user")
        if not user or not user.is_authenticated:
            await self.close()
            return

        self.group_name = f"dashboard_{user.pk}"

        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()

    async def disconnect(self, close_code):
        if hasattr(self, "group_name"):
            await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def receive(self, text_data):
        try:
            data = json.loads(text_data)
        except (json.JSONDecodeError, ValueError):
            return
        if data.get("type") == "ping":
            await self.send(text_data=json.dumps({"type": "pong"}))

    # Receive message from the channel group (sent by workers/views.py)
    async def task_update(self, event):
        await self.send(text_data=json.dumps(event["data"]))


class QueueConsumer(AsyncWebsocketConsumer):
    """
    WebSocket consumer for the task queue view.
    Clients connect to ws/queue/ and receive position/status updates for all
    active tasks belonging to the authenticated user.
    """

    async def connect(self):
        user = self.scope.get("user")
        if not user or not user.is_authenticated:
            await self.close()
            return

        self.group_name = f"queue_{user.pk}"

        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()

    async def disconnect(self, close_code):
        if hasattr(self, "group_name"):
            await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def receive(self, text_data):
        try:
            data = json.loads(text_data)
        except (json.JSONDecodeError, ValueError):
            return
        if data.get("type") == "ping":
            await self.send(text_data=json.dumps({"type": "pong"}))

    async def queue_update(self, event):
        await self.send(text_data=json.dumps(event["data"]))
